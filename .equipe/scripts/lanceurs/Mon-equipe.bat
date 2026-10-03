@echo off
rem Lanceur de JURIX (Windows) : ouvre Claude Code dans le dossier du projet, en mode automatique.
rem Delegue a Mon-equipe.ps1 (PowerShell 5.1 ou plus recent), sans demande de politique d'execution.
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Mon-equipe.ps1" %*
if errorlevel 1 pause
