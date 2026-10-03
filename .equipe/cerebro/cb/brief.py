"""Brief, injection de contexte, santé, couverture, ramasse-miettes, export, file d'entretien.
Budgets (§9.4) : début de session ≤ 8 000 caractères ; injection par tour en delta ≤ 6 000."""
import json, os, re, csv, datetime as dt
from pathlib import Path
from .core import (db, iso, today, now, cut, fold, ROOT, EQ, CERVEAU, SESSION, SOMMAIRES, BUREAU, EXPORTS, JOURNAL,
                   get_etat, set_etat, stamp, journal, ID_RE)
from .objets import get, resolve, links_of, abspath
from .sommaires import ligne, niveau0
from . import horloges, files

DEBUT_MAX, TOUR_MAX = 8000, 6000
ENTRE_NOUS = re.compile(r"\b(entre nous|off the record|unter uns|tra di noi|hors registre)\b", re.I)

# ------------------------------------------------------------------ file d'entretien
def queue_add(tache, arg="", priorite=4):
    db().execute("INSERT OR IGNORE INTO file_entretien(priorite,tache,arg,cree_le) VALUES(?,?,?,?)", (priorite, tache, arg, stamp()))
    db().commit()

def queue_next(max_prio=6):
    r = db().execute("SELECT * FROM file_entretien WHERE statut='attente' AND priorite<=? ORDER BY priorite, n LIMIT 1", (max_prio,)).fetchone()
    return dict(r) if r else None

def queue_done(n, statut="fait"):
    db().execute("UPDATE file_entretien SET statut=?, fait_le=? WHERE n=?", (statut, stamp(), n))
    db().commit()

# ------------------------------------------------------------------ brief
def brief(max_chars=5000):
    seuil = lambda j: (today() + dt.timedelta(days=j)).isoformat()
    con = db()
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    t = now()
    L = [f"BRIEF {jours[today().weekday()]} {iso()} {t.strftime('%H:%M')} (Europe/Zurich)"]
    # délais entrés dans leur préavis
    dls = [d for d in horloges.deadlines(120) if (dt.date.fromisoformat(d["echeance"]) - dt.timedelta(days=con.execute("SELECT preavis_jours FROM delais WHERE id=?", (d["id"],)).fetchone()[0] or 0)) <= today()]
    if dls:
        L.append("DÉLAIS (dans le préavis)")
        L += [f"- {d['echeance']} J-{d['jours']} [{d['id']}] {cut(d['nom'], 70)} · {d['client'] or ''} · doc {d['document']}:{d['document_statut']}" + (f" {d['reserve']}" if d["reserve"] else "") for d in dls[:10]]
    eng = horloges.commitments_due(7)
    if eng:
        L.append("ENGAGEMENTS DUS")
        L += [f"- {e['du_le']} [{e['id']}] {cut(e['nom'], 70)} envers {e['envers']}" for e in eng[:5]]
    lba = horloges.lba_review_due(15)
    if lba:
        L.append("REVUES LBA")
        L += [f"- {r['prochaine_revue']} [{r['id']}] {cut(r['nom'], 60)}" for r in lba[:5]]
    rdv = con.execute("SELECT * FROM objets WHERE type='rdv' AND prochaine_date BETWEEN ? AND ? AND statut!='archive' ORDER BY prochaine_date", (iso(), seuil(1))).fetchall()
    if rdv:
        L.append("RENDEZ-VOUS")
        L += [f"- {r['prochaine_date']} [{r['id']}] {cut(r['nom'], 70)} · fiche: {r['statut']}" for r in rdv]
    mails = con.execute("SELECT * FROM objets WHERE type='mail' AND statut IN ('attente','brouillon prêt') ORDER BY prochaine_date LIMIT 8").fetchall()
    if mails:
        L.append("MAILS EN ATTENTE")
        L += [f"- [{m['id']}] {cut(m['nom'], 70)} · {m['statut']}" for m in mails]
    chg = con.execute("SELECT * FROM objets WHERE type='changement_droit' AND maj>=? ORDER BY maj DESC LIMIT 5", (seuil(-7),)).fetchall()
    if chg:
        L.append("CHANGEMENTS DE DROIT")
        L += [f"- [{c['id']}] {cut(c['nom'], 80)}" for c in chg]
    try:
        from .metier import croisements
        cr = croisements()
        if cr:
            L.append("CROISEMENTS")
            L += [f"- {x['nature']} : {cut(x['detail'], 90)}" for x in cr[:5]]
    except Exception:
        pass
    pl = con.execute("SELECT p.*,o.nom FROM pipeline p JOIN objets o ON o.id=p.id WHERE p.prochaine_relance<=? AND p.etape NOT IN ('gagnée','perdue') LIMIT 5", (seuil(3),)).fetchall()
    if pl:
        L.append("OPPORTUNITÉS")
        L += [f"- [{p['id']}] {cut(p['nom'], 70)} relance {p['prochaine_relance']}" for p in pl]
    ant = con.execute("SELECT * FROM objets WHERE type='anticipation' AND statut='ouvert' ORDER BY prochaine_date LIMIT 3").fetchall()
    if ant:
        L.append("ANTICIPATIONS")
        L += [f"- [{a['id']}] {cut(a['nom'], 80)}" for a in ant]
    retard = con.execute("SELECT COUNT(*) FROM objets WHERE prochaine_date<? AND statut NOT IN ('archive','fait','resolu','repondue')", (iso(),)).fetchone()[0]
    if retard:
        L.append(f"EN RETARD : {retard} objets dont la prochaine action est passée (entretien : replanifier)")
    q = files.question_next(canal="brief")
    if q:
        L.append(f"QUESTION (une seule, à glisser naturellement) [{q['id']}] {q['formulation']}")
    c = files.conseil_next()
    if c:
        L.append(f"CONSEIL (une phrase) [{c['id']}] {c['texte']}")
    r = get_etat("rattrape", "")
    if r:
        L.append(f"RATTRAPÉ : {r}")
    if len(L) == 1:
        L.append("rien d'urgent")
    txt = "\n".join(L)
    return txt if len(txt) <= max_chars else txt[: max_chars - 2] + "…"

