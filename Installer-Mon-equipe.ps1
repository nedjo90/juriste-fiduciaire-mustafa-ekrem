# Installation complete de "Mon equipe" en UNE commande, sur un Windows sans rien (ni Git, ni Python, ni Claude).
# Ordre : 1. Git (portable officiel, mode utilisateur, sans droits administrateur)  2. clonage du depot  3. installateur du projet.
# Aucune question. Relancable sans risque (met a jour au lieu de recloner).
#
# Commande a coller dans PowerShell (depot public) :
#   irm https://raw.githubusercontent.com/nedjo90/juriste-fiduciaire-mustafa-ekrem/ccr-e8f5838b-808ukj/Installer-Mon-equipe.ps1 | iex
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
    Start-Process -FilePath $sfx -ArgumentList ('-o"' + $dest + '"'), '-y' -Wait -WindowStyle Hidden
    if (Test-Path -LiteralPath (Join-Path $dest 'post-install.bat')) {
      Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'post-install.bat' -WorkingDirectory $dest -Wait -WindowStyle Hidden
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
Dire 'Etape 1/3 : Git est pret.'

# ------------------------------------------------------------------ 2. clonage (ou mise a jour) du depot
Dire 'Etape 2/3 : recuperation du dossier de votre equipe...'
$auth = @()
if ($Jeton) {
  $b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('x-access-token:' + $Jeton))
  $auth = @('-c', ('http.extraHeader=Authorization: Basic ' + $b64))
}
if (Test-Path -LiteralPath (Join-Path $Dossier '.git')) {
  & $Git @auth -C $Dossier pull --ff-only 2>&1 | ForEach-Object { Noter ("git pull : " + $_) }
} else {
  if ((Test-Path -LiteralPath $Dossier) -and (Get-ChildItem -LiteralPath $Dossier -Force -ErrorAction SilentlyContinue)) {
    $ancien = $Dossier + '-ancien-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
    Rename-Item -LiteralPath $Dossier -NewName (Split-Path $ancien -Leaf)
    Noter "dossier existant non vide deplace vers $ancien"
  }
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Dossier) | Out-Null
  & $Git @auth clone --branch $Branche --single-branch $Depot $Dossier 2>&1 | ForEach-Object { Noter ("git clone : " + $_) }
}
if (-not (Test-Path -LiteralPath (Join-Path $Dossier 'Installer.bat'))) {
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
$inst = Join-Path $Dossier '.equipe\scripts\installer.ps1'
$p = Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $inst + '"') -Wait -NoNewWindow -PassThru
Noter ("installateur : code " + $p.ExitCode)
Dire ''
Dire "C'est termine. Ouvrez une NOUVELLE fenetre PowerShell (ou double-cliquez sur 'Mon equipe' sur le bureau) et tapez :  claude"
}
