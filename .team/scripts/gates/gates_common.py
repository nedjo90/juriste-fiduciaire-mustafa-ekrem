"""Chargement d'un livrable pour les portes (§7.5) : markdown structuré, docx, pptx, xlsx, pdf, eml, txt.
Renvoie un dict {format, chemin, meta, blocs, texte, paragraphes, titres, langue, type}. Jamais d'exception : au pire texte vide."""
import sys, re, json, subprocess, shutil, email
from email import policy
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "producer"))
import common as C  # noqa: E402
import mdparse as MD  # noqa: E402

ETAT_OK, ETAT_KO, ETAT_NA = "ok", "ko", "na"

STOP = {
    "fr": {"le", "la", "les", "des", "est", "une", "dans", "pour", "que", "qui", "pas", "sur", "avec", "vous", "nous", "aux", "du", "au", "cette", "sont"},
    "de": {"der", "die", "das", "und", "ist", "nicht", "mit", "für", "auf", "den", "dem", "ein", "eine", "sie", "wir", "von", "zu", "im", "sich", "werden"},
    "it": {"il", "lo", "gli", "che", "non", "per", "una", "sono", "della", "nel", "con", "del", "alla", "questo", "anche", "come", "più", "essere", "delle", "dei"},
    "en": {"the", "and", "is", "of", "to", "in", "that", "for", "it", "with", "as", "on", "are", "this", "be", "by", "not", "or", "we", "you"},
}


def detecter_langue(texte):
    mots = re.findall(r"[a-zàâäéèêëïîôöùûüçßìòó]+", (texte or "").lower())[:3000]
    if not mots:
        return "fr"
    sc = {l: sum(1 for m in mots if m in s) for l, s in STOP.items()}
    return max(sc, key=sc.get)


def phrases(texte):
    """découpage en phrases tolérant aux abréviations juridiques (art. 5, al. 2, let. a, ch. 3, p. ex.)"""
    t = re.sub(r"\s+", " ", texte or "").strip()
    if not t:
        return []
    parts = re.split(r"(?<=[.!?…])\s+(?=[«\"“„(A-ZÀ-ÖØ-Ý0-9])", t)
    out, buf = [], ""
    for p in parts:
        buf = f"{buf} {p}".strip() if buf else p
        if re.search(r"\b(art|al|let|ch|cf|p\. ex|n|no|Abs|Ziff|lit|cpv|cfr|ss|al\.?\s?\d+|M|Mme|Dr|Me|St|Nr|vgl|bzw|z\.B|s|para)\.$", buf):
            continue
        out.append(buf); buf = ""
    if buf:
        out.append(buf)
    return out


def _docx(p):
    from docx import Document
    doc = Document(str(p))
    paras, titres = [], []
    for para in doc.paragraphs:
        s = para.style.name if para.style is not None else ""
        if para.text.strip():
            paras.append({"texte": para.text, "style": s})
            if s.startswith("Heading") or s == "Title":
                titres.append({"texte": para.text.strip(), "niveau": int(s.split()[-1]) if s.split()[-1].isdigit() else 0})
    for t in doc.tables:
        for row in t.rows:
            seen = set()
            for c in row.cells:
                if id(c._tc) in seen:
                    continue
                seen.add(id(c._tc))
                if c.text.strip():
                    paras.append({"texte": c.text, "style": "tableau"})
    cp = doc.core_properties
    meta = {"type": cp.category or "", "langue": cp.language or "", "titre": cp.title or "", "version": cp.version or "",
            "liens": [x for x in re.split(r"[ ,;]+", cp.keywords or "") if x]}
    return doc, paras, titres, meta