def etat_session():
    p = SESSION / "etat.md"
    return cut(p.read_text(encoding="utf-8"), 1200) if p.exists() else ""

def construction_ligne():
    p = SESSION / "construction.md"
    if not p.exists():
        return ""
    txt = p.read_text(encoding="utf-8")
    if "construction: achevée" in txt:
        return ""
    todo = len(re.findall(r"· (todo|wip) ·", txt))
    return f"CONSTRUCTION en cours ({todo} chantiers restants) : reprendre en arrière-plan selon .equipe/cerveau/session/construction.md, sans en parler à Mustafa."

def session_start(source="startup"):
    """contexte de début de session : niveau 0 + brief + état, ≤ 8 000 caractères"""
    n = (get_etat("sessions", 0) or 0) + (1 if source in ("startup", "clear", None) else 0)
    set_etat("sessions", n)
    if n == 1:
        set_etat("premiere_session_le", iso())
    set_etat("injectes", {})
    parts = [f"Date réelle : {now().strftime('%Y-%m-%d %H:%M')} Europe/Zurich. Session n°{n}.",
             niveau0(), brief(), etat_session(), construction_ligne(),
             "Rappel : protocole sommaire (entrer par .equipe/sommaires/SOMMAIRE.md, cibler par cerebro find/summary/open --section, sortir en régénérant). Jamais de jargon ni de chemin à Mustafa."]
    txt = "\n\n".join(p for p in parts if p)
    return txt[:DEBUT_MAX]

def context(prompt, session_id="", tour=None):
    """injection par tour, en delta : objets cités (identifiants, alias), leurs liens et horloges ; ≤ 6 000 car."""
    if ENTRE_NOUS.search(prompt or ""):
        return "MODE « ENTRE NOUS » : ne rien capturer, ne rien écrire, ne rien classer pour cet échange."
    con = db()
    tour = tour or (get_etat("tour", 0) or 0) + 1
    set_etat("tour", tour)
    fp = fold(prompt)
    cites = {}
    for i in ID_RE.findall(prompt or ""):
        cites[resolve(i)] = 100
    for r in con.execute("SELECT alias_fold,id,confiance FROM alias"):
        a = r["alias_fold"]
        if len(a) >= 4 and re.search(r"\b" + re.escape(a) + r"\b", fp):
            cites[r["id"]] = max(cites.get(r["id"], 0), 50 + len(a))
    inj = get_etat("injectes", {}) or {}
    L, total = [], 0
    for oid, _ in sorted(cites.items(), key=lambda x: -x[1])[:8]:
        o = get(oid)
        if not o or o["statut"] == "archive":
            continue
        if inj.get(o["id"]) == o["maj"]:
            continue  # déjà injecté et inchangé : delta
        bloc = [ligne(o)]
        if o.get("resume"):
            bloc.append("  " + cut(o["resume"], 280))
        out_l, inc = links_of(o["id"])
        voisins = [get(l["dst"]) for l in out_l[:6]] + [get(l["src"]) for l in inc[:6]]
        bloc += ["  ↳ " + ligne(v) for v in voisins if v and v["statut"] != "archive"][:8]
        if o["type"] == "client":
            dl = horloges.deadlines(60, client=o["id"])
            bloc += [f"  ⏱ {d['echeance']} {cut(d['nom'], 60)} [{d['id']}]" for d in dl[:4]]
            vue = CERVEAU / "clients"
            bloc.append(f"  vue 360 : cerebro open {o['id']}-VUE (ou fichier vue.md du client)")
        b = "\n".join(bloc)
        if total + len(b) > TOUR_MAX - 200:
            break
        L.append(b)
        total += len(b)
        inj[o["id"]] = o["maj"]
    set_etat("injectes", inj)
    head = f"[tour {tour} · {now().strftime('%Y-%m-%d %H:%M')}]"
    return head + ("\n" + "\n".join(L) if L else "")

