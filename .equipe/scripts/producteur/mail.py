"""Brouillon de mail (§7.1) : texte brut lisible dans Outlook et Gmail, réponse en tête, signature de la maison,
pièces nommées client-objet-date-vN. Sortie : .eml (X-Unsent: 1, s'ouvre comme brouillon dans Outlook) + .txt.
Jamais d'envoi : l'envoi reste le geste de Mustafa."""
import re, mimetypes
from email.message import EmailMessage
from email.utils import formatdate
from pathlib import Path
import mdparse as MD


def texte_brut(blocs):
    out = []
    for b in blocs:
        if b["t"] in ("p", "quote"):
            out.append(MD.texte_brut(b["texte"]))
        elif b["t"] in ("ul", "ol"):  # pas de puces dans une correspondance : phrases liées
            out.append(" ".join(MD.texte_brut(x).rstrip(".") + "." for x in b["items"]))
        elif b["t"] == "table":
            out.append("\n".join("  ".join(MD.texte_brut(c) for c in r) for r in [b["entete"]] + b["lignes"]))
    return "\n\n".join(x for x in out if x.strip())


def signature(d):
    i = d["identite"]
    lignes = [i.get("signature") or "", i.get("raison_sociale") or "", i.get("adresse") or ""]
    return "\n".join(l for l in lignes if l and not l.startswith("["))


def rendre(meta, blocs, dest_base, d, pieces=()):
    corps = texte_brut(blocs)
    if meta.get("salutation"):
        corps = meta["salutation"] + "\n\n" + corps
    if meta.get("formule"):
        corps += "\n\n" + meta["formule"]
    corps += "\n\n" + signature(d)
    if pieces:
        corps += "\n\n" + ("Pièces jointes" if meta.get("langue", "fr") == "fr" else "Attachments") + " :\n" + "\n".join(Path(p).name for p in pieces)
    msg = EmailMessage()
    msg["Subject"] = MD.texte_brut(meta.get("objet_mail") or meta.get("titre", ""))
    if meta.get("a"):
        msg["To"] = meta["a"]
    if meta.get("cc"):
        msg["Cc"] = meta["cc"]
    msg["Date"] = formatdate(localtime=True)
    msg["X-Unsent"] = "1"
    msg["Content-Language"] = {"fr": "fr-CH", "de": "de-CH", "it": "it-CH", "en": "en-GB"}.get(meta.get("langue", "fr"), "fr-CH")
    msg.set_content(corps, charset="utf-8")
    for p in pieces:
        p = Path(p)
        if p.exists():
            typ = (mimetypes.guess_type(p.name)[0] or "application/octet-stream").split("/")
            msg.add_attachment(p.read_bytes(), maintype=typ[0], subtype=typ[1], filename=p.name)
    eml = Path(str(dest_base) + ".eml")
    eml.write_bytes(bytes(msg))
    txt = Path(str(dest_base) + ".txt")
    txt.write_text(f"Objet : {msg['Subject']}\n\n{corps}\n", encoding="utf-8")
    return eml, txt