def _pptx(p):
    from pptx import Presentation
    prs = Presentation(str(p))
    paras, titres, diapos = [], [], []
    for i, s in enumerate(prs.slides, 1):
        titre = s.shapes.title.text_frame.text.strip() if s.shapes.title is not None and s.shapes.title.has_text_frame else ""
        puces = []
        for sh in s.shapes:
            if sh.has_text_frame and sh != s.shapes.title:
                for para in sh.text_frame.paragraphs:
                    t = "".join(r.text for r in para.runs).strip()
                    if t:
                        puces.append(t)
        notes = s.notes_slide.notes_text_frame.text.strip() if s.has_notes_slide else ""
        diapos.append({"n": i, "titre": titre, "puces": puces, "notes": notes})
        if titre:
            titres.append({"texte": titre, "niveau": 1}); paras.append({"texte": titre, "style": "titre"})
        paras += [{"texte": x, "style": "puce"} for x in puces]
    cp = prs.core_properties
    meta = {"type": cp.category or "presentation", "langue": cp.language or "", "titre": cp.title or ""}
    return diapos, paras, titres, meta


def _xlsx(p):
    from openpyxl import load_workbook
    wb = load_workbook(str(p))
    paras, formules = [], []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    formules.append({"feuille": ws.title, "cellule": c.coordinate, "formule": c.value})
                elif isinstance(c.value, str) and c.value.strip():
                    paras.append({"texte": c.value, "style": "cellule"})
    meta = {"type": "calcul", "langue": wb.properties.language or "", "titre": wb.properties.title or ""}
    return wb, paras, formules, meta


def pdf_texte(p, par_page=False):
    exe = shutil.which("pdftotext")
    if exe:
        try:
            r = subprocess.run([exe, "-layout", str(p), "-"], capture_output=True, timeout=60)
            t = r.stdout.decode("utf-8", "replace")
            return t.split("\f") if par_page else t
        except Exception:
            pass
    try:
        from pypdf import PdfReader
        pages = [pg.extract_text() or "" for pg in PdfReader(str(p)).pages]
        return pages if par_page else "\n\f".join(pages)
    except Exception:
        return [] if par_page else ""


def charger(chemin, meta_sup=None):
    p = Path(chemin)
    ext = p.suffix.lower()
    doc = {"format": ext.lstrip("."), "chemin": str(p), "meta": {}, "blocs": [], "paragraphes": [], "titres": [], "objet": None}
    try:
        if ext in (".md", ".markdown"):
            raw = p.read_text(encoding="utf-8")
            meta, bl = MD.parse(raw)
            doc.update(meta=meta, blocs=bl, brut=raw)
            for b in bl:
                if b["t"] == "h":
                    doc["titres"].append({"texte": MD.texte_brut(b["texte"]), "niveau": b["niveau"]})
                    doc["paragraphes"].append({"texte": MD.texte_brut(b["texte"]), "style": f"Heading {b['niveau']}"})
                elif b["t"] in ("p", "quote"):
                    doc["paragraphes"].append({"texte": b["texte"], "style": "corps"})
                elif b["t"] in ("ul", "ol"):
                    doc["paragraphes"] += [{"texte": x, "style": "puce"} for x in b["items"]]
                elif b["t"] == "table":
                    doc["paragraphes"] += [{"texte": c, "style": "tableau"} for r in b["lignes"] for c in r if c]
        elif ext == ".docx":
            obj, paras, titres, meta = _docx(p)
            doc.update(objet=obj, paragraphes=paras, titres=titres, meta=meta)
        elif ext == ".pptx":
            diapos, paras, titres, meta = _pptx(p)
            doc.update(diapos=diapos, paragraphes=paras, titres=titres, meta=meta)
        elif ext == ".xlsx":
            obj, paras, formules, meta = _xlsx(p)
            doc.update(objet=obj, paragraphes=paras, formules=formules, meta=meta)
        elif ext == ".pdf":
            t = pdf_texte(p)
            doc.update(paragraphes=[{"texte": x, "style": "corps"} for x in re.split(r"\n\s*\n", t) if x.strip()], meta={"type": ""})
        elif ext == ".eml":
            m = email.message_from_bytes(p.read_bytes(), policy=policy.default)
            body = m.get_body(preferencelist=("plain",))
            txt = body.get_content() if body else ""
            pieces = [a.get_filename() for a in m.iter_attachments() if a.get_filename()]
            doc.update(paragraphes=[{"texte": x, "style": "corps"} for x in re.split(r"\n\s*\n", txt) if x.strip()],
                       meta={"type": "mail", "objet": str(m.get("Subject", "")), "pieces": pieces, "a": str(m.get("To", ""))}, brut=txt)
        else:
            t = p.read_text(encoding="utf-8", errors="replace")
            meta, body = MD.front_matter(t)
            doc.update(paragraphes=[{"texte": x, "style": "corps"} for x in re.split(r"\n\s*\n", body) if x.strip()], meta=meta or {"type": "mail" if ext == ".txt" else ""}, brut=t)
    except Exception as e:
        C.journal("erreurs-portes", op="charger", chemin=str(p), erreur=repr(e))
    if meta_sup:
        doc["meta"].update({k: v for k, v in meta_sup.items() if v})
    doc["texte"] = "\n\n".join(x["texte"] for x in doc["paragraphes"])
    doc["langue"] = (doc["meta"].get("langue") or detecter_langue(doc["texte"]))[:2].lower()
    doc["type"] = (doc["meta"].get("type") or "").lower() or ("mail" if ext in (".eml",) else "")
    return doc


