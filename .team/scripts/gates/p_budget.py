"""Porte (i) budget / efficience (§7.5, §7.6) : longueur, tokens estimés, résumé exécutif ≤ une page."""
from gates_common import resultat, ETAT_OK, ETAT_KO, design, section_alias

CAR_PAR_TOKEN = 3.6  # FR/DE/IT ; estimation sans appel de modèle


def verifier(doc, ctx=None):
    d = design()
    typ = doc.get("type") or "note"
    conf = (d.get("livrables") or {}).get(typ, {})
    budget = conf.get("budget_caracteres")
    n = len(doc.get("texte", ""))
    tokens = int(n / CAR_PAR_TOKEN)
    det = [f"{n} caractères, ~{tokens} tokens estimés" + (f", budget {budget}" if budget else "")]
    corr = []
    if budget and n > budget:
        corr.append({"probleme": f"longueur {n} > budget {budget}", "correction": "condenser : une idée par paragraphe, renvoyer le détail en annexe"})
    if conf.get("resume_max_caracteres"):
        dedans, lg = False, 0
        for p in doc.get("paragraphes", []):
            if p["style"].startswith("Heading"):
                dedans = section_alias(p["texte"], d) == "resume"
                continue
            if dedans:
                lg += len(p["texte"])
        if lg > conf["resume_max_caracteres"]:
            corr.append({"probleme": f"résumé exécutif {lg} car. > {conf['resume_max_caracteres']} (une page)", "correction": "ramener le résumé à une page"})
        det.append(f"résumé exécutif : {lg} caractères")
    return resultat(ETAT_KO if corr else ETAT_OK, det, corr, caracteres=n, tokens=tokens)
