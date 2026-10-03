#!/bin/bash
# Lanceur de JURIX (macOS) : double-clic dans le Finder → Terminal dans le dossier du projet.
ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# raccourci copié sur le bureau : le chemin du projet est écrit à côté par l'installateur
if [ ! -f "$ICI/launch-jurix.sh" ] && [ -f "$HOME/.mon-equipe-racine" ]; then
  ICI="$(cat "$HOME/.mon-equipe-racine")/.team/scripts/launchers"
fi
exec /bin/bash "$ICI/launch-jurix.sh" "$@"
