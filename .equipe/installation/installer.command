#!/bin/bash
# Installateur de JURIX (macOS) : double-clic dans le Finder → exécute installer.sh dans un Terminal.
ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
/bin/bash "$ICI/installer.sh"
echo ""
read -r -p "Vous pouvez fermer cette fenêtre (Entrée). " _
