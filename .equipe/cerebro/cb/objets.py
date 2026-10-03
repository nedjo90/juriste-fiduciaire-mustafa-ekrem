"""Objets : création, révision, archivage avec redirection, en-têtes, liens, alias.
Créer un objet crée son identifiant, son fichier avec en-tête, ses liens et le marque pour le sommaire (§0 quater.2)."""
import json, re, sqlite3, subprocess
from pathlib import Path
from .core import db, new_id, slug, fold, cut, iso, stamp, audit, journal, ROOT, CERVEAU, EQ, ID_RE, lire, date_iso, ecriture, has_fts, has_tri

CHAMPS = ["type", "nom", "statut", "client", "prochaine_action", "prochaine_date", "proprietaire", "risque",
          "chiffre_cle", "resume", "mots_cles", "source", "chemin", "domaine", "canton", "langue", "valide_du", "valide_au"]
EXTERNES = {"role", "skill", "ticket", "capacite", "gabarit", "cabinet", "question", "incident", "conseil"}  # fichier tenu ailleurs ou sans fichier : pas de corps généré

def _md(chemin):
    """seuls les fichiers markdown d'objets sont lus ou écrits (jamais la base, un binaire, un livrable)"""
    return bool(chemin) and str(chemin).lower().endswith(".md")

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
    text = text.lstrip("\ufeff").replace("\r\n", "\n")
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            return text[4:end], text[end + 4:].lstrip("\n")
        # en-tête non fermé : il s'arrête à la première ligne qui n'est pas « clé: valeur »
        lines = text[4:].split("\n")
        k = 0
        while k < len(lines) and k < 30 and re.match(r"^[\wéèàùç_ -]+:", lines[k]):
            k += 1
        return "\n".join(lines[:k]), "\n".join(lines[k:]).lstrip("\n")
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
    if not _md(o.get("chemin")):
        return ""
    p = abspath(o["chemin"])
    if not p.exists():
        return ""
    return split_file(lire(p))[1]

def _restaurer(o, p):
    """fichier d'objet disparu : restauration depuis git, sinon depuis l'index ; jamais de talon vide (loi 5)"""
    rel = str(o["chemin"]).replace("\\", "/")
    try:
        r = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=str(ROOT), capture_output=True, timeout=10)
        if r.returncode == 0 and r.stdout:
            corps = split_file(r.stdout.decode("utf-8", "replace"))[1]
            source = "git"
        else:
            raise RuntimeError
    except Exception:
        row = db().execute("SELECT corps FROM objets_fts WHERE id=?", (o["id"],)).fetchone() if True else None
        corps, source = ((row[0] if row else "") or ""), "index"
    from .files import incident_add
    incident_add("fichier_disparu", f"fichier de {o['id']} supprimé ({rel})", f"restauré depuis {source}" if corps else "contenu introuvable, objet marqué à revoir")
    return corps or f"# {o['nom']}\n\n## À revoir\nfichier disparu le {iso()}, contenu non retrouvé.\n"

def write_file(o, body=None):
    if o["type"] in EXTERNES or (o.get("chemin") and not _md(o["chemin"])):
        return
    p = abspath(o["chemin"]) if o.get("chemin") else default_path(o)
    if body is None:
        if p.exists():
            body = split_file(lire(p))[1]
        elif o.get("chemin"):
            body = _restaurer(o, p)
        else:
            body = f"# {o['nom']}\n\n## Résumé\n{o.get('resume') or ''}\n"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\n{header_lines(o)}\n---\n{body.rstrip()}\n", encoding="utf-8")
    if not o.get("chemin"):
        o["chemin"] = relpath(p)
        db().execute("UPDATE objets SET chemin=? WHERE id=?", (o["chemin"], o["id"]))

def index_fts(o, body=None):
    """à appeler dans une transaction d'écriture ; une erreur remonte (jamais avalée au milieu d'une transaction)"""
    con = db()
    if not has_fts():
        return
    if True:
        con.execute("DELETE FROM objets_fts WHERE id=?", (o["id"],))
        al = " ".join(r[0] for r in con.execute("SELECT alias FROM alias WHERE id=?", (o["id"],)))
        con.execute("INSERT INTO objets_fts(id,nom,resume,mots_cles,corps) VALUES(?,?,?,?,?)",
                    (o["id"], f"{o['nom']} {al}", o.get("resume") or "", o.get("mots_cles") or "", (body if body is not None else body_of(o))[:20000]))
        if has_tri():
            con.execute("DELETE FROM noms_tri WHERE id=?", (o["id"],))
            con.execute("INSERT INTO noms_tri(id,texte) VALUES(?,?)", (o["id"], fold(f"{o['nom']} {al} {o.get('mots_cles') or ''}")))

def regen(oid):
    """régénère en-tête, index et marque le sommaire ; renvoie la ligne de sommaire"""
    o = get(oid)
    if not o:
        return None
    body = None
    with ecriture() as con:
        write_file(o)
        index_fts(o)
        con.execute("UPDATE objets SET a_regenerer=0 WHERE id=?", (o["id"],))
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
    src, dst = resolve(src), resolve(dst)
    if not db().execute("SELECT 1 FROM objets WHERE id=?", (dst,)).fetchone() or not db().execute("SELECT 1 FROM objets WHERE id=?", (src,)).fetchone():
        journal("liens-refuses", src=src, dst=dst, motif="objet inexistant")
        return
    db().execute("INSERT OR IGNORE INTO liens(src,dst,type,cree_le) VALUES(?,?,?,?)", (src, dst, typ, iso()))
    db().execute("UPDATE objets SET a_regenerer=1 WHERE id IN (?,?)", (src, dst))

