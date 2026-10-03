# Dossier technique — équipe et « cerebro » de Mustafa Ekrem

Document lisible par un humain (informaticien ou responsable de la fiduciaire). Il décrit ce qui est installé, comment cela fonctionne, ce qui sort du poste et vers qui, et les replis choisis. Il est tenu à jour par l'équipe à chaque découverte.

## 1. Décisions consignées

| Sujet | Décision | Source |
|---|---|---|
| Autorisations Claude Code | Mode `bypassPermissions` (aucune demande d'autorisation), aucune liste `deny`, liste `allow` large en repli | Constitution §0.6 |
| Données des clients | Les conversations et requêtes de recherche transitent par les services des fournisseurs (Anthropic, serveurs de recherche, éditeurs) sans anonymisation ni restriction de contenu | Constitution §13 |
| Outils tiers | Installation autonome d'outils, skills et serveurs MCP, après lecture du code et test en isolation, inventaire obligatoire | Constitution §6.4 |
| Envois vers des tiers | Jamais d'envoi automatique : brouillons uniquement, connecteurs sans droit d'envoi quand l'éditeur le permet | Constitution §4.4, §12 |
| Stockage | Poste de Mustafa uniquement (versions locales git + sauvegarde chiffrée locale). Le dépôt `github.com/nedjo90/juriste-fiduciaire-mustafa-ekrem` est **public** : il sert à installer et mettre à jour l'équipe et ne reçoit jamais le travail ni les données de Mustafa. Un envoi n'a lieu que vers un dépôt privé explicitement ajouté sous le nom `sauvegarde`. Aucun autre cloud | Constitution §4.11 |
| Mode « entre nous » | Rien n'est écrit par l'équipe ; le transcript local de Claude Code (`~/.claude/projects/…`) existe hors de notre contrôle | Constitution §11 |

### Ce qui sort du poste, et vers qui

| Donnée | Destination | Pourquoi |
|---|---|---|
| Conversation, extraits de documents, contexte injecté | Anthropic (Claude) | Fonctionnement de l'assistant |
| Requêtes de recherche juridique | Fedlex (SPARQL public), Zefix, bger.ch, sites officiels, OpenAlex/CrossRef | Recherche de sources primaires |
| Rien des dossiers de Mustafa | — | Le dépôt public ne reçoit aucun envoi automatique ; seulement un dépôt privé `sauvegarde` s'il est configuré |
| Bibliothèque, base SQLite brute, index, archives, livrables, `Bureau/` | Restent sur le poste (non suivis par git) | Volume et confidentialité |

## 2. Fiche substrat (Claude Code 2.1.288, vérifiée le 2026-10-03)

Machine de construction : conteneur Linux distant (Ubuntu 24.04, Python 3.11, Node 22, LibreOffice). Tout ce qui est portable est construit ici et livré par git ; le reste se fait sur le poste par l'installateur.

### Mécanismes testés réellement
| Mécanisme | Résultat du test | Usage |
|---|---|---|
| Hook `SessionStart` avec `hookSpecificOutput.additionalContext` | Contexte injecté et vu par le modèle | Brief, date, état de session |
| Hook `UserPromptSubmit` (reçoit `prompt`) | Contexte injecté et vu | Injection en delta des objets cités |
| Hook `PostToolUse` (reçoit `tool_name`, `tool_input`, `tool_response`) | Déclenché | Marquage « à régénérer » |
| Hook `Stop` (reçoit `last_assistant_message`) | Déclenché | Capture de l'échange, filtre de vocabulaire |
| Hook `SessionEnd` (reçoit `reason`) | Déclenché | Consolidation, commit, push |
| `claude -p … --output-format json` | Fonctionne, `permission_denials` vide | Rôles de fond |
| `permissions.allow` d'un dossier non approuvé | **Ignoré** tant que le dossier n'est pas déclaré de confiance | L'installateur pose `projects[<chemin>].hasTrustDialogAccepted: true` dans `~/.claude.json` |
| Entrée standard de `claude -p` | Attend 3 s si rien n'est fourni | Les rôles de fond sont lancés avec `< /dev/null` (ou `$null` sous Windows) |

### Événements de hooks disponibles dans cette version
`PreToolUse, PostToolUse, PostToolUseFailure, PostToolBatch, Notification, UserPromptSubmit, UserPromptExpansion, SessionStart, SessionEnd, Stop, StopFailure, SubagentStart, SubagentStop, PreCompact, PostCompact, PreModelSwitch, PostModelSwitch, PermissionRequest, PermissionDenied, Setup, TeammateIdle, TaskCreated, TaskCompleted, Elicitation, ElicitationResult, ConfigChange, WorktreeCreate, WorktreeRemove, InstructionsLoaded, CwdChanged, FileChanged, DirectoryAdded, MessageDisplay`.
Utilisés : `SessionStart`, `UserPromptSubmit`, `Stop`, `PreCompact`, `SessionEnd`, `PostToolUse`. Jamais utilisés (constitution §0.3) : `PreToolUse` en refus, `PermissionRequest`.

### Modes d'autorisation (nom exact)
`acceptEdits`, `auto`, `bypassPermissions`, `manual`, `dontAsk`, `plan`. Le lanceur utilise `--dangerously-skip-permissions` ; `permissions.defaultMode` vaut `bypassPermissions` ; la clé utilisateur `skipDangerousModePermissionPrompt: true` évite la confirmation au premier lancement.

### Formats
- Sous-agents : `.claude/agents/<nom>.md`, en-tête YAML `name`, `description`, `tools`, `model`.
- Skills : `.claude/skills/<nom>/SKILL.md`, en-tête YAML `name`, `description` (déclenchement par la description).
- MCP projet : `.mcp.json` à la racine, ou `claude mcp add --scope project <nom> -- <commande>`.
- Plugins : `claude plugin marketplace add <dépôt>`, `claude plugin install <plugin>@<marketplace>`.
- Modèles : alias `fable`, `opus`, `sonnet`, `haiku` acceptés par `--model`. Option `--effort low|medium|high|xhigh|max`.

## 3. Incidents et replis
(tenu par l'intendant ; une ligne par incident)

- 2026-10-03 · construction · une seule branche git autorisée dans l'environnement de construction → les chantiers sont des commits et des tags sur `ccr-e8f5838b-808ukj` au lieu d'une branche chacun.
- 2026-10-03 · construction · `bger.ch` ne répond pas depuis la machine distante → repli sur les autres sources officielles, nouvel essai depuis le poste.
- 2026-10-03 · construction · OpenAlex renvoie 429 (limite d'accès automatisés) → repli CrossRef / Semantic Scholar, puis navigateur.
- 2026-10-03 · configuration · configuration refusée par la validation : session de contrôle : délai dépassé → aucune copie valide disponible
- 2026-10-03 · configuration · configuration refusée par la validation : hooks non exécutés pendant la session de contrôle : ['SessionStart', 'UserPromptSubmit'] → aucune copie valide disponible
- 2026-10-03 · connecteurs · messagerie et agenda Microsoft 365 pas encore reliés (autorisation de Mustafa à venir ; non testé avec un vrai compte sur la machine de construction) → mails déposés (.eml/.msg) comme source de la boucle d'initiative ; connexion proposée plus tard (un clic « autoriser »)

## 4. Coût de la construction
(tokens par chantier et par palier, complété à chaque étape)
