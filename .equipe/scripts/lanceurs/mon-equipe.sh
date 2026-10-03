#!/bin/bash
# Lanceur « Mon équipe » (Linux ; appelé aussi par Mon-equipe.command sous macOS).
# Dossier du projet, PATH += .equipe/bin, contrôle rapide de la configuration (restauration si cassée),
# vérification que Claude Code démarre, entretien en arrière-plan, puis Claude Code en mode automatique.
ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RACINE="$(cd "$ICI/../../.." && pwd)"
cd "$RACINE" || exit 0
export PATH="$RACINE/.equipe/bin:$HOME/.local/bin:$PATH"
mkdir -p "$RACINE/.equipe/run"
JOURNAL="$RACINE/.equipe/run/lanceur.log"
noter() { echo "$(date '+%Y-%m-%dT%H:%M:%S') $*" >> "$JOURNAL" 2>/dev/null; }

PY="${CEREBRO_PYTHON:-}"
if [ -z "$PY" ] && [ -f "$RACINE/.equipe/run/poste.json" ]; then
  PY="$(sed -n 's/.*"python": *"\([^"]*\)".*/\1/p' "$RACINE/.equipe/run/poste.json" | head -1)"
fi
[ -n "$PY" ] && [ -x "$PY" ] || PY="$(command -v python3 || command -v python)"
export CEREBRO_PYTHON="$PY"
VALIDER="$RACINE/.equipe/scripts/valider_config.py"
[ -n "$PY" ] && noter "controle: $("$PY" "$VALIDER" --lancement 2>&1 | tail -1)"

CLAUDE="$(command -v claude)"
if [ -z "$CLAUDE" ]; then
  echo ""
  echo "Claude n'est pas encore installé sur cet ordinateur. Lancez d'abord l'installateur, puis recommencez."
  noter "claude introuvable"
  read -r -p "Appuyez sur Entrée pour fermer " _
  exit 1
fi
if ! "$CLAUDE" --version >/dev/null 2>&1; then
  noter "claude --version en échec : restauration de la configuration valide"
  [ -n "$PY" ] && "$PY" "$VALIDER" --restaurer >/dev/null 2>&1 && "$PY" "$VALIDER" --lancement >/dev/null 2>&1
fi
# entretien de fond (rattrapage), priorité basse, détaché ; le verrou évite les doublons avec le hook de début
if [ -n "$PY" ]; then
  ( CEREBRO_BACKGROUND=1 nohup nice -n 10 "$PY" "$RACINE/.equipe/scripts/entretien/cycle.py" --rattrapage >/dev/null 2>&1 & ) 2>/dev/null
fi
T0=$(date +%s)
"$CLAUDE" --dangerously-skip-permissions "$@"
CODE=$?
if [ $CODE -ne 0 ] && [ $(( $(date +%s) - T0 )) -lt 15 ]; then
  noter "démarrage en échec (code $CODE) : restauration et nouvel essai"
  [ -n "$PY" ] && "$PY" "$VALIDER" --restaurer >/dev/null 2>&1 && "$PY" "$VALIDER" --lancement >/dev/null 2>&1
  "$CLAUDE" --dangerously-skip-permissions "$@"
fi
exit 0
