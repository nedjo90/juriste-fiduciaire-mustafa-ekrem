"""Sommaires générés (§9.3) : niveau 0 (carte, 2 000 car.), niveau 1 (par client / par domaine, 160 car. par ligne,
subdivision au-delà de 150 lignes), niveau 2 = en-têtes des fichiers."""
import json
from .core import db, SOMMAIRES, cut, iso, today, get_etat, set_etat

N0_MAX, LIGNE_MAX, N1_MAX = 2000, 160, 150

def ligne(o):
    if not o:
        return ""
    pa = " ".join(x for x in [o.get("prochaine_date") or "", o.get("prochaine_action") or ""] if x)
    parts = [f"[{o['id']}] {o['type']}", o["nom"], o.get("statut") or "actif", pa]
    if o.get("risque"):
        parts.append(o["risque"] if str(o["risque"]).startswith("⚠") else "⚠" + o["risque"])
    return cut(" · ".join(p for p in parts if p), LIGNE_MAX)

def _write_n1(path, titre, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [ligne(dict(r)) for r in rows]
    if len(lines) <= N1_MAX:
        path.write_text(f"# {titre}\n" + "\n".join(lines) + "\n", encoding="utf-8")
        for old in path.parent.glob(path.stem + "--*.md"):
            old.unlink()
        return [path]
    parts = [lines[i:i + N1_MAX] for i in range(0, len(lines), N1_MAX)]
    files = []
    for old in path.parent.glob(path.stem + "--*.md"):
        old.unlink()
    for i, chunk in enumerate(parts, 1):
        p = path.with_name(f"{path.stem}--{i}.md")
        p.write_text(f"# {titre} (partie {i}/{len(parts)})\n" + "\n".join(chunk) + "\n", encoding="utf-8")
        files.append(p)
    path.write_text(f"# {titre} — {len(lines)} lignes, subdivisé\n" + "\n".join(f"- {f.name}" for f in files) + "\n", encoding="utf-8")
    return files

ORDER = "CASE WHEN statut='archive' THEN 1 ELSE 0 END, COALESCE(prochaine_date,'9999'), id"

def client_n1(cid):
    con = db()
    c = con.execute("SELECT * FROM objets WHERE id=?", (cid,)).fetchone()
    if not c:
        return
    rows = con.execute(f"SELECT * FROM objets WHERE (client=? OR id=?) AND statut!='archive' ORDER BY {ORDER}", (cid, cid)).fetchall()
    _write_n1(SOMMAIRES / "clients" / f"{cid}.md", f"{cid} {c['nom']} — niveau 1", rows)

def domaine_n1(typ):
    con = db()
    rows = con.execute(f"SELECT * FROM objets WHERE type=? AND client IS NULL AND statut!='archive' ORDER BY {ORDER}", (typ,)).fetchall()
    _write_n1(SOMMAIRES / "domaines" / f"{typ}.md", f"domaine {typ} — niveau 1", rows)

def touch(o):
    """régénération incrémentale des sommaires concernés"""
    if o.get("client"):
        client_n1(o["client"])
    elif o["type"] == "client":
        client_n1(o["id"])
    else:
        domaine_n1(o["type"])
    sales = set(get_etat("n0_sale", []) or [])
    sales.add(o["id"])
    set_etat("n0_sale", sorted(sales)[-50:])

def niveau0():
    con = db()
    d = today()
    out = [f"# SOMMAIRE niveau 0 · {iso(d)}", "entrer ici → niveau 1 (.equipe/sommaires/clients/<C>.md | domaines/<type>.md) → cerebro find/summary/open --section"]
    clients = con.execute(f"SELECT * FROM objets WHERE type='client' AND statut!='archive' ORDER BY {ORDER}").fetchall()
    out.append(f"## clients ({len(clients)})")
    for c in clients[:12]:
        n = con.execute("SELECT COUNT(*) FROM objets WHERE client=? AND statut!='archive'", (c["id"],)).fetchone()[0]
        out.append(cut(f"[{c['id']}] {c['nom']} · {n} obj · {c['prochaine_date'] or ''} {c['prochaine_action'] or ''}", 120))
    if len(clients) > 12:
        out.append(f"… +{len(clients) - 12} (cerebro find)")
    dls = con.execute("SELECT d.id,d.echeance,o.nom FROM delais d JOIN objets o ON o.id=d.id WHERE d.statut='ouvert' ORDER BY d.echeance LIMIT 5").fetchall()
    if dls:
        out.append("## délais proches")
        out += [cut(f"[{r['id']}] {r['echeance']} {r['nom']}", 100) for r in dls]
    types = con.execute("SELECT type,COUNT(*) n FROM objets WHERE client IS NULL AND statut!='archive' AND type!='client' GROUP BY type ORDER BY n DESC").fetchall()
    out.append("## domaines")
    out.append(cut(" · ".join(f"{t['type']}:{t['n']}" for t in types), 400))
    q = con.execute("SELECT COUNT(*) FROM questions_ouvertes WHERE statut='ouverte'").fetchone()[0]
    inc = con.execute("SELECT COUNT(*) FROM incidents WHERE statut='ouvert'").fetchone()[0]
    out.append(f"## file · questions:{q} · incidents:{inc}")
    txt = "\n".join(out)
    if len(txt) > N0_MAX:
        txt = txt[: N0_MAX - 2].rsplit("\n", 1)[0] + "\n…"
    SOMMAIRES.mkdir(parents=True, exist_ok=True)
    (SOMMAIRES / "SOMMAIRE.md").write_text(txt + "\n", encoding="utf-8")
    set_etat("n0_sale", [])
    return txt

def tout():
    con = db()
    for (cid,) in con.execute("SELECT id FROM objets WHERE type='client'").fetchall():
        client_n1(cid)
    for (t,) in con.execute("SELECT DISTINCT type FROM objets WHERE client IS NULL AND type!='client'").fetchall():
        domaine_n1(t)
    return niveau0()

def importer_provisoire(path):
    """importe le SOMMAIRE.md tenu à la main à l'étape 0 : lignes [ID] type · nom · statut · prochaine action"""
    import re
    from .objets import create, get
    n = 0
    if not path.exists():
        return 0
    for l in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\[([A-Z]+-\d+)\]\s*(\w+)\s*·\s*([^·]+)·\s*([^·]+)·\s*(.*)", l)
        if m and not get(m.group(1)):
            oid, typ, nom, statut, pa = (x.strip() for x in m.groups())
            create(typ, nom, id=oid, statut=statut, prochaine_action=pa, source="sommaire provisoire étape 0",
                   chemin=".equipe/cerveau/session/backlog.md" if typ in ("chantier", "ticket") else None)
            n += 1
    return n
