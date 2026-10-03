"""Gabarit PDF de la maison (reportlab) : repli quand Word/PowerPoint sont absents du poste, et rapports PDF natifs.
Page de titre, en-tête raison sociale | Confidentiel, pied « Version · État du droit au … » | Page x / y."""
import re
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle, PageBreak,
                                ListFlowable, ListItem, Image, KeepTogether)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import design as D
import mdparse as MD

_POLICES = {}


def polices(d):
    if _POLICES:
        return _POLICES
    ttf = d["typographie"]["ttf"]
    res = {"corps": "Helvetica", "gras": "Helvetica-Bold", "italique": "Helvetica-Oblique", "titres": "Times-Bold"}
    for cle, nom in (("corps", "MaisonCorps"), ("corps_gras", "MaisonCorpsGras"), ("corps_italique", "MaisonCorpsItal"), ("titres", "MaisonTitres")):
        f = D.premier_fichier([p for p in ttf.get(cle, []) if not p.lower().endswith(".ttc")])
        if f:
            try:
                pdfmetrics.registerFont(TTFont(nom, f))
                res[{"corps": "corps", "corps_gras": "gras", "corps_italique": "italique", "titres": "titres"}[cle]] = nom
            except Exception:
                pass
    sym = D.premier_fichier(d["typographie"]["ttf"].get("symboles", []))
    if sym:
        try:
            pdfmetrics.registerFont(TTFont("MaisonSymboles", sym)); res["symboles"] = "MaisonSymboles"
        except Exception:
            pass
    try:
        from reportlab.lib.fonts import addMapping
        addMapping(res["corps"], 0, 0, res["corps"]); addMapping(res["corps"], 1, 0, res["gras"])
        addMapping(res["corps"], 0, 1, res["italique"]); addMapping(res["corps"], 1, 1, res["gras"])
    except Exception:
        pass
    _POLICES.update(res)
    return res


def styles(d):
    f = polices(d)
    c = lambda n: colors.HexColor(D.couleur(d, n))
    ty = d["typographie"]
    base = ParagraphStyle("corps", fontName=f["corps"], fontSize=ty["corps"]["taille"], leading=ty["corps"]["taille"] * 1.38,
                          textColor=c("encre"), spaceAfter=ty["corps"]["apres"])
    st = {"corps": base,
          "titre": ParagraphStyle("titre", parent=base, fontName=f["titres"], fontSize=ty["titre_document"]["taille"], leading=ty["titre_document"]["taille"] * 1.2, textColor=c("primaire"), spaceAfter=10),
          "sous_titre": ParagraphStyle("st", parent=base, fontSize=ty["sous_titre"]["taille"], textColor=c("secondaire"), spaceAfter=18),
          "petit": ParagraphStyle("petit", parent=base, fontSize=8.5, leading=11, textColor=c("discret")),
          "legende": ParagraphStyle("leg", parent=base, fontName=f["italique"], fontSize=d["legendes"]["taille"], textColor=c("secondaire")),
          "reserve": ParagraphStyle("res", parent=base, textColor=c("alerte")),
          "citation": ParagraphStyle("cit", parent=base, leftIndent=8 * mm, textColor=c("secondaire")),
          "encadre": ParagraphStyle("enc", parent=base, backColor=c("fond_clair"), borderPadding=6, leftIndent=4 * mm, rightIndent=4 * mm)}
    for i, niv in enumerate(ty["niveaux"], 1):
        st[f"h{i}"] = ParagraphStyle(f"h{i}", parent=base, fontName=f["titres"], fontSize=niv["taille"], leading=niv["taille"] * 1.25,
                                     textColor=c("primaire"), spaceBefore=niv["avant"], spaceAfter=niv["apres"], keepWithNext=1)
    return st


def _xml(t):
    t = (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\*)\*([^*\s][^*]*)\*(?!\*)", r"<i>\1</i>", t)
    t = re.sub(r"`([^`]+)`", r"<font face='Courier'>\1</font>", t)
    if _POLICES.get("symboles"):
        t = re.sub(r"([\u2600-\u27BF])", r"<font face='MaisonSymboles'>\1</font>", t)
    return t


class _Doc(BaseDocTemplate):
    def __init__(self, fichier, d, meta, **kw):
        g = d["grille"]["marges_mm"]
        super().__init__(str(fichier), pagesize=A4, leftMargin=g["gauche"] * mm, rightMargin=g["droite"] * mm,
                         topMargin=g["haut"] * mm, bottomMargin=g["bas"] * mm, title=meta.get("titre", ""),
                         author=d["identite"]["raison_sociale"], **kw)
        self.d, self.meta = d, meta
        fr = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates([PageTemplate(id="p", frames=[fr], onPage=self._cadre)])
        self._total = None

    def _cadre(self, canv, doc):
        d, m = self.d, self.meta
        f = polices(d)
        canv.saveState()
        canv.setFont(f["corps"], d["entete_pied"]["taille"])
        canv.setFillColor(colors.HexColor(D.couleur(d, "discret")))
        w, h = A4
        y_h = h - d["grille"]["entete_mm"] * mm
        canv.drawString(self.leftMargin, y_h, d["identite"]["raison_sociale"])
        canv.setFillColor(colors.HexColor(D.couleur(d, "primaire")))
        canv.setFont(f["gras"], d["entete_pied"]["taille"])
        canv.drawRightString(w - self.rightMargin, y_h, D.mention_confidentialite(d, m.get("langue", "fr")) if m.get("confidentiel", True) else "")
        canv.setStrokeColor(colors.HexColor(D.couleur(d, "filet"))); canv.setLineWidth(0.5)
        canv.line(self.leftMargin, y_h - 2 * mm, w - self.rightMargin, y_h - 2 * mm)
        canv.setFont(f["corps"], d["entete_pied"]["taille"]); canv.setFillColor(colors.HexColor(D.couleur(d, "discret")))
        y_p = d["grille"]["pied_mm"] * mm
        canv.drawString(self.leftMargin, y_p, m.get("_pied", ""))
        tot = f" / {self._total}" if self._total else ""
        canv.drawRightString(w - self.rightMargin, y_p, f"Page {doc.page}{tot}")
        canv.restoreState()


