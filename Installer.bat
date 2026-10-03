@echo off
rem Installateur de "Mon equipe" pour Windows : double-clic, aucune question, sans droits administrateur.
rem Lance .equipe\scripts\installer.ps1 avec PowerShell (politique d execution contournee pour ce seul script).
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0.equipe\scripts\installer.ps1"
echo.
echo Vous pouvez fermer cette fenetre.
if not defined MON_EQUIPE_SANS_PAUSE pause >nul
