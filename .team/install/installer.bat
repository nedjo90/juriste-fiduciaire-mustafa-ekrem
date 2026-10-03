@echo off
rem Installateur de JURIX pour Windows, sur un dossier deja present : double-clic, aucune question, sans droits administrateur.
rem Lance installer.ps1 (meme dossier) avec PowerShell. Ce qui est deja installe (Python, Git, Claude) est garde tel quel.
chcp 65001 >nul
cd /d "%~dp0..\.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer.ps1"
echo.
echo Vous pouvez fermer cette fenetre.
if not defined MON_EQUIPE_SANS_PAUSE pause >nul
