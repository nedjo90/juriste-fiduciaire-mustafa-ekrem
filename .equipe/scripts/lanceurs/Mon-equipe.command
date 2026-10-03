#!/bin/bash
# Lanceur « Mon équipe » (macOS) : double-clic dans le Finder → Terminal dans le dossier du projet.
ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# raccourci copié sur le bureau : le chemin du projet est écrit à côté par l'installateur
if [ ! -f "$ICI/mon-equipe.sh" ] && [ -f "$HOME/.mon-equipe-racine" ]; then
  ICI="$(cat "$HOME/.mon-equipe-racine")/.equipe/scripts/lanceurs"
fi
exec /bin/bash "$ICI/mon-equipe.sh" "$@"
