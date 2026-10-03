"""Porte (f) contexte (§7.5, §9.4, critère 24) : l'injection du tour qui a produit le livrable reste sous le budget
(≤ 6 000 caractères en delta) et la question courante n'a pas demandé plus de cinq ouvertures (table `ouvertures`).
Tour : ctx["tour"], sinon CEREBRO_TOUR, sinon l'état `tour`. Mesure de l'injection : ctx["injection"] (texte ou taille),
sinon journal `injections.jsonl` du tour, sinon simulation de `brief.context` sur ctx["prompt"] sans toucher l'état."""
import os, json
from commun_portes import resultat, ETAT_OK, ETAT_KO, ETAT_NA
import commun as C

TOUR_MAX = 6000
OUVERTURES_MAX = 5


def _tour(ctx):
    t = ctx.get("tour") or os.environ.get("CEREBRO_TOUR")
    if t:
        return str(t)
    try:
        return str(C.cb()[0].get_etat("tour", "") or "")
    except Exception:
        return ""


def taille_injection(ctx, tour):
    """(caractères, origine) ou (None, raison)"""
    inj = ctx.get("injection")
    if isinstance(inj, int):
        return inj, "mesure fournie"
    if isinstance(inj, str):
        return len(inj), "texte fourni"
    j = C.EQ / "cerveau" / "journal" / "injections.jsonl"
    if j.exists() and tour:
        try:
            der = None
            for l in j.read_text(encoding="utf-8").splitlines()[-500:]:
                r = json.loads(l)
                if str(r.get("tour")) == tour:
                    der = r
            if der and der.get("caracteres") is not None:
                return int(der["caracteres"]), "journal des injections"
        except Exception:
            pass
    if ctx.get("prompt"):
        return simuler(ctx["prompt"]), "simulation de l'injection"
    return None, "injection du tour non journalisée"


def simuler(prompt):
    """taille de l'injection que produirait `prompt`, état (tour, déjà injectés) restauré ensuite"""
    core = C.cb()[0]
    from cb import brief as B
    t, inj = core.get_etat("tour", 0), core.get_etat("injectes", {})
    try:
        return len(B.context(prompt) or "")
    finally:
        core.set_etat("tour", t)
        core.set_etat("injectes", inj)


def ouvertures(tour):
    core = C.cb()[0]
    rows = core.db().execute("SELECT acteur, COUNT(*) n FROM ouvertures WHERE tour=? GROUP BY acteur", (str(tour),)).fetchall()
    par = {r["acteur"] or "?": r["n"] for r in rows}
    return sum(par.values()), par


def verifier(doc, ctx=None):
    ctx = ctx or {}
    try:
        C.cb()
    except Exception:
        return resultat(ETAT_NA, ["cerebro indisponible : contexte non vérifié"], reserves=1)
    tour = _tour(ctx)
    det, corr, mesure = [], [], 0
    n, origine = taille_injection(ctx, tour)
    if n is None:
        det.append(f"injection : {origine} (hook UserPromptSubmit : journaliser la taille)")
    else:
        mesure += 1
        det.append(f"injection du tour {tour or '?'} : {n} car. ({origine}), budget {TOUR_MAX}")
        if n > TOUR_MAX:
            corr.append({"probleme": f"injection {n} car. > {TOUR_MAX}", "correction": "réduire le bloc injecté : delta seulement, voisins limités (brief.context)"})
    if tour:
        tot, par = ouvertures(tour)
        mesure += 1
        det.append(f"ouvertures du tour {tour} : {tot} (" + ", ".join(f"{k} {v}" for k, v in sorted(par.items())) + f"), plafond {OUVERTURES_MAX}" if par else f"ouvertures du tour {tour} : 0")
        if tot > OUVERTURES_MAX:
            corr.append({"probleme": f"{tot} ouvertures pour une question (plafond {OUVERTURES_MAX})" + (f", dont {par['hors-cli']} hors CLI" if par.get("hors-cli") else ""),
                         "correction": "cibler : find → summary → open --section ; réutiliser l'existant ; rôle à réviser si répété"})
    if not mesure:
        return resultat(ETAT_NA, det, reserves=1)
    return resultat(ETAT_KO if corr else ETAT_OK, det, corr, tour=tour)
