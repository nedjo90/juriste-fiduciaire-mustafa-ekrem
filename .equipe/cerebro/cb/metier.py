"""Objets métier : clients, entités, personnes, participations, dossiers, contrôle de conflit, LBA, temps, pipeline,
engagements, événements déclencheurs (§17 c6-c7), vues à 360° et croisements (§9.2)."""
import json, datetime as dt
from .core import db, iso, today, cut, fold, CERVEAU, audit, journal
from .objets import create, update, get, link, add_alias, client_dir
from . import horloges

def _upd_typed(table, oid, **vals):
    if vals:
        db().execute(f"UPDATE {table} SET {','.join(k + '=?' for k in vals)} WHERE id=?", [*vals.values(), oid])
        db().commit()

# ------------------------------------------------------------------ création
def client_new(nom, forme="", canton=None, langue="fr", alias=(), resume="", **kw):
    return create("client", nom, alias=alias, canton=canton, langue=langue, resume=resume or f"Client {nom}",
                  prochaine_action="vue 360 à compléter", typed=("clients", {"forme": forme, "canton": canton, "langue": langue, "depuis": iso()}), **kw)

def entity_new(nom, client, forme="SA", ide="", siege="", canton=None, cloture="12-31", organes=(), alias=(), resume="", **kw):
    eid = create("entite", nom, client=client, alias=alias, canton=canton, resume=resume or f"{forme} {nom}, siège {siege}",
                 chiffre_cle=ide or None, typed=("entites", {"client": client, "forme": forme, "ide": ide, "siege": siege, "canton": canton,
                                                             "cloture": cloture, "organes": json.dumps(list(organes), ensure_ascii=False)}), **kw)
    for org in organes:  # organe : {"personne": P-xxx, "fonction": "administrateur", "signature": "individuelle"}
        if org.get("personne"):
            link(eid, org["personne"], org.get("fonction", "organe"))
    return eid

def person_new(nom, client=None, naissance=None, domicile=None, canton=None, nationalite=None, alias=(), resume="", **kw):
    return create("personne", nom, client=client, alias=alias, canton=canton, resume=resume or f"Personne {nom}",
                  typed=("personnes", {"naissance": naissance, "domicile": domicile, "canton": canton, "nationalite": nationalite}), **kw)

def participation(detenteur, detenue, pct, ayant_droit=False, source="", valide_du=None):
    db().execute("INSERT OR REPLACE INTO participations VALUES(?,?,?,?,?,?,?)", (detenteur, detenue, pct, int(ayant_droit), valide_du or iso(), None, source))
    link(detenteur, detenue, f"détient {pct}%")
    db().commit()

# ------------------------------------------------------------------ lecture
def client_show(cid):
    from .sommaires import ligne
    c = get(cid)
    if not c:
        return None
    rows = db().execute("SELECT * FROM objets WHERE client=? AND statut!='archive' ORDER BY type, COALESCE(prochaine_date,'9999')", (c["id"],)).fetchall()
    return {"client": ligne(c), "objets": [ligne(dict(r)) for r in rows]}

def entity_show(eid):
    from .recherche import summary
    s = summary(eid)
    r = db().execute("SELECT * FROM entites WHERE id=?", (eid,)).fetchone()
    if r:
        s["registre"] = {k: r[k] for k in r.keys() if k != "id"}
    return s

def entity_organs(eid):
    r = db().execute("SELECT organes FROM entites WHERE id=?", (eid,)).fetchone()
    orgs = json.loads(r[0]) if r else []
    for o in orgs:
        p = get(o.get("personne")) if o.get("personne") else None
        o["nom"] = p["nom"] if p else o.get("nom")
    return orgs

def entity_chain(oid, depth=6):
    """chaîne de détention vers le haut (ayants droit économiques)"""
    con = db()
    out, frontier, seen = [], [(oid, 100.0, 0)], set()
    while frontier:
        cur, pct, d = frontier.pop(0)
        if cur in seen or d > depth:
            continue
        seen.add(cur)
        for r in con.execute("SELECT * FROM participations WHERE detenue=? AND (valide_au IS NULL OR valide_au>=?)", (cur, iso())):
            eff = pct * r["pourcentage"] / 100
            o = get(r["detenteur"])
            out.append({"niveau": d + 1, "detenteur": r["detenteur"], "nom": o["nom"] if o else "?", "detient": cur,
                        "pct": r["pourcentage"], "pct_effectif": round(eff, 2), "ayant_droit": bool(r["ayant_droit"]) or (o and o["type"] == "personne" and eff >= 25)})
            frontier.append((r["detenteur"], eff, d + 1))
    return out

