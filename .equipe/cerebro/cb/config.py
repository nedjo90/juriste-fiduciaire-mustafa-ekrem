"""Configuration à trous (§0 bis) : get lit valeur sinon defaut ; set renseigne, journalise la source et recalcule
ce qui en dépend ; gaps liste les clés vides classées par effet (source de la file des questions)."""
import json, re
import yaml
from .core import EQ, SESSION, iso, audit, db, stamp

CONF = EQ / "config"

# clé → recalculs à mettre en file d'entretien (priorité 2 = prochain cycle)
DEPENDANCES = {
    "mustafa.cantons_suivis": ["horloges_recalcul", "doctrine_cantons", "bibliotheque_cantons", "profil"],
    "mustafa.langues": ["gabarits", "profil"],
    "mustafa.tutoiement": ["profil"],
    "mustafa.domaines": ["specialistes", "profil"],
    "cabinet.charte": ["gabarits", "design"],
    "cabinet.logo": ["gabarits"],
    "cabinet.raison_sociale": ["gabarits"],
    "cabinet.signature": ["gabarits"],
    "cabinet.adresse": ["gabarits"],
    "poste.messagerie": ["connecteurs", "environnement"],
    "poste.agenda": ["connecteurs", "environnement"],
    "poste.systeme": ["lanceurs", "environnement"],
    "acces.bases_recherche": ["connecteurs", "environnement"],
    "modeles.profil": ["modeles_roles"],
    "modeles.plus_capable": ["modeles_roles"],
    "modeles.intermediaire": ["modeles_roles"],
    "modeles.leger": ["modeles_roles"],
    "clients.principaux": ["clients_import"],
}
DEFAUTS_MAP = {"mustafa.cantons_suivis": "canton", "poste.messagerie": "messagerie", "poste.agenda": "agenda",
               "mustafa.tutoiement": "tutoiement", "cabinet.charte": "gabarit", "acces.abonnement_claude": "abonnement",
               "poste.systeme": "systeme_poste", "acces.bases_recherche": "bases_recherche"}

def _load(f):
    p = CONF / f"{f}.yaml"
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.exists() else {}

def _save(f, data):
    """écriture atomique : fichier temporaire puis remplacement (jamais de YAML à moitié écrit)"""
    import os
    p = CONF / f"{f}.yaml"
    head = [l for l in p.read_text(encoding="utf-8").splitlines() if l.startswith("#")] if p.exists() else [f"# {f}.yaml"]
    tmp = p.with_suffix(".yaml.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(head) + "\n")
        yaml.safe_dump(data, fh, allow_unicode=True, sort_keys=False)
    os.replace(tmp, p)

def get(key):
    if not key or "." not in key:
        return None
    f, k = key.split(".", 1)
    e = _load(f).get(k)
    if e is None:
        return None
    return e.get("valeur") if e.get("valeur") not in (None, "", []) else e.get("defaut")

def get_full(key):
    if not key or "." not in key:
        return None
    f, k = key.split(".", 1)
    return _load(f).get(k)

LISTES = {"cantons_suivis", "langues", "domaines", "bases_recherche", "principaux", "connecteurs"}

def _parse(v, liste=False):
    if isinstance(v, str):
        s = v.strip()
        if s[:1] in "[{" or s in ("true", "false", "null") or re.fullmatch(r"-?\d+(\.\d+)?", s):
            try:
                return json.loads(s)
            except Exception:
                pass
        if liste:
            return [x.strip() for x in re.split(r"[,;]", s) if x.strip()]
    return v

def set_(key, valeur, source=None, acteur="agent"):
    if not key or "." not in key:
        return {"erreur": "clé attendue sous la forme fichier.clé (ex. poste.messagerie)"}
    if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
        return {"cle": key, "ignore": "valeur vide : le défaut reste appliqué"}
    f, k = key.split(".", 1)
    if not (CONF / f"{f}.yaml").exists():
        return {"erreur": f"fichier de configuration inconnu : {f} (connus : {', '.join(p.stem for p in CONF.glob('*.yaml'))})"}
    data = _load(f)
    e = data.get(k) or {"valeur": None, "defaut": None, "source": "défaut", "question": "", "effet": 1}
    e["valeur"] = _parse(valeur, liste=(k in LISTES or isinstance(e.get("defaut"), list)))
    e["source"] = source or f"déclaré par Mustafa le {iso()}"
    data[k] = e
    _save(f, data)
    # défauts.md : la ligne passe de [défaut] à la source réelle
    if key in DEFAUTS_MAP:
        p = SESSION / "defauts.md"
        if p.exists():
            lines = p.read_text(encoding="utf-8").splitlines()
            lab = DEFAUTS_MAP[key]
            v = ", ".join(e["valeur"]) if isinstance(e["valeur"], list) else e["valeur"]
            lines = [f"{lab}: {v} [{e['source']}]" if l.startswith(lab + ":") else l for l in lines]
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    con = db()
    con.execute("UPDATE questions_ouvertes SET statut='repondue', reponse=? WHERE cle_config=? AND statut='ouverte'", (json.dumps(e["valeur"], ensure_ascii=False), key))
    recalc = DEPENDANCES.get(key, [])
    for t in recalc:
        con.execute("INSERT OR IGNORE INTO file_entretien(priorite,tache,arg,cree_le) VALUES(2,?,?,?)", (t, key, stamp()))
    con.commit()
    audit("config_set", key, json.dumps(e["valeur"], ensure_ascii=False), acteur)
    from .sommaires import niveau0
    niveau0()
    return {"cle": key, "valeur": e["valeur"], "source": e["source"], "recalculs": recalc}

def gaps():
    out = []
    for p in sorted(CONF.glob("*.yaml")):
        for k, e in (_load(p.stem) or {}).items():
            if not isinstance(e, dict):
                continue
            if e.get("valeur") in (None, "", []):
                out.append({"cle": f"{p.stem}.{k}", "effet": e.get("effet", 1), "defaut": e.get("defaut"), "question": e.get("question") or ""})
    out.sort(key=lambda x: -x["effet"])
    return out

def taux_remplissage():
    tot = vides = 0
    for p in CONF.glob("*.yaml"):
        for k, e in (_load(p.stem) or {}).items():
            if isinstance(e, dict):
                tot += 1
                vides += e.get("valeur") in (None, "", [])
    return round(1 - vides / tot, 3) if tot else 0.0
