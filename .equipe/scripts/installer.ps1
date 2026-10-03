# Installateur « Mon équipe » pour Windows (constitution §2, §5). Fichier UTF-8 avec BOM, compatible PowerShell 5.1.
# Sans droits d'administrateur, sans aucune question, idempotent (peut être relancé autant de fois que nécessaire).
# Lancement : double-clic sur Installer.bat à la racine du projet (ou : powershell -ExecutionPolicy Bypass -File installer.ps1).
# Étapes : Python (utilisateur) · bibliothèques · Git (utilisateur ou portable) · Claude Code · Node (optionnel)
#          · confiance du dossier · mode sans demande · réglages adaptés au poste · base cerebro · raccourci bureau
#          · tâche planifiée d'entretien · zone machine cachée · validation · rapport en français simple.
param([switch]$SansReseau)

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch {}
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch {}

$Racine = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Run = Join-Path $Racine '.equipe\run'
New-Item -ItemType Directory -Force -Path $Run | Out-Null
$Log = Join-Path $Run 'installation.log'
$Rapport = New-Object System.Collections.Generic.List[string]
$Tmp = Join-Path $env:TEMP 'mon-equipe-installation'
New-Item -ItemType Directory -Force -Path $Tmp | Out-Null

function Noter([string]$m) {
  try { Add-Content -LiteralPath $Log -Value ((Get-Date -Format s) + ' ' + $m) -Encoding UTF8 } catch {}
}
function Dire([string]$m) { Write-Host $m; Noter $m }
function Bilan([string]$m) { $Rapport.Add($m) | Out-Null; Noter ('BILAN ' + $m) }

function Ajouter-PathUtilisateur([string]$dossier) {
  if (-not $dossier -or -not (Test-Path -LiteralPath $dossier)) { return }
  $actuel = [Environment]::GetEnvironmentVariable('Path', 'User')
  if (-not $actuel) { $actuel = '' }
  $parts = $actuel.Split(';') | Where-Object { $_ -ne '' }
  if ($parts -notcontains $dossier) {
    [Environment]::SetEnvironmentVariable('Path', (($parts + $dossier) -join ';'), 'User')
  }
  if ((("$env:Path").Split(';')) -notcontains $dossier) { $env:Path = $dossier + ';' + $env:Path }
}

function Telecharger([string]$url, [string]$dest) {
  if ($SansReseau) { return $false }
  try { Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing -TimeoutSec 600; return (Test-Path -LiteralPath $dest) }
  catch { Noter ("téléchargement en échec $url : " + $_); return $false }
}

function Winget-Utilisateur([string]$id) {
  if ($SansReseau) { return $false }
  $w = Get-Command winget.exe -ErrorAction SilentlyContinue
  if (-not $w) { return $false }
  try {
    & $w.Source install -e --id $id --scope user --silent --accept-package-agreements --accept-source-agreements --disable-interactivity 2>&1 | ForEach-Object { Noter ("winget: " + $_) }
    return ($LASTEXITCODE -eq 0)
  } catch { Noter ("winget en échec $id : " + $_); return $false }
}

function Python-Valide([string]$exe) {
  if (-not $exe -or -not (Test-Path -LiteralPath $exe)) { return $false }
  if ($exe -match 'WindowsApps') { return $false }   # alias du Microsoft Store, pas un vrai Python
  try {
    $v = & $exe -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
    if (-not $v) { return $false }
    $p = "$v".Trim().Split('.')
    return ([int]$p[0] -eq 3 -and [int]$p[1] -ge 10)
  } catch { return $false }
}

function Trouver-Python {
  $candidats = @()
  $candidats += Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Programs\Python') -Filter python.exe -Recurse -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | ForEach-Object { $_.FullName }
  $candidats += Get-Command python.exe -All -ErrorAction SilentlyContinue | ForEach-Object { $_.Source }
  $candidats += @("$env:ProgramFiles\Python312\python.exe", "$env:ProgramFiles\Python311\python.exe")
  foreach ($c in $candidats) { if (Python-Valide $c) { return $c } }
  return $null
}

# fichiers venus d'Internet (archive téléchargée) : retirer la marque qui déclenche des avertissements
try { Get-ChildItem -LiteralPath $Racine -Recurse -File -Force -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue } catch {}

