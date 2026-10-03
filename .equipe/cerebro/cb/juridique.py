"""Bibliothèque juridique (§10) : ingestion d'un texte officiel par document (juridiction, type, identifiant pérenne,
langue, dates, version, texte intégral, source, licence), recherche, état du droit à une date, vérification des règles de
délais contre le texte, barèmes versionnés. Aucun contenu juridique n'est écrit de mémoire : tout vient d'un texte ingéré."""
import json, re, hashlib
from pathlib import Path
from .core import db, iso, today, fold, cut, EQ, audit, journal, new_id, slug
from .objets import create, update, get, link, abspath, relpath, write_file
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
            if old.get("chemin") and not abspath(old["chemin"]).exists():
                # mémoire importée sur un nouveau poste : l'objet existe, le texte (hors git, §9.4) manque → réécrit
                write_file(old, body)
                index_articles(ex[0])
                return {"id": ex[0], "statut": "texte réécrit sur ce poste"}
            return {"id": ex[0], "statut": "inchangé"}
        update(ex[0], body=body, empreinte=h, acteur=acteur)
        index_articles(ex[0])
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
    # version antérieure ingérée après coup : elle cesse de valoir à la date de la version suivante déjà présente
    nxt = con.execute("SELECT MIN(version) FROM bibliotheque WHERE identifiant=? AND langue=? AND version>?", (identifiant, langue, version)).fetchone()
    if nxt and nxt[0]:
        con.execute("UPDATE objets SET valide_au=? WHERE id=?", (nxt[0], bid))
    con.commit()
    index_articles(bid)
    audit("law_ingest", bid, f"{identifiant} {langue} {version}", acteur)
    return {"id": bid, "statut": "ingéré", "chemin": relpath(p)}

def _table_articles():
    db().execute("CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(source UNINDEXED, abrev UNINDEXED, langue UNINDEXED, version UNINDEXED, "
                 "article, texte, tokenize='unicode61 remove_diacritics 2')")

def index_articles(bid):
    """index article par article : l'agent trouve l'article pertinent sans lire la loi (loi 4, économie de tokens)"""
    from .core import ecriture
    _table_articles()
    r = db().execute("SELECT * FROM bibliotheque WHERE id=?", (bid,)).fetchone()
    if not r:
        return 0
    p = abspath(r["chemin"])
    if not p.exists():
        return 0
    from .core import lire
    secs = [(t, c) for t, c in sections(lire(p)) if re.match(r"art\.?\s*\d", fold(t))]
    with ecriture() as con:
        con.execute("DELETE FROM articles_fts WHERE source=?", (bid,))
        con.executemany("INSERT INTO articles_fts(source,abrev,langue,version,article,texte) VALUES(?,?,?,?,?,?)",
                        [(bid, r["abreviation"] or r["identifiant"], r["langue"], r["version"], t, c[:8000]) for t, c in secs])
    return len(secs)

def reindex_articles():
    n = 0
    for (bid,) in db().execute("SELECT id FROM bibliotheque").fetchall():
        n += index_articles(bid)
    return {"articles": n}

def search_articles(q, langue="fr", limit=8, date=None):
    """articles en vigueur (version courante ou à la date donnée) qui répondent à la question ; extraits courts"""
    _table_articles()
    from .recherche import _tokens
    toks = _tokens(q)[:20]
    if not toks:
        return []
    m = " OR ".join(f'"{t}"*' if len(t) > 3 else f'"{t}"' for t in toks)
    date = date or iso()
    rows = db().execute("""SELECT a.source, a.abrev, a.version, a.article, snippet(articles_fts, 5, '«', '»', ' … ', 24) extrait, bm25(articles_fts, 0, 0, 0, 0, 4.0, 1.0) b
                           FROM articles_fts a JOIN objets o ON o.id=a.source JOIN bibliotheque bb ON bb.id=a.source
                           WHERE articles_fts MATCH ? AND a.langue=? AND bb.date_etat<=? AND (o.valide_au IS NULL OR o.valide_au='' OR o.valide_au>?)
                           ORDER BY b LIMIT ?""", (m, langue, date, date, limit)).fetchall()
    return [{"source": r["source"], "loi": r["abrev"], "version": r["version"], "article": r["article"], "extrait": r["extrait"]} for r in rows]

