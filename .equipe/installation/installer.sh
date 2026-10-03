#!/bin/bash
# Installateur de JURIX pour macOS et Linux (constitution §2, §5). Sans droits administrateur, sans question, idempotent.
# Étapes : Python (système, sinon via uv en mode utilisateur) · bibliothèques · Git (constat) · Claude Code (installateur officiel)
#          · confiance du dossier · mode sans demande · réglages adaptés au poste · base cerebro · raccourci bureau
#          · entretien planifié (launchd sous macOS, cron sous Linux) · zone machine cachée · validation · rapport simple.
# Variables utiles (tests) : INSTALLER_SANS_RESEAU=1 (aucun téléchargement), HOME (dossier utilisateur cible).
ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RACINE="$(cd "$ICI/../.." && pwd)"
RUN="$RACINE/.equipe/run"
mkdir -p "$RUN"
LOG="$RUN/installation.log"
RAPPORT=()
SYS="$(uname -s)"
noter() { echo "$(date '+%Y-%m-%dT%H:%M:%S') $*" >> "$LOG" 2>/dev/null; }
dire() { echo "$*"; noter "$*"; }
bilan() { RAPPORT+=("$1"); noter "BILAN $1"; }
reseau() { [ -z "${INSTALLER_SANS_RESEAU:-}" ]; }
export PATH="$HOME/.local/bin:$HOME/.local/node/bin:$PATH"
TMPD="$(mktemp -d 2>/dev/null || echo /tmp)"

dire ""
dire "Installation de JURIX : cela prend quelques minutes. Vous pouvez laisser cette fenêtre ouverte."
noter "racine: $RACINE ; système: $SYS"