Dire ''
Dire 'Installation de votre équipe : cela prend quelques minutes. Vous pouvez laisser cette fenêtre ouverte.'
Noter "racine: $Racine"

# ---------------------------------------------------------------- 1. Python (mode utilisateur)
$Py = Trouver-Python
if (-not $Py) {
  Dire 'Installation de Python…'
  if (Winget-Utilisateur 'Python.Python.3.12') { $Py = Trouver-Python }
  if (-not $Py) {
    $exe = Join-Path $Tmp 'python-installer.exe'
    $arch = 'amd64'
    if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { $arch = 'arm64' }
    if (Telecharger "https://www.python.org/ftp/python/3.12.8/python-3.12.8-$arch.exe" $exe) {
      Start-Process -FilePath $exe -ArgumentList '/quiet', 'InstallAllUsers=0', 'PrependPath=1', 'Include_launcher=0', 'Include_test=0', 'Shortcuts=0' -Wait
      $Py = Trouver-Python
    }
  }
}
if ($Py) {
  Bilan "Python : prêt ($Py)"
  Ajouter-PathUtilisateur (Split-Path -Parent $Py)
  [Environment]::SetEnvironmentVariable('CEREBRO_PYTHON', $Py, 'User')
  $env:CEREBRO_PYTHON = $Py
} else {
  Bilan "Python : non installé (pas d'accès à Internet ?). Relancez l'installateur plus tard."
}

# ---------------------------------------------------------------- 2. bibliothèques Python (mode utilisateur)
if ($Py) {
  Dire 'Installation des outils de documents (Word, Excel, PowerPoint, PDF, graphiques)…'
  & $Py -m ensurepip --user 2>&1 | Out-Null
  $libs = @('pyyaml', 'python-docx', 'openpyxl', 'python-pptx', 'reportlab', 'matplotlib', 'pandas', 'cryptography', 'uv')
  if (-not $SansReseau) {
    & $Py -m pip install --user --upgrade --disable-pip-version-check --no-warn-script-location @libs 2>&1 | ForEach-Object { Noter ("pip: " + $_) }
  }
  $manque = & $Py -c "import importlib.util as u; m=[x for x in ('yaml','docx','openpyxl','pptx','reportlab','matplotlib','pandas','cryptography') if not u.find_spec(x)]; print(','.join(m))" 2>$null
  if ($manque) { Bilan "Outils de documents : il manque $manque (nouvel essai au prochain lancement de l'installateur)." }
  else { Bilan 'Outils de documents : prêts.' }
  $scripts = & $Py -c "import sysconfig, os; print(sysconfig.get_path('scripts', os.name + '_user'))" 2>$null
  if ($scripts) { Ajouter-PathUtilisateur (("$scripts").Trim()) }
}

