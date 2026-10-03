"""Porte (b) sources (§7.5, loi 7) : toute affirmation de droit ou de chiffre légal porte un identifiant de source
(BIB-…) ou une référence officielle datée ; sinon ⚠ est inséré (correction automatique). Jamais bloquante."""
import re
from commun_portes import resultat, ETAT_OK, ETAT_KO, phrases, transformer_md

LOIS = r"LIFD|LHID|LTVA|LIA|LT|LP|LPP|LAVS|LAA|LACI|LAMal|LEI|LBA|LDIP|LFus|LPD|LSA|CO|CC|CP|Cst\.?|ORC|OIA|OLTVA|LI|LIPP|LIPM|LICD|LDTR|LFAIE|DBG|StHG|MWSTG|VStG|StG|SchKG|OR|ZGB|BVG|AHVG|FusG|GwG|DSG|BewG|HRegV|LIVA|LIPI|TUIR|IVA|LImp"
MOTIFS = [
    (r"\b(?:art|Art|artt)\.\s*\d+", "article"),
    (r"\b(?:al|Abs|cpv|para)\.\s*\d+", "alinéa"),
    (r"(?<![\w-])(?:" + LOIS + r")(?![\w-])", "loi"),
    (r"\b\d+(?:[.,]\d+)?\s?%", "taux"),
    (r"\b(?:selon|en vertu de|conformément à) la loi\b|\bla loi (?:prévoit|dispose|impose)\b|\bgemäss Gesetz\b|\blaut Gesetz\b|\bsecondo la legge\b|\bai sensi della legge\b|\bunder the (?:law|act)\b", "renvoi à la loi"),
    (r"\b(?i:délais?|frist(?:en)?|termine|deadline|time limit)\b[^.;]{0,50}?\b\d+\s?(?i:jours|mois|ans|Tage|Monate|Jahre|giorni|mesi|anni|days|months|years)\b", "délai"),
    (r"\b(?:Tribunal fédéral|Bundesgericht|Tribunale federale|Federal Supreme Court)\b", "jurisprudence"),
    (r"\bsection\s+\d+", "section"),
]
SOURCE = [
    r"\bBIB-\d{3,5}\b",
    r"\b(?:état au|état le|en vigueur (?:au|depuis le|dès le)|version (?:du|au)|Stand (?:am|vom)|in Kraft (?:seit|ab)|stato (?:al|il)|in vigore dal|as (?:at|of)|in force (?:since|from))\s+[\w.  ]{0,20}\d{4}",
    r"\b(?:ATF|BGE|DTF)\s+\d{2,3}\s+[IVX]+[a-z]?\s+\d+",
    r"\b\d[A-Z]_\d+/\d{4}\b",
    r"\b(?:RS|SR)\s?\d{3}(?:\.\d+)*\b[^.]{0,60}\b\d{1,2}[./]\d{1,2}[./]\d{4}",
    r"\[\d+\]",   # renvoi numéroté produit par le producteur depuis un BIB-… (annexe des sources)
]
_M = [(re.compile(p), n) for p, n in MOTIFS]
_S = [re.compile(p, re.I) for p in SOURCE]
MARQUE = "⚠"


def analyser_phrase(ph):
    motifs = sorted({n for r, n in _M if r.search(ph)})
    if not motifs:
        return None
    if MARQUE in ph:
        return {"phrase": ph, "motifs": motifs, "etat": "marquee"}
    if any(r.search(ph) for r in _S):
        return {"phrase": ph, "motifs": motifs, "etat": "sourcee"}
    return {"phrase": ph, "motifs": motifs, "etat": "non_sourcee"}


def marquer_paragraphe(par):
    """insère ⚠ avant la ponctuation finale de chaque phrase de droit non sourcée"""
    if not par.strip():
        return par, 0
    n = 0
    out = []
    # on travaille phrase par phrase en conservant le texte d'origine (retours à la ligne compris)
    reste = par
    for ph in phrases(par):
        a = analyser_phrase(ph)
        if a and a["etat"] == "non_sourcee":
            m = re.search(r"([.!?…:;]*)\s*$", ph)
            nv = ph[:m.start()].rstrip() + f" {MARQUE}" + m.group(1)
            # remplacer la première occurrence tolérante aux espaces
            motif = re.escape(ph).replace(r"\ ", r"\s+")
            reste, k = re.subn(motif, lambda _: nv, reste, count=1)
            n += k
    return reste, n


def corriger_md(raw):
    tot = [0]

    def fn(par):
        nv, k = marquer_paragraphe(par)
        tot[0] += k
        return nv
    return transformer_md(raw, fn, titres=False, sauter_sections=("sources",)), tot[0]


def verifier(doc, ctx=None):
    from commun_portes import section_alias
    stats = {"sourcee": 0, "marquee": 0, "non_sourcee": 0}
    manquants = []
    dans_sources = False
    for p in doc.get("paragraphes", []):
        if p["style"].startswith("Heading"):
            dans_sources = section_alias(p["texte"]) == "sources"
            continue
        if dans_sources or p["style"] in ("titre",):
            continue
        for ph in phrases(p["texte"]):
            a = analyser_phrase(ph)
            if a:
                stats[a["etat"]] += 1
                if a["etat"] == "non_sourcee":
                    manquants.append(a)
    det = [f"affirmations de droit : {sum(stats.values())} (sourcées {stats['sourcee']}, marquées ⚠ {stats['marquee']}, sans source {stats['non_sourcee']})"]
    if stats["non_sourcee"]:
        corr = [{"phrase": a["phrase"][:220], "motifs": a["motifs"], "correction": f"ajouter BIB-… (cerebro law article …) ou insérer {MARQUE}"} for a in manquants[:30]]
        return resultat(ETAT_KO, det, corr, automatique=True, reserves=stats["marquee"] + stats["non_sourcee"])
    return resultat(ETAT_OK, det, reserves=stats["marquee"])