# ------------------------------------------------------------- 1. Python ≥ 3.10
python_ok() { [ -n "$1" ] && "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; }
PY=""; PY_DEJA=""
for c in "${CEREBRO_PYTHON:-}" "$(command -v python3)" /opt/homebrew/bin/python3 /usr/local/bin/python3 "$(command -v python)"; do
  if python_ok "$c"; then PY="$c"; PY_DEJA=1; break; fi
done
if [ -z "$PY" ] && reseau; then
  dire "Installation de Python…"
  if ! command -v uv >/dev/null 2>&1; then curl -LsSf https://astral.sh/uv/install.sh | sh >>"$LOG" 2>&1; fi
  if command -v uv >/dev/null 2>&1; then
    uv python install 3.12 >>"$LOG" 2>&1
    c="$(uv python find 3.12 2>/dev/null)"
    python_ok "$c" && PY="$c"
  fi
fi
if [ -n "$PY_DEJA" ]; then bilan "Python : déjà installé ($PY)."; elif [ -n "$PY" ]; then bilan "Python : installé ($PY)."; else bilan "Python : non installé (pas d'accès à Internet ?). Relancez l'installateur plus tard."; fi

# ------------------------------------------------------------- 2. bibliothèques (mode utilisateur)
if [ -n "$PY" ]; then
  dire "Installation des outils de documents (Word, Excel, PowerPoint, PDF, graphiques)…"
  LIBS="pyyaml python-docx openpyxl python-pptx reportlab matplotlib pandas cryptography pypdf"
  manque() { "$PY" -c "import importlib.util as u; m=[x for x in ('yaml','docx','openpyxl','pptx','reportlab','matplotlib','pandas','cryptography','pypdf') if not u.find_spec(x)]; print(' '.join(m))" 2>/dev/null; }
  if [ -n "$(manque)" ] && reseau; then
    "$PY" -m pip install --user --upgrade --disable-pip-version-check $LIBS >>"$LOG" 2>&1 \
      || "$PY" -m pip install --user --break-system-packages --disable-pip-version-check $LIBS >>"$LOG" 2>&1 \
      || { command -v uv >/dev/null 2>&1 && uv pip install --python "$PY" --system $LIBS >>"$LOG" 2>&1; }
  fi
  if ! command -v uvx >/dev/null 2>&1 && reseau; then
    "$PY" -m pip install --user uv >>"$LOG" 2>&1 || "$PY" -m pip install --user --break-system-packages uv >>"$LOG" 2>&1
  fi
  # lecture de documents (markitdown) installée d'avance : sinon son premier démarrage dépasse le délai de connexion (30 s)
  if reseau; then
    { command -v uv >/dev/null 2>&1 && uv tool install markitdown-mcp; } >>"$LOG" 2>&1 || "$PY" -m uv tool install markitdown-mcp >>"$LOG" 2>&1 || true
  fi
  M="$(manque)"
  if [ -n "$M" ]; then bilan "Outils de documents : il manque $M (nouvel essai au prochain lancement)."; else bilan "Outils de documents : prêts."; fi
  # [connecteurs] courrier Outlook (.msg) et liaison Microsoft 365 : installation séparée (un échec n'empêche pas les outils de documents)
  LIBS_COURRIER="extract-msg msal msal-extensions"
  manque_c() { "$PY" -c "import importlib.util as u; m=[x for x in ('extract_msg','msal','msal_extensions') if not u.find_spec(x)]; print(' '.join(m))" 2>/dev/null; }
  if [ -n "$(manque_c)" ] && reseau; then
    "$PY" -m pip install --user --upgrade --disable-pip-version-check $LIBS_COURRIER >>"$LOG" 2>&1 \
      || "$PY" -m pip install --user --break-system-packages --disable-pip-version-check $LIBS_COURRIER >>"$LOG" 2>&1 \
      || "$PY" -m pip install --user --break-system-packages --use-pep517 --disable-pip-version-check $LIBS_COURRIER >>"$LOG" 2>&1 \
      || { command -v uv >/dev/null 2>&1 && uv pip install --python "$PY" --system $LIBS_COURRIER >>"$LOG" 2>&1; }
  fi
  MC="$(manque_c)"
  if [ -n "$MC" ]; then bilan "Courrier Outlook et messagerie : il manque $MC (nouvel essai au prochain lancement)."; else bilan "Courrier Outlook et messagerie : prêts."; fi
  # [connecteurs] OPTIONNEL : transcription des notes vocales sur le poste (faster-whisper) ; échec = repli, jamais bloquant
  fw() { "$PY" -c "import importlib.util as u; print('ok' if u.find_spec('faster_whisper') else '')" 2>/dev/null; }
  if [ -z "$(fw)" ] && reseau; then
    "$PY" -m pip install --user --disable-pip-version-check faster-whisper >>"$LOG" 2>&1 \
      || "$PY" -m pip install --user --break-system-packages --disable-pip-version-check faster-whisper >>"$LOG" 2>&1 || true
  fi
  if [ -n "$(fw)" ]; then bilan "Notes vocales : transcription sur ce poste prête (le modèle, environ 500 Mo, se télécharge à la première note)."
  else bilan "Notes vocales : transcription non disponible sur ce poste ; l'équipe vous demandera un court résumé à la place."; fi
fi

# ------------------------------------------------------------- 3. Git
if command -v git >/dev/null 2>&1 && git --version >/dev/null 2>&1; then
  bilan "Git : prêt."
  if [ -d "$RACINE/.git" ] && [ -z "$(git -C "$RACINE" config user.name)" ]; then
    git -C "$RACINE" config user.name "Mon equipe"; git -C "$RACINE" config user.email "equipe@poste.local"
  fi
else
  bilan "Git : absent (sous macOS, accepter l'installation des outils de développement proposée par le système) ; les sauvegardes sur le dépôt attendront."
fi

# ------------------------------------------------------------- 4. Claude Code
# le VRAI Claude, quelle que soit son installation (officielle, npm, Homebrew) ; jamais la commande de l'équipe
# (.equipe/bin/claude, en tête du PATH après une première installation, qui ouvre une session)
trouver_claude() {
  for c in "${CEREBRO_CLAUDE:-}" "$HOME/.local/bin/claude" "$HOME/.claude/local/claude" /opt/homebrew/bin/claude /usr/local/bin/claude; do
    [ -n "$c" ] && [ -x "$c" ] && [ "$(cd "$(dirname "$c")" && pwd)" != "$RACINE/.equipe/bin" ] && { echo "$c"; return; }
  done
  OLDIFS="$IFS"; IFS=:
  for d in $PATH; do
    [ -n "$d" ] && [ -x "$d/claude" ] && [ "$(cd "$d" 2>/dev/null && pwd)" != "$RACINE/.equipe/bin" ] && { IFS="$OLDIFS"; echo "$d/claude"; return; }
  done
  IFS="$OLDIFS"
}
CLAUDE="$(trouver_claude)"; CLAUDE_DEJA=""
if [ -n "$CLAUDE" ]; then
  CLAUDE_DEJA=1  # déjà présent : rien n'est réinstallé ni modifié, son compte et ses réglages restent
  noter "Claude déjà installé : $CLAUDE $("$CLAUDE" --version 2>/dev/null)"
elif reseau; then
  dire "Installation de Claude…"
  curl -fsSL https://claude.ai/install.sh | bash >>"$LOG" 2>&1
  CLAUDE="$(trouver_claude)"
fi
if [ -n "$CLAUDE_DEJA" ]; then bilan "Claude : déjà installé sur cet ordinateur, gardé tel quel."
elif [ -n "$CLAUDE" ]; then bilan "Claude : installé."; else bilan "Claude : non installé (nouvel essai au prochain lancement de l'installateur)."; fi

# ------------------------------------------------------------- 4 bis. modèles de documents officiels d'Anthropic (plugin)
if [ -n "$CLAUDE" ] && reseau; then
  if ! "$CLAUDE" plugin list 2>/dev/null | grep -q document-skills; then
    "$CLAUDE" plugin marketplace list 2>/dev/null | grep -q "anthropics/skills" || "$CLAUDE" plugin marketplace add anthropics/skills >>"$LOG" 2>&1
    NOM="$("$CLAUDE" plugin marketplace list 2>/dev/null | grep -B1 "anthropics/skills" | sed -n 's/^ *> *\([^ ]*\).*/\1/p' | head -1)"
    "$CLAUDE" plugin install "document-skills@${NOM:-anthropic-agent-skills}" --scope user -y >>"$LOG" 2>&1
  fi
  if "$CLAUDE" plugin list 2>/dev/null | grep -q document-skills; then bilan "Modèles de documents (Word, Excel, PowerPoint, PDF) : prêts."
  else bilan "Modèles de documents complémentaires : non installés (nouvel essai au prochain lancement ; l'équipe a les siens)."; fi
fi

# ------------------------------------------------------------- 5. Node (navigateur automatisé, MCP Playwright) et poppler
if ! command -v npx >/dev/null 2>&1 && reseau; then
  if [ "$SYS" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
    brew install node >>"$LOG" 2>&1
  fi
  if ! command -v npx >/dev/null 2>&1; then
    # Node officiel en mode utilisateur, sans Homebrew ni droits administrateur
    ARCH="$(uname -m)"; case "$ARCH" in arm64|aarch64) NA=arm64 ;; *) NA=x64 ;; esac
    OS=linux; [ "$SYS" = "Darwin" ] && OS=darwin
    VER="$(curl -fsSL https://nodejs.org/dist/index.json 2>>"$LOG" | "$PY" -c 'import json,sys;print(next(v["version"] for v in json.load(sys.stdin) if v["lts"]))' 2>>"$LOG")"
    if [ -n "$VER" ]; then
      mkdir -p "$HOME/.local/node" "$HOME/.local/bin"
      if curl -fsSL "https://nodejs.org/dist/$VER/node-$VER-$OS-$NA.tar.gz" -o "$TMPD/node.tgz" 2>>"$LOG"; then
        tar xzf "$TMPD/node.tgz" -C "$HOME/.local/node" --strip-components 1 2>>"$LOG"
        for b in node npm npx; do ln -sf "$HOME/.local/node/bin/$b" "$HOME/.local/bin/$b"; done
      fi
    fi
  fi