def create(typ, nom, body=None, liens=(), alias=(), acteur="cerebro", typed=None, **kw):
    """crée un objet complet : id, en-tête, fichier, liens, alias, index, sommaire"""
    con = db()
    for k in ("prochaine_date", "valide_du", "valide_au"):
        if kw.get(k):
            kw[k] = date_iso(kw[k])
    fixe = kw.pop("id", None)
    for essai in range(5):
        try:
            with ecriture():
                oid = _create(con, typ, nom, body, liens, alias, acteur, typed, fixe, dict(kw))
            regen(oid)
            audit("creer", oid, nom, acteur)
            journal("objets", op="creer", id=oid, type=typ, acteur=acteur)
            return oid
        except sqlite3.IntegrityError:
            if fixe:
                raise
    raise RuntimeError("identifiant introuvable après 5 essais")

def _create(con, typ, nom, body, liens, alias, acteur, typed, fixe, kw):
    oid = fixe or new_id(con, typ)
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
    return oid

def update(oid, body=None, acteur="cerebro", **kw):
    """révision : met à jour les champs (bitemporalité : l'ancienne version est archivée dans data.historique)"""
    o = get(oid)
    if not o:
        raise KeyError(oid)
    with ecriture() as con:
        _update(con, o, body, kw)
    audit("reviser", o["id"], ",".join(k for k in kw if k in CHAMPS), acteur)
    return regen(o["id"])

def _update(con, o, body, kw):
    for k in ("prochaine_date", "valide_du", "valide_au"):
        if kw.get(k):
            kw[k] = date_iso(kw[k])
    valide_le = date_iso(kw.pop("valide_le", None)) or iso()
    data = o["data"]
    hist = data.setdefault("historique", [])
    changed = {k: v for k, v in kw.items() if k in CHAMPS and o.get(k) != v}
    for k, v in changed.items():
        con.execute("UPDATE versions SET valide_au=? WHERE id=? AND champ=? AND valide_au IS NULL", (valide_le, o["id"], k))
        if not con.execute("SELECT 1 FROM versions WHERE id=? AND champ=?", (o["id"], k)).fetchone():
            con.execute("INSERT INTO versions(id,champ,valeur,valide_du,valide_au,enregistre_le) VALUES(?,?,?,?,?,?)", (o["id"], k, o.get(k), o.get("valide_du") or "0000-01-01", valide_le, stamp()))
        con.execute("INSERT INTO versions(id,champ,valeur,valide_du,valide_au,enregistre_le) VALUES(?,?,?,?,NULL,?)", (o["id"], k, v, valide_le, stamp()))
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

def archive(oid, vers=None, acteur="cerebro"):
    """archive avec redirection : l'ancien identifiant reste atteignable"""
    o = get(oid)
    if not o:
        return None
    with ecriture() as con:
        _archive(con, o, vers)
    audit("archiver", o["id"], f"vers={vers}", acteur)
    return regen(o["id"])

def _archive(con, o, vers):
    for k, v in (("statut", "archive"),):
        con.execute("UPDATE versions SET valide_au=? WHERE id=? AND champ=? AND valide_au IS NULL", (iso(), o["id"], k))
        if not con.execute("SELECT 1 FROM versions WHERE id=? AND champ=?", (o["id"], k)).fetchone():
            con.execute("INSERT INTO versions(id,champ,valeur,valide_du,valide_au,enregistre_le) VALUES(?,?,?,?,?,?)", (o["id"], k, o.get(k), o.get("valide_du") or "0000-01-01", iso(), stamp()))
        con.execute("INSERT INTO versions(id,champ,valeur,valide_du,valide_au,enregistre_le) VALUES(?,?,?,?,NULL,?)", (o["id"], k, v, iso(), stamp()))
    con.execute("UPDATE objets SET statut='archive', valide_au=?, a_regenerer=1 WHERE id=?", (iso(), o["id"]))
    if vers:
        con.execute("INSERT OR REPLACE INTO redirections(ancien,nouveau,le) VALUES(?,?,?)", (o["id"], vers, iso()))
        for a in con.execute("SELECT alias,langue FROM alias WHERE id=?", (o["id"],)).fetchall():
            add_alias(vers, a[0], a[1], 0.9)


def rename(oid, nouveau_nom, acteur="cerebro"):
    """renommer garde l'ancien nom comme alias (objet atteignable par son ancien nom)"""
    o = get(oid)
    if not o:
        return None
    add_alias(o["id"], o["nom"], confiance=0.9)
    return update(o["id"], nom=nouveau_nom, acteur=acteur)

def ids_in(text):
    return sorted(set(ID_RE.findall(text or "")))

def etat_au(oid, date):
    """bitemporalité : l'objet tel qu'il était valide à une date (champs suivis dans la table versions)"""
    o = get(oid)
    if not o:
        return None
    date = date_iso(date)
    for r in db().execute("SELECT champ, valeur FROM versions WHERE id=? AND valide_du<=? AND (valide_au IS NULL OR valide_au>?) ORDER BY valide_du", (o["id"], date, date)):
        o[r["champ"]] = r["valeur"]
    o["etat_au"] = date
    return o
