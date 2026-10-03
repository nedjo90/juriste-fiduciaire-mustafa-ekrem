"""Porte (a) liens (§7.5) : tout identifiant cerebro cité résout (redirections suivies)."""
from gates_common import resultat, ETAT_OK, ETAT_KO, ETAT_NA
import common as C


def ids_du_document(doc):
    try:
        core, _, _, _ = C.cb()
        rx = core.ID_RE
    except Exception:
        return None
    texte = doc.get("texte", "") + " " + doc.get("brut", "")
    ids = set(rx.findall(texte))
    m = doc.get("meta", {})
    for k in ("client", "dossier"):
        if m.get(k):
            ids |= set(rx.findall(str(m[k])))
    for k in ("liens", "sources"):
        for x in (m.get(k) or []):
            ids |= set(rx.findall(str(x)))
    return sorted(ids)


def verifier(doc, ctx=None):
    ids = ids_du_document(doc)
    if ids is None:
        return resultat(ETAT_NA, ["cerebro indisponible : liens non vérifiés"], reserves=1)
    morts = [i for i in ids if not C.objet(i)]
    det = [f"{len(ids)} identifiant(s) cité(s), {len(morts)} sans objet"]
    if morts:
        return resultat(ETAT_KO, det, [{"identifiant": i, "correction": "corriger l'identifiant (cerebro find …) ou retirer la mention"} for i in morts], morts=morts)
    return resultat(ETAT_OK, det, ids=ids)