fi
if command -v npx >/dev/null 2>&1; then
  # navigateur pour Playwright : Chrome s'il est installé, sinon Chromium téléchargé une fois (mode utilisateur)
  if [ "$SYS" = "Darwin" ] && [ ! -d "/Applications/Google Chrome.app" ] && reseau; then
    npx -y playwright@latest install chromium >>"$LOG" 2>&1 || true
  fi
  bilan "Navigateur automatisé : prêt."
else
  bilan "Navigateur automatisé : non installé (nouvel essai au prochain lancement ; l'équipe travaille sans)."
fi
if [ "$SYS" = "Darwin" ] && command -v brew >/dev/null 2>&1 && reseau; then
  command -v pdftotext >/dev/null 2>&1 || brew install poppler >>"$LOG" 2>&1
fi
command -v pdftotext >/dev/null 2>&1 || bilan "Lecture avancée des PDF : non installée (optionnelle)."

# ------------------------------------------------------------- 5 bis. « claude » dans n'importe quel Terminal ouvre l'équipe
BLOC_DEBUT="# >>> mon-equipe >>>"; BLOC_FIN="# <<< mon-equipe <<<"
for rc in "$HOME/.zprofile" "$HOME/.bash_profile" "$HOME/.profile"; do
  [ -f "$rc" ] || [ "$rc" = "$HOME/.zprofile" ] || [ "$rc" = "$HOME/.profile" ] || continue
  touch "$rc"
  "$PY" - "$rc" "$RACINE" "$CLAUDE" <<'PYEOF'
