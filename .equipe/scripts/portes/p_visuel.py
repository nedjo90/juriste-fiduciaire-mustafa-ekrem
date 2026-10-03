"""Porte (h) contrôle visuel (§7.3) : rendu PDF → PNG par page (Word/PowerPoint du poste via office.py, ou PDF fourni, + pdftoppm), détection simple
des débordements (encre dans les marges latérales), titres orphelins en bas de page (pdftotext), tableaux et
images plus larges que la zone de texte (analyse docx). Les PNG restent dans .equipe/run/rendus/ pour le
regard de modèle de l'appel adverse groupé. Outil absent → « na » avec réserve, jamais un blocage."""
import re, shutil, subprocess, tempfile
from pathlib import Path
from commun_portes import resultat, ETAT_OK, ETAT_KO, ETAT_NA, design, pdf_texte
import commun as C

DPI = 50
SEUIL_ENCRE = 200      # niveau de gris en dessous duquel un pixel est « encré »
TOLERANCE_MM = 4       # marge de sécurité avant de parler de débordement


def _docx_largeurs(obj, corr):
    from docx.shared import Emu
    s = obj.sections[0]
    utile = s.page_width - s.left_margin - s.right_margin
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    for i, t in enumerate(obj.tables, 1):
        cols = t._tbl.findall(".//w:tblGrid/w:gridCol", ns)
        larg = sum(int(c.get("{%s}w" % ns["w"]) or 0) for c in cols) * 635  # twips → EMU
        if larg > utile * 1.02:
            corr.append({"objet": f"tableau {i}", "probleme": f"plus large que la zone de texte ({larg / 36000:.0f} mm > {utile / 36000:.0f} mm)", "correction": "réduire les colonnes ou passer en paysage"})
        n = len(t.rows)
        if n > 12:
            tr = t.rows[0]._tr.xml
            if "tblHeader" not in tr:
                corr.append({"objet": f"tableau {i}", "probleme": f"{n} lignes sans en-tête répété : coupure illisible", "correction": "répéter l'en-tête (style de la maison)"})
    for shp in obj.inline_shapes:
        if shp.width and shp.width > utile * 1.01:
            corr.append({"objet": "image", "probleme": "image plus large que la zone de texte", "correction": "redimensionner à la largeur utile"})


def _marges_png(pngs, d, corr):
    try:
        from PIL import Image
    except Exception:
        return False
    g = d.get("grille", {}).get("marges_mm", {"gauche": 25, "droite": 22})
    for n, f in enumerate(pngs, 1):
        im = Image.open(f).convert("L")
        W, H = im.size
        px_mm = W / 210.0
        gl = int((g["gauche"] - TOLERANCE_MM) * px_mm)
        dr = int((g["droite"] - TOLERANCE_MM) * px_mm)
        for nom, box in (("gauche", (0, 0, max(1, gl), H)), ("droite", (W - max(1, dr), 0, W, H))):
            zone = im.crop(box)
            hist = zone.histogram()
            encre = sum(hist[:SEUIL_ENCRE])
            if encre > 0.002 * zone.size[0] * zone.size[1] + 3:
                corr.append({"page": n, "probleme": f"débordement dans la marge {nom}", "correction": "couper la ligne, réduire le tableau ou l'image"})
    return True


def _orphelins(pages_txt, titres, corr):
    tit = [re.sub(r"\s+", " ", t["texte"]).strip().lower() for t in titres if t.get("niveau", 0) >= 1 and len(t["texte"]) > 3]
    for n, page in enumerate(pages_txt[:-1], 1):
        lignes = [l.strip() for l in page.split("\n") if l.strip()]
        lignes = [l for l in lignes if not re.search(r"(Page|Seite|Pagina)\s+\d+\s*/\s*\d+", l)]
        if not lignes:
            continue
        der = re.sub(r"\s+", " ", re.sub(r"^[\d.]+\s*", "", lignes[-1])).lower()
        if any(der == t or (len(der) > 6 and t.startswith(der)) for t in tit):
            corr.append({"page": n, "probleme": f"titre orphelin en bas de page : « {lignes[-1][:60]} »", "correction": "le titre doit rester avec son texte (style « lié au suivant »)"})


