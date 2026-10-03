"""Retrouver et charger peu (§9.4) : find (alias, identifiants, plein texte, vecteurs locaux, graphe, temps),
summary (menu des sections), open --section, trace. Chaque ouverture est journalisée."""
import os, re, math, json
from collections import Counter
from .core import db, fold, cut, iso, today, journal, has_fts, EQ, get_etat, set_etat, ID_RE
from .objets import get, resolve, links_of, body_of, split_file, abspath
from .sommaires import ligne

STOP = set("le la les de des du un une et ou en au aux pour par sur dans est que qui quoi avec sans ce cette ces son sa ses mon ma mes the of and to in is a der die das und von zu mit il lo gli di che per".split())

def _grams(s):
    s = f"  {fold(s)}  "
    return Counter(s[i:i + 3] for i in range(len(s) - 2))

def _cos(a, b):
    if not a or not b:
        return 0.0
    num = sum(v * b.get(k, 0) for k, v in a.items())
    return num / (math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values())) or 1)

def _tokens(q):
    return [t for t in re.findall(r"\w+", fold(q)) if len(t) > 1 and t not in STOP]

def _valid(o, asof):
    if not asof:
        return True
    return (o["valide_du"] or "0000") <= asof and (not o["valide_au"] or o["valide_au"] >= asof)

def find(q, limit=10, deep=False, asof=None, types=None):
    con = db()
    scores = {}
    def add(oid, s, why):
        """cumul des indices : le meilleur compte plein, chaque indice supplémentaire ajoute 25 %"""
        oid = resolve(oid)
        cur = scores.get(oid)
        if not cur:
            scores[oid] = (s, why)
        elif s > cur[0]:
            scores[oid] = (s + 0.25 * cur[0], why)
        else:
            scores[oid] = (cur[0] + 0.25 * s, cur[1])
    for i in ID_RE.findall(q):
        add(i, 100, "id")
    fq = fold(q)
    # alias : l'alias apparaît dans la question, ou la question est un alias
    for r in con.execute("SELECT alias_fold,id,confiance FROM alias"):
        a = r["alias_fold"]
        if len(a) < 3:
            continue
        if a == fq:
            add(r["id"], 90 * r["confiance"], "alias")
        elif re.search(r"\b" + re.escape(a) + r"\b", fq):
            add(r["id"], (60 + min(len(a), 20)) * r["confiance"], "alias")
        elif len(fq) >= 4 and fq in a:
            add(r["id"], 45 * r["confiance"], "alias~")
    toks = _tokens(q)
    if toks and has_fts():
        try:
            m = " OR ".join(f'"{t}"*' if len(t) > 3 else f'"{t}"' for t in toks)
            for r in con.execute("SELECT id, bm25(objets_fts) b FROM objets_fts WHERE objets_fts MATCH ? ORDER BY b LIMIT 50", (m,)):
                add(r["id"], min(55, 20 + -r["b"] * 4), "texte")
        except Exception:
            pass
    elif toks:
        for t in toks:
            for r in con.execute("SELECT id FROM objets WHERE lower(nom||' '||COALESCE(resume,'')||' '||COALESCE(mots_cles,'')) LIKE ?", (f"%{t}%",)):
                add(r["id"], 25, "texte")
    # vecteurs locaux (trigrammes) : rattrape fautes, langues, reformulations
    gq = _grams(q)
    noms = {}
    for r in con.execute("SELECT id, alias FROM alias"):
        noms.setdefault(r["id"], []).append(r["alias"])
    for r in con.execute("SELECT id,nom,resume,mots_cles FROM objets" + ("" if deep else " WHERE statut!='archive'")):
        s = max([_cos(gq, _grams(f"{r['nom']} {r['mots_cles'] or ''} {r['resume'] or ''}"))] + [_cos(gq, _grams(a)) * 1.1 for a in noms.get(r["id"], [r["nom"]])])
        if s > 0.18:
            add(r["id"], 50 * s, "vecteur")
    # expansion par le graphe
    top = sorted(scores.items(), key=lambda x: -x[1][0])[:5]
    for oid, (s, _) in top:
        for r in con.execute("SELECT dst FROM liens WHERE src=? UNION SELECT src FROM liens WHERE dst=?", (oid, oid)):
            add(r[0], s * 0.35, "graphe")
    res = []
    for oid, (s, why) in sorted(scores.items(), key=lambda x: -x[1][0]):
        o = get(oid)
        if not o or (o["statut"] == "archive" and not deep) or not _valid(o, asof):
            continue
        if types and o["type"] not in types:
            continue
        res.append({"id": o["id"], "score": round(s, 1), "via": why, "ligne": ligne(o), "presque": s < 35})
        if len(res) >= limit:
            break
    if deep:
        arch = EQ / "archives"
        if arch.exists():
            for p in arch.rglob("*.md"):
                t = p.read_text(encoding="utf-8", errors="ignore")
                if toks and all(tok in fold(t) for tok in toks[:3]):
                    res.append({"id": None, "score": 10, "via": "archives", "ligne": str(p.relative_to(EQ)), "presque": True})
    journal("find", q=cut(q, 120), n=len(res))
    return res

