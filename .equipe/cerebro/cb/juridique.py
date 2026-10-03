"""Bibliothèque juridique (§10) : ingestion d'un texte officiel par document (juridiction, type, identifiant pérenne,
langue, dates, version, texte intégral, source, licence), recherche, état du droit à une date, vérification des règles de
délais contre le texte, barèmes versionnés. Aucun contenu juridique n'est écrit de mémoire : tout vient d'un texte ingéré."""
import json, re, hashlib
from pathlib import Path
from .core import db, iso, today, fold, cut, EQ, audit, journal, new_id, slug
from .objets import create, update, get, link, abspath, relpath
from .recherche import sections

BIB = EQ / "bibliotheque"

def ingest(texte, juridiction, type_, identifiant, titre, langue="fr", version=None, date_etat=None, url="", abreviation="",
           licence="domaine public (art. 5 LDA)", fiabilite="officielle", acteur="documentaliste"):
    """texte : markdown où chaque article est une section « ## Art. N … ». Idempotent par empreinte."""
    con = db()
    version = version or date_etat or iso()
    h = hashlib.sha256(texte.encode("utf-8")).hexdigest()[:16]
    ex = con.execute("SELECT id FROM bibliotheque WHERE identifiant=? AND langue=? AND version=?", (identifiant, langue, version)).fetchone()
    p = BIB / slug(juridiction, 10) / slug(abreviation or identifiant, 30) / f"{version}-{langue}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    body = f"# {titre}\n\n## Métadonnées\njuridiction: {juridiction} · type: {type_} · identifiant: {identifiant} · langue: {langue} · version: {version} · état au: {date_etat or version} · source: {url} · licence: {licence} · empreinte: {h}\n\n{texte.strip()}\n"
    if ex:
        old = get(ex[0])
        if old and old.get("data", {}).get("empreinte") == h:
            return {"id": ex[0], "statut": "inchangé"}
        update(ex[0], body=body, empreinte=h, acteur=acteur)
        return {"id": ex[0], "statut": "mis à jour"}
    # versions antérieures : valide_au = veille de la nouvelle version
    for r in con.execute("SELECT id FROM bibliotheque WHERE identifiant=? AND langue=? AND version<? ", (identifiant, langue, version)).fetchall():
        o = get(r[0])
        if o and not o["valide_au"]:
            con.execute("UPDATE objets SET valide_au=? WHERE id=?", (version, r[0]))
    bid = create("source", f"{abreviation or identifiant} ({langue}, état {date_etat or version})", chemin=relpath(p), body=body,
                 statut="actif", domaine="bibliothèque", langue=langue, source=url, valide_du=date_etat or version,
                 resume=cut(f"{titre} — {juridiction} {identifiant}, version {version}", 280), mots_cles=f"{abreviation} {identifiant} {juridiction} {type_}",
                 alias=[a for a in [abreviation, f"RS {identifiant}" if juridiction == "CH" else ""] if a],
                 prochaine_action="vérifier mise à jour", empreinte=h,
                 typed=("bibliotheque", {"juridiction": juridiction, "type": type_, "identifiant": identifiant, "abreviation": abreviation, "titre": titre,
                                         "langue": langue, "version": version, "date_etat": date_etat or version, "url": url, "chemin": relpath(p),
                                         "licence": licence, "fiabilite": fiabilite, "ingere_le": iso()}))
    con.commit()
    audit("law_ingest", bid, f"{identifiant} {langue} {version}", acteur)
    return {"id": bid, "statut": "ingéré", "chemin": relpath(p)}

def asof(identifiant, date=None, langue="fr"):
    """version en vigueur à une date (état du droit)"""
    date = date or iso()
    r = db().execute("SELECT b.*, o.valide_au FROM bibliotheque b JOIN objets o ON o.id=b.id WHERE (b.identifiant=? OR b.abreviation=?) AND b.langue=? AND b.date_etat<=? ORDER BY b.date_etat DESC LIMIT 1",
                     (identifiant, identifiant, langue, date)).fetchone()
    return dict(r) if r else None

def article(identifiant, art, date=None, langue="fr"):
    v = asof(identifiant, date, langue)
    if not v:
        return {"erreur": f"{identifiant} ({langue}) absent de la bibliothèque", "reserve": "⚠ aucune source primaire ingérée"}
    p = abspath(v["chemin"])
    secs = sections(p.read_text(encoding="utf-8")) if p.exists() else []
    a = fold(art).replace("art.", "").replace("art", "").strip()
    for t, c in secs:
        ft = fold(t)
        m = re.match(r"art\.?\s*([0-9]+[a-z]*)", ft)
        if m and m.group(1) == a.split()[0]:
            return {"source": v["id"], "identifiant": v["identifiant"], "version": v["version"], "langue": langue, "url": v["url"],
                    "article": t, "texte": c, "verifie_le": iso()}
    return {"source": v["id"], "erreur": f"{art} introuvable dans {v['identifiant']} version {v['version']}"}

def search(q, juridiction=None, limit=10):
    from .recherche import find
    res = [r for r in find(q, limit=limit * 3, types=["source"])]
    if juridiction:
        res = [r for r in res if f" {juridiction} " in f" {r['ligne']} " or juridiction in r["ligne"]]
    return res[:limit]

def verify_rules():
    """vérifie chaque règle de délai contre le texte officiel ingéré : l'extrait attendu doit figurer dans l'article"""
    con = db()
    out = []
    for r in con.execute("SELECT * FROM regles_delais WHERE juridiction='CH'").fetchall():
        rs = (r["source"] or "").replace("RS", "").strip()
        res = article(rs, r["article"])
        ok = "texte" in res and fold(r["extrait_attendu"]) in fold(res["texte"])
        if ok:
            con.execute("UPDATE regles_delais SET verifie_le=?, source=? WHERE id=?", (iso(), f"RS {rs} ({res['source']}, version {res['version']})", r["id"]))
            link(r["id"], res["source"], "source")
            # lever la réserve des délais déjà ouverts
            for d in con.execute("SELECT id FROM delais WHERE regle=? AND statut='ouvert'", (r["id"],)).fetchall():
                o = get(d[0])
                if o and o["risque"] and "non vérifiée" in o["risque"]:
                    update(d[0], risque=None, resume=(o["resume"] or "").split(" ⚠")[0] + f" Vérifié le {iso()} contre {res['source']}.")
        out.append({"regle": r["type"], "article": f"RS {rs} {r['article']}", "verifie": ok, "detail": res.get("erreur") or cut(res.get("texte", ""), 160)})
    con.commit()
    return out

def rates_get(nom, juridiction="CH", annee=None, cle=None):
    q = "SELECT * FROM bareme WHERE nom=? AND juridiction=?"
    a = [nom, juridiction]
    if annee:
        q += " AND annee=?"; a.append(int(annee))
    if cle:
        q += " AND cle=?"; a.append(cle)
    rows = [dict(r) for r in db().execute(q + " ORDER BY annee DESC", a)]
    return rows or {"erreur": "barème absent", "reserve": "⚠ aucun barème versionné : ne pas calculer de mémoire"}

def rates_set(nom, juridiction, annee, cle, valeur, source, verifie_le=None):
    con = db()
    bid = new_id(con, "bareme")
    con.execute("INSERT INTO bareme(id,nom,juridiction,annee,cle,valeur,source,verifie_le) VALUES(?,?,?,?,?,?,?,?)",
                (bid, nom, juridiction, int(annee), cle, str(valeur), source, verifie_le or iso()))
    con.commit()
    return bid
