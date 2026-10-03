# Installation complete de JURIX en UNE commande, sur un Windows sans rien (ni Git, ni Python, ni Claude)
# ou deja equipe : ce qui est present (Git, Python, Claude et son compte) est garde tel quel ("deja installe").
# Ordre : 1. Git (portable officiel, mode utilisateur, sans droits administrateur)  2. clonage du depot  3. installateur du projet.
# Aucune question. Relancable sans risque (met a jour au lieu de recloner).
#
# Commande a coller dans PowerShell (depot public) :
#   irm https://raw.githubusercontent.com/nedjo90/juriste-fiduciaire-mustafa-ekrem/ccr-e8f5838b-808ukj/.team/install/installer-jurix.ps1 | iex
#
# Reglages facultatifs (variables d'environnement) : MON_EQUIPE_JETON, MON_EQUIPE_DOSSIER (defaut : Documents\jurix),
# MON_EQUIPE_DEPOT, MON_EQUIPE_BRANCHE. Pas de bloc param ni de exit : le script doit pouvoir etre execute par "iex".

& {
$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch {}
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch {}

$Depot   = if ($env:MON_EQUIPE_DEPOT)   { $env:MON_EQUIPE_DEPOT }   else { 'https://github.com/nedjo90/juriste-fiduciaire-mustafa-ekrem.git' }
$Branche = if ($env:MON_EQUIPE_BRANCHE) { $env:MON_EQUIPE_BRANCHE } else { 'ccr-e8f5838b-808ukj' }
$Jeton   = $env:MON_EQUIPE_JETON

# Dossier : Documents\jurix, mais jamais dans un dossier synchronise (OneDrive, souvent active d'office avec Microsoft 365,
# Dropbox, partage reseau d'une fiduciaire) : la synchronisation verrouille les fichiers que l'equipe reecrit et abime
# l'historique. Dans ce cas : Documents local du profil (non synchronise), et un raccourci JURIX dans le Documents visible.
function Dossier-Local([string]$d) {
  if (-not $d) { return $false }
  if ($d.StartsWith('\\')) { return $false }
  foreach ($v in 'OneDrive', 'OneDriveCommercial', 'OneDriveConsumer') {
    foreach ($o in @((Get-Item -LiteralPath ('Env:' + $v) -ErrorAction SilentlyContinue).Value, [Environment]::GetEnvironmentVariable($v, 'User'))) {
      if ($o -and $d.TrimEnd('\').ToLower().StartsWith($o.TrimEnd('\').ToLower())) { return $false }
    }
  }
  if ($d -match '(?i)onedrive|dropbox|icloud|google drive|nextcloud|owncloud') { return $false }
  try { if ((New-Object IO.DriveInfo ([IO.Path]::GetPathRoot($d))).DriveType -ne [IO.DriveType]::Fixed) { return $false } } catch {}
  return $true
}
$DocsVisibles = [Environment]::GetFolderPath('MyDocuments')
$RaccourciDocs = $false
if ($env:MON_EQUIPE_DOSSIER) {
  $Dossier = $env:MON_EQUIPE_DOSSIER
} else {
  $cands = @()
  if ($DocsVisibles) { $cands += (Join-Path $DocsVisibles 'jurix') }
  $cands += (Join-Path (Join-Path $env:USERPROFILE 'Documents') 'jurix'), (Join-Path $env:LOCALAPPDATA 'jurix')
  $Dossier = $cands | Where-Object { Test-Path -LiteralPath (Join-Path $_ '.git') } | Select-Object -First 1   # deja installe : on le garde
  if (-not $Dossier) { $Dossier = $cands | Where-Object { Dossier-Local (Split-Path -Parent $_) } | Select-Object -First 1 }
  if (-not $Dossier) { $Dossier = Join-Path $env:LOCALAPPDATA 'jurix' }
  $RaccourciDocs = $DocsVisibles -and ((Split-Path -Parent $Dossier) -ne $DocsVisibles)
}
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
Dire 'Installation de JURIX. Cela prend de 10 a 20 minutes ; laissez cette fenetre ouverte.'

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
Dire 'Etape 2/3 : recuperation de JURIX...'
$auth = @()
if ($Jeton) {
  $b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('x-access-token:' + $Jeton))
  $auth = @('-c', ('http.extraHeader=Authorization: Basic ' + $b64))
}
if (Test-Path -LiteralPath (Join-Path $Dossier '.git')) {
  # Mise a jour sans jamais perdre le travail de Mustafa : l'entretien commite son travail en local sur la meme branche,
  # donc un simple "pull --ff-only" echouerait des le premier commit local. On enregistre d'abord ce qui ne l'est pas,
  # puis on fusionne la nouvelle version de l'equipe ; en cas de conflit sur un meme passage, la version du poste l'emporte.
  $ident = @('-c', 'user.name=Mon equipe', '-c', 'user.email=equipe@workstation.local')
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
if (-not (Test-Path -LiteralPath (Join-Path $Dossier '.team\install\installer.ps1'))) {
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
Dire 'Etape 3/3 : installation des outils de JURIX...'
$inst = Join-Path $Dossier '.team\install\installer.ps1'
$code = Lancer 'powershell.exe' @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $inst + '"')) 3600 $null -Visible
Noter ("installateur : code " + $code)
# cette fenetre devient directement utilisable : reglages relus, positionnee dans le dossier de l'equipe, « claude » actif
# (une nouvelle fenetre l'a aussi, par le profil PowerShell ; la commande de l'equipe se place toujours dans le bon dossier)
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
foreach ($v in 'CEREBRO_CLAUDE', 'CEREBRO_PYTHON', 'CLAUDE_CODE_GIT_BASH_PATH') {
  $val = [Environment]::GetEnvironmentVariable($v, 'User'); if ($val) { Set-Item -Path ('Env:' + $v) -Value $val }
}
$cible = Join-Path $Dossier '.team\bin\claude.cmd'
if (Test-Path -LiteralPath $cible) {
  Set-Item -Path 'function:global:claude' -Value ([ScriptBlock]::Create("& '" + ($cible -replace "'", "''") + "' @args"))
}
if (Test-Path -LiteralPath $cible) {
  # « jurix » : banniere puis l'equipe (caracteres speciaux par leur code : ce fichier reste en ASCII pour « irm | iex »)
  $b = [string][char]0x2591 + [char]0x2592 + [char]0x2593 + [char]0x2588
  $f = [string][char]0x2588 + [char]0x2593 + [char]0x2592 + [char]0x2591
  $l1 = '   ' + $b + '  J U R I X  ' + $f
  $l2 = '   cabinet augment' + [char]0x00E9 + ' ' + [char]0x00B7 + ' droit suisse ' + [char]0x00B7 + ' en ligne'
  $corps = "if (`$args.Count -eq 0) { Write-Host ''; Write-Host '" + $l1 + "' -ForegroundColor Cyan; Write-Host '" + $l2 + "' -ForegroundColor DarkCyan; Write-Host '' }; & '" + ($cible -replace "'", "''") + "' @args"
  Set-Item -Path 'function:global:jurix' -Value ([ScriptBlock]::Create($corps))
}
if ($RaccourciDocs -and (Test-Path -LiteralPath $Dossier)) {
  # dossier hors du Documents synchronise : Mustafa le retrouve quand meme dans Documents
  try {
    $ws = New-Object -ComObject WScript.Shell
    $sc = $ws.CreateShortcut((Join-Path $DocsVisibles 'JURIX.lnk'))
    $sc.TargetPath = $Dossier
    $sc.Description = 'Dossier de JURIX (sur cet ordinateur)'
    $sc.Save()
    Noter ("raccourci dans Documents vers " + $Dossier)
  } catch { Noter ("raccourci dans Documents impossible : " + $_) }
}
if (Test-Path -LiteralPath $Dossier) { Set-Location -LiteralPath $Dossier }
Dire ''
Dire "C'est termine. Tapez maintenant :  jurix"
Dire "(Plus tard : double-cliquez sur JURIX sur le bureau, ou tapez jurix dans n'importe quelle fenetre PowerShell.)"
}
