"""Porte (c) typographie suisse par langue (§7.3) avec correction automatique proposée.
FR : insécables avant ; : ! ? et dans « » ; DE : «…» suisses, ß → ss ; IT : «…» ; EN : “…”.
Toutes langues : montants CHF 1'234.50, dates en toutes lettres, points de suspension."""
import re
from gates_common import resultat, ETAT_OK, ETAT_KO, transformer_md

NBSP = " "
MOIS = {
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"],
    "it": ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
}
GUILL = {"fr": ("«" + NBSP, NBSP + "»"), "de": ("«", "»"), "it": ("«", "»"), "en": ("“", "”")}
PROTEGE = re.compile(r"(`[^`]*`|https?://\S+|www\.\S+|\b[\w.+-]+@[\w-]+\.[\w.]+\b|\[\^?[^\]]*\]\([^)]*\)|\b(?:BIB|DOC|GAB|SK|CAP|LIV|[A-Z]{1,4})-\d{3,5}\b|\{\{[^}]*\}\})")
SUFFIXE_ECHELLE = re.compile(r"^\s*(mio|mia|mrd|millions?|milliards?|Mio\.?|Mrd\.?|Mia\.?|k\b)", re.I)


def format_montant(entier, dec, sep="'"):
    entier = re.sub(r"[^\d]", "", entier)
    if not entier:
        return None
    n = int(entier)
    s = f"{n:,}".replace(",", sep)
    d = (dec or "")
    d = (d + "00")[:2]
    return f"{s}.{d}"


def _montants(t, corr):
    def rep_avant(m):
        if SUFFIXE_ECHELLE.match(t[m.end():m.end() + 12]):
            return m.group(0)
        suffixe_tiret = re.match(r"^\.[-–—]", t[m.end():m.end() + 2] or "")
        dec = m.group(3)
        if suffixe_tiret and not dec:
            v = format_montant(m.group(2), "")
            nv = f"CHF{NBSP}{v.split('.')[0]}" if v else m.group(0)
        else:
            v = format_montant(m.group(2), dec)
            nv = f"CHF{NBSP}{v}" if v else m.group(0)
        if nv != m.group(0):
            corr.append({"motif": "montant", "avant": m.group(0), "apres": nv})
        return nv
    t = re.sub(r"\b(CHF|Fr\.|SFr\.)\s*(\d{1,3}(?:['’   ]\d{3})+|\d+)(?:[.,](\d{1,2}))?(?![\d'’])", rep_avant, t)

    def rep_apres(m):
        if SUFFIXE_ECHELLE.match(m.group(0)):
            return m.group(0)
        v = format_montant(m.group(1), m.group(2))
        nv = f"CHF{NBSP}{v}" if v else m.group(0)
        corr.append({"motif": "montant", "avant": m.group(0), "apres": nv})
        return nv
    t = re.sub(r"(?<![\w.'’])(\d{1,3}(?:['’]\d{3})+|\d{2,})(?:[.,](\d{1,2}))?\s?CHF\b", rep_apres, t)
    return t


def _dates(t, langue, corr):
    mois = MOIS.get(langue, MOIS["fr"])

    def rep(m):
        a, mo, j = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if not (1 <= mo <= 12 and 1 <= j <= 31):
            return m.group(0)
        if langue == "fr":
            nv = f"{'1er' if j == 1 else j}{NBSP}{mois[mo - 1]} {a}"
        elif langue == "de":
            nv = f"{j}.{NBSP}{mois[mo - 1]} {a}"
        else:
            nv = f"{j}{NBSP}{mois[mo - 1]} {a}"
        corr.append({"motif": "date", "avant": m.group(0), "apres": nv})
        return nv
    t = re.sub(r"(?<![\w/.-])(\d{4})-(\d{2})-(\d{2})(?![\w/-])", rep, t)
    if langue == "fr":
        def rep1(m):
            nv = f"1er{NBSP}{m.group(1)}"
            corr.append({"motif": "date", "avant": m.group(0), "apres": nv}); return nv
        t = re.sub(r"(?<!\d)\b1\s(" + "|".join(mois) + r")\b", rep1, t)
    return t


