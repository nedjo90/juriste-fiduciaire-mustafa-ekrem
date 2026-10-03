# Installation complete de "Mon equipe" en UNE commande, sur un Windows sans rien (ni Git, ni Python, ni Claude)
# ou deja equipe : ce qui est present (Git, Python, Claude et son compte) est garde tel quel ("deja installe").
# Ordre : 1. Git (portable officiel, mode utilisateur, sans droits administrateur)  2. clonage du depot  3. installateur du projet.
# Aucune question. Relancable sans risque (met a jour au lieu de recloner).
#
# Commande a coller dans PowerShell (depot public) :
#   irm https://raw.githubusercontent.com/nedjo90/juriste-fiduciaire-mustafa-ekrem/ccr-e8f5838b-808ukj/.equipe/installation/installer-mon-equipe.ps1 | iex
#
# Reglages facultatifs (variables d'environnement) : MON_EQUIPE_JETON, MON_EQUIPE_DOSSIER (defaut : Documents\mon-equipe),
# MON_EQUIPE_DEPOT, MON_EQUIPE_BRANCHE. Pas de bloc param ni de exit : le script doit pouvoir etre execute par "iex".

& {
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch {}
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch {}

$Depot   = if ($env:MON_EQUIPE_DEPOT)   { $env:MON_EQUIPE_DEPOT }   else { 'https://github.com/nedjo90/juriste-fiduciaire-mustafa-ekrem.git' }
$Branche = if ($env:MON_EQUIPE_BRANCHE) { $env:MON_EQUIPE_BRANCHE } else { 'ccr-e8f5838b-808ukj' }
$Dossier = if ($env:MON_EQUIPE_DOSSIER) { $env:MON_EQUIPE_DOSSIER } else { Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'mon-equipe' }
$Jeton   = $env:MON_EQUIPE_JETON
$Tmp = Join-Path $env:TEMP 'mon-equipe-amorcage'
New-Item -ItemType Directory -Force -Path $Tmp | Out-Null
$Journal = Join-Path $Tmp 'amorcage.log'
function Noter([string]$m) { try { Add-Content -LiteralPath $Journal -Value ((Get-Date -Format s) + ' ' + $m) -Encoding UTF8 } catch {} }
function Dire([string]$m) { Write-Host $m; Noter $m }
function Lancer([string]$fichier, [string[]]$arguments, [int]$secondes, [string]$dossier = $null, [switch]$Visible) {
  # attend SEULEMENT ce processus (Start-Process -Wait attendrait aussi les processus lances en arriere-plan), avec un delai maximal
  $o = @{ FilePath = $fichier; PassThru = $true }
  if ($arguments) { $o.ArgumentList = $arguments }
  if ($dossier) { $o.WorkingDirectory = $dossier }
  if ($Visible) { $o.NoNewWindow = $true } else { $o.WindowStyle = 'Hidden' }
  try { $p = Start-Process @o } catch { Noter ("lancement impossible $fichier : " + $_); return -1 }
  $null = $p.Handle  # sans cela, ExitCode reste vide une fois le processus terminé (particularité PowerShell)
  if (-not $p.WaitForExit($secondes * 1000)) { Noter ("delai depasse ($secondes s) : $fichier"); try { $p.Kill() } catch {}; return -2 }
  return $p.ExitCode
}

function Ajouter-Path([string]$d) {
  if (-not $d -or -not (Test-Path -LiteralPath $d)) { return }
  $u = [Environment]::GetEnvironmentVariable('Path', 'User'); if (-not $u) { $u = '' }
  $parts = $u.Split(';') | Where-Object { $_ -ne '' }
  if ($parts -notcontains $d) { [Environment]::SetEnvironmentVariable('Path', (($parts + $d) -join ';'), 'User') }
  if ((("$env:Path").Split(';')) -notcontains $d) { $env:Path = $d + ';' + $env:Path }
}

function Trouver-Git {
  $c = @()
  $g = Get-Command git.exe -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($g) { $c += $g.Source }
  $c += @((Join-Path $env:LOCALAPPDATA 'Programs\PortableGit\cmd\git.exe'), (Join-Path $env:LOCALAPPDATA 'Programs\Git\cmd\git.exe'),
          "$env:ProgramFiles\Git\cmd\git.exe", "${env:ProgramFiles(x86)}\Git\cmd\git.exe")
  foreach ($x in $c) { if ($x -and (Test-Path -LiteralPath $x)) { return $x } }
  return $null
}

Dire ''
Dire 'Installation de votre equipe. Cela prend de 10 a 20 minutes ; laissez cette fenetre ouverte.'

# ------------------------------------------------------------------ 1. Git (portable officiel de git-for-windows, mode utilisateur)
$Git = Trouver-Git
$GitDeja = [bool]$Git
if (-not $Git) {
  Dire 'Etape 1/3 : installation de Git...'
  $arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'arm64' } else { '64-bit' }
  $url = $null
  try {
    $rel = Invoke-RestMethod -Uri 'https://api.github.com/repos/git-for-windows/git/releases/latest' -UseBasicParsing -TimeoutSec 60
    $a = $rel.assets | Where-Object { $_.name -match ('^PortableGit-.*-' + [regex]::Escape($arch) + '\.7z\.exe$') } | Select-Object -First 1
    if ($a) { $url = $a.browser_download_url }
  } catch { Noter ("liste des versions de Git indisponible : " + $_) }
  if (-not $url) { $url = "https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/PortableGit-2.47.1-$arch.7z.exe" }
  $sfx = Join-Path $Tmp 'PortableGit.7z.exe'
  $ok = $false
  for ($i = 1; $i -le 3 -and -not $ok; $i++) {
    try { Invoke-WebRequest -Uri $url -OutFile $sfx -UseBasicParsing -TimeoutSec 900; $ok = (Test-Path -LiteralPath $sfx) } catch { Noter ("telechargement de Git, essai $i : " + $_); Start-Sleep -Seconds (5 * $i) }
  }
  if ($ok) {
    $dest = Join-Path $env:LOCALAPPDATA 'Programs\PortableGit'
    New-Item -ItemType Directory -Force -Path $dest | Out-Null
    $null = Lancer $sfx @(('-o"' + $dest + '"'), '-y') 900
    if (Test-Path -LiteralPath (Join-Path $dest 'post-install.bat')) {
      $null = Lancer 'cmd.exe' @('/c', 'post-install.bat') 300 $dest
    }
  }
  $Git = Trouver-Git
}
if (-not $Git) {
  Dire "Git n'a pas pu etre installe (connexion Internet ?). Relancez la meme commande plus tard."
  return
}
$GitRacine = Split-Path -Parent (Split-Path -Parent $Git)
Ajouter-Path (Join-Path $GitRacine 'cmd')
$bash = Join-Path $GitRacine 'bin\bash.exe'
if (Test-Path -LiteralPath $bash) { [Environment]::SetEnvironmentVariable('CLAUDE_CODE_GIT_BASH_PATH', $bash, 'User'); $env:CLAUDE_CODE_GIT_BASH_PATH = $bash }
if ($GitDeja) { Dire 'Etape 1/3 : Git est deja installe.' } else { Dire 'Etape 1/3 : Git est installe.' }

