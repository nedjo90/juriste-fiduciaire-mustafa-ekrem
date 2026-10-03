# Lanceur « Mon équipe » (Windows, PowerShell 5.1+). Fichier UTF-8 avec BOM.
# 1. se place dans le dossier du projet, ajoute .equipe\bin au PATH ;
# 2. contrôle rapide de la configuration (restaure la dernière configuration valide si elle est cassée) ;
# 3. vérifie que Claude Code démarre (claude --version), sinon restaure et réessaie ;
# 4. lance l'entretien en arrière-plan (un seul à la fois, verrou) puis Claude Code en mode automatique.
$ErrorActionPreference = 'Continue'
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false } catch {}
$Racine = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
Set-Location -LiteralPath $Racine
$env:PATH = (Join-Path $Racine '.equipe\bin') + ';' + $env:PATH
$Journal = Join-Path $Racine '.equipe\run\lanceur.log'
New-Item -ItemType Directory -Force -Path (Join-Path $Racine '.equipe\run') | Out-Null
function Noter([string]$m) { try { Add-Content -LiteralPath $Journal -Value ((Get-Date -Format s) + ' ' + $m) -Encoding UTF8 } catch {} }

# interpréteur Python et Claude Code repérés par l'installateur (.equipe\run\poste.json), sinon recherche
$Py = $null; $Claude = $null
$Poste = Join-Path $Racine '.equipe\run\poste.json'
if (Test-Path -LiteralPath $Poste) {
  try { $p = Get-Content -LiteralPath $Poste -Raw -Encoding UTF8 | ConvertFrom-Json; $Py = $p.python; $Claude = $p.claude
        if ($p.git_bash) { $env:CLAUDE_CODE_GIT_BASH_PATH = $p.git_bash } } catch {}
}
if (-not $Py -or -not (Test-Path -LiteralPath $Py)) {
  $c = Get-Command python.exe -ErrorAction SilentlyContinue | Where-Object { $_.Source -notmatch 'WindowsApps' } | Select-Object -First 1
  if ($c) { $Py = $c.Source }
}
if (-not $Claude -or -not (Test-Path -LiteralPath $Claude)) {
  $c = Get-Command claude -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($c) { $Claude = $c.Source } elseif (Test-Path (Join-Path $env:USERPROFILE '.local\bin\claude.exe')) { $Claude = Join-Path $env:USERPROFILE '.local\bin\claude.exe' }
}
if ($Py) { $env:CEREBRO_PYTHON = $Py }
$Valider = Join-Path $Racine '.equipe\scripts\valider_config.py'

if ($Py) { $r = & $Py $Valider --lancement 2>&1; Noter ('controle: ' + ($r -join ' ')) }

if (-not $Claude) {
  Write-Host ''
  Write-Host "Claude n'est pas encore installé sur cet ordinateur. Lancez d'abord l'installateur (Installer.bat), puis recommencez."
  Noter 'claude introuvable'
  Read-Host 'Appuyez sur Entrée pour fermer'
  exit 1
}

& $Claude --version *> $null
if ($LASTEXITCODE -ne 0) {
  Noter 'claude --version en échec : restauration de la configuration valide'
  if ($Py) { & $Py $Valider --restaurer | Out-Null; & $Py $Valider --lancement | Out-Null }
}

# entretien de fond (rattrapage), priorité basse, fenêtre cachée ; le verrou évite les doublons avec le hook de début
if ($Py -and -not (Test-Path -LiteralPath (Join-Path $Racine '.equipe\run\sans-fond'))) {
  $Pyw = Join-Path (Split-Path -Parent $Py) 'pythonw.exe'
  if (-not (Test-Path -LiteralPath $Pyw)) { $Pyw = $Py }
  try {
    $env:CEREBRO_BACKGROUND = '1'
    $pr = Start-Process -FilePath $Pyw -ArgumentList @('"' + (Join-Path $Racine '.equipe\scripts\entretien\cycle.py') + '"', '--rattrapage') -WorkingDirectory $Racine -WindowStyle Hidden -PassThru
    try { $pr.PriorityClass = 'BelowNormal' } catch {}
  } catch { Noter ('entretien non lancé: ' + $_) }
  finally { Remove-Item Env:\CEREBRO_BACKGROUND -ErrorAction SilentlyContinue }
}

$t0 = Get-Date
if ($args.Count -eq 0) { & $Claude --dangerously-skip-permissions 'Bonjour' } else { & $Claude --dangerously-skip-permissions @args }
$code = $LASTEXITCODE
if ($code -ne 0 -and ((Get-Date) - $t0).TotalSeconds -lt 15) {
  # démarrage raté : on revient à la dernière configuration valide et on relance une fois
  Noter ("démarrage en échec (code $code) : restauration et nouvel essai")
  if ($Py) { & $Py $Valider --restaurer | Out-Null; & $Py $Valider --lancement | Out-Null }
  if ($args.Count -eq 0) { & $Claude --dangerously-skip-permissions 'Bonjour' } else { & $Claude --dangerously-skip-permissions @args }
}
exit 0
