@echo off
rem claude tape dans n importe quel terminal : ouvre l equipe (dossier du projet, sans demande d autorisation).
rem Ce dossier est place en tete du PATH utilisateur par l installateur ; le VRAI Claude est appele par son chemin,
rem quelle que soit son installation (officielle, ancienne installation npm, winget), jamais ce fichier lui-meme.
setlocal
set "ICI=%~dp0"
set "EXE="
if defined CEREBRO_CLAUDE for %%i in ("%CEREBRO_CLAUDE%") do if exist "%%~fi" if /i not "%%~dpi"=="%ICI%" set "EXE=%%~fi"
if not defined EXE if exist "%USERPROFILE%\.local\bin\claude.exe" set "EXE=%USERPROFILE%\.local\bin\claude.exe"
if not defined EXE for /f "delims=" %%i in ('where claude.exe 2^>nul') do if not defined EXE set "EXE=%%i"
if not defined EXE if exist "%APPDATA%\npm\claude.cmd" set "EXE=%APPDATA%\npm\claude.cmd"
if not defined EXE if exist "%USERPROFILE%\.claude\local\claude.cmd" set "EXE=%USERPROFILE%\.claude\local\claude.cmd"
if not defined EXE for /f "delims=" %%i in ('where claude.cmd 2^>nul') do if not defined EXE if /i not "%%~dpi"=="%ICI%" set "EXE=%%i"
if not defined EXE (
  echo Claude n'est pas encore installe sur cet ordinateur : relancez la commande d'installation.
  exit /b 1
)
rem un claude.cmd (installation npm) doit etre appele par CALL pour rendre la main
set "APPEL="
if /i "%EXE:~-4%"==".cmd" set "APPEL=call"
pushd "%~dp0..\.."
rem commandes d outillage (version, aide, MCP, extensions, compte, mode non interactif) : transmises telles quelles,
rem sans ouvrir la connexion au compte (elle attendrait un navigateur)
set "A1=%~1"
set "DIRECT="
for %%s in (--version -v -h --help mcp plugin plugins auth update doctor config install setup-token migrate-installer -p --print) do if /i "%A1%"=="%%s" set "DIRECT=1"
if defined DIRECT (
  %APPEL% "%EXE%" %*
  goto fin
)
rem pas encore connecte : la page de connexion s ouvre dans le navigateur (aucun /login a taper)
%APPEL% "%EXE%" auth status --json 2>nul | findstr /c:"\"loggedIn\": true" >nul || %APPEL% "%EXE%" auth login --claudeai
if "%~1"=="" (
  %APPEL% "%EXE%" --dangerously-skip-permissions "Bonjour"
) else (
  %APPEL% "%EXE%" --dangerously-skip-permissions %*
)
:fin
set "CODE=%ERRORLEVEL%"
popd
exit /b %CODE%