# ------------------------------------------------------------------ dossiers et conflits
def conflict_check(noms, client=None):
    """signale (jamais ne bloque) : partie déjà connue chez un autre client, ou adverse"""
    from .recherche import find
    hits = []
    for n in noms:
        for h in find(n, limit=5):
            o = get(h["id"])
            if not o or h["score"] < 55:
                continue
            autre = o["client"] or (o["id"] if o["type"] == "client" else None)
            if autre and autre != client:
                hits.append({"nom": n, "trouve": h["ligne"], "client": autre, "nature": "partie liée à un autre client"})
        for r in db().execute("SELECT id,client,parties FROM dossiers"):
            if fold(n) in fold(r["parties"]) and r["client"] != client:
                hits.append({"nom": n, "trouve": r["id"], "client": r["client"], "nature": "partie (adverse ?) dans un dossier d'un autre client"})
    res = {"verifie_le": iso(), "noms": noms, "signalements": hits, "conflit_possible": bool(hits)}
    audit("conflict_check", client or "", json.dumps(res, ensure_ascii=False)[:400])
    return res

def matter_new(client, objet, parties=(), canton=None, domaine=None):
    cc = conflict_check(list(parties), client)
    did = create("dossier", objet, client=client, canton=canton, domaine=domaine, prochaine_action="analyse initiale", prochaine_date=(today() + dt.timedelta(days=7)).isoformat(),
                 risque=("conflit possible : voir contrôle" if cc["conflit_possible"] else None), resume=f"Mandat {objet} ; parties : {', '.join(parties) or '-'}",
                 typed=("dossiers", {"client": client, "objet": objet, "ouvert_le": iso(), "parties": json.dumps(list(parties), ensure_ascii=False)}),
                 body=f"# {objet}\n\n## Contrôle de conflit\n{json.dumps(cc['signalements'], ensure_ascii=False) or 'aucun signalement'} (vérifié le {cc['verifie_le']})\n\n## Faits\n\n## Analyse\n\n## Prochaines étapes\n")
    return {"dossier": did, "conflit": cc}

# ------------------------------------------------------------------ événements déclencheurs
_CANTONS_NOMS = {"vaud": "VD", "vaudois": "VD", "vaudoise": "VD", "geneve": "GE", "genevois": "GE", "genevoise": "GE", "valais": "VS",
                 "neuchatel": "NE", "fribourg": "FR", "jura": "JU", "berne": "BE", "zurich": "ZH", "tessin": "TI", "ticino": "TI"}
_CODES = {"AG", "AI", "AR", "BE", "BL", "BS", "FR", "GE", "GL", "GR", "JU", "LU", "NE", "NW", "OW", "SG", "SH", "SO", "SZ", "TG", "TI", "UR", "VD", "VS", "ZG", "ZH"}

def _taxation_regles(autorite, canton, impot):
    """[(type de règle, impôt, canton)] : IFD → LIFD art. 132 ; ICC → règle du canton (cantons suivis : loi cantonale
    vérifiée ; autre canton : cadre LHID art. 48, pratique cantonale à vérifier). Une décision cantonale qui couvre IFD et
    ICC ouvre les deux horloges en parallèle. Autorité fédérale seule (AFC) → IFD seulement."""
    a, imp = fold(autorite or ""), (impot or "").upper()
    c = (canton or "").strip().upper() or None
    if not c:
        toks = set((autorite or "").replace("(", " ").replace(")", " ").split())
        c = next((t for t in toks if t in _CODES), None) or next((v for k, v in _CANTONS_NOMS.items() if k in a), None)
    federale = ("afc" in a.split() or "federal" in a or "confederation" in a) and "cantonal" not in a
    ifd = "IFD" in imp or "LIFD" in imp or "DBG" in imp or federale or not imp
    icc = ("ICC" in imp or "CANTON" in imp or "COMMUN" in imp or not imp) and not (federale and "ICC" not in imp)
    if imp and "IFD" in imp and "ICC" not in imp and not federale and "/" not in imp:
        icc = False
    out = []
    if icc:
        types = {r[0] for r in horloges.REGLES}
        t = f"reclamation_icc_{c.lower()}" if c and f"reclamation_icc_{c.lower()}" in types else "reclamation_icc"
        out.append((t, "ICC", c))
    if ifd:
        out.append(("reclamation_ifd", "IFD", c))
    return out or [("reclamation_ifd", "IFD", c)]