def resultat(etat, details=None, corrections=None, **kw):
    return {"etat": etat, "details": details or [], "corrections": corrections or [], **kw}


def design():
    try:
        import design as D
        return D.charger()
    except Exception:
        return {}


def corps_md(doc):
    """lignes du corps markdown hors front matter, blocs de code et section des sources (pour les corrections)"""
    return doc.get("brut", "")


def section_alias(titre, d=None):
    """titre → clé de section (resume, question, …) selon alias_sections du design"""
    d = d or design()
    t = re.sub(r"^[\d.\s]+", "", (titre or "").strip().lower())
    t = re.sub(r"^annexe\s*[—–-]\s*", "annexe des ", t) if t.startswith("annexe") else t
    for cle, alias in (d.get("alias_sections") or {}).items():
        for a in alias:
            if t == a or t.startswith(a):
                return cle
    return None


def transformer_md(raw, fn, titres=True, sauter_sections=(), tableaux=True):
    """applique fn(paragraphe) → paragraphe aux paragraphes de prose d'un markdown (front matter, code, sources protégés)"""
    m = MD.FM_RE.match(raw)
    tete, corps = (raw[:m.end()], raw[m.end():]) if m else ("", raw)
    lignes = corps.split("\n")
    out, buf, code, saute = [], [], False, False

    def flush():
        if buf:
            txt = "\n".join(buf)
            out.extend((txt if saute else fn(txt)).split("\n"))
            buf.clear()

    for l in lignes:
        s = l.strip()
        if s.startswith("```"):
            flush(); code = not code; out.append(l); continue
        if code:
            out.append(l); continue
        h = re.match(r"^(#{1,6})\s+(.*)$", s)
        if h:
            flush()
            saute = section_alias(h.group(2)) in sauter_sections if sauter_sections else False
            out.append(l if (not titres or saute) else h.group(1) + " " + fn(h.group(2)))
            continue
        if not s:
            flush(); out.append(l); continue
        if s.startswith("|"):
            flush()
            if re.fullmatch(r"\|?[\s:\-|]+\|?", s) or not tableaux or saute:
                out.append(l)
            else:
                cells = s.strip("|").split("|")
                out.append("| " + " | ".join(fn(c.strip()) for c in cells) + " |")
            continue
        mm = re.match(r"^(\s*(?:[-*•]|\d+[.)])\s+)(.*)$", l)
        if mm:
            flush(); out.append(l if saute else mm.group(1) + fn(mm.group(2))); continue
        buf.append(l)
    flush()
    return tete + "\n".join(out)