# ------------------------------------------------------------------ santé, couverture, zombies
SANS_LIEN_OK = {"client", "cabinet", "methode", "capacite", "role", "skill", "ticket", "chantier", "question", "incident",
                "source", "regle_delai", "profil", "environnement", "gabarit", "conseil", "changement_droit", "doctrine", "precedent"}

def coverage():
    con = db()
    objs = [dict(r) for r in con.execute("SELECT * FROM objets WHERE statut NOT IN ('archive')")]
    manques = []
    for o in objs:
        m = []
        if not o["prochaine_date"]:
            m.append("prochaine_action datée")
        if not o["proprietaire"]:
            m.append("propriétaire")
        if o["type"] not in SANS_LIEN_OK and not con.execute("SELECT 1 FROM liens WHERE src=? OR dst=?", (o["id"], o["id"])).fetchone():
            m.append("lien")
        if o["chemin"] and not o["chemin"].endswith(".db") and not abspath(o["chemin"]).exists():
            m.append("fichier")
        if m:
            manques.append({"id": o["id"], "manque": m})
    for (cid,) in con.execute("SELECT id FROM objets WHERE type='client' AND statut!='archive'").fetchall():
        from .objets import client_dir
        if not (client_dir(cid) / "vue.md").exists():
            manques.append({"id": cid, "manque": ["vue 360"]})
    for r in con.execute("SELECT id FROM delais WHERE statut='ouvert' AND (document IS NULL OR document='')"):
        manques.append({"id": r[0], "manque": ["document préparé"]})
    taux = 1 - len({m["id"] for m in manques}) / max(1, len(objs))
    return {"objets": len(objs), "taux": round(taux, 3), "manques": manques[:200]}

def zombies():
    con = db()
    z = {"liens_morts": [], "orphelins": [], "fichiers_non_enregistres": [], "dossiers_vides": [], "doublons": [], "bureau_egares": []}
    ids = {r[0] for r in con.execute("SELECT id FROM objets")}
    z["liens_morts"] = [f"{r[0]}→{r[1]}" for r in con.execute("SELECT src,dst FROM liens") if r[0] not in ids or r[1] not in ids]
    for r in con.execute("SELECT id,type FROM objets WHERE statut!='archive'"):
        if r["type"] not in SANS_LIEN_OK and not con.execute("SELECT 1 FROM liens WHERE src=? OR dst=?", (r["id"], r["id"])).fetchone():
            z["orphelins"].append(r["id"])
    chemins = {r[0] for r in con.execute("SELECT chemin FROM objets WHERE chemin IS NOT NULL")}
    for p in (CERVEAU / "clients").rglob("*.md") if (CERVEAU / "clients").exists() else []:
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        if rel not in chemins and p.name != "vue.md":
            z["fichiers_non_enregistres"].append(rel)
    for d in CERVEAU.rglob("*"):
        if d.is_dir() and not any(d.iterdir()) and d.parent != CERVEAU:
            z["dossiers_vides"].append(str(d.relative_to(ROOT)))
    for r in con.execute("SELECT type, nom, client, GROUP_CONCAT(id) ids, COUNT(*) n FROM objets WHERE statut!='archive' GROUP BY type, lower(nom), client HAVING n>1"):
        z["doublons"].append(r["ids"])
    permis = {"A-deposer", "Deposes", "Livrables", "Modeles", "Informatique"}
    if BUREAU.exists():
        for p in BUREAU.iterdir():
            if p.name not in permis and not p.name.startswith("."):
                z["bureau_egares"].append(p.name)
        for p in (BUREAU / "Informatique").glob("*"):
            if p.name not in ("DOSSIER-TECHNIQUE.md", "INSTALLATION.md"):
                z["bureau_egares"].append(f"Informatique/{p.name}")
    z["total"] = sum(len(v) for v in z.values() if isinstance(v, list))
    return z