def event_taxation(client, contribuable, autorite, canton, periode, notifiee_le, montant=None, impot="IFD/ICC"):
    """décision de taxation → horloge(s) de réclamation + projet de réclamation (§17 c6). Règle choisie selon l'autorité
    et le canton (IFD : LIFD ; ICC : loi du canton) ; décision IFD/ICC → deux horloges, la cantonale en premier."""
    dt_id = create("decision_taxation", f"Décision de taxation {periode} — {autorite}", client=client, canton=canton, domaine="fiscalité",
                   chiffre_cle=(f"CHF {montant:,.2f}".replace(",", "'") if montant else None), liens=[contribuable] if contribuable else [],
                   resume=f"Décision {impot} {periode}, notifiée le {notifiee_le} par {autorite}", prochaine_action="examiner : réclamation ?", prochaine_date=iso(),
                   typed=("decisions_taxation", {"client": client, "contribuable": contribuable, "autorite": autorite, "canton": canton, "periode": periode,
                                                 "notifiee_le": notifiee_le, "montant": montant, "impot": impot}))
    hs = []
    for type_, imp, c in _taxation_regles(autorite, canton, impot):
        h = horloges.clock_start(type_, notifiee_le, client=client, canton=c or canton, objet=f"décision {periode} ({imp})")
        if "delai" not in h:
            continue
        link(h["delai"], dt_id, "declencheur")
        hs.append({**h, "regle": type_, "impot": imp})
    if not hs:  # règle introuvable : jamais sans horloge
        h = horloges.clock_start("reclamation_ifd", notifiee_le, client=client, canton=canton, objet=f"décision {periode}")
        link(h["delai"], dt_id, "declencheur")
        hs.append({**h, "regle": "reclamation_ifd", "impot": "IFD"})
    return {"decision": dt_id, **hs[0], "horloges": hs}

def event_dividende(client, societe, echeance_dividende, montant=None):
    h = horloges.clock_start("impot_anticipe_dividende", echeance_dividende, client=client, objet=f"dividende {get(societe)['nom'] if get(societe) else societe}")
    link(h["delai"], societe, "societe")
    return h

def event_relation(client, nom_relation, risque="normal"):
    """nouvelle relation d'affaires → dossier LBA ouvert, prochaine revue datée (§17 c6)"""
    nxt = horloges.add_months(today(), 12 if risque == "normal" else 6).isoformat()
    lid = create("lba", f"Dossier LBA — {nom_relation}", client=client, domaine="LBA", risque=None if risque == "normal" else f"risque {risque}",
                 prochaine_action="identification, ayant droit économique, profil", prochaine_date=(today() + dt.timedelta(days=10)).isoformat(),
                 resume=f"Ouverture du dossier LBA pour {nom_relation} (risque {risque}). Le système signale et prépare ; il ne communique jamais.",
                 typed=("dossiers_lba", {"client": client, "ouverture": iso(), "risque": risque, "derniere_revue": iso(), "prochaine_revue": nxt}))
    return {"lba": lid, "prochaine_revue": nxt}

def time_add(client, minutes, libelle, dossier=None, date=None):
    return create("temps", cut(libelle, 60), client=client, prochaine_action="facturer", prochaine_date=(today() + dt.timedelta(days=30)).isoformat(),
                  resume=f"{minutes} min · {libelle}", liens=[dossier] if dossier else [],
                  typed=("temps", {"client": client, "dossier": dossier, "date": date or iso(), "minutes": int(minutes), "libelle": libelle}))

def pipeline_add(client, opportunite, valeur=None, etape="identifiée"):
    return create("pipeline", opportunite, client=client, prochaine_action="proposition", prochaine_date=(today() + dt.timedelta(days=14)).isoformat(),
                  chiffre_cle=f"CHF {valeur}" if valeur else None, resume=f"Opportunité : {opportunite} ({etape})",
                  typed=("pipeline", {"client": client, "opportunite": opportunite, "etape": etape, "valeur": valeur, "prochaine_relance": (today() + dt.timedelta(days=14)).isoformat()}))

def pipeline_list():
    return [dict(r) for r in db().execute("SELECT p.*, o.nom FROM pipeline p JOIN objets o ON o.id=p.id WHERE p.etape NOT IN ('gagnée','perdue') ORDER BY p.prochaine_relance")]

