#!/usr/bin/env python3
"""OCR local d'un PDF scanné ou d'une image (§6.4 « OCR si installable en mode utilisateur ») ; rien ne sort du poste.
Moteurs, dans l'ordre : ocrmypdf (si présent) → tesseract (binaire du système, de Program Files, de
%LOCALAPPDATA%\\Programs ou de .team/tools) avec rendu des pages par PyMuPDF ou pdftoppm → RapidOCR (pip
`rapidocr-onnxruntime`, installable en mode utilisateur sous Windows/macOS/Linux) → None.
None = repli documenté : l'ingesteur classe le document « scan_a_lire » et la lecture se fait par le modèle (images
des pages), ou une question simple est mise en file ; jamais d'arrêt.
Usage : python ocr.py <fichier.pdf|png|jpg> [--langues fra+deu+eng]   → JSON {moteur, caracteres, extrait}
        python ocr.py --moteur                                         → moteur disponible"""
import os, sys, json, shutil, subprocess, tempfile, argparse
from pathlib import Path

LANGUES = "fra+deu+eng+ita"
DPI = 300


def _tesseract():
    cands = [shutil.which("tesseract"),
             r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
             str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR" / "tesseract.exe"),
             str(Path(__file__).resolve().parents[2] / "tools" / "tesseract" / ("tesseract.exe" if os.name == "nt" else "tesseract")),
             "/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"]
    for c in cands:
        if c and Path(c).exists():
            return c
    return None


def _rapidocr():
    try:
        from rapidocr_onnxruntime import RapidOCR  # noqa: F401
        return True
    except Exception:
        return False


def moteur():
    if shutil.which("ocrmypdf") and _tesseract():
        return "ocrmypdf"
    if _tesseract():
        return "tesseract"
    if _rapidocr():
        return "rapidocr"
    return None


def _langues_dispo(exe, voulu):
    try:
        r = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=20)
        dispo = set(r.stdout.split()[1:]) if r.stdout else set()
    except Exception:
        dispo = set()
    l = [x for x in voulu.split("+") if x in dispo]
    return "+".join(l) or ("eng" if "eng" in dispo else None)


def pages_en_images(pdf, dest, dpi=DPI):
    """PNG par page : PyMuPDF d'abord (pip, Windows sans poppler), sinon pdftoppm"""
    try:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz
        out = []
        with fitz.open(str(pdf)) as d:
            for i, pg in enumerate(d, 1):
                f = Path(dest) / f"p-{i:03d}.png"
                pg.get_pixmap(dpi=dpi).save(str(f))
                out.append(f)
        return out
    except Exception:
        pass
    exe = shutil.which("pdftoppm")
    if exe:
        subprocess.run([exe, "-r", str(dpi), "-png", str(pdf), str(Path(dest) / "p")], capture_output=True, timeout=600)
        return sorted(Path(dest).glob("p-*.png"))
    return []


def ocr(chemin, langues=LANGUES):
    """texte reconnu (str) ou None si aucun moteur ; ne lève jamais"""
    p = Path(chemin)
    m = moteur()
    if not m or not p.exists():
        return None
    tmp = Path(tempfile.mkdtemp(prefix="ocr-"))
    try:
        if m == "ocrmypdf" and p.suffix.lower() == ".pdf":
            side = tmp / "texte.txt"
            subprocess.run(["ocrmypdf", "--force-ocr", "-l", _langues_dispo(_tesseract(), langues) or "eng", "--sidecar", str(side),
                            str(p), str(tmp / "sortie.pdf")], capture_output=True, timeout=1800)
            if side.exists() and side.read_text(encoding="utf-8", errors="replace").strip():
                return side.read_text(encoding="utf-8", errors="replace")
            m = "tesseract"
        images = pages_en_images(p, tmp) if p.suffix.lower() == ".pdf" else [p]
        if not images:
            return None
        textes = []
        if m in ("tesseract", "ocrmypdf"):
            exe = _tesseract()
            lg = _langues_dispo(exe, langues)
            for im in images:
                r = subprocess.run([exe, str(im), "stdout", *(["-l", lg] if lg else []), "--psm", "3"], capture_output=True, timeout=600)
                textes.append(r.stdout.decode("utf-8", "replace"))
        else:
            from rapidocr_onnxruntime import RapidOCR
            eng = RapidOCR()
            for im in images:
                res, _ = eng(str(im))
                textes.append("\n".join(x[1] for x in (res or [])))
        t = "\n\f".join(textes).strip()
        return t or None
    except Exception as e:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from network import journal
            journal("ocr erreur", fichier=str(p), moteur=m, erreur=repr(e)[:200])
        except Exception:
            pass
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fichier", nargs="?"); ap.add_argument("--langues", default=LANGUES); ap.add_argument("--moteur", action="store_true")
    a = ap.parse_args()
    if a.moteur or not a.fichier:
        print(json.dumps({"moteur": moteur(), "tesseract": _tesseract(), "rapidocr": _rapidocr()}, ensure_ascii=False))
    else:
        t = ocr(a.fichier, a.langues)
        print(json.dumps({"moteur": moteur(), "caracteres": len(t or ""), "extrait": (t or "")[:500]}, ensure_ascii=False))