def construire(fichier, d, meta, histoire):
    """deux passes pour connaître le nombre total de pages (Page x / y)"""
    doc = _Doc(fichier, d, meta)
    doc.build(list(histoire))
    n = doc.page
    doc2 = _Doc(fichier, d, meta); doc2._total = n
    doc2.build(list(histoire))
    return n


def tableau_rl(d, entete, lignes, st, largeur):
    c = lambda n: colors.HexColor(D.couleur(d, n))
    data = [[Paragraph(_xml(x), ParagraphStyle("te", parent=st["corps"], textColor=colors.white, fontName=polices(d)["gras"], fontSize=d["tableaux"]["taille"])) for x in entete]]
    for r in lignes:
        data.append([Paragraph(_xml(x), ParagraphStyle("tc", parent=st["corps"], fontSize=d["tableaux"]["taille"], spaceAfter=0)) for x in r + [""] * (len(entete) - len(r))])
    t = Table(data, colWidths=[largeur / len(entete)] * len(entete), repeatRows=1)
    sty = [("BACKGROUND", (0, 0), (-1, 0), c("primaire")), ("GRID", (0, 0), (-1, -1), 0.4, c("filet")), ("VALIGN", (0, 0), (-1, -1), "TOP")]
    for i in range(2, len(data), 2):
        sty.append(("BACKGROUND", (0, i), (-1, i), c("fond_clair")))
    t.setStyle(TableStyle(sty))
    return t


def histoire_depuis_blocs(d, meta, blocs, page_titre=True, images=None):
    st = styles(d)
    W = A4[0] - (d["grille"]["marges_mm"]["gauche"] + d["grille"]["marges_mm"]["droite"]) * mm
    h = []
    if page_titre:
        h += [Spacer(1, 50 * mm), Paragraph(_xml(meta.get("titre", "")), st["titre"])]
        if meta.get("sous_titre") or meta.get("client_nom"):
            h.append(Paragraph(_xml(meta.get("sous_titre") or meta.get("client_nom")), st["sous_titre"]))
        lignes = [["Date", meta.get("date_affichee", "")], ["État du droit au", meta.get("date_etat_affichee", "")],
                  ["Niveau de confort", meta.get("confort", "")], ["Version", f"v{meta.get('version', 1)}"]]
        h.append(tableau_rl(d, ["Destinataire", meta.get("client_nom", "")], lignes, st, W))
        h.append(PageBreak())
    nums = [0, 0, 0]
    for b in blocs:
        t = b["t"]
        if t == "h":
            n = min(b["niveau"], 3)
            nums[n - 1] += 1
            for k in range(n, 3):
                nums[k] = 0
            num = ".".join(str(x) for x in nums[:n]) + ("." if n == 1 else "")
            sans = b.get("sans_numero")
            h.append(Paragraph(_xml(b["texte"] if sans else f"{num} {b['texte']}"), st[f"h{n}"]))
        elif t == "p":
            h.append(Paragraph(_xml(b["texte"]), st["reserve"] if "⚠" in b["texte"] and len(b["texte"]) < 200 else st["corps"]))
        elif t == "quote":
            h.append(Paragraph(_xml(b["texte"]), st["citation"]))
        elif t in ("ul", "ol"):
            h.append(ListFlowable([ListItem(Paragraph(_xml(x), st["corps"])) for x in b["items"]],
                                  bulletType="bullet" if t == "ul" else "1", leftIndent=12))
        elif t == "table":
            h.append(tableau_rl(d, b["entete"], b["lignes"], st, W))
            h.append(Spacer(1, 4 * mm))
        elif t == "saut":
            h.append(PageBreak())
        elif t == "image" and Path(b["chemin"]).exists():
            from reportlab.lib.utils import ImageReader
            ir = ImageReader(b["chemin"]); iw, ih = ir.getSize()
            w = min(W, iw); hh = ih * w / iw
            h.append(KeepTogether([Image(b["chemin"], width=w, height=hh), Paragraph(_xml(b.get("legende", "")), st["legende"])]))
    return h


def rendre(fichier, d, meta, blocs):
    return construire(fichier, d, meta, histoire_depuis_blocs(d, meta, blocs))


def specimen(fichier, d):
    meta = {"titre": "Titre-affirmation du rapport", "client_nom": "Destinataire", "date_affichee": "jj mois aaaa",
            "date_etat_affichee": "jj mois aaaa", "confort": "moyen", "version": 1, "_pied": "Version 1 · État du droit au jj mois aaaa"}
    md = """## Résumé exécutif
Conclusion d'abord. Chiffres précis avec leur source (BIB-… ou référence datée).

## Analyse
### Sous-titre numéroté
Une idée par paragraphe. Phrases courtes mêlées de plus longues.

| Option | Coût | Délai |
|---|---|---|
| A | CHF 1'234.50 | 30 jours |
| B | CHF 12'000.— | 60 jours |

> Citation d'une source, avec sa date.

⚠ Affirmation non sourcée : marquée jusqu'à vérification.
"""
    _, bl = MD.parse(md)
    return rendre(fichier, d, meta, bl)