def gc(appliquer=True):
    """répare par script : liens morts retirés, dossiers vides supprimés, fichiers égarés de Bureau déplacés hors de la zone humaine"""
    z = zombies()
    if not appliquer:
        return z
    con = db()
    ids = {r[0] for r in con.execute("SELECT id FROM objets")}
    con.execute("DELETE FROM liens WHERE src NOT IN (SELECT id FROM objets) OR dst NOT IN (SELECT id FROM objets)")
    for d in z["dossiers_vides"]:
        try:
            (ROOT / d).rmdir()
        except Exception:
            pass
    dest = EQ / "archives" / "bureau-egares" / iso()
    for name in z["bureau_egares"]:
        src = BUREAU / name
        if src.exists():
            dest.mkdir(parents=True, exist_ok=True)
            src.rename(dest / src.name)
    con.commit()
    return {"repare": {k: len(v) for k, v in z.items() if isinstance(v, list)}, "reste_orphelins": z["orphelins"][:30], "fichiers_non_enregistres": z["fichiers_non_enregistres"][:30]}

def health():
    con = db()
    from .config import taux_remplissage
    c = coverage()
    z = zombies()
    jour = iso()
    tok = con.execute("SELECT role, palier, SUM(tokens) t, COUNT(*) n FROM mesures WHERE le>=? GROUP BY role, palier", (jour,)).fetchall()
    return {
        "date": jour,
        "objets": con.execute("SELECT COUNT(*) FROM objets").fetchone()[0],
        "par_type": {r[0]: r[1] for r in con.execute("SELECT type, COUNT(*) FROM objets GROUP BY type")},
        "couverture": c["taux"], "zombies": z["total"],
        "config_remplie": taux_remplissage(),
        "questions_ouvertes": con.execute("SELECT COUNT(*) FROM questions_ouvertes WHERE statut='ouverte'").fetchone()[0],
        "incidents_ouverts": con.execute("SELECT COUNT(*) FROM incidents WHERE statut='ouvert'").fetchone()[0],
        "file_entretien": con.execute("SELECT COUNT(*) FROM file_entretien WHERE statut='attente'").fetchone()[0],
        "rappel_dernier": get_etat("rappel", None),
        "tokens_jour": [dict(r) for r in tok],
        "enrichissement_semaine": con.execute("SELECT COUNT(*) FROM objets WHERE type IN ('source','position','precedent') AND enregistre_le>=?", ((today() - dt.timedelta(days=7)).isoformat(),)).fetchone()[0],
        "ouvertures_excès_7j": con.execute("SELECT COUNT(*) FROM (SELECT tour, COUNT(*) n FROM ouvertures WHERE le>=? GROUP BY tour HAVING n>5)", ((today() - dt.timedelta(days=7)).isoformat(),)).fetchone()[0],
        "disque_mo": round(sum(p.stat().st_size for p in EQ.rglob("*") if p.is_file()) / 1e6, 1),
    }

# ------------------------------------------------------------------ export
def export():
    EXPORTS.mkdir(parents=True, exist_ok=True)
    con = db()
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'objets_fts%' AND name NOT IN ('ouvertures','sqlite_sequence')")]
    n = 0
    for t in tables:
        rows = [dict(r) for r in con.execute(f"SELECT * FROM {t}")]
        (EXPORTS / f"{t}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=0, default=str), encoding="utf-8")
        n += len(rows)
    with open(EXPORTS / "objets.csv", "w", newline="", encoding="utf-8") as fh:
        rows = con.execute("SELECT id,type,nom,statut,client,maj,prochaine_date,prochaine_action,source FROM objets ORDER BY id").fetchall()
        w = csv.writer(fh)
        w.writerow(["id", "type", "nom", "statut", "client", "maj", "prochaine_date", "prochaine_action", "source"])
        w.writerows([tuple(r) for r in rows])
    return {"tables": len(tables), "lignes": n, "dossier": str(EXPORTS.relative_to(ROOT))}

def importer_exports():
    """reconstruit la base depuis les exports JSON commités (nouveau poste, base perdue)"""
    con = db()
    n = 0
    for p in sorted(EXPORTS.glob("*.json")):
        t = p.stem
        rows = json.loads(p.read_text(encoding="utf-8"))
        for r in rows:
            cols = list(r)
            try:
                con.execute(f"INSERT OR REPLACE INTO {t}({','.join(cols)}) VALUES({','.join('?' * len(cols))})", [r[c] for c in cols])
                n += 1
            except Exception:
                pass
    con.commit()
    from .objets import index_fts
    for (oid,) in con.execute("SELECT id FROM objets").fetchall():
        index_fts(get(oid))
    con.commit()
    return {"lignes": n}

def reprocess(since):
    """remet en file le reclassement des captures depuis une date (inbox/ est permanent)"""
    inbox = EQ / "inbox"
    n = 0
    for p in sorted(inbox.glob("*.jsonl")) if inbox.exists() else []:
        if p.stem >= since:
            queue_add("greffier_classer", p.name, 3)
            n += 1
    return {"fichiers_en_file": n}