# ------------------------------------------------------------------ 2. clonage (ou mise a jour) du depot
Dire 'Etape 2/3 : recuperation du dossier de votre equipe...'
$auth = @()
if ($Jeton) {
  $b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('x-access-token:' + $Jeton))
  $auth = @('-c', ('http.extraHeader=Authorization: Basic ' + $b64))
}
if (Test-Path -LiteralPath (Join-Path $Dossier '.git')) {
  # Mise a jour sans jamais perdre le travail de Mustafa : l'entretien commite son travail en local sur la meme branche,
  # donc un simple "pull --ff-only" echouerait des le premier commit local. On enregistre d'abord ce qui ne l'est pas,
  # puis on fusionne la nouvelle version de l'equipe ; en cas de conflit sur un meme passage, la version du poste l'emporte.
  $ident = @('-c', 'user.name=Mon equipe', '-c', 'user.email=equipe@poste.local')
  & $Git -C $Dossier add -A 2>&1 | Out-Null
  & $Git @ident -C $Dossier commit -q -m 'avant mise a jour : travail du poste enregistre' 2>&1 | ForEach-Object { Noter ("git commit : " + $_) }
  & $Git @auth -C $Dossier fetch -q origin $Branche 2>&1 | ForEach-Object { Noter ("git fetch : " + $_) }
  & $Git @ident -C $Dossier merge --no-edit -X ours ('origin/' + $Branche) 2>&1 | ForEach-Object { Noter ("git merge : " + $_) }
  if ($LASTEXITCODE -ne 0) {
    & $Git -C $Dossier merge --abort 2>&1 | Out-Null
    Noter 'mise a jour non appliquee (fusion impossible) : version actuelle conservee, aucun travail perdu'
  }
  $global:LASTEXITCODE = 0
} else {
  if ((Test-Path -LiteralPath $Dossier) -and (Get-ChildItem -LiteralPath $Dossier -Force -ErrorAction SilentlyContinue)) {
    $ancien = $Dossier + '-ancien-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
    Rename-Item -LiteralPath $Dossier -NewName (Split-Path $ancien -Leaf)
    Noter "dossier existant non vide deplace vers $ancien"
  }
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Dossier) | Out-Null
  & $Git @auth clone --depth 1 --branch $Branche --single-branch $Depot $Dossier 2>&1 | ForEach-Object { Noter ("git clone : " + $_) }
}
if (-not (Test-Path -LiteralPath (Join-Path $Dossier '.equipe\installation\installer.ps1'))) {
  Dire "Le dossier n'a pas pu etre recupere. Verifiez la connexion Internet (ou l'acces au depot) puis relancez la meme commande."
  Dire ("Detail technique : " + $Journal)
  return
}
# depot public : il sert aux mises a jour (pull) ; il ne recoit jamais le travail de Mustafa (aucun push automatique vers origin)
if ($Jeton) {
  $cred = "protocol=https`nhost=github.com`nusername=x-access-token`npassword=$Jeton`n`n"
  try { $cred | & $Git -C $Dossier credential approve 2>&1 | Out-Null } catch {}
}
Dire 'Etape 2/3 : le dossier est pret.'

# ------------------------------------------------------------------ 3. installateur du projet (Python, outils, Claude, reglages, raccourci)
Dire 'Etape 3/3 : installation des outils de votre equipe...'
$inst = Join-Path $Dossier '.equipe\installation\installer.ps1'
$code = Lancer 'powershell.exe' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $inst + '"')) 3600 $null -Visible
Noter ("installateur : code " + $code)
Dire ''
Dire "C'est termine. Ouvrez une NOUVELLE fenetre PowerShell (ou double-cliquez sur 'Mon equipe' sur le bureau) et tapez :  claude"
}