import sys, re
rc, racine, claude = sys.argv[1], sys.argv[2], sys.argv[3]
t = open(rc, encoding="utf-8", errors="ignore").read()
t = re.sub(r"(?s)# >>> mon-equipe >>>.*?# <<< mon-equipe <<<\n?", "", t)
q = racine.replace("'", "'\\''")
bloc = f"# >>> mon-equipe >>>\nexport PATH='{q}/.equipe/bin':\"$HOME/.local/bin:$HOME/.local/node/bin:$PATH\"\n"
if claude:  # chemin du vrai Claude, lu par la commande de l'équipe et par les tâches de fond
    bloc += "export CEREBRO_CLAUDE='" + claude.replace("'", "'\\''") + "'\n"
bloc += "# <<< mon-equipe <<<\n"
open(rc, "w", encoding="utf-8").write(t.rstrip() + ("\n\n" if t.strip() else "") + bloc)
PYEOF
done
export PATH="$RACINE/.equipe/bin:$HOME/.local/bin:$HOME/.local/node/bin:$PATH"
bilan "Commande « jurix » (ou « claude ») : ouvre JURIX depuis n'importe quel Terminal."

# ------------------------------------------------------------- 6. réglages de Claude
VALIDER="$RACINE/.equipe/scripts/valider_config.py"
if [ -n "$PY" ]; then
  "$PY" "$VALIDER" --confiance >>"$LOG" 2>&1
  "$PY" - <<'EOF' >>"$LOG" 2>&1
import json, os
p = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
os.makedirs(os.path.dirname(p), exist_ok=True)
try:
    d = json.load(open(p, encoding="utf-8-sig"))
except Exception:
    d = {}
d["skipDangerousModePermissionPrompt"] = True
open(p, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
EOF
  "$PY" "$VALIDER" --adapter-poste --python "$PY" >>"$LOG" 2>&1
  printf '{\n "python": "%s",\n "claude": "%s",\n "installe_le": "%s"\n}\n' "$PY" "$CLAUDE" "$(date '+%Y-%m-%dT%H:%M:%S')" > "$RUN/poste.json"
  bilan "Réglages : dossier déclaré de confiance, aucune demande d'autorisation."
fi

# ------------------------------------------------------------- 7. mémoire de l'équipe
if [ -n "$PY" ]; then
  export PYTHONIOENCODING=utf-8
  R_INIT="$("$PY" "$RACINE/.equipe/cerebro/cerebro.py" init --importer-si-vide 2>&1)"
  echo "cerebro init: $R_INIT" >>"$LOG"
  case "$R_INIT" in
    *'"import"'*) bilan "Mémoire de l'équipe : reconstituée." ;;
    *) bilan "Mémoire de l'équipe : en place." ;;
  esac
fi

# ------------------------------------------------------------- 8. raccourci « JURIX » sur le bureau
BUREAU_U="$HOME/Desktop"
[ -d "$HOME/Bureau" ] && [ ! -d "$HOME/Desktop" ] && BUREAU_U="$HOME/Bureau"
command -v xdg-user-dir >/dev/null 2>&1 && [ "$SYS" != "Darwin" ] && D="$(xdg-user-dir DESKTOP 2>/dev/null)" && [ -n "$D" ] && BUREAU_U="$D"
mkdir -p "$BUREAU_U"
echo "$RACINE" > "$HOME/.mon-equipe-racine"
if [ "$SYS" = "Darwin" ]; then
  rm -f "$BUREAU_U/Mon équipe.command"  # ancien nom
  cp "$RACINE/.equipe/scripts/lanceurs/Mon-equipe.command" "$BUREAU_U/JURIX.command" && chmod +x "$BUREAU_U/JURIX.command"
else
  rm -f "$BUREAU_U/mon-equipe.desktop" "$HOME/.local/share/applications/mon-equipe.desktop"  # ancien nom
  cat > "$BUREAU_U/jurix.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=JURIX