def asof(identifiant, date=None, langue="fr"):
    """version en vigueur à une date (état du droit). valide_au est exclusif (date de la version suivante ou lendemain de la fin
    d'applicabilité publiée) : une date non couverte par une version ingérée renvoie None (⚠) plutôt qu'un texte périmé."""
    date = date or iso()
    r = db().execute("SELECT b.*, o.valide_au FROM bibliotheque b JOIN objets o ON o.id=b.id WHERE (b.identifiant=? OR b.abreviation=?) AND b.langue=? AND b.date_etat<=? "
                     "AND (o.valide_au IS NULL OR o.valide_au='' OR o.valide_au>?) ORDER BY b.date_etat DESC LIMIT 1",
                     (identifiant, identifiant, langue, date, date)).fetchone()
    return dict(r) if r else None

def article(identifiant, art, date=None, langue="fr"):
    v = asof(identifiant, date, langue)
    if not v:
        return {"erreur": f"{identifiant} ({langue}) absent de la bibliothèque", "reserve": "⚠ aucune source primaire ingérée"}
    p = abspath(v["chemin"])
    if not p.exists():
        # texte pas encore téléchargé sur ce poste (la bibliothèque n'est pas dans git) : rattrapage en file, réserve explicite
        from .brief import queue_add
        queue_add("bibliotheque_mise_a_jour", "", 2)
        return {"source": v["id"], "erreur": f"texte de {v['identifiant']} pas encore disponible sur ce poste (téléchargement en cours)",
                "reserve": "⚠ source primaire en cours de chargement : vérifier avant d'affirmer"}
    secs = sections(p.read_text(encoding="utf-8"))
    a = fold(art).replace("art.", "").replace("art", "").strip()
    for t, c in secs:
        ft = fold(t)
        m = re.match(r"art\.?\s*([0-9]+[a-z]*)", ft)
        if m and m.group(1) == a.split()[0]:
            return {"source": v["id"], "identifiant": v["identifiant"], "version": v["version"], "langue": langue, "url": v["url"],
                    "article": t, "texte": c, "verifie_le": iso()}
    return {"source": v["id"], "erreur": f"{art} introuvable dans {v['identifiant']} version {v['version']}"}

def search(q, juridiction=None, limit=10, langue="fr"):
    """articles pertinents d'abord (index article par article), puis textes entiers correspondants"""
    arts = search_articles(q, langue, limit)
    if arts:
        return {"articles": arts, "suite": "cerebro law article <loi> \"art. N\" pour le texte exact, version et URL"}
    from .recherche import find
    res = [r for r in find(q, limit=limit * 3, types=["source"])]
    if juridiction:
        res = [r for r in res if f" {juridiction} " in f" {r['ligne']} " or juridiction in r["ligne"]]
    return res[:limit]

def verify_rules():
    """vérifie chaque règle de délai contre le texte officiel ingéré : l'extrait attendu doit figurer dans l'article"""
    con = db()
    out = []
    for r in con.execute("SELECT * FROM regles_delais WHERE COALESCE(juridiction,'CH')<>'maison'").fetchall():
        # la source est réécrite après vérification (« RS 642.11 (BIB-002, version …) ») : n'en garder que le numéro RS,
        # ou l'abréviation d'un texte cantonal (« LI-VD (BIB-030, version …) », règles cantonales : cantons.yaml)
        m = re.match(r"\s*(?:RS\s+)?([^\s(]+)", r["source"] or "")
        rs = m.group(1) if m else (r["source"] or "").strip()
        res = article(rs, r["article"])
        ok = "texte" in res and bool(r["extrait_attendu"]) and fold(r["extrait_attendu"]) in fold(res["texte"])
        if not ok and r["verifie_le"]:
            # une règle qui n'est plus confirmée par le texte en vigueur perd sa vérification (nouvelle version, abrogation)
            con.execute("UPDATE regles_delais SET verifie_le=NULL WHERE id=?", (r["id"],))
        if ok:
            pre = "RS " if rs[:1].isdigit() else ""
            con.execute("UPDATE regles_delais SET verifie_le=?, source=? WHERE id=?", (iso(), f"{pre}{rs} ({res['source']}, version {res['version']})", r["id"]))
            link(r["id"], res["source"], "source")
            # lever la réserve des délais déjà ouverts
            for d in con.execute("SELECT id FROM delais WHERE regle=? AND statut='ouvert'", (r["id"],)).fetchall():
                o = get(d[0])
                if o and o["risque"] and "non vérifiée" in o["risque"]:
                    update(d[0], risque=None, resume=(o["resume"] or "").split(" ⚠")[0] + f" Vérifié le {iso()} contre {res['source']}.")
        out.append({"id": r["id"], "regle": r["type"], "article": f"{'RS ' if rs[:1].isdigit() else ''}{rs} {r['article']}", "juridiction": r["juridiction"] or "CH", "extrait_attendu": r["extrait_attendu"], "verifie": ok,
                    "version": res.get("version"), "detail": res.get("erreur") or cut(res.get("texte", ""), 160)})
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