def _guillemets(t, langue, corr):
    o, f = GUILL.get(langue, GUILL["fr"])

    def rep(m):
        nv = f"{o}{m.group(1).strip()}{f}"
        if nv != m.group(0):
            corr.append({"motif": "guillemets", "avant": m.group(0), "apres": nv})
        return nv
    t = re.sub(r'"([^"\n]{1,300})"', rep, t)
    if langue != "en":
        t = re.sub(r"[“„]([^”“\n]{1,300})[”“]", rep, t)
    if langue == "fr":  # espaces insécables à l'intérieur de « »
        t2 = re.sub(r"«[  ]?(?=\S)", "«" + NBSP, t)
        t2 = re.sub(r"(?<=\S)[  ]?»", NBSP + "»", t2)
        if t2 != t:
            corr.append({"motif": "insécable guillemets", "avant": "« x »", "apres": "« x »"})
        t = t2
    elif langue in ("de", "it"):
        t2 = re.sub(r"«[\s ]+", "«", t)
        t2 = re.sub(r"[\s ]+»", "»", t2)
        if t2 != t:
            corr.append({"motif": "guillemets suisses sans espace", "avant": "« x »", "apres": "«x»"})
        t = t2
    return t


def _ponctuation(t, langue, corr):
    if langue == "fr":
        def rep(m):
            nv = m.group(1) + NBSP + m.group(2)
            corr.append({"motif": "insécable avant " + m.group(2)[0], "avant": m.group(0), "apres": nv})
            return nv
        # ; ! ? : précédés d'un mot, suivis d'une espace ou d'une fin (exclut 14:30, URL, émoticônes)
        t = re.sub(r"([\w»)\]’'%.…])[  ]?([;:!?]+)(?=\s|$|\*|\))", rep, t)
    else:
        def rep2(m):
            corr.append({"motif": "espace avant ponctuation", "avant": m.group(0), "apres": m.group(1) + m.group(2)})
            return m.group(1) + m.group(2)
        t = re.sub(r"([\w»”)\]%])[ \u00a0\u202f]+([;:!?])(?=\s|$)", rep2, t)
    return t


def corriger_texte(t, langue="fr"):
    """texte → (texte corrigé, liste des corrections) ; segments protégés : code, URL, adresses, identifiants"""
    corr = []
    morceaux = PROTEGE.split(t)
    out = []
    for i, m in enumerate(morceaux):
        if i % 2 == 1 or not m:
            out.append(m or ""); continue
        s = m
        s = s.replace("...", "…") if "..." in s else s
        if langue == "de" and "ß" in s:
            corr.append({"motif": "ß → ss (usage suisse)", "avant": "ß", "apres": "ss"}); s = s.replace("ß", "ss")
        s = _montants(s, corr)
        s = _dates(s, langue, corr)
        s = _guillemets(s, langue, corr)
        s = _ponctuation(s, langue, corr)
        s = re.sub(r"(?<=\S) {2,}(?=\S)", " ", s)
        out.append(s)
    return "".join(out), corr


def corriger_md(raw, langue="fr"):
    tout = []

    def fn(par):
        nv, c = corriger_texte(par, langue)
        tout.extend(c)
        return nv
    return transformer_md(raw, fn), tout


def verifier(doc, ctx=None):
    langue = doc.get("langue", "fr")
    corr = []
    for p in doc.get("paragraphes", []):
        _, c = corriger_texte(p["texte"], langue)
        corr += c
    if not corr:
        return resultat(ETAT_OK, [f"typographie {langue} conforme"])
    resume = {}
    for c in corr:
        resume[c["motif"]] = resume.get(c["motif"], 0) + 1
    return resultat(ETAT_KO, [f"{k} : {v}" for k, v in resume.items()], corr[:40], automatique=True)
