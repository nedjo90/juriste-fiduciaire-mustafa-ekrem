#!/usr/bin/env python3
"""Relecteur (§6.2) par script : ce qui est vérifiable l'est sans modèle.
Contrôles : termes définis (définis et employés, casse constante) ; renvois internes (ch. / chiffre / section / annexe N
existants) ; chiffres du résumé présents dans le corps ; dates valides ; canton nommé quand le texte traite de droit ou
d'impôt cantonal ; langue conforme ; aucune note interne recopiée (perceptions, hypothèses internes, « entre nous »,
identifiants internes autres que les sources numérotées).
Sortie au format des portes : {etat ok|ko|na, details, corrections}. Jamais bloquant.
Usage : python proofread.py <source.md> [--langue fr] [--type memo]"""
import re, sys, json, datetime as dt, argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "gates"))

DEF_RE = re.compile(r"\((?:ci-après|ci-dessous|ensemble|chacun|chacune)?\s*[:,]?\s*(?:l[ae]s?\s+|l’|l')?[«\"“]\s*([^»\"”]{2,40}?)\s*[»\"”]\s*\)", re.I)
RENVOI_RE = re.compile(r"\b(?:ch\.|chiffre|section|point)\s+(\d+(?:\.\d+)*)", re.I)
ANNEXE_RE = re.compile(r"\bannexe\s+([A-Z0-9]{1,3})\b")
CHF_RE = re.compile(r"CHF\s?[\d'’ .,]+\d")
DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b|\b(\d{4})-(\d{2})-(\d{2})\b")
CANTONAL_RE = re.compile(r"\b(ICC|impôts? cantona|droit cantonal|loi cantonale|LI\b|LIPP|LIPM|LPFisc|administration cantonale|kantonal|Staatssteuer|StG)\b", re.I)
CANTONS_RE = re.compile(r"\b(VD|GE|VS|NE|FR|JU|BE|ZH|TI|BS|BL|AG|LU|SG|ZG|SZ|vaudois\w*|genevois\w*|Vaud|Genève|Valais|Neuchâtel|Fribourg|Jura|Berne|Zurich|Tessin|Zoug|canton d[eu] \w+)\b")
INTERNE_RE = re.compile(r"\[(perception|déclaré par|hypothèse interne|à confirmer)[^\]]*\]|\bentre nous\b|selon lui le", re.I)
ID_INTERNE_RE = re.compile(r"\b(?:C|P|E|D|DOC|DL|N|M|LIV|POS|NOTE|T|RD|DT|CAP|MET)-\d{3,5}\b")


def _corps(raw):
    import mdparse as MD
    meta, corps = MD.front_matter(raw)
    corps = re.sub(r"```.*?```", "", corps, flags=re.S)
    return meta or {}, corps


def _sections(corps):
    """[(titre, niveau, texte)]"""
    out, cur, niv, buf = [], "", 0, []
    for l in corps.split("\n"):
        m = re.match(r"^(#{1,6})\s+(.*)$", l.strip())
        if m:
            out.append((cur, niv, "\n".join(buf))); cur, niv, buf = m.group(2).strip(), len(m.group(1)), []
        else:
            buf.append(l)
    out.append((cur, niv, "\n".join(buf)))
    return out


