"""Objets : création, révision, archivage avec redirection, en-têtes, liens, alias.
Créer un objet crée son identifiant, son fichier avec en-tête, ses liens et le marque pour le sommaire (§0 quater.2)."""
import json, re
from pathlib import Path
from .core import db, new_id, slug, fold, cut, iso, stamp, audit, journal, ROOT, CERVEAU, EQ, ID_RE

CHAMPS = ["type", "nom", "statut", "client", "prochaine_action", "prochaine_date", "proprietaire", "risque",
          "chiffre_cle", "resume", "mots_cles", "source", "chemin", "domaine", "canton", "langue", "valide_du", "valide_au"]
EXTERNES = {"role", "skill", "ticket", "capacite", "gabarit", "cabinet"}  # fichier tenu ailleurs : pas de corps généré

# ------------------------------------------------------------------ lecture
def resolve(oid):
    """suit les redirections (anciens identifiants)"""
    con = db()
    seen = set()
    while oid and oid not in seen:
        seen.add(oid)
        r = con.execute("SELECT nouveau FROM redirections WHERE ancien=?", (oid,)).fetchone()
        if not r:
            break
        oid = r[0]
    return oid

def get(oid):
    r = db().execute("SELECT * FROM objets WHERE id=?", (resolve(oid),)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["data"] = json.loads(d.get("data") or "{}")
    return d

def links_of(oid):
    con = db()
    out = [dict(dst=r["dst"], type=r["type"]) for r in con.execute("SELECT dst,type FROM liens WHERE src=?", (oid,))]
    inc = [dict(src=r["src"], type=r["type"]) for r in con.execute("SELECT src,type FROM liens WHERE dst=?", (oid,))]
    return out, inc

# ------------------------------------------------------------------ chemins
def client_dir(cid):
    c = db().execute("SELECT nom FROM objets WHERE id=?", (cid,)).fetchone()
    return CERVEAU / "clients" / f"{cid}-{slug(c['nom'] if c else cid, 30)}"

DOSSIER_TYPE = {"methode": CERVEAU / "cabinet" / "methodes", "position": CERVEAU / "doctrine" / "positions",
                "doctrine": CERVEAU / "doctrine", "precedent": CERVEAU / "precedents",
                "correspondant": CERVEAU / "correspondants", "note": CERVEAU / "notes",
                "source": EQ / "bibliotheque" / "fiches", "changement_droit": CERVEAU / "doctrine" / "changements",
                "question": CERVEAU / "session" / "questions", "incident": CERVEAU / "session" / "incidents",
                "livrable": CERVEAU / "livrables", "regle_delai": CERVEAU / "doctrine" / "regles-delais"}

def default_path(o):
    if o["type"] == "client":
        return client_dir(o["id"]) / f"{o['id']}.md"
    if o.get("client"):
        return client_dir(o["client"]) / o["type"] / f"{o['id']}-{slug(o['nom'], 40)}.md"
    base = DOSSIER_TYPE.get(o["type"], CERVEAU / "notes" / o["type"])
    return base / f"{o['id']}-{slug(o['nom'], 40)}.md"

def abspath(chemin):
    p = Path(chemin)
    return p if p.is_absolute() else ROOT / p

def relpath(p):
    try:
        return str(Path(p).resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except Exception:
        return str(p)

# ------------------------------------------------------------------ en-tête / corps
def split_file(text):
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            return text[4:end], text[end + 4:].lstrip("\n")
    return "", text

def header_lines(o):
    out_l, _ = links_of(o["id"])
    liens = ", ".join(sorted({l["dst"] for l in out_l}))
    pa = o.get("prochaine_action") or ""
    if o.get("prochaine_date"):
        pa = f"{o['prochaine_date']} {pa}".strip()
    f = [("id", o["id"]), ("type", o["type"]), ("statut", o.get("statut") or "actif"), ("maj", o.get("maj") or iso()),
         ("prochaine_action", pa), ("risque_principal", o.get("risque") or ""), ("chiffre_clé", o.get("chiffre_cle") or ""),
         ("résumé", cut(o.get("resume") or o["nom"], 280)), ("mots_clés", o.get("mots_cles") or ""), ("liens", liens),
         ("source", o.get("source") or "")]
    if o.get("client"):
        f.insert(3, ("client", o["client"]))
    return "\n".join(f"{k}: {str(v).replace(chr(10), ' ')}" for k, v in f)

def body_of(o):
    if not o.get("chemin"):
        return ""
    p = abspath(o["chemin"])
    if not p.exists():
        return ""
    return split_file(p.read_text(encoding="utf-8"))[1]

def write_file(o, body=None):
    if o["type"] in EXTERNES and o.get("chemin"):
        return
    p = abspath(o["chemin"]) if o.get("chemin") else default_path(o)
    if body is None:
        body = split_file(p.read_text(encoding="utf-8"))[1] if p.exists() else f"# {o['nom']}\n\n## Résumé\n{o.get('resume') or ''}\n"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{header_lines(o)}\n---\n{body.rstrip()}\n", encoding="utf-8")
    if not o.get("chemin"):
        o["chemin"] = relpath(p)
        db().execute("UPDATE objets SET chemin=? WHERE id=?", (o["chemin"], o["id"]))

def index_fts(o, body=None):
    con = db()
    try:
        con.execute("DELETE FROM objets_fts WHERE id=?", (o["id"],))
        al = " ".join(r[0] for r in con.execute("SELECT alias FROM alias WHERE id=?", (o["id"],)))
        con.execute("INSERT INTO objets_fts(id,nom,resume,mots_cles,corps) VALUES(?,?,?,?,?)",
                    (o["id"], f"{o['nom']} {al}", o.get("resume") or "", o.get("mots_cles") or "", (body if body is not None else body_of(o))[:20000]))
    except Exception:
        pass

def regen(oid):
    """régénère en-tête, index et marque le sommaire ; renvoie la ligne de sommaire"""
    o = get(oid)
    if not o:
        return None
    write_file(o)
    index_fts(o)
    db().execute("UPDATE objets SET a_regenerer=0 WHERE id=?", (o["id"],))
    db().commit()
    from .sommaires import ligne, touch
    touch(o)
    return ligne(get(o["id"]))

# ------------------------------------------------------------------ écriture
def add_alias(oid, alias, langue=None, confiance=1.0):
    if not alias:
        return
    db().execute("INSERT OR IGNORE INTO alias(alias,alias_fold,id,langue,confiance) VALUES(?,?,?,?,?)", (alias, fold(alias), oid, langue, confiance))

def link(src, dst, typ="lie"):
    if not src or not dst or src == dst:
        return
    db().execute("INSERT OR IGNORE INTO liens(src,dst,type,cree_le) VALUES(?,?,?,?)", (src, dst, typ, iso()))
    db().execute("UPDATE objets SET a_regenerer=1 WHERE id IN (?,?)", (src, dst))

def create(typ, nom, body=None, liens=(), alias=(), acteur="cerebro", typed=None, **kw):
    """crée un objet complet : id, en-tête, fichier, liens, alias, index, sommaire"""
    con = db()
    oid = kw.pop("id", None) or new_id(con, typ)
    if not kw.get("prochaine_action"):
        kw["prochaine_action"] = "revoir"
    if not kw.get("prochaine_date"):
        from .core import today
        import datetime as dt
        kw["prochaine_date"] = (today() + dt.timedelta(days=90)).isoformat()
    data = kw.pop("data", {}) or {}
    cols = {k: v for k, v in kw.items() if k in CHAMPS}
    for k in list(kw):
        if k not in CHAMPS:
            data[k] = kw[k]
    cols.update(id=oid, type=typ, nom=nom, maj=iso(), enregistre_le=stamp(), data=json.dumps(data, ensure_ascii=False))
    cols.setdefault("valide_du", iso())
    con.execute(f"INSERT INTO objets({','.join(cols)}) VALUES({','.join('?' * len(cols))})", list(cols.values()))
    add_alias(oid, nom)
    for a in alias:
        add_alias(oid, a)
    for l in liens:
        if isinstance(l, (list, tuple)):
            link(oid, l[0], l[1])
        else:
            link(oid, l)
    if cols.get("client") and typ != "client":
        link(oid, cols["client"], "client")
    if typed:
        table, vals = typed
        vals = {"id": oid, **vals}
        con.execute(f"INSERT OR REPLACE INTO {table}({','.join(vals)}) VALUES({','.join('?' * len(vals))})", list(vals.values()))
    o = get(oid)
    write_file(o, body)
    con.commit()
    regen(oid)
    audit("creer", oid, nom, acteur)
    journal("objets", op="creer", id=oid, type=typ, acteur=acteur)
    return oid

def update(oid, body=None, acteur="cerebro", **kw):
    """révision : met à jour les champs (bitemporalité : l'ancienne version est archivée dans data.historique)"""
    o = get(oid)
    if not o:
        raise KeyError(oid)
    con = db()
    data = o["data"]
    hist = data.setdefault("historique", [])
    changed = {k: v for k, v in kw.items() if k in CHAMPS and o.get(k) != v}
    if changed:
        hist.append({"enregistre_le": stamp(), "avant": {k: o.get(k) for k in changed}})
        data["historique"] = hist[-30:]
    for k in list(kw):
        if k not in CHAMPS:
            data[k] = kw.pop(k)
    sets = {**changed, "maj": iso(), "data": json.dumps(data, ensure_ascii=False), "a_regenerer": 1}
    con.execute(f"UPDATE objets SET {','.join(k + '=?' for k in sets)} WHERE id=?", [*sets.values(), o["id"]])
    if body is not None:
        write_file(get(o["id"]), body)
    con.commit()
    audit("reviser", o["id"], ",".join(changed), acteur)
    return regen(o["id"])

def archive(oid, vers=None, acteur="cerebro"):
    """archive avec redirection : l'ancien identifiant reste atteignable"""
    o = get(oid)
    if not o:
        return None
    con = db()
    con.execute("UPDATE objets SET statut='archive', valide_au=?, a_regenerer=1 WHERE id=?", (iso(), o["id"]))
    if vers:
        con.execute("INSERT OR REPLACE INTO redirections(ancien,nouveau,le) VALUES(?,?,?)", (o["id"], vers, iso()))
        for a in con.execute("SELECT alias,langue FROM alias WHERE id=?", (o["id"],)).fetchall():
            add_alias(vers, a[0], a[1], 0.9)
    con.commit()
    audit("archiver", o["id"], f"vers={vers}", acteur)
    return regen(o["id"])

def rename(oid, nouveau_nom, acteur="cerebro"):
    """renommer garde l'ancien nom comme alias (objet atteignable par son ancien nom)"""
    o = get(oid)
    add_alias(o["id"], o["nom"], confiance=0.9)
    return update(o["id"], nom=nouveau_nom, acteur=acteur)

def ids_in(text):
    return sorted(set(ID_RE.findall(text or "")))
