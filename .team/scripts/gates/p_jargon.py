"""Porte (e) règle zéro (§4.1) : aucun vocabulaire de mécanique dans un texte destiné à Mustafa.
S'applique quand le destinataire est Mustafa (front matter `destinataire: mustafa`) ou pour les types réponse/brief/note interne."""
import re
from gates_common import resultat, ETAT_OK, ETAT_KO, ETAT_NA

JARGON = [
    (r"\bfichiers?\b", "« le document »"), (r"\bchemins?\b(?! de fer)", "(ne rien dire)"), (r"\br[ée]pertoires?\b", "(ne rien dire)"),
    (r"\bformats?\s+(?:de fichier|docx|pdf|xlsx|json|yaml|md)\b", "« le document Word / PDF »"), (r"\boutils?\b", "(décrire ce qui est fait)"),
    (r"\bskills?\b", "(ne rien dire)"), (r"\bplugins?\b", "(ne rien dire)"), (r"\b(?:sous-)?agents?\b", "« l'équipe »"),
    (r"\bhooks?\b", "(ne rien dire)"), (r"\bMCP\b", "(ne rien dire)"), (r"\bconnecteurs?\b", "« la liaison avec votre messagerie »"),
    (r"\bAPI\b", "(ne rien dire)"), (r"\bcl[ée]s? (?:API|d['’]accès)\b", "(ne rien dire)"), (r"\btokens?\b", "« je ralentis un peu aujourd'hui »"),
    (r"\bpermissions?\b|\bautorisations? d['’]accès\b", "(ne rien dire)"), (r"\bconfiguration\b|\bconfig\b|\bparam[ée]trage\b", "(ne rien dire)"),
    (r"\bmod[èe]les? (?:de langage|d['’]IA|Claude|Opus|Sonnet|Haiku)\b", "(ne rien dire)"), (r"\bcontexte (?:du modèle|de session)\b|\bfen[êe]tre de contexte\b", "(ne rien dire)"),
    (r"\bgit\b|\bcommits?\b|\bpush\b|\bd[ée]p[ôo]t git\b", "(ne rien dire)"), (r"\bscripts?\b", "(ne rien dire)"), (r"\bterminal\b|\bconsole\b|\bligne de commande\b", "(ne rien dire)"),
    (r"\bbase de donn[ée]es\b|\bSQLite\b|\btable SQL\b", "« vos dossiers »"), (r"\blogs?\b|\bjournaux techniques\b", "(ne rien dire)"),
    (r"\berreurs? (?:technique|système|python|d['’]exécution)\b|\bexception\b|\bbug\b", "(ne rien dire ; l'équipe s'en occupe)"),
    (r"\bversions? (?:de|du) (?:logiciel|Claude Code|Python)\b", "(ne rien dire)"), (r"\bcerebro\b", "« vos dossiers »"),
    (r"`[^`]+`", "(retirer le code)"), (r"(?:[A-Za-z]:\\|\.team/|\.claude/|~/)[\w/\\.-]*", "(retirer le chemin)"),
    (r"\b[\w-]+\.(?:py|md|json|ya?ml|db|jsonl|ps1|sh|cmd)\b", "(retirer le nom technique)"),
    (r"\b(?:DOC|POS|GAB|SK|CAP|LIV|ROLE|MET|INC|BIB|T|Q)-\d{3,5}\b", "(nommer l'objet en clair)"),
]
POUR_MUSTAFA = {"reponse", "brief", "note-interne", "note_mustafa", "message"}


def concerne(doc):
    dest = str(doc.get("meta", {}).get("destinataire", "")).lower()
    return "mustafa" in dest or doc.get("type") in POUR_MUSTAFA


def analyser(texte):
    out = []
    for pat, remp in JARGON:
        for m in re.finditer(pat, texte, re.I if not pat.startswith(r"\bMCP") else 0):
            out.append({"terme": m.group(0)[:60], "remplacement": remp})
    return out


def verifier(doc, ctx=None):
    if not concerne(doc):
        return resultat(ETAT_NA, ["texte non destiné à Mustafa"])
    c = analyser(doc.get("texte", ""))
    if not c:
        return resultat(ETAT_OK, ["aucun terme de mécanique"])
    return resultat(ETAT_KO, [f"{len(c)} terme(s) de mécanique : " + ", ".join(sorted({x['terme'] for x in c})[:12])], c[:30])