def relire(source, principal=None, langue=None, type_=None):
    from gates_common import resultat, ETAT_OK, ETAT_KO, ETAT_NA, detecter_langue, section_alias
    if not source or not Path(source).exists():
        return resultat(ETAT_NA, ["source introuvable : relecture impossible"], reserves=1)
    raw = Path(source).read_text(encoding="utf-8")
    meta, corps = _corps(raw)
    langue = (langue or meta.get("langue") or "fr")[:2]
    corr, det = [], []
    if type_ == "mail" or str(meta.get("type")) == "mail":
        return resultat(ETAT_NA, ["mail : lecteur humain intégré à la rédaction"])
    # 1. termes définis
    defs = {m.group(1).strip() for m in DEF_RE.finditer(corps)}
    for t in sorted(defs):
        n = len(re.findall(r"(?<![«\"“])\b" + re.escape(t) + r"\b", corps))
        if n <= 1:
            corr.append({"lieu": f"terme « {t} »", "probleme": "terme défini mais jamais employé ensuite", "correction": "employer le terme défini ou retirer la définition"})
        if t[:1].isupper() and re.search(r"\b" + re.escape(t[:1].lower() + t[1:]) + r"\b", corps) and len(t) > 3:
            corr.append({"lieu": f"terme « {t} »", "probleme": "casse irrégulière du terme défini", "correction": f"écrire toujours « {t} »"})
    det.append(f"{len(defs)} terme(s) défini(s)")
    # 2. renvois internes
    secs = _sections(corps)
    titres = [s[0] for s in secs if s[0]]
    nums = {re.match(r"^(\d+(?:\.\d+)*)", t).group(1) for t in titres if re.match(r"^\d", t)}
    n1 = len([s for s in secs if s[1] == min([x[1] for x in secs if x[1]] or [1])])
    for m in RENVOI_RE.finditer(corps):
        v = m.group(1)
        ok = v in nums if nums else (v.split(".")[0].isdigit() and int(v.split(".")[0]) <= n1)
        if not ok:
            corr.append({"lieu": m.group(0), "probleme": "renvoi interne vers une partie qui n'existe pas", "correction": "corriger le numéro du renvoi"})
    annexes = {m.group(1) for t in titres for m in [re.match(r"(?i)annexe\s+([A-Z0-9]{1,3})", t)] if m}
    for m in ANNEXE_RE.finditer(corps):
        if annexes and m.group(1) not in annexes:
            corr.append({"lieu": m.group(0), "probleme": "annexe citée absente", "correction": "ajouter l'annexe ou corriger le renvoi"})
    # 3. chiffres du résumé présents dans le corps
    resume = " ".join(s[2] for s in secs if section_alias(s[0]) == "resume")
    reste = " ".join(s[2] for s in secs if section_alias(s[0]) != "resume")
    norm = lambda x: re.sub(r"[^\d]", "", x)
    for m in CHF_RE.finditer(resume):
        if norm(m.group(0)) and norm(m.group(0)) not in {norm(x) for x in CHF_RE.findall(reste)}:
            corr.append({"lieu": f"résumé : {m.group(0)}", "probleme": "montant du résumé introuvable dans le corps", "correction": "aligner le résumé sur l'analyse chiffrée"})
    # 4. dates valides
    for m in DATE_RE.finditer(corps):
        try:
            if m.group(3):
                dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            else:
                dt.date(int(m.group(4)), int(m.group(5)), int(m.group(6)))
        except ValueError:
            corr.append({"lieu": m.group(0), "probleme": "date impossible", "correction": "corriger la date"})
    # 5. canton nommé
    if CANTONAL_RE.search(corps) and not (CANTONS_RE.search(corps) or meta.get("canton")):
        corr.append({"lieu": "ensemble", "probleme": "droit ou impôt cantonal traité sans canton nommé", "correction": "nommer le canton (et la commune si utile)"})
    # 6. langue
    lg = detecter_langue(corps)
    if lg != langue:
        corr.append({"lieu": "ensemble", "probleme": f"langue détectée « {lg} » ≠ langue du livrable « {langue} »", "correction": "relecture de langue"})
    # 7. notes internes recopiées
    for m in INTERNE_RE.finditer(corps):
        corr.append({"lieu": m.group(0)[:60], "probleme": "note interne recopiée dans un document sortant", "correction": "reformuler pour le destinataire ou retirer"})
    for i in sorted(set(ID_INTERNE_RE.findall(corps)))[:5]:
        corr.append({"lieu": i, "probleme": "identifiant interne visible dans le livrable", "correction": "remplacer par le nom ou la référence lisible"})
    det.append(f"{len(corr)} point(s) de relecture")
    return resultat(ETAT_KO if corr else ETAT_OK, det, corr)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source"); ap.add_argument("--langue"); ap.add_argument("--type")
    a = ap.parse_args()
    print(json.dumps(relire(a.source, langue=a.langue, type_=a.type), ensure_ascii=False))
