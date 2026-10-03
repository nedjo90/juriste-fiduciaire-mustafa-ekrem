"""Porte (g) couverture (§7.5, loi 6) : chaque dossier touché (client, dossier, délai, contrat cités) a une prochaine action datée."""
from commun_portes import resultat, ETAT_OK, ETAT_KO, ETAT_NA
import commun as C
from p_liens import ids_du_document

TYPES_SUIVIS = {"client", "dossier", "delai", "contrat", "lba", "decision_taxation", "engagement", "ruling", "entite"}


def verifier(doc, ctx=None):
    ids = ids_du_document(doc)
    if ids is None:
        return resultat(ETAT_NA, ["cerebro indisponible"], reserves=1)
    aujourd = C.today().isoformat()
    touches, manques = [], []
    for i in ids:
        o = C.objet(i)
        if not o or o["type"] not in TYPES_SUIVIS or o.get("statut") in ("archive", "clos", "resolu"):
            continue
        touches.append(i)
        if not (o.get("prochaine_action") and o.get("prochaine_date")):
            manques.append({"id": i, "probleme": "sans prochaine action datée", "correction": f"cerebro update {i} prochaine_action=… prochaine_date=AAAA-MM-JJ"})
        elif o["prochaine_date"] < aujourd:
            manques.append({"id": i, "probleme": f"prochaine action échue ({o['prochaine_date']})", "correction": f"cerebro update {i} prochaine_date=AAAA-MM-JJ (nouvelle échéance)"})
    if not touches:
        return resultat(ETAT_NA, ["aucun dossier touché identifié (client/dossier absents du front matter)"])
    if manques:
        return resultat(ETAT_KO, [f"{len(manques)}/{len(touches)} dossier(s) sans prochaine action valable"], manques)
    return resultat(ETAT_OK, [f"{len(touches)} dossier(s) touché(s), tous avec prochaine action datée"])