def _pptx_cadres(chemin, corr):
    """formes hors de la diapositive ou texte trop long pour sa zone (estimation)"""
    from pptx import Presentation
    prs = Presentation(str(chemin))
    W, H = prs.slide_width, prs.slide_height
    for i, s in enumerate(prs.slides, 1):
        for sh in s.shapes:
            if sh.left is None or sh.width is None:
                continue
            if sh.left < 0 or sh.top < 0 or sh.left + sh.width > W * 1.005 or sh.top + sh.height > H * 1.005:
                corr.append({"diapo": i, "probleme": f"forme « {sh.name} » hors de la diapositive", "correction": "replacer dans la zone"})
            if sh.has_text_frame:
                n = len(sh.text_frame.text)
                capacite = (sh.width / 914400 * 2.54) * (sh.height / 914400 * 2.54) * 6  # ~6 caractères par cm² en 18-20 pt
                if n > capacite > 0:
                    corr.append({"diapo": i, "probleme": f"texte probablement trop long pour « {sh.name} » ({n} car.)", "correction": "raccourcir ou scinder la diapositive"})


def rendre_png(pdf, dest):
    exe = shutil.which("pdftoppm")
    if not exe:
        return []
    dest.mkdir(parents=True, exist_ok=True)
    for old in dest.glob("page-*.png"):
        old.unlink()
    try:
        subprocess.run([exe, "-r", str(DPI), "-png", str(pdf), str(dest / "page")], capture_output=True, timeout=120)
    except Exception:
        return []
    return sorted(dest.glob("page-*.png"))


def verifier(doc, ctx=None):
    ctx = ctx or {}
    d = design()
    p = Path(doc["chemin"])
    corr, det, reserves = [], [], 0
    if doc.get("format") == "xlsx":
        return resultat(ETAT_NA, ["tableur : pas de contrôle de mise en page"])
    if doc.get("format") == "docx" and doc.get("objet") is not None:
        _docx_largeurs(doc["objet"], corr)
    if doc.get("format") == "pptx":
        try:
            _pptx_cadres(p, corr)
        except Exception as e:
            det.append(f"analyse des diapositives partielle ({e.__class__.__name__})")
    pdf = ctx.get("pdf")
    if not pdf and doc.get("format") == "pdf":
        pdf = p
    tmp = None
    if not pdf and doc.get("format") in ("docx", "pptx", "xlsx"):
        tmp = Path(tempfile.mkdtemp(prefix="portes-"))
        pdf = C.vers_pdf(p, tmp)
    if not pdf or not Path(pdf).exists():
        det.append("rendu PDF impossible (Word/PowerPoint indisponibles sur ce poste) : contrôle visuel limité à l'analyse du document")
        reserves += 1
    else:
        dest = C.EQ / "run" / "rendus" / C.slug(p.stem, 60)
        pngs = rendre_png(pdf, dest)
        ctx["pages"] = len(pngs) or ctx.get("pages")
        if pngs and doc.get("format") in ("docx", "pdf"):  # marges A4 de la maison
            _marges_png(pngs, d, corr)
            det.append(f"{len(pngs)} page(s) rendue(s) en images ({C.EQ.name}/run/rendus/{dest.name})")
        else:
            det.append("pdftoppm absent : pas d'images de contrôle"); reserves += 1
        pages_txt = pdf_texte(pdf, par_page=True)
        if pages_txt:
            ctx["pages"] = ctx.get("pages") or len([x for x in pages_txt if x.strip()])
            _orphelins(pages_txt, doc.get("titres", []), corr)
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    if not det and not corr:
        return resultat(ETAT_NA, ["format sans rendu visuel"])
    return resultat(ETAT_KO if corr else ETAT_OK, det, corr, reserves=reserves, pages=ctx.get("pages"))