def engagement_add(client, envers, objet, du_le):
    return create("engagement", objet, client=client, prochaine_action=f"tenir envers {envers}", prochaine_date=du_le, resume=f"Engagement envers {envers} : {objet}, dû le {du_le}",
                  typed=("engagements", {"client": client, "envers": envers, "objet": objet, "du_le": du_le}))

# ------------------------------------------------------------------ vues et croisements
def vue_client(cid):
    """vue à 360° (vue.md) régénérée à chaque cycle et injectée quand le client est cité"""
    from .sommaires import ligne
    c = get(cid)
    if not c:
        return None
    con = db()
    rows = [dict(r) for r in con.execute("SELECT * FROM objets WHERE client=? AND statut!='archive' ORDER BY COALESCE(prochaine_date,'9999')", (cid,))]
    by = {}
    for r in rows:
        by.setdefault(r["type"], []).append(r)
    dl = horloges.deadlines(400, client=cid)
    cr = [x for x in croisements() if cid in (x.get("clients") or [])]
    L = [f"---\nid: {cid}-VUE\ntype: vue\nclient: {cid}\nmaj: {iso()}\nrésumé: vue à 360° de {c['nom']}\n---",
         f"# Vue 360 — {c['nom']} ({cid})", "## Prochaines actions"]
    L += [f"- {r['prochaine_date']} · [{r['id']}] {cut(r['prochaine_action'] or '', 70)} ({r['nom'][:50]})" for r in rows[:10]]
    L.append("## Délais")
    L += [f"- {d['echeance']} ({d['jours']} j) · [{d['id']}] {d['nom'][:60]} · document {d['document']} {d['document_statut']}" + (f" · {d['reserve']}" if d['reserve'] else "") for d in dl] or ["- aucun"]
    for t in ["entite", "personne", "dossier", "contrat", "decision_taxation", "lba", "document", "position", "engagement", "pipeline"]:
        if t in by:
            L.append(f"## {t} ({len(by[t])})")
            L += [f"- {ligne(r)}" for r in by[t][:15]]
    L.append("## Croisements")
    L += [f"- {x['nature']} : {x['detail']}" for x in cr] or ["- aucun"]
    p = client_dir(cid) / "vue.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    return str(p)

def croisements():
    """même personne dans deux sociétés / deux clients, même ayant droit, collisions de délais (§9.2)"""
    con = db()
    out = []
    # personne liée à des objets de plusieurs clients
    rows = con.execute("""SELECT l.dst pid, o2.client cl FROM liens l JOIN objets o1 ON o1.id=l.dst JOIN objets o2 ON o2.id=l.src
                          WHERE o1.type='personne' AND o2.client IS NOT NULL
                          UNION SELECT l.src, o2.client FROM liens l JOIN objets o1 ON o1.id=l.src JOIN objets o2 ON o2.id=l.dst
                          WHERE o1.type='personne' AND o2.client IS NOT NULL
                          UNION SELECT id, client FROM objets WHERE type='personne' AND client IS NOT NULL""").fetchall()
    m = {}
    for r in rows:
        m.setdefault(r["pid"], set()).add(r["cl"])
    for pid, cls in m.items():
        if len(cls) > 1:
            p = get(pid)
            out.append({"nature": "personne liée à plusieurs clients", "objet": pid, "clients": sorted(cls), "detail": f"{p['nom']} ({pid}) ↔ {', '.join(sorted(cls))}"})
    # même nom de personne sous deux identifiants (doublon probable ou homonyme)
    seen = {}
    for r in con.execute("SELECT id,nom,client FROM objets WHERE type='personne' AND statut!='archive'"):
        seen.setdefault(fold(r["nom"]), []).append(r)
    for k, v in seen.items():
        if len(v) > 1:
            out.append({"nature": "même nom, deux fiches", "objet": v[0]["id"], "clients": sorted({x["client"] for x in v if x["client"]}),
                        "detail": " / ".join(f"{x['id']}({x['client']})" for x in v)})
    # collisions de délais : deux échéances le même jour
    for r in con.execute("SELECT echeance, GROUP_CONCAT(id) ids, GROUP_CONCAT(DISTINCT client) cls, COUNT(*) n FROM delais WHERE statut='ouvert' GROUP BY echeance HAVING n>1"):
        out.append({"nature": "collision de délais", "objet": r["ids"].split(",")[0], "clients": (r["cls"] or "").split(","), "detail": f"{r['echeance']} : {r['ids']}"})
    return out
