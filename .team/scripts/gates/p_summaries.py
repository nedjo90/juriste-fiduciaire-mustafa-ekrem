"""Porte (d) sommaires (§7.5, §0 ter 5) : tout objet cité ou touché par le livrable (identifiants du texte, client,
dossier, livrable lui-même, objets touchés déclarés) est régénéré (a_regenerer = 0) et a sa ligne dans le sommaire de
niveau 1 (client ou domaine). Correction déterministe : `cerebro regen <IDs>` (reparer())."""
from gates_common import resultat, ETAT_OK, ETAT_KO, ETAT_NA
import common as C
from p_links import ids_du_document


def fichiers_sommaire(o):
    """fichier(s) de niveau 1 où la ligne de l'objet doit figurer (subdivision --N comprise)"""
    core = C.cb()[0]
    base = core.SOMMAIRES / "clients" / f"{o['client']}.md" if o.get("client") else \
        core.SOMMAIRES / "clients" / f"{o['id']}.md" if o["type"] == "client" else core.SOMMAIRES / "domains" / f"{o['type']}.md"
    return [base] + sorted(base.parent.glob(base.stem + "--*.md"))


def au_sommaire(o):
    for f in fichiers_sommaire(o):
        try:
            if f"[{o['id']}]" in f.read_text(encoding="utf-8"):
                return True
        except Exception:
            continue
    return False


def a_controler(doc, ctx=None):
    ctx = ctx or {}
    ids = set(ids_du_document(doc) or [])
    for k in ("livrable",):
        if ctx.get(k):
            ids.add(ctx[k])
    ids |= set(ctx.get("touches") or [])
    return sorted(ids)


def verifier(doc, ctx=None):
    try:
        C.cb()
    except Exception:
        return resultat(ETAT_NA, ["cerebro indisponible : sommaires non vérifiés"], reserves=1)
    ids = a_controler(doc, ctx)
    if not ids:
        return resultat(ETAT_NA, ["aucun objet cité ou touché"])
    vus, manques = 0, []
    for i in ids:
        o = C.objet(i)
        if not o or o.get("statut") == "archive":
            continue  # identifiant mort : porte liens ; archivé : hors sommaire par construction
        vus += 1
        pb = []
        if o.get("a_regenerer"):
            pb.append("en-tête et ligne à régénérer")
        if not au_sommaire(o):
            pb.append("absent du sommaire de niveau 1")
        if pb:
            manques.append({"id": o["id"], "probleme": " ; ".join(pb), "correction": f"cerebro regen {o['id']}"})
    if not vus:
        return resultat(ETAT_NA, ["aucun objet vivant cité"])
    if manques:
        return resultat(ETAT_KO, [f"{len(manques)}/{vus} objet(s) cité(s) ou touché(s) hors sommaire à jour"], manques,
                        a_regenerer=[m["id"] for m in manques])
    return resultat(ETAT_OK, [f"{vus} objet(s) cité(s) ou touché(s), tous régénérés et au sommaire"])


def reparer(ids):
    """correction déterministe (script, pas de modèle) : régénère en-têtes, index et sommaires ; renvoie les lignes"""
    _, objets, _, _ = C.cb()
    out = []
    for i in ids or []:
        try:
            out.append(objets.regen(i))
        except Exception as e:
            C.journal("erreurs-portes", porte="sommaires", op="reparer", id=i, erreur=repr(e))
    return [l for l in out if l]
