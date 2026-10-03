"""Files et registres : questions (§0 bis), conseils, incidents (intendant), capacités (§6.4), livrables, types de tâche, mesures."""
import json, datetime as dt
from .core import db, new_id, iso, today, stamp, audit, get_etat, set_etat, cut

# ------------------------------------------------------------------ questions
def question_add(formulation, besoin, defaut_applique="", type_="metier", priorite=3, cle_config=None, sujet=None):
    con = db()
    if cle_config:
        r = con.execute("SELECT id FROM questions_ouvertes WHERE cle_config=? AND statut='ouverte'", (cle_config,)).fetchone()
        if r:
            return r[0]
    r = con.execute("SELECT id FROM questions_ouvertes WHERE formulation=? AND statut='ouverte'", (formulation,)).fetchone()
    if r:
        return r[0]
    qid = new_id(con, "question")
    con.execute("INSERT INTO compteurs(prefixe,n) VALUES('Q',0) ON CONFLICT DO NOTHING")
    con.execute("INSERT INTO questions_ouvertes(id,type,besoin,defaut_applique,priorite,formulation,cle_config,sujet,cree_le) VALUES(?,?,?,?,?,?,?,?,?)",
                (qid, type_, besoin, defaut_applique, priorite, formulation, cle_config, sujet, iso()))
    # la question est aussi un objet léger (atteignable, sommaire du domaine « question »)
    con.execute("INSERT OR IGNORE INTO objets(id,type,nom,statut,maj,prochaine_action,prochaine_date,resume,enregistre_le,valide_du,chemin) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (qid, "question", cut(formulation, 80), "ouverte", iso(), "poser au bon moment", iso(), f"{besoin} · défaut: {defaut_applique}", stamp(), iso(), ".equipe/cerebro/cerebro.db"))
    con.commit()
    return qid

def question_list(statut="ouverte"):
    return [dict(r) for r in db().execute("SELECT * FROM questions_ouvertes WHERE statut=? ORDER BY priorite DESC, cree_le", (statut,))]

def questions_autorisees():
    """aucune question pendant la première session ni pendant une session de construction"""
    if (get_etat("sessions", 0) or 0) < 2:
        return False
    if get_etat("construction_en_cours_tour", False):
        return False
    return True

def question_next(sujet=None, canal="message"):
    """renvoie au plus UNE question à poser maintenant, ou rien. Règles : ≤ 3/jour, jamais deux fois le même jour,
    au plus une fois par semaine ensuite, abandon après 3 poses ; rodage de 14 jours = priorité à l'effet."""
    if not questions_autorisees():
        return None
    con = db()
    t = iso()
    if con.execute("SELECT COUNT(*) FROM questions_ouvertes WHERE posee_le=?", (t,)).fetchone()[0] >= 3:
        return None
    if canal == "message" and get_etat("question_tour", None) == (get_etat("tour", "0")):
        return None
    debut = get_etat("premiere_session_le", t)
    rodage = (today() - dt.date.fromisoformat(debut)).days < 14
    rows = con.execute("SELECT * FROM questions_ouvertes WHERE statut='ouverte' ORDER BY priorite DESC, cree_le").fetchall()
    best = None
    for r in rows:
        if r["posee_le"] == t:
            continue
        if r["posee_le"] and (today() - dt.date.fromisoformat(r["posee_le"])).days < 7:
            continue
        if r["nb_posee"] >= 3:
            con.execute("UPDATE questions_ouvertes SET statut='abandonnee' WHERE id=?", (r["id"],))
            continue
        if not rodage and r["type"] == "config" and not sujet:
            continue  # après le rodage : seulement les questions déclenchées par un besoin réel
        if sujet and r["sujet"] and sujet.lower() not in (r["sujet"] or "").lower() and r["sujet"].lower() not in sujet.lower():
            continue
        best = r
        break
    con.commit()
    if not best:
        return None
    con.execute("UPDATE questions_ouvertes SET posee_le=?, nb_posee=nb_posee+1 WHERE id=?", (t, best["id"]))
    con.commit()
    set_etat("question_tour", get_etat("tour", "0"))
    return {"id": best["id"], "formulation": best["formulation"], "defaut": best["defaut_applique"]}

def question_answer(qid, reponse):
    con = db()
    r = con.execute("SELECT * FROM questions_ouvertes WHERE id=?", (qid,)).fetchone()
    if not r:
        return None
    con.execute("UPDATE questions_ouvertes SET statut='repondue', reponse=? WHERE id=?", (reponse, qid))
    con.execute("UPDATE objets SET statut='repondue' WHERE id=?", (qid,))
    con.commit()
    res = {"id": qid, "reponse": reponse}
    if r["cle_config"]:
        from .config import set_
        res["config"] = set_(r["cle_config"], reponse)
    return res

def questions_depuis_gaps():
    """alimente la file depuis config gaps (rodage : questions à fort effet)"""
    from .config import gaps
    n = 0
    for g in gaps():
        if g["question"] and g["effet"] >= 3:
            question_add(g["question"], f"config {g['cle']} vide", str(g["defaut"]), "config", g["effet"], g["cle"])
            n += 1
    return n

# ------------------------------------------------------------------ conseils
def conseil_add(texte, cle, gain=3):
    con = db()
    if con.execute("SELECT 1 FROM conseils WHERE cle=?", (cle,)).fetchone():
        return None
    cid = new_id(con, "conseil")
    con.execute("INSERT INTO conseils(id,texte,gain,cle,cree_le) VALUES(?,?,?,?,?)", (cid, texte, gain, cle, iso()))
    con.commit()
    return cid

def conseil_next():
    """au plus un conseil par jour, dans le brief ; ignoré deux fois → plus présenté"""
    if not questions_autorisees():
        return None
    con = db()
    t = iso()
    if con.execute("SELECT 1 FROM conseils WHERE presente_le=?", (t,)).fetchone():
        return None
    # un conseil présenté un autre jour et resté ouvert compte comme ignoré
    con.execute("UPDATE conseils SET nb_ignore=nb_ignore+1, presente_le=NULL WHERE statut='ouvert' AND presente_le IS NOT NULL AND presente_le<?", (t,))
    con.execute("UPDATE conseils SET statut='abandonne' WHERE nb_ignore>=2 AND statut='ouvert'")
    r = con.execute("SELECT * FROM conseils WHERE statut='ouvert' ORDER BY gain DESC, cree_le LIMIT 1").fetchone()
    if r:
        con.execute("UPDATE conseils SET presente_le=? WHERE id=?", (t, r["id"]))
    con.commit()
    return dict(r) if r else None

def conseil_suivi(cid):
    db().execute("UPDATE conseils SET statut='suivi' WHERE id=?", (cid,))
    db().commit()

# ------------------------------------------------------------------ incidents
def incident_add(categorie, description, repli="", phrase=""):
    con = db()
    r = con.execute("SELECT id FROM incidents WHERE categorie=? AND description=? AND statut='ouvert'", (categorie, description)).fetchone()
    if r:
        return r[0]
    iid = new_id(con, "incident")
    con.execute("INSERT INTO incidents(id,le,categorie,description,repli,phrase) VALUES(?,?,?,?,?,?)", (iid, stamp(), categorie, description, repli, phrase))
    con.execute("INSERT OR IGNORE INTO objets(id,type,nom,statut,maj,prochaine_action,prochaine_date,resume,enregistre_le,valide_du,chemin) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (iid, "incident", cut(f"{categorie}: {description}", 80), "ouvert", iso(), "intendant : résoudre", iso(), cut(repli, 200), stamp(), iso(), ".equipe/cerebro/cerebro.db"))
    con.commit()
    _dossier_technique(f"- {iso()} · {categorie} · {cut(description, 160)}" + (f" → {cut(repli, 120)}" if repli else ""))
    audit("incident", iid, description, "intendant")
    return iid

def incident_resolve(iid, repli=""):
    con = db()
    con.execute("UPDATE incidents SET statut='resolu', resolu_le=?, repli=COALESCE(NULLIF(?,''),repli) WHERE id=?", (stamp(), repli, iid))
    con.execute("UPDATE objets SET statut='resolu' WHERE id=?", (iid,))
    con.commit()
    return iid

def incident_list(statut="ouvert"):
    return [dict(r) for r in db().execute("SELECT * FROM incidents WHERE statut=? ORDER BY le", (statut,))]

def _dossier_technique(ligne):
    from .core import BUREAU
    p = BUREAU / "Informatique" / "DOSSIER-TECHNIQUE.md"
    try:
        txt = p.read_text(encoding="utf-8")
        marker = "## 3. Incidents et replis"
        if marker in txt and ligne not in txt:
            head, rest = txt.split(marker, 1)
            nxt = rest.find("\n## ")
            sec, tail = (rest, "") if nxt == -1 else (rest[:nxt], rest[nxt:])
            p.write_text(head + marker + sec.rstrip() + "\n" + ligne + "\n" + tail, encoding="utf-8")
    except Exception:
        pass

# ------------------------------------------------------------------ capacités
def capability_register(nom, categorie, localisation="LOCAL", sort_quoi="rien", vers_qui="-", licence="", version="", statut="actif", source=""):
    con = db()
    r = con.execute("SELECT id FROM capacites WHERE nom=?", (nom,)).fetchone()
    cid = r[0] if r else new_id(con, "capacite")
    con.execute("INSERT OR REPLACE INTO capacites(id,nom,categorie,localisation,sort_quoi,vers_qui,licence,version,statut,teste_le,source) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (cid, nom, categorie, localisation, sort_quoi, vers_qui, licence, version, statut, iso(), source))
    con.execute("INSERT OR REPLACE INTO objets(id,type,nom,statut,maj,prochaine_action,prochaine_date,resume,enregistre_le,valide_du,chemin,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (cid, "capacite", nom, statut, iso(), "réévaluer", (today() + dt.timedelta(days=90)).isoformat(), f"{categorie} · {localisation} · sort: {sort_quoi} → {vers_qui} · {licence}", stamp(), iso(), ".equipe/cerebro/cerebro.db", source))
    con.commit()
    return cid

def capability_list():
    return [dict(r) for r in db().execute("SELECT * FROM capacites ORDER BY categorie, nom")]

def capability_propose(besoin):
    """demande de découverte : mise en file d'entretien (priorité 5), traitée par la découverte continue"""
    db().execute("INSERT OR IGNORE INTO file_entretien(priorite,tache,arg,cree_le) VALUES(5,'decouverte',?,?)", (besoin, stamp()))
    db().commit()
    return {"file": "decouverte", "besoin": besoin}

# ------------------------------------------------------------------ livrables, tâches, mesures
def deliverable_register(chemin, client=None, dossier=None, type_="memo", portes=None, reserves=""):
    from .objets import create
    import os
    nom = os.path.basename(chemin)
    con = db()
    prev = con.execute("SELECT MAX(version) FROM livrables WHERE chemin=?", (chemin,)).fetchone()[0]
    lid = create("livrable", nom, client=client, source=chemin, prochaine_action="présenter à Mustafa", prochaine_date=iso(),
                 resume=f"{type_} · {chemin}", liens=[dossier] if dossier else [],
                 typed=("livrables", {"client": client, "dossier": dossier, "type": type_, "chemin": chemin, "version": (prev or 0) + 1,
                                      "portes": json.dumps(portes or {}, ensure_ascii=False), "reserves": reserves, "cree_le": iso()}))
    return lid

def task_seen(type_):
    con = db()
    con.execute("INSERT INTO types_de_tache(type,nb,dernier) VALUES(?,1,?) ON CONFLICT(type) DO UPDATE SET nb=nb+1, dernier=excluded.dernier", (type_, iso()))
    con.commit()

def mesure(role, tache, palier, tokens=0, duree_ms=0, ok=1):
    db().execute("INSERT INTO mesures(le,role,tache,palier,tokens,duree_ms,ok) VALUES(?,?,?,?,?,?,?)", (stamp(), role, tache, palier, tokens, duree_ms, ok))
    db().commit()
