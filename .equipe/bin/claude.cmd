@echo off
rem claude tape dans n importe quel terminal : ouvre l equipe (dossier du projet, sans demande d autorisation).
rem Ce dossier est place en tete du PATH utilisateur par l installateur ; le vrai Claude est appele par son chemin.
setlocal
set "EXE=%USERPROFILE%\.local\bin\claude.exe"
if not exist "%EXE%" for /f "delims=" %%i in ('where claude.exe 2^>nul') do if not defined TROUVE (set "EXE=%%i" & set "TROUVE=1")
pushd "%~dp0..\.."
if "%~1"=="" (
  "%EXE%" --dangerously-skip-permissions "Bonjour"
) else (
  "%EXE%" --dangerously-skip-permissions %*
)
set "CODE=%ERRORLEVEL%"
popd
exit /b %CODE%