# ---------------------------------------------------------------- 3. Git (nécessaire à Claude Code sous Windows et aux sauvegardes)
$GitBash = $null
function Trouver-GitBash {
  $c = @((Join-Path $env:LOCALAPPDATA 'Programs\Git\bin\bash.exe'), (Join-Path $env:LOCALAPPDATA 'Programs\PortableGit\bin\bash.exe'),
         "$env:ProgramFiles\Git\bin\bash.exe", "${env:ProgramFiles(x86)}\Git\bin\bash.exe")
  $g = Get-Command git.exe -ErrorAction SilentlyContinue
  if ($g) { $c += (Join-Path (Split-Path -Parent (Split-Path -Parent $g.Source)) 'bin\bash.exe') }
  foreach ($x in $c) { if ($x -and (Test-Path -LiteralPath $x)) { return $x } }
  return $null
}
$GitBash = Trouver-GitBash
if (-not $GitBash) {
  Dire 'Installation de Git…'
  if (Winget-Utilisateur 'Git.Git') { $GitBash = Trouver-GitBash }
  if (-not $GitBash -and -not $SansReseau) {
    try {
      $rel = Invoke-RestMethod -Uri 'https://api.github.com/repos/git-for-windows/git/releases/latest' -UseBasicParsing -TimeoutSec 60
      $motif = 'PortableGit-.*-64-bit\.7z\.exe$'
      if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { $motif = 'PortableGit-.*-arm64\.7z\.exe$' }
      $asset = $rel.assets | Where-Object { $_.name -match $motif } | Select-Object -First 1
      if ($asset) {
        $sfx = Join-Path $Tmp $asset.name
        if (Telecharger $asset.browser_download_url $sfx) {
          $dest = Join-Path $env:LOCALAPPDATA 'Programs\PortableGit'
          New-Item -ItemType Directory -Force -Path $dest | Out-Null
          Start-Process -FilePath $sfx -ArgumentList "-o`"$dest`"", '-y' -Wait -WindowStyle Hidden
          if (Test-Path (Join-Path $dest 'post-install.bat')) {
            Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'post-install.bat' -WorkingDirectory $dest -Wait -WindowStyle Hidden
          }
          $GitBash = Trouver-GitBash
        }
      }
    } catch { Noter ("PortableGit en échec : " + $_) }
  }
}
if ($GitBash) {
  $gitRoot = Split-Path -Parent (Split-Path -Parent $GitBash)
  Ajouter-PathUtilisateur (Join-Path $gitRoot 'cmd')
  [Environment]::SetEnvironmentVariable('CLAUDE_CODE_GIT_BASH_PATH', $GitBash, 'User')
  $env:CLAUDE_CODE_GIT_BASH_PATH = $GitBash
  Bilan 'Git : prêt.'
  $git = Join-Path $gitRoot 'cmd\git.exe'
  if (Test-Path -LiteralPath (Join-Path $Racine '.git')) {
    $nom = & $git -C $Racine config user.name 2>$null
    if (-not $nom) { & $git -C $Racine config user.name 'Mon equipe' ; & $git -C $Racine config user.email 'equipe@poste.local' }
  }
} else {
  Bilan "Git : non installé (nouvel essai au prochain lancement de l'installateur)."
}

# ---------------------------------------------------------------- 4. Claude Code (installateur officiel, mode utilisateur)
function Trouver-Claude {
  $c = Get-Command claude -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($c) { return $c.Source }
  $x = Join-Path $env:USERPROFILE '.local\bin\claude.exe'
  if (Test-Path -LiteralPath $x) { return $x }
  return $null
}
$Claude = Trouver-Claude
if (-not $Claude -and -not $SansReseau) {
  Dire 'Installation de Claude…'
  try {
    # commande officielle : irm https://claude.ai/install.ps1 | iex (dans un processus séparé, fenêtre cachée)
    Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', '"irm https://claude.ai/install.ps1 | iex"' -Wait -WindowStyle Hidden
  } catch { Noter ("installation de Claude en échec : " + $_) }
  Ajouter-PathUtilisateur (Join-Path $env:USERPROFILE '.local\bin')
  $Claude = Trouver-Claude
}
if ($Claude) { Ajouter-PathUtilisateur (Split-Path -Parent $Claude); Bilan 'Claude : prêt.' }
else { Bilan "Claude : non installé (nouvel essai au prochain lancement de l'installateur)." }

# ---------------------------------------------------------------- 5. optionnel : Node (navigateur automatisé), LibreOffice (conversion PDF)
if (-not (Get-Command npx -ErrorAction SilentlyContinue)) {
  if (Winget-Utilisateur 'OpenJS.NodeJS.LTS') { Bilan 'Navigateur automatisé : prêt.' }
  else { Bilan 'Navigateur automatisé : non installé (optionnel, l''équipe travaille sans).' }
}
$soffice = @("$env:ProgramFiles\LibreOffice\program\soffice.exe", (Join-Path $env:LOCALAPPDATA 'Programs\LibreOffice\program\soffice.exe')) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $soffice) { Bilan 'Conversion bureautique avancée : non installée (optionnelle ; les documents sont produits sans).' }

# ---------------------------------------------------------------- 6. réglages de Claude : confiance du dossier, mode sans demande, poste
$Valider = Join-Path $Racine '.equipe\scripts\valider_config.py'
if ($Py) {
  & $Py $Valider --confiance 2>&1 | ForEach-Object { Noter ("confiance: " + $_) }
  $code = @'
import json, os, sys
p = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
os.makedirs(os.path.dirname(p), exist_ok=True)
try:
    d = json.load(open(p, encoding="utf-8-sig"))
except Exception:
    d = {}
d["skipDangerousModePermissionPrompt"] = True
open(p, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
'@
  $f = Join-Path $Tmp 'reglage.py'
  [IO.File]::WriteAllText($f, $code, (New-Object System.Text.UTF8Encoding $false))
  & $Py $f
  & $Py $Valider --adapter-poste --python $Py 2>&1 | ForEach-Object { Noter ("adaptation: " + $_) }
  $poste = @{ python = $Py; claude = $Claude; git_bash = $GitBash; installe_le = (Get-Date -Format s) } | ConvertTo-Json
  [IO.File]::WriteAllText((Join-Path $Run 'poste.json'), $poste, (New-Object System.Text.UTF8Encoding $false))
  Bilan 'Réglages : dossier déclaré de confiance, aucune demande d''autorisation.'
}

# ---------------------------------------------------------------- 7. mémoire de l'équipe (base cerebro)
if ($Py) {
  $Cerebro = Join-Path $Racine '.equipe\cerebro\cerebro.py'
  $env:PYTHONIOENCODING = 'utf-8'
  if (-not (Test-Path -LiteralPath (Join-Path $Racine '.equipe\cerebro\cerebro.db'))) {
    & $Py $Cerebro init 2>&1 | ForEach-Object { Noter ("cerebro init: " + $_) }
    & $Py $Cerebro import-exports 2>&1 | ForEach-Object { Noter ("cerebro import: " + $_) }
    Bilan 'Mémoire de l''équipe : reconstituée.'
  } else { Bilan 'Mémoire de l''équipe : déjà en place.' }
}

# ---------------------------------------------------------------- 8. raccourci « Mon équipe » sur le bureau
try {
  $bureau = [Environment]::GetFolderPath('Desktop')
  $lnk = Join-Path $bureau ('Mon ' + [char]0x00E9 + 'quipe.lnk')   # « Mon équipe » sans dépendre de l'encodage du fichier
  $ws = New-Object -ComObject WScript.Shell
  $sc = $ws.CreateShortcut($lnk)
  $sc.TargetPath = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
  $sc.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $Racine '.equipe\scripts\lanceurs\Mon-equipe.ps1') + '"'
  $sc.WorkingDirectory = $Racine
  $sc.Description = 'Ouvrir mon équipe'
  $sc.IconLocation = (Join-Path $env:SystemRoot 'System32\imageres.dll') + ',117'
  $sc.Save()
  Bilan 'Raccourci « Mon équipe » : sur le bureau.'
} catch { Noter ("raccourci en échec : " + $_); Bilan 'Raccourci : non créé (ouvrir le fichier Mon-equipe.bat dans le dossier .equipe\scripts\lanceurs).' }

# ---------------------------------------------------------------- 9. entretien automatique (Planificateur de tâches, utilisateur)
if ($Py) {
  $Pyw = Join-Path (Split-Path -Parent $Py) 'pythonw.exe'
  if (-not (Test-Path -LiteralPath $Pyw)) { $Pyw = $Py }
  $cycle = Join-Path $Racine '.equipe\scripts\entretien\cycle.py'
  $user = "$env:USERDOMAIN\$env:USERNAME"
  try { $user = [Security.Principal.WindowsIdentity]::GetCurrent().Name } catch {}
  function Esc([string]$s) { return [Security.SecurityElement]::Escape($s) }
  $declencheurs = @"
    <LogonTrigger><Enabled>true</Enabled><UserId>$(Esc $user)</UserId><Delay>PT2M</Delay></LogonTrigger>
    <SessionStateChangeTrigger><Enabled>true</Enabled><StateChange>SessionUnlock</StateChange><UserId>$(Esc $user)</UserId><Delay>PT1M</Delay></SessionStateChangeTrigger>
    <EventTrigger><Enabled>true</Enabled><Subscription>&lt;QueryList&gt;&lt;Query Id="0" Path="System"&gt;&lt;Select Path="System"&gt;*[System[Provider[@Name='Microsoft-Windows-Power-Troubleshooter'] and EventID=1]]&lt;/Select&gt;&lt;/Query&gt;&lt;/QueryList&gt;</Subscription><Delay>PT2M</Delay></EventTrigger>
    <IdleTrigger><Enabled>true</Enabled></IdleTrigger>
"@
  $minimal = @"
    <LogonTrigger><Enabled>true</Enabled><UserId>$(Esc $user)</UserId><Delay>PT2M</Delay></LogonTrigger>
    <TimeTrigger><Enabled>true</Enabled><StartBoundary>2026-01-01T09:00:00</StartBoundary><Repetition><Interval>PT3H</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition></TimeTrigger>
"@
  function Xml-Tache([string]$trig) {
    return @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.3" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Entretien automatique de Mon equipe (rattrapage, sauvegarde, classement).</Description></RegistrationInfo>
  <Triggers>
$trig
  </Triggers>
  <Principals><Principal id="Author"><UserId>$(Esc $user)</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings><Duration>PT10M</Duration><WaitTimeout>PT1H</WaitTimeout><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>
    <Enabled>true</Enabled>
    <Hidden>true</Hidden>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec><Command>$(Esc $Pyw)</Command><Arguments>"$(Esc $cycle)" --complet</Arguments><WorkingDirectory>$(Esc $Racine)</WorkingDirectory></Exec>
  </Actions>
</Task>
"@
  }
  $ok = $false
  foreach ($t in @($declencheurs, $minimal)) {
    try {
      Register-ScheduledTask -TaskName 'MonEquipe-Entretien' -Xml (Xml-Tache $t) -Force -ErrorAction Stop | Out-Null
      $ok = $true; break
    } catch { Noter ("tâche planifiée refusée : " + $_) }
  }
  if ($ok) { Bilan 'Entretien automatique : programmé (ouverture de session, sortie de veille, inactivité).' }
  else { Bilan 'Entretien automatique : non programmé ; il se fera à chaque ouverture de l''équipe.' }
}

# ---------------------------------------------------------------- 10. zone machine cachée (Mustafa ne voit que « Bureau » et le raccourci)
foreach ($n in @('.equipe', '.claude', '.git', '.mcp.json', '.gitignore', 'CLAUDE.md', 'constitution.md')) {
  $p = Join-Path $Racine $n
  if (Test-Path -LiteralPath $p) { try { (Get-Item -LiteralPath $p -Force).Attributes = (Get-Item -LiteralPath $p -Force).Attributes -bor [IO.FileAttributes]::Hidden } catch {} }
}
foreach ($d in @('A-deposer', 'Deposes', 'Livrables', 'Modeles', 'Informatique')) {
  New-Item -ItemType Directory -Force -Path (Join-Path $Racine "Bureau\$d") | Out-Null
}
Bilan 'Dossier « Bureau » : prêt (A-deposer pour vos documents, Livrables pour les documents produits).'

# ---------------------------------------------------------------- 11. validation de la configuration et premier entretien
if ($Py) {
  $v = & $Py $Valider --sans-session --copier 2>&1 | Select-Object -Last 1
  Noter ("validation: " + $v)
  if ("$v" -match '"ok": true') { Bilan 'Vérification de la configuration : réussie.' }
  else { Bilan 'Vérification de la configuration : un point sera corrigé automatiquement au premier lancement.' }
  try {
    $env:CEREBRO_BACKGROUND = '1'
    Start-Process -FilePath $Pyw -ArgumentList @('"' + $cycle + '"', '--complet') -WorkingDirectory $Racine -WindowStyle Hidden | Out-Null
  } catch {} finally { Remove-Item Env:\CEREBRO_BACKGROUND -ErrorAction SilentlyContinue }
}

# ---------------------------------------------------------------- rapport final
Dire ''
Dire '==================== Installation terminée ===================='
foreach ($l in $Rapport) { Dire ('- ' + $l) }
Dire ''
Dire 'Pour commencer : double-cliquez sur « Mon équipe » sur le bureau.'
Dire 'Au tout premier lancement, Claude peut demander de se connecter : connectez-vous avec votre compte.'
Dire '================================================================'
try { [IO.File]::WriteAllLines((Join-Path $Run 'rapport-installation.txt'), $Rapport, (New-Object System.Text.UTF8Encoding $true)) } catch {}
exit 0