def sections(body):
    out, cur, buf = [], None, []
    for l in body.splitlines():
        m = re.match(r"^(#{2,4})\s+(.*)", l)
        if m:
            if cur is not None:
                out.append((cur, "\n".join(buf).strip()))
            cur, buf = m.group(2).strip(), []
        else:
            buf.append(l)
    if cur is not None:
        out.append((cur, "\n".join(buf).strip()))
    return out

def _ouverture(oid, section, acteur):
    tour = os.environ.get("CEREBRO_TOUR") or get_etat("tour", "0")
    db().execute("INSERT INTO ouvertures(le,tour,id,section,acteur) VALUES(datetime('now'),?,?,?,?)", (str(tour), oid, section, acteur))
    db().commit()
    n = db().execute("SELECT COUNT(*) FROM ouvertures WHERE tour=?", (str(tour),)).fetchone()[0]
    if n > 5:
        journal("ouvertures-excès", tour=tour, n=n, id=oid)
    return n

def summary(oid, acteur="agent"):
    o = get(oid)
    if not o:
        alt = find(oid, limit=3)
        return {"erreur": "inconnu", "presque": [a["ligne"] for a in alt]}
    _ouverture(o["id"], "*summary", acteur)
    out_l, inc = links_of(o["id"])
    secs = sections(body_of(o))
    return {"id": o["id"], "type": o["type"], "nom": o["nom"], "statut": o["statut"], "client": o["client"],
            "maj": o["maj"], "prochaine_action": f"{o['prochaine_date'] or ''} {o['prochaine_action'] or ''}".strip(),
            "risque": o["risque"], "chiffre_cle": o["chiffre_cle"], "resume": cut(o["resume"] or "", 280),
            "source": o["source"], "liens_sortants": [f"{l['dst']}({l['type']})" for l in out_l][:25],
            "liens_entrants": [f"{l['src']}({l['type']})" for l in inc][:25],
            "sections": [f"{t} ({len(c)} car.)" for t, c in secs], "chemin": o["chemin"]}

def open_section(oid, section=None, acteur="agent"):
    o = get(oid)
    if not o:
        return {"erreur": "inconnu"}
    body = body_of(o)
    secs = sections(body)
    if not section:
        _ouverture(o["id"], "*", acteur)
        return {"id": o["id"], "sections": [t for t, _ in secs], "note": "préciser --section"}
    fs = fold(section)
    for t, c in secs:
        if fold(t) == fs or fs in fold(t):
            _ouverture(o["id"], t, acteur)
            return {"id": o["id"], "section": t, "contenu": c}
    return {"id": o["id"], "erreur": "section absente", "sections": [t for t, _ in secs]}

def trace(oid, n=30):
    """lecture ciblée des traces d'un objet (seule lecture de journal autorisée à un modèle)"""
    con = db()
    oid = resolve(oid)
    rows = con.execute("SELECT le,acteur,action,detail FROM journal_audit WHERE objet=? ORDER BY n DESC LIMIT ?", (oid, n)).fetchall()
    return [f"{r['le'][:16]} {r['acteur']} {r['action']} {cut(r['detail'] or '', 100)}" for r in rows]

def autotest_rappel(n=20):
    """§9.4 : vingt faits reformulés, rappel > 95 % sinon reconstruction de l'index"""
    import random
    con = db()
    rows = con.execute("SELECT id,nom,resume,mots_cles FROM objets WHERE statut!='archive' AND length(COALESCE(resume,''))>20 ORDER BY random() LIMIT ?", (n,)).fetchall()
    ok = 0
    for r in rows:
        words = [w for w in re.findall(r"\w{4,}", r["resume"] or "") if fold(w) not in STOP]
        random.shuffle(words)
        q = " ".join(words[:5]) or r["nom"]
        if any(x["id"] == r["id"] for x in find(q, limit=10)):
            ok += 1
    taux = ok / len(rows) if rows else 1.0
    if taux < 0.95:
        from .objets import index_fts
        for (oid,) in con.execute("SELECT id FROM objets").fetchall():
            index_fts(get(oid))
        con.commit()
    return {"echantillon": len(rows), "rappel": round(taux, 3), "reindexe": taux < 0.95}
