#!/usr/bin/env python3
"""Anciens formats Office (.doc, .rtf, .odt, .xls, .ppt) → formats modernes (.docx, .xlsx, .pptx) par Microsoft Office
installé sur le poste (automatisation COM, fenêtre invisible, macros désactivées, Quit() garanti), via un petit script
PowerShell appelé par subprocess (sans pywin32). Hors Windows, ou Office absent : None (l'appelant replie sur une
lecture par le modèle). Rien ne sort du poste."""
import os, subprocess, tempfile, shutil
from pathlib import Path

APPLI = {".doc": "word", ".rtf": "word", ".odt": "word", ".wpd": "word",
         ".xls": "excel", ".ods": "excel",
         ".ppt": "powerpoint", ".pps": "powerpoint", ".odp": "powerpoint"}
CIBLE = {"word": ".docx", "excel": ".xlsx", "powerpoint": ".pptx"}

# chemins passés par variables d'environnement (aucun problème de guillemets ni d'accents)
PS = r"""
$ErrorActionPreference = 'Stop'
$src = $env:CB_SRC; $dst = $env:CB_DST; $kind = $env:CB_APP
$app = $null; $doc = $null
try {
  switch ($kind) {
    'word' {
      $app = New-Object -ComObject Word.Application
      $app.Visible = $false; $app.DisplayAlerts = 0; $app.AutomationSecurity = 3
      # Open(FileName, ConfirmConversions, ReadOnly, AddToRecentFiles, PasswordDocument) : mot de passe factice = erreur au lieu d'une invite
      $doc = $app.Documents.Open($src, $false, $true, $false, '~~cb~~')
      $doc.SaveAs2($dst, 16)   # wdFormatXMLDocument
      $doc.Close($false)
    }
    'excel' {
      $app = New-Object -ComObject Excel.Application
      $app.Visible = $false; $app.DisplayAlerts = $false; $app.AutomationSecurity = 3; $app.AskToUpdateLinks = $false
      # Open(Filename, UpdateLinks, ReadOnly, Format, Password)
      $doc = $app.Workbooks.Open($src, 0, $true, 5, '~~cb~~')
      $doc.SaveAs($dst, 51)    # xlOpenXMLWorkbook
      $doc.Close($false)
    }
    'powerpoint' {
      $app = New-Object -ComObject PowerPoint.Application
      $app.AutomationSecurity = 3
      # Open(FileName, ReadOnly, Untitled, WithWindow) : msoTrue = -1, msoFalse = 0
      $doc = $app.Presentations.Open($src, -1, 0, 0)
      $doc.SaveAs($dst, 24)    # ppSaveAsOpenXMLPresentation
      $doc.Close()
    }
  }
  Write-Output 'OK'
} catch {
  Write-Output ('ERREUR ' + $_.Exception.Message)
} finally {
  if ($doc) { try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($doc) } catch {} }
  if ($app) { try { $app.Quit() } catch {}; try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) } catch {} }
  [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}
"""


def disponible():
    return os.name == "nt" and bool(shutil.which("powershell") or shutil.which("powershell.exe"))


def vers_moderne(chemin, dossier=None, timeout=180):
    """→ Path du fichier converti (.docx/.xlsx/.pptx) ou None"""
    p = Path(chemin).resolve()
    kind = APPLI.get(p.suffix.lower())
    if not kind or not disponible():
        return None
    d = Path(dossier or tempfile.mkdtemp(prefix="cb-office-"))
    d.mkdir(parents=True, exist_ok=True)
    dst = (d / (p.stem[:100] + CIBLE[kind])).resolve()
    env = {**os.environ, "CB_SRC": str(p), "CB_DST": str(dst), "CB_APP": kind}
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", PS],
                           env=env, capture_output=True, timeout=timeout, creationflags=0x08000000)
        sortie = r.stdout.decode("utf-8", "ignore") + r.stderr.decode("utf-8", "ignore")
    except Exception as e:
        sortie = repr(e)
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    try:
        import json, time
        j = Path(os.environ.get("CEREBRO_ROOT") or Path(__file__).resolve().parents[3]) / ".team" / "brain" / "journal" / "office-lecture.jsonl"
        j.parent.mkdir(parents=True, exist_ok=True)
        with open(j, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"le": time.strftime("%Y-%m-%dT%H:%M:%S"), "fichier": p.name, "app": kind, "sortie": sortie[-300:]}, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return None
