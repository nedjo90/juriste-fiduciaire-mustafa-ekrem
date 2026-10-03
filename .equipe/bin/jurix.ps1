# « jurix » tapé dans PowerShell : bannière, puis JURIX (même chose que « claude »)
if ($args.Count -eq 0) {
  Write-Host ''
  Write-Host '   ░▒▓█  J U R I X  █▓▒░' -ForegroundColor Cyan
  Write-Host '   cabinet augmenté · droit suisse · en ligne' -ForegroundColor DarkCyan
  Write-Host ''
}
& (Join-Path $PSScriptRoot 'claude.cmd') @args
exit $LASTEXITCODE
