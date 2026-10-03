# Rapport de chantier — plomberie (T-012 à T-016, T-031 partie entretien) · 2026-10-03

## Fait
| Élément | Fichier(s) | État |
|---|---|---|
| Dispatcher unique des hooks (SessionStart, UserPromptSubmit, Stop, PreCompact, SessionEnd, PostToolUse, Observer) | `.claude/hooks/hook.py`, `.claude/hooks/vocabulaire-technique.txt` | testé |
| Socle commun (chemins, journal, lancement détaché Windows/POSIX priorité basse, verrou PID + péremption, incidents) | `.equipe/scripts/entretien/fond.py` | testé |
| Réglages projet | `.claude/settings.json` (bypassPermissions, allow large, 0 deny, hooks en forme exec `python3 ${CLAUDE_PROJECT_DIR}/.claude/hooks/hook.py <Evt>`, timeout 10 s, `enableAllProjectMcpServers`, `model: opus`, `effortLevel: high`) | validé (session de contrôle) |
| MCP projet | `.mcp.json` : cerebro (python3 .equipe/cerebro/mcp_server.py, initialize + tools/list vérifiés), playwright (`npx -y @playwright/mcp@latest --help` OK), markitdown (`uvx markitdown-mcp --help` OK) | vérifié |
| Validation §0.10 | `.equipe/scripts/valider_config.py` (a) JSON + absence deny/PreToolUse/PermissionRequest/disableAllHooks/CEREBRO_BACKGROUND, (b) chaque hook seul sur entrée simulée < 2 s sur copie de la base, (c) `claude -p ok` borné, preuve que les hooks ont tourné (journal `controle` à jeton), (d) copie dans `config-valide/` ; sinon restauration + incident. Options `--sans-session` (sans copie sauf `--copier`), `--lancement`, `--restaurer`, `--confiance`, `--adapter-poste` | exécuté réellement : OK, 7 s, 0 refus, hooks vus SessionStart/UserPromptSubmit/Stop/SessionEnd, 0,12 $ |
| Greffier | `.equipe/roles/greffier.md` (ROLE-044), `.equipe/scripts/entretien/greffier.py` (verrou, lot ≤ 20 000 car. par l'entrée standard, état `inbox/_etat-greffier.json`, `cerebro mesure`, `--simuler`, `--marquer-tout`) | testé réellement (haiku, 3 captures fictives, racine jetable) : 64 s, 22 918 tokens, 0,13 $, E-004/DL-004/DOC-0005/ENG-002 créés, bavardage ignoré |
| Intendant | `.equipe/roles/intendant.md` (ROLE-045), `entretien/intendant.py` (désarme deny/ask/PreToolUse/PermissionRequest/disableAllHooks/mode restrictif → observation journalisée ; hook en échec répété ; valider --sans-session ; incidents simples ; disque 80 % ; MCP sans exécutable) | testé |
| Cycle d'entretien | `.equipe/roles/entretien.md` (ROLE-046), `entretien/cycle.py` (`--rattrapage/--court/--complet/--increment/--une-passe`), `entretien/fin_session.py` | testé |
| Lanceurs | `.equipe/scripts/lanceurs/Mon-equipe.bat`, `Mon-equipe.ps1` (UTF-8 BOM), `Mon-equipe.command`, `mon-equipe.sh` | sh testé ; ps1 testé sous pwsh 7 Linux avec faux claude |
| Installateurs | `Installer.bat` (racine, demandé par l'orchestrateur), `.equipe/scripts/installer.ps1` (UTF-8 BOM, CRLF), `installer.sh`, `installer.command` | sh exécuté (racine + HOME jetables, 2 fois) ; ps1 analysé (0 erreur) et exécuté à blanc sous pwsh Linux `-SansReseau` |
| Guide d'installation | `Bureau/Informatique/INSTALLATION.md` | réécrit |
| Tests | `.equipe/tests/test_plomberie.py` | 26/26 OK (6 passes consécutives) |

Enregistré dans la base réelle : ROLE-044 greffier, ROLE-045 intendant, ROLE-046 entretien ; CAP-034 MCP playwright, CAP-035 MCP markitdown, CAP-036 MCP cerebro, CAP-037 hooks non bloquants, CAP-038 cryptography, CAP-039 uv/uvx. INC-001/INC-002 (validations ratées pendant la mise au point) résolus.

### Détails de conception
- Hooks : sortie immédiate si `CEREBRO_BACKGROUND` ; try global (y compris import du socle) ; garde-fou 1,7 s (`os._exit(0)`) ; sortie JSON écrite en une fois à la fin ; mesures 30 à 130 ms. Contexte via `cb.brief` en processus (même code que `cerebro context`). « Entre nous » : le drapeau du tour ne garde pas le message, Stop n'écrit rien, le filtre ne journalise rien.
- Stop : capture `inbox/AAAA-MM-JJ.jsonl` (ajout seul) ; filtre de vocabulaire (liste éditable, journal `vocabulaire.jsonl`, jamais de réécriture) ignoré si interlocuteur technicien (présentation, code, commande, ≥ 3 termes) ; greffier détaché tous les 15 échanges ; un incrément d'entretien détaché à chaque fin de réponse (temps mort ; sort aussitôt si la file est vide).
- PostToolUse : lit l'en-tête du fichier touché, `UPDATE objets SET a_regenerer=1` via `cb.core` (aucune sous-commande cerebro ajoutée).
- Drapeaux : `.equipe/run/mustafa-ecrit` (pause du cycle), `run/sans-fond` ou `CEREBRO_CONTROLE` (aucun job de fond ; la session de contrôle n'écrit rien dans inbox et travaille sur une copie de la base).
- Cycle : file `file_entretien` triée 1→6, incréments de 120 s reprenables, pause si Mustafa écrit, cadences 7 j (rappel, bloc cardinal, revue hebdomadaire) et 30 j (test de restauration, découverte) au premier cycle venu (état `cadences`), cycle complet si > 20 h. Tâches script : intendant, regen, sommaires, vues client, croisements, coverage/gc, rappel, cardinal, santé, brief, sauvegarde chiffrée (Fernet, clé `~/.cerebro/cle-sauvegarde.key`, 14 copies, copie `sqlite3.backup`), test de restauration, export, commit+push (verrou git), ingesteur, initiative, greffier, `gabarits` (gabarits.py --inscrire), `bibliotheque_mise_a_jour` (fedlex.py priorites si la LIFD est absente du poste, puis mise_a_jour.py), `tests_cerebro` (échec → incident + ticket). Tâches de modèle sans script (revue_hebdomadaire, construction, decouverte*, bibliotheque_maj…) laissées en file. Ligne « rattrapé » écrite dans l'état `rattrape` (lue par le brief). `CEREBRO_SANS_MODELE` / `CEREBRO_SANS_RESEAU` pour les tests.
- Windows : hooks en forme exec (Claude Code substitue `${CLAUDE_PROJECT_DIR}` lui-même, pas de shell) ; l'installateur remplace `python3` par le chemin réel de python.exe (`--adapter-poste`, aussi pour le MCP cerebro) puis recopie la configuration valide ; le lanceur répare au démarrage (JSON cassé → restauration ; interpréteur introuvable ou alias WindowsApps → adaptation).

## Testé
- `python .equipe/tests/test_plomberie.py` : 26/26 OK — chaque hook < 2 s et JSON valide ; erreur interne simulée et base illisible → succès vide + journal ; entrée vide ; anti-récursion ; lancement détaché ; entre nous sans trace ; capture ; filtre journalise sans réécrire ; technicien ignoré ; greffier tous les 15 ; settings sans deny ; validation sans session ; settings.json corrompu restauré au lancement ; hook en échec → refus + restauration ; lanceur Linux (faux claude) : restauration + `--dangerously-skip-permissions` ; intendant désarme ; cycle une passe/complet (sauvegarde chiffrée restaurée) ; verrou ; pause.
- `valider_config.py` réel avec session de contrôle : OK (voir plus haut).
- `installer.sh` réel dans racine + HOME jetables : confiance posée, skipDangerousModePermissionPrompt, base reconstituée, raccourci .desktop, plugin `document-skills@anthropic-agent-skills` installé, validation OK, cycle complet lancé ; deuxième passage idempotent.

## Écarts et décisions
- **Hooks déjà actifs dans la session de construction** : Claude Code recharge les hooks à chaud ; ils ont commencé à tourner dans la session de l'orchestrateur. J'ai posé `.equipe/run/sans-fond` (aucun greffier, entretien, commit ni push lancé par les hooks pendant la construction). L'orchestrateur a de son côté mis `env.CEREBRO_BACKGROUND=1` dans `.claude/settings.local.json` (non suivi) ; la validation le détecte et contrôle alors la configuration livrée seule (`--setting-sources project`).
- **Machine distante** : le hook Stop de l'environnement (« commit and push ») fait boucler une session `claude -p` dans un dépôt modifié ; la session de contrôle exclut donc la source `user` quand `CLAUDE_CODE_REMOTE` est défini, et est bornée (`--max-turns 2`, `--append-system-prompt` « réponds ok »). Sur le poste, toutes les sources sont chargées.
- `cerebro queue done` viole l'unicité `(tache,arg,statut)` quand une tâche identique a déjà été faite : le cycle utilise sa propre fonction `terminer()` (efface l'ancienne ligne de même statut). **Correctif à faire dans `cb/brief.py`** (hors périmètre).
- Marketplace `anthropics/skills` ajoutée dans l'environnement de construction (vérification du nom : `anthropic-agent-skills`) ; plugin non installé ici.
- Une clé de sauvegarde de test existe dans `~/.cerebro/` du conteneur (sans conséquence).

## Pour l'orchestrateur (hors périmètre, à faire)
1. Fin de construction : supprimer `.equipe/run/sans-fond` et `env.CEREBRO_BACKGROUND` de `.claude/settings.local.json` ; marquer les captures de construction comme traitées : `python .equipe/scripts/entretien/greffier.py --marquer-tout`.
2. DOSSIER-TECHNIQUE §2 : ajouter « hooks en forme exec (`command` + `args`, `${CLAUDE_PROJECT_DIR}` substitué par Claude Code) ; Claude Code recharge les hooks à chaud ; `claude plugin install … -y` requis hors terminal ; marketplace anthropics/skills = `anthropic-agent-skills` ».
3. Corriger `queue_done` (voir écarts).

## Dette / reste à faire sur le poste Windows
- `installer.ps1` jamais exécuté sous Windows : vérifier winget `--scope user` (Python, Git, Node), repli python.org 3.12.8, PortableGit (extraction 7z SFX `-o… -y` + post-install.bat), `irm https://claude.ai/install.ps1 | iex` en fenêtre cachée, tâche planifiée XML (LogonTrigger, SessionUnlock, EventTrigger sortie de veille, IdleTrigger ; repli connexion + toutes les 3 h), raccourci « Mon équipe.lnk » (COM, `[char]0x00E9`), attribut caché, plugin document-skills, poppler (zip GitHub oschwartz10612), Node zip.
- Vérifier que Claude Code Windows exécute bien les hooks en forme exec avec le chemin absolu de python.exe, et que `Bash(cerebro:*)` trouve `cerebro` sous Git Bash (`CEREBRO_PYTHON` posé en variable utilisateur).
- LibreOffice : non installé (admin en général) ; noté optionnel.
- Greffier : la consigne « [à confirmer] si incertain » n'a pas été appliquée par haiku sur « je crois qu'il s'appelle » → révision du rôle par la fabrique si l'écart se répète.
- Coût du chantier : ≈ 0,9 $ d'appels réels (greffier 0,13 ; sessions de contrôle ≈ 0,6 ; essais haiku 0,03).