Comment=Ouvrir JURIX
Exec=bash "$RACINE/.equipe/scripts/lanceurs/mon-equipe.sh"
Path=$RACINE
Terminal=true
Icon=utilities-terminal
EOF
  chmod +x "$BUREAU_U/jurix.desktop"
  mkdir -p "$HOME/.local/share/applications" && cp "$BUREAU_U/jurix.desktop" "$HOME/.local/share/applications/" 2>/dev/null
  command -v gio >/dev/null 2>&1 && gio set "$BUREAU_U/jurix.desktop" metadata::trusted true 2>/dev/null
fi
bilan "Raccourci « JURIX » : sur le bureau."

# ------------------------------------------------------------- 9. entretien automatique
CYCLE="$RACINE/.equipe/scripts/entretien/cycle.py"
if [ -n "$PY" ]; then
  if [ "$SYS" = "Darwin" ]; then
    PL="$HOME/Library/LaunchAgents/ch.monequipe.entretien.plist"
    mkdir -p "$(dirname "$PL")"
    cat > "$PL" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>ch.monequipe.entretien</string>
  <key>ProgramArguments</key><array><string>$PY</string><string>$CYCLE</string><string>--complet</string></array>
  <key>WorkingDirectory</key><string>$RACINE</string>
  <key>EnvironmentVariables</key><dict><key>CEREBRO_BACKGROUND</key><string>1</string><key>PATH</key><string>$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string></dict>
  <key>RunAtLoad</key><true/>
  <key>StartInterval</key><integer>7200</integer>
  <key>Nice</key><integer>10</integer>
  <key>LowPriorityIO</key><true/>
  <key>ProcessType</key><string>Background</string>
</dict></plist>
EOF
    launchctl unload "$PL" >/dev/null 2>&1; launchctl load "$PL" >/dev/null 2>&1
    bilan "Entretien automatique : programmé (ouverture de session, toutes les deux heures, rattrapage après la veille)."
  elif command -v crontab >/dev/null 2>&1; then
    L1="@reboot sleep 120 && cd \"$RACINE\" && CEREBRO_BACKGROUND=1 nice -n 10 \"$PY\" \"$CYCLE\" --complet >/dev/null 2>&1 # mon-equipe"
    L2="17 */2 * * * cd \"$RACINE\" && CEREBRO_BACKGROUND=1 nice -n 10 \"$PY\" \"$CYCLE\" --complet >/dev/null 2>&1 # mon-equipe"
    { crontab -l 2>/dev/null | grep -v '# mon-equipe'; echo "$L1"; echo "$L2"; } | crontab - 2>>"$LOG" \
      && bilan "Entretien automatique : programmé (démarrage et toutes les deux heures)." \
      || bilan "Entretien automatique : non programmé ; il se fera à chaque ouverture de l'équipe."
  else
    bilan "Entretien automatique : pas de planificateur sur ce poste ; il se fera à chaque ouverture de l'équipe."
  fi
fi

# ------------------------------------------------------------- 10. zone machine cachée, zone humaine prête
if [ "$SYS" = "Darwin" ]; then
  for n in CLAUDE.md constitution.md; do [ -e "$RACINE/$n" ] && chflags hidden "$RACINE/$n" 2>/dev/null; done
fi
for d in A-deposer Deposes Livrables Modeles Informatique; do mkdir -p "$RACINE/Bureau/$d"; done
bilan "Dossier « Bureau » : prêt (A-deposer pour vos documents, Livrables pour les documents produits)."

# ------------------------------------------------------------- 11. validation, premier entretien
if [ -n "$PY" ]; then
  V="$("$PY" "$VALIDER" --sans-session --copier 2>>"$LOG" | tail -1)"
  noter "validation: $V"
  case "$V" in *'"ok": true'*) bilan "Vérification de la configuration : réussie." ;;
               *) bilan "Vérification de la configuration : un point sera corrigé automatiquement au premier lancement." ;; esac
  if [ -z "${INSTALLER_SANS_ENTRETIEN:-}" ]; then
    ( cd "$RACINE" && CEREBRO_BACKGROUND=1 nohup nice -n 10 "$PY" "$CYCLE" --complet >/dev/null 2>&1 & ) 2>/dev/null
  fi
fi

dire ""
dire "==================== Installation terminée ===================="
for l in "${RAPPORT[@]}"; do dire "- $l"; done
dire ""
dire "Pour commencer : double-cliquez sur « JURIX » sur le bureau, ou tapez jurix dans un Terminal."
dire "Au tout premier lancement, Claude peut demander de se connecter : connectez-vous avec votre compte."
dire "================================================================"
printf '%s\n' "${RAPPORT[@]}" > "$RUN/rapport-installation.txt"
exit 0
