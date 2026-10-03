#!/usr/bin/env python3
"""Lecture des fichiers Outlook .msg (§6.4, écart 8) avec extract-msg (GPL-3.0, usage interne local, rien ne sort du poste).
Rend l'en-tête (expéditeur, destinataires, date, objet), le corps texte et les noms des pièces jointes ; les pièces
sont écrites dans le dossier d'archive indiqué (hors git) pour être ingérées comme documents liés."""
import re
from pathlib import Path


def _nom_sur(nom, i):
    nom = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (nom or "").strip()) or f"piece-{i}"
    return nom[:120]


def lire_msg(chemin, dossier_pieces=None):
    """→ (texte, [chemins des pièces écrites]) ; lève une exception si le fichier est illisible"""
    import extract_msg
    m = extract_msg.openMsg(str(chemin))
    try:
        corps = m.body or ""
        if not corps.strip():
            h = m.htmlBody or b""
            h = h.decode("utf-8", "ignore") if isinstance(h, bytes) else str(h)
            corps = re.sub(r"\s+\n", "\n", re.sub(r"<[^>]+>", " ", h))
        noms, ecrites = [], []
        for i, a in enumerate(m.attachments, 1):
            nom = _nom_sur(getattr(a, "longFilename", None) or getattr(a, "shortFilename", None) or a.getFilename(), i)
            noms.append(nom)
            if dossier_pieces is None:
                continue
            d = Path(dossier_pieces)
            d.mkdir(parents=True, exist_ok=True)
            data = a.data
            if isinstance(data, (bytes, bytearray)):
                cible = d / nom
                k = 2
                while cible.exists():
                    cible = d / f"{Path(nom).stem} ({k}){Path(nom).suffix}"; k += 1
                cible.write_bytes(bytes(data))
                ecrites.append(cible)
            else:  # message joint dans le message : enregistré tel quel en .msg
                try:
                    a.save(customPath=str(d), extractEmbedded=True)
                    ecrites += [p for p in d.iterdir() if p.suffix.lower() == ".msg" and p not in ecrites]
                except Exception:
                    pass
        def adr(x):
            return str(x or "").strip() or "-"
        date = m.date.isoformat() if hasattr(m.date, "isoformat") else adr(m.date)
        tete = (f"De: {adr(m.sender)}\nÀ: {adr(m.to)}\n" + (f"Cc: {adr(m.cc)}\n" if m.cc else "")
                + f"Date: {date}\nObjet: {adr(m.subject)}\nPièces: {', '.join(noms) or '-'}\n\n")
        return tete + corps.strip(), ecrites
    finally:
        try:
            m.close()
        except Exception:
            pass
