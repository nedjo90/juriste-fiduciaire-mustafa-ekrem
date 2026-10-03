#!/usr/bin/env python3
"""Conversion docx/pptx/xlsx → PDF par la suite Microsoft 365 du poste (pas de LibreOffice dans le projet).
- Windows : automatisation COM de Word / PowerPoint / Excel par un petit script PowerShell (sans pywin32),
  application invisible, fermeture garantie (try/finally, Quit()), délai maximal.
  Word : Documents.Open → SaveAs2(pdf, 17) ; PowerPoint : Presentations.Open → SaveAs(pdf, 32) ;
  Excel : Workbooks.Open → ExportAsFixedFormat(0, pdf).
- macOS : Word / PowerPoint / Excel par osascript s'ils sont installés dans /Applications.
- Sinon : None. L'appelant prend le repli (PDF de la maison par reportlab pour mémo / lettre / PV ;
  contrôle visuel limité à l'analyse du fichier, avec réserve). Jamais d'exception vers l'appelant.
Usage : python office.py <fichier.docx|pptx|xlsx> [--outdir D]   → JSON {pdf, methode}"""
import json, os, subprocess, sys, shutil, time
from pathlib import Path

WORD = {".docx", ".doc", ".docm", ".rtf", ".dotx"}
PPT = {".pptx", ".ppt", ".pptm", ".potx"}
XLS = {".xlsx", ".xls", ".xlsm", ".xltx"}

# Les chemins passent par des variables d'environnement : aucun problème de guillemets ni d'accents.
PS_WORD = r"""
$ErrorActionPreference = 'Stop'
$app = $null; $doc = $null
try {
  $app = New-Object -ComObject Word.Application
  $app.Visible = $false; $app.DisplayAlerts = 0
  $doc = $app.Documents.Open($env:OFFICE_SRC, $false, $true)
  $doc.SaveAs2($env:OFFICE_PDF, 17)
} finally {
  if ($doc) { try { $doc.Close(0) } catch {} }
  if ($app) { try { $app.Quit() } catch {}; [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) }
}
"""
PS_PPT = r"""
$ErrorActionPreference = 'Stop'
$app = $null; $p = $null
try {
  $app = New-Object -ComObject PowerPoint.Application
  $p = $app.Presentations.Open($env:OFFICE_SRC, -1, 0, 0)
  $p.SaveAs($env:OFFICE_PDF, 32)
} finally {
  if ($p) { try { $p.Close() } catch {} }
  if ($app) { try { $app.Quit() } catch {}; [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) }
}
"""
PS_XLS = r"""
$ErrorActionPreference = 'Stop'
$app = $null; $wb = $null
try {
  $app = New-Object -ComObject Excel.Application
  $app.Visible = $false; $app.DisplayAlerts = $false
  $wb = $app.Workbooks.Open($env:OFFICE_SRC, 0, $true)
  $wb.ExportAsFixedFormat(0, $env:OFFICE_PDF)
} finally {
  if ($wb) { try { $wb.Close($false) } catch {} }
  if ($app) { try { $app.Quit() } catch {}; [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) }
}
"""
OSA = {
    "word": ('Microsoft Word', 'tell application "Microsoft Word"\n set d to open (POSIX file (system attribute "OFFICE_SRC"))\n'
             ' save as active document file name (system attribute "OFFICE_PDF") file format format PDF\n close active document saving no\nend tell'),
    "ppt": ('Microsoft PowerPoint', 'tell application "Microsoft PowerPoint"\n open (POSIX file (system attribute "OFFICE_SRC"))\n'
            ' save active presentation in (POSIX file (system attribute "OFFICE_PDF")) as save as PDF\n close active presentation\nend tell'),
    "xls": ('Microsoft Excel', 'tell application "Microsoft Excel"\n open (POSIX file (system attribute "OFFICE_SRC"))\n'
            ' save workbook as active workbook filename (system attribute "OFFICE_PDF") file format PDF file format\n'
            ' close active workbook saving no\nend tell'),
}


def _journal(**rec):
    try:
        import common as C
        C.journal("office", **rec)
    except Exception:
        pass


def famille(chemin):
    e = Path(chemin).suffix.lower()
    return "word" if e in WORD else "ppt" if e in PPT else "xls" if e in XLS else None


def _powershell():
    for c in ("powershell.exe", "powershell", "pwsh.exe", "pwsh"):
        p = shutil.which(c)
        if p:
            return p
    return None


def disponible(fam="word"):
    """méthode de conversion utilisable sur ce poste : 'com', 'osascript' ou None (repli)"""
    if os.environ.get("OFFICE_DESACTIVE"):
        return None
    if sys.platform.startswith("win") and _powershell():
        return "com"
    if sys.platform == "darwin" and shutil.which("osascript") and fam in OSA and Path(f"/Applications/{OSA[fam][0]}.app").exists():
        return "osascript"
    return None


def vers_pdf(chemin, outdir=None, timeout=240):
    """chemin_pdf (Path) ou None. Le PDF porte le nom du fichier source (extension .pdf)."""
    t0 = time.time()
    src = Path(chemin).resolve()
    fam = famille(src)
    if not fam or not src.exists():
        return None
    methode = disponible(fam)
    if not methode:
        return None
    out = Path(outdir or src.parent).resolve()
    out.mkdir(parents=True, exist_ok=True)
    pdf = out / (src.stem + ".pdf")
    try:
        if pdf.exists():
            pdf.unlink()
    except Exception:
        pass
    env = {**os.environ, "OFFICE_SRC": str(src), "OFFICE_PDF": str(pdf)}
    try:
        if methode == "com":
            script = {"word": PS_WORD, "ppt": PS_PPT, "xls": PS_XLS}[fam]
            r = subprocess.run([_powershell(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
                               capture_output=True, timeout=timeout, env=env)
        else:
            r = subprocess.run(["osascript", "-e", OSA[fam][1]], capture_output=True, timeout=timeout, env=env)
        ok = pdf.exists() and pdf.stat().st_size > 0
        _journal(op="vers_pdf", methode=methode, src=str(src), ok=ok, code=r.returncode,
                 err=(r.stderr or b"").decode("utf-8", "replace")[-300:], duree_ms=int((time.time() - t0) * 1000))
        return pdf if ok else None
    except Exception as e:
        _journal(op="vers_pdf", methode=methode, src=str(src), ok=False, erreur=repr(e))
        if methode == "com" and isinstance(e, subprocess.TimeoutExpired):  # application restée ouverte : on la ferme
            exe = {"word": "WINWORD.EXE", "ppt": "POWERPNT.EXE", "xls": "EXCEL.EXE"}[fam]
            try:
                subprocess.run(["taskkill", "/IM", exe, "/F"], capture_output=True, timeout=20)
            except Exception:
                pass
        return None


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fichier"); ap.add_argument("--outdir")
    a = ap.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    p = vers_pdf(a.fichier, a.outdir)
    print(json.dumps({"pdf": str(p) if p else None, "methode": disponible(famille(a.fichier) or "word")}, ensure_ascii=False))
