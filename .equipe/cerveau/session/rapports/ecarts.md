# Audit indépendant : écarts entre la constitution et le système construit

auditeur: sous-agent indépendant (n'a pas participé à la construction) · date: 2026-10-03 ~17:10-17:40 UTC
référence: `.equipe/constitution.md` (556 lignes, lue en entière)
état audité: branche `ccr-e8f5838b-808ukj`, HEAD `18e435d` puis `5ea8844` (« Plomberie livrée », commité pendant la rédaction) + modifications NON COMMITÉES du chantier plomberie en cours (cycle.py, installer.ps1/.sh, lanceurs, test_plomberie.py, config-valide). Le dépôt a bougé pendant l'audit (commits 5171f89 puis 18e435d) ; les constats portent sur l'état le plus récent observé.
méthode: lecture du code et des fichiers ; exécution des 5 suites de tests dans des copies jetables (`git ls-files` → scratchpad) ; tests ciblés (hooks simulés, ingestion piégée, export, clone vierge, MCP, calculs) ; **banc de bout en bout réel** (`.equipe/tests/e2e/banc.py`, vraies sessions `claude -p`, copie jetable `/tmp/banc-mustafa-gpvwo4ax`) sur 5 scénarios. Aucun fichier du dépôt modifié hormis ce rapport ; rien commité.

Légende statut : **FV** fait et vérifié · **FNV** fait non vérifié · **P** partiel · **A** absent · **I** impossible ici (raison).

---

## A. Constats majeurs vérifiés par exécution (à lire d'abord)

1. **Clone vierge = cerveau vide.** Aucun export de la base n'est commité (`git ls-files | grep export` → rien ; `.equipe/cerebro/exports/` n'existe pas). La base SQLite (13 Mo : 46 rôles, 32 skills, 16 méthodes, 28 sources BIB, 39 capacités, 11 règles de délai vérifiées, 24 barèmes, questions, conseils) n'existe que dans le conteneur de construction. Sur copie vierge : `cerebro init` + `import-exports` → `{"lignes": 0}` ; `cerebro open MET-013` → `{"erreur":"inconnu"}` ; `law article LIFD "art. 132"` → `⚠ aucune source primaire ingérée`. `test_equipe.py` → 4 échecs, `test_bibliotheque.py` → 4 échecs sur copie vierge, 18/18 et 10/10 avec la base du conteneur. L'installateur affiche pourtant « Mémoire de l'équipe : reconstituée ». **Correction en cours à la fin de l'audit** (non commitée, donc non comptée) : `brief.py` exclut désormais les tables virtuelles, `importer_exports()` réindexe les articles, et un dossier `.equipe/cerebro/exports/` (472 Ko, non suivi) vient d'apparaître. À vérifier après commit : clone vierge → `import-exports` > 0 lignes, `open MET-013` OK, `test_equipe.py` 18/18.
2. **Premier « Bonjour » de Mustafa = relance de la construction sur son abonnement.** Banc réel, scénario « ouverture » : l'associé a fait 9 appels Bash (dont `head -60 construction.md`, `sed -n 1,60p impot_anticipe.py`, `cat profil-mustafa.md`, `ls .claude/skills`, `cat SKILL.md`) avant de répondre, puis a lancé un sous-agent **general-purpose en arrière-plan (« Reprise de la construction »)** qui a lu la constitution, fait `find . -type f`, `cat` de scripts entiers, relancé toutes les suites de tests, tenté des commits (47 appels d'outils en ~4 min avant que je l'arrête). Cause : `construction.md` n'est jamais marqué « construction: achevée », le contexte de début dit « CONSTRUCTION en cours … reprendre en arrière-plan » et `CLAUDE.md` ordonne la reprise. Effets : coût massif à chaque session, et **aucune question ne sera jamais posée** (`files.py:37-46` bloque les questions tant que la construction n'est pas achevée).
3. **Coût fixe par message élevé.** Banc : « Entre nous… » (réponse de 685 tokens, aucun outil) = 42 508 tokens d'entrée ; « Bonjour » = 133 820 ; question société = 137 981 ; question de droit cantonal = 504 220 ; règle « désormais » = 223 372. Le socle fixe (invite système + CLAUDE.md et ses deux imports ≈ 9 400 car. + descriptions de 37 sous-agents et 26 skills + schémas des outils MCP playwright/markitdown/cerebro) dépasse largement le budget « début de session ≤ 8 000 car. ».
4. **Export qui pousserait la bibliothèque dans git.** `brief.export()` exclut seulement `objets_fts%` : sur copie de la base réelle, `cerebro export` écrit 25 Mo dont `articles_fts_data.json` 13 Mo, `articles_fts.json` 5,7 Mo, `articles_fts_content.json` 5,7 Mo (texte intégral des lois), non ignorés par `.gitignore`. Le premier cycle complet ou la première fin de session (`fin_session.py` → export → `commit_push`) commiterait et pousserait ces fichiers (contraire à §9.4) ; leur réimport dans des tables d'ombre FTS5 est en outre risqué. **Correctif en cours (diff non commité de `brief.py`)** : exclusion des tables virtuelles et de leurs tables internes ; à confirmer par commit et test de taille.
5. **Boucles autonomes non câblées.** La fabrique, la découverte continue, la veille, la revue hebdomadaire, la poursuite de la construction, la double lecture, le recalcul après `config set` (`horloges_recalcul`, `doctrine_cantons`, `bibliotheque_cantons`, `profil`) sont mis en file mais **aucun exécutant ne les consomme** (`cycle.py` : « laissées en file pour l'associé ou la fabrique ; le cycle ne les consomme pas » ; seuls `greffier.md` et `initiative/mission.md` sont lancés par `claude -p`). Les missions `.equipe/roles/fabricant.md`, `veilleur.md`, `tuteur.md`, `archiviste.md`, `chef-de-cabinet.md`, `ingesteur.md` ne sont lancées par aucun script.
6. **Transcription vocale, OCR, messagerie/agenda, recherche académique : absents.** Une note vocale déposée devient une tâche `lecture_modele` alors que le modèle ne lit pas l'audio (vérifié : `note.m4a` → `N-002`, nature `audio`, file `lecture_modele`). Un `.msg` Outlook glissé depuis Outlook part vers LibreOffice, qui ne convertit pas ce format → `a_lire_par_modele`.

---

## B. Tableau exigence par exigence

### §0 Règle d'or : rien ne bloque

| # | Exigence (citation courte) | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 0.1 | « Toute information manquante reçoit une valeur par défaut, inscrite dans defauts.md » | FV | `.equipe/cerveau/session/defauts.md` (18 lignes `[défaut]`) ; `config set mustafa.cantons_suivis VD,FR` → ligne `canton: VD, FR [déclaré par Mustafa le …]` réécrite (testé en racine fictive) | — |
| 0.2 | « Aucun mécanisme ne bloque » (hook, permission, porte, test) | FV | hooks : try global + `os._exit(0)` (`.claude/hooks/hook.py:304-320`) ; portes : code 0 toujours (`portes.py:7`) ; tests plomberie « Erreur interne simulée → succès vide » OK | — |
| 0.3 | « Zéro règle de refus : pas de deny, pas de hook de décision de permission, pas de filtre par motif » | FV | `settings.json` sans `deny`, aucun PreToolUse/PermissionRequest ; test plomberie « aucune liste deny, aucun hook de refus » OK | — |
| 0.4 | « Un mécanisme qui bloque est une panne : désactivé sur-le-champ, remplacé par une version qui journalise » | FV | `intendant.py:34-80` `desarmer()` ; test « liste deny et hook PreToolUse neutralisés (remplacés par une observation) » OK | Ne s'exécute qu'au cycle (pas en temps réel) |
| 0.5 | « Pendant la construction aucune protection ; protections non bloquantes à la dernière étape » | FV (par absence) | aucune empreinte/tag/verrou installé | Voir §12 (non installées) |
| 0.6a | « Lanceur avec l'option qui supprime les demandes d'autorisation » | FV | `Mon-equipe.ps1` : `& $Claude --dangerously-skip-permissions` ; `settings.json` `defaultMode: bypassPermissions` | — |
| 0.6b | « Dossier déclaré de confiance par toi » | FNV | `valider_config.py --confiance` appelé par `installer.ps1` (section 6) | I : poste Windows absent |
| 0.6c | « Liste allow large » (git, python, cerebro, claude, npx, uvx, pip, npm) | FV | `.claude/settings.json` lignes `allow` (31 entrées) | — |
| 0.6d | « Une demande d'autorisation qui apparaît malgré tout est un incident journalisé » | A | aucun hook `PermissionRequest` en mode observation ; rien ne détecte une demande | Hook d'observation `PermissionRequest`/`Notification` qui fait `incident add` (jamais de décision) |
| 0.7 | « Source inaccessible, installateur admin, modèle payant → repli inscrit dans DOSSIER-TECHNIQUE, et continuer » | P | `DOSSIER-TECHNIQUE.md §3` : bger.ch KO, OpenAlex 429 notés ; `fond.incident()` écrit dans §3 | Pas de repli effectif pour OpenAlex (aucun script CrossRef/Semantic Scholar) |
| 0.8 | « Limite d'usage atteinte : sauvegarde, phrase simple, reprise automatique » | A | `grep -ri "rate.limit\|usage limit\|plus tard"` sur scripts, cerebro, rôles → rien | Détection des erreurs de limite dans `initiative.py`/`greffier.py` (code/texte de `claude -p`), report en file, consigne dans `associe.md` |
| 0.9 | « Interlocuteur technicien → réponse technique ; filtre ne bloque ni ne réécrit » | FV | `hook.py:156-166` `interlocuteur_technicien()` ; test « ignoré si l'interlocuteur est technicien » OK | — |
| 0.10a | « JSON relu par script » | FV | `valider_config.py` étape a ; exécuté : `"a_json": "ok"` | — |
| 0.10b | « Chaque hook exécuté seul, succès < 2 s » | FV | exécuté : `b_hooks` 31-49 ms par événement | — |
| 0.10c | « Session de contrôle non interactive démarre, répond, se termine » | FV | exécuté dans copie jetable : `c_session: code 0, resultat "ok", 7,7 s, hooks_vus [SessionEnd, SessionStart, Stop, UserPromptSubmit]` | — |
| 0.10d | « Seulement alors commit ; échec → retour version précédente + incident » | P | copie dans `config-valide/` + restauration testée (tests plomberie 18-19) | Le commit n'est pas conditionné à la validation (le cycle `commit_push` fait `git add -A` sans validation préalable) |
| 0.10e | « Copie de la dernière config valide ; lanceur la restaure si Claude ne démarre pas » | FV | `config-valide/manifeste.json` ; `Mon-equipe.ps1` : `--lancement`, `--restaurer` si code ≠ 0 en < 15 s ; test « settings.json corrompu → restauré au lancement » OK | Sous Windows non exécuté (I) |
| 0.11 | « Règles cardinales pour les rôles, jamais pour le démarrage » | FV | bloc cardinal dans chaque rôle/skill ; aucun mécanisme de démarrage n'en dépend | — |

### §0 bis Prêt à l'emploi ; questions et conseils

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 0b.1 | « Le démarrage ne pose aucune question » | FV | banc « ouverture » : `q=0 confirm=0` ; `files.py:37-46` | — |
| 0b.2 | defauts.md créé dès l'étape 0 | FV | fichier présent, commit c8b915f | — |
| 0b.3 | profil-mustafa.md avec `[défaut]` | FV | `.equipe/cerveau/cabinet/profil-mustafa.md` (7 marqueurs défaut) | Pas mis à jour après `config set` (tâche `profil` jamais consommée) |
| 0b.4 | environnement.md, complété par détection | P | `environnement.md` : poste Windows [défaut] | L'installateur ne détecte ni Outlook, ni Office, ni navigateur, ni chiffrement du disque (`grep -i outlook installer.ps1` → rien) |
| 0b.5 | DOSSIER-TECHNIQUE et INSTALLATION complétés à chaque découverte | P | les deux fichiers existent (65 et 46 lignes) | §4 « Coût de la construction » vide ; INSTALLATION ne dit pas que la mémoire et la bibliothèque seront vides au premier lancement |
| 0b.6 | « Une valeur réelle remplace le défaut et tout ce qui en dépend est recalculé » | P | `config set` → `recalculs: [horloges_recalcul, doctrine_cantons, bibliotheque_cantons, profil]` mis en file | Ces tâches ne sont dans `TACHES` d'aucun exécutant : jamais recalculé (seul `gabarits` l'est, ajout en cours) |
| 0b.7 | Table `questions_ouvertes` type métier/technique, besoin, défaut, priorité, formulation | FV | 11 questions en base réelle, champs complets | Type `config` utilisé au lieu de `métier`/`technique` (mineur) |
| 0b.8 | « Aucune question pendant la première session ni la construction » | FV | test_cerebro c36 OK ; `files.py:37` | Effet pervers : construction jamais déclarée achevée ⇒ jamais de question (constat A2) |
| 0b.9 | « Une question au plus par message, au plus trois par jour, jamais deux fois le même jour, une fois/semaine puis abandon » | FV | `files.py:49-90` ; tests c36 ×4 OK | « une par message » repose sur l'associé (`associe.md`), le brief peut aussi en contenir une |
| 0b.10 | Questions techniques en langage simple, un mot | FV | formulations Q-001…Q-011 (« Votre messagerie, c'est Outlook ? ») | Q-011 se termine par « Vous voulez qu'on le fasse maintenant ? » (confirmation déguisée) |
| 0b.11 | Table `conseils`, ≤ 1/jour, dédupliqué, classé par gain, abandon après deux ignorés | FV | `files.py:115-140` (`nb_ignore>=2 → abandonne`) ; 2 conseils en base | — |
| 0b.12 | Fichiers YAML à trous (cabinet, mustafa, poste, acces, modeles, clients) avec valeur/defaut/source/question | FV | `.equipe/config/*.yaml` (6 fichiers, 4 champs + `effet`) | — |
| 0b.13 | `cerebro config set` recalcule et met à jour le sommaire | P | voir 0b.6 ; sommaire niveau 0 non modifié | Régénération du sommaire après `config set` |
| 0b.14 | `cerebro config gaps` classé par effet = source de la file | FV | exécuté : liste classée effet 5→3 ; `question from-gaps` | — |
| 0b.15 | Rapport de santé affiche le taux de remplissage | FV | `health` → `config_remplie` | — |
| 0b.16 | Rodage deux semaines : priorité aux questions à effet | FV | `files.py:64` (`premiere_session_le`, 14 jours) | — |

### §0 ter Le sommaire, point central

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 0t.1 | Protocole écrit en tête de chaque fichier de rôle et de skill | FV | 37 agents, 26 skills, 9 missions : `BLOC-CARDINAL v…` + `PROTOCOLE SOMMAIRE` (boucle grep : bloc=1 proto=1 partout) ; `cardinal check` vide | — |
| 0t.2 | « Entrer par le sommaire : niveau 0 puis niveau 1 ; rien d'autre » | P | contexte de début contient le niveau 0 ; banc « contexte-societe » : `summary`/`open --section` uniquement (conforme) | Banc « ouverture » : `head -60 construction.md`, `cat profil-mustafa.md`, `ls .claude/skills`, `cat SKILL.md`, `sed -n 1,60p script` ; sous-agent de construction : `find . -type f`, `cat` intégraux |
| 0t.3 | « find → summary → open --section ; jamais de listing, jamais de fichier entier » | P | outils présents et rapides (find 0,11 s, summary 0,08 s) ; `open` sans `--section` renvoie tout le corps (banc : `$B open M-001` sans section) | `open` sans `--section` devrait renvoyer le menu ; le protocole n'est pas suivi par le sous-agent général |
| 0t.4 | « Réutiliser l'existant » | P | consigne dans chaque rôle (`find --type position`) | Non mesuré ; aucune porte « travail refait » |
| 0t.5 | « Affirmer seulement ce qui est lié (ID ou ⚠) » | P | porte `p_sources.py` (motifs) | Ne s'applique qu'aux livrables, pas aux réponses de conversation |
| 0t.6 | « Sortir par le sommaire : en-tête et ligne régénérés avant la fin du tour » | P | hook PostToolUse marque `a_regenerer` (testé) ; `regen` au cycle | Si l'agent écrit sans en-tête `id:` rien n'est marqué ; aucune vérification de fin de tour |
| 0t.7 | Rapport de sous-agent ≤ 1 500 car., IDs + lignes | FV (consigne) | test_equipe « chaque sous-agent impose un rapport ≤ 1 500 caractères » OK | Non contrôlé à l'exécution |
| 0t.8 | « Pendant la construction aussi : tout reçoit un ID et une ligne ; tableau de bord = vue du sommaire » | P | rôles, skills, méthodes, gabarits, capacités enregistrés (base du conteneur) | `construction.md` et `backlog.md` tenus à la main (non issus de la base) ; rapports de chantier sans ID ; backlog périmé (T-001…T-110 « todo » alors que faits) |
| 0t.9 | SOMMAIRE.md manuel à l'étape 0 puis importé | FV | `init --import-provisoire` ; `.equipe/sommaires/SOMMAIRE.md` généré | — |
| 0t.10 | « L'archiviste vérifie à chaque cycle que chaque agent a appliqué le protocole (ouvertures journalisées, objets touchés régénérés) ; agent en écart révisé par la fabrique » | A | `ouvertures` ne compte que les excès (>5/tour) dans `health` ; aucune analyse par agent ; mission archiviste jamais lancée | Script de conformité par rôle (ouvertures, régénérations, lectures hors CLI via transcripts) + file `fabrique` |

### §0 quater Règles cardinales partout

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 0q.1 | Bloc cardinal ≤ 2 000 car., généré depuis la constitution, inséré partout, importé par CLAUDE.md | P | `bloc-cardinal.md` 1 717 car. ; `CLAUDE.md` `@.equipe/cerveau/cabinet/bloc-cardinal.md` ; version = empreinte des §1 et §0 ter (`cardinal.py:26-38`) | Texte condensé à la main (pas généré) ; une modification de la constitution change l'empreinte mais pas le texte |
| 0q.2 | « Une version périmée est remplacée au cycle suivant » | FV | tâche `cardinal` cadence 7 j dans `cycle.py` | Cadence hebdomadaire, pas « cycle suivant » |
| 0q.3 | Outillage qui rend la règle naturelle (créer = ID+en-tête+ligne+liens) | FV | `cerebro new` (test c26) | — |
| 0q.4 | Portes de correction | P | voir §7.5 | — |
| 0q.5 | « Tableau de bord des principes à chaque cycle ; fabrique révise ce qui dérive » | P | `portes/tableau.py` | Non appelé par `cycle.py` ; fabrique non câblée |
| 0q.6 | « Au moins un test par loi et un test du protocole sommaire, rejoués à chaque création ou révision d'agent » | P | test_equipe vérifie la présence des déclarations (L1-L10 → portes) | Aucun test comportemental par loi ; rien ne rejoue à la création d'un agent |

### §1 Les dix lois

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 1.1 | Dix lois injectées telles quelles en tête de chaque rôle, skill, sous-agent, exécution de fond | P | bloc présent partout ; `initiative.py prompt()` préfixe `X.bloc()` ; `greffier.py` envoie `greffier.md` (bloc inclus) | Lois reformulées (raccourcies), pas « telles quelles » |
| 1.2 | Loi 3 « jamais à vide, tout mesuré » | P | initiative : aucun appel si rien à faire ; `mesures` alimentée par initiative/greffier/portes | Coût de l'associé non mesuré ; base réelle `mesures` = 0 ligne |
| 1.3 | Départage (3 et 4 ne violent jamais 5-7 ; §0 prime) | FV | dans le bloc | — |

### §2 Détection et adaptation

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 2.1 | Machine distante : construire le portable, lanceurs .bat/.ps1/.command | FV | `.equipe/scripts/lanceurs/` (4 fichiers), `Installer.bat` | — |
| 2.2 | « Script d'installation unique installer.ps1 / installer.sh » | FNV | `installer.ps1` (394 lignes, en cours de modification), `installer.sh` | I : aucun poste Windows ; non exécuté |
| 2.3 | Installations locales en mode utilisateur, raccourcis, planificateur, attribut caché | FNV | installer.ps1 §1-10 : winget `--scope user`, `WScript.Shell` raccourci, `Register-ScheduledTask` (logon, déverrouillage, veille, inactivité), attribut Hidden | I : Windows |
| 2.4 | Connexion des connecteurs par l'installateur | A | aucun connecteur messagerie/agenda dans l'installateur | Voir §6.4 |
| 2.5 | Push sur le dépôt privé = voie de livraison | FV | `git status` : à jour avec `origin/ccr-e8f5838b-808ukj` | — |
| 2.6 | Ce qui ne peut se faire que sur le poste listé dans INSTALLATION.md, langage simple | P | INSTALLATION.md : trois gestes clairs | Omet : téléchargement de la bibliothèque au premier cycle (~25 Mo, minutes), mémoire vide ; ZIP d'un dépôt privé exige un compte GitHub |
| 2.7 | Windows probable : PowerShell/Python, chemins Windows, Planificateur | FV | pathlib partout, `cerebro.cmd`, tests B4 cp1252 OK | — |
| 2.8 | Droits admin jamais supposés ; repli OCR / transcription | P | Python utilisateur, winget `--scope user` | OCR et transcription : ni installés ni repli fonctionnel (A) |
| 2.9 | Modèle le plus capable sans surcoût ; noms exacts au dossier technique | P | `settings.json` `"model": "opus"` ; DOSSIER-TECHNIQUE liste les alias | Nom exact servi non consigné (le banc montre `claude-opus-5-5`) ; `effortLevel: high` au lieu d'effort maximal |
| 2.10 | Redémarrage si modèle inférieur | A | aucune détection du modèle courant | — |
| 2.11 | Messagerie, agenda, Office détectés ; défaut Outlook | P | défaut posé | Aucune détection (installateur ni script) |
| 2.12 | Abonnement détecté sinon frugal | P | défaut frugal | Aucune tentative de détection |
| 2.13 | Version de Claude Code et mécanismes vérifiés par test réel | FV | DOSSIER-TECHNIQUE §2 (événements, modes, formats) ; control session réussie | — |

### §3 Stratégie de construction

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 3.1 | Persistance d'abord (constitution, construction.md, backlog, CLAUDE.md, commit) | FV | commit 7386692 | — |
| 3.2 | Fiche substrat par sous-agent dans DOSSIER-TECHNIQUE | FV | §2 du dossier technique | — |
| 3.3 | Rapport de chantier écrit dans un fichier avant de rendre la main | P | 4 rapports (bibliotheque, equipe, production, relecture-noyau) | Pas de rapport pour plomberie (en cours), ni pour ingesteur/brief/horloges/initiative (étapes 2-3) |
| 3.4 | Cycle construire → tester → relire (sous-agent tiers) → adversaire | P | noyau : relecture adverse (34 Ko) puis corrections B1-B7, I1-I16 (test_cerebro 50/50) | Production, équipe, bibliothèque, plomberie : aucune relecture tierce ni tentative de casse documentée |
| 3.5 | « Aucun test, aucun écart ne bloque ; ils produisent des tickets » | P | `t_tests_cerebro` crée un ticket en cas d'échec (ajout en cours) | Les autres suites de tests ne créent pas de ticket |
| 3.6 | Un commit par chantier, un tag par étape, push à chaque étape | P | commits par étape | `git tag` → aucun tag |
| 3.7 | Données de répétition : dossier fictif complet (sociétés, personnes, décisions, délais, mails, documents, notes vocales) | P | `tests/fixtures/dossier_fictif.py` : 2 clients, 3 personnes, 3 entités, décision, dividende, mail, RDV, note « vocale » | Uniquement des objets en base : aucun vrai fichier mail (.eml/.msg), PDF, Word ni audio à ingérer |
| 3.8 | Budget de construction mesuré et inscrit (tokens par chantier) | A | DOSSIER-TECHNIQUE §4 vide | — |
| 3.9 | Tableau de bord de construction à jour par chantier | P | `construction.md` | Périmé : T-012…T-016, T-040, T-050…T-100 « todo » alors que livrés ou en cours ; backlog : tout « todo » |
| 3.10 | Une branche par chantier, revue avant fusion | I | une seule branche autorisée (consigné dans `defauts.md`) | — |
| 3.11 | Versions taguées et CHANGELOG.md | A | `ls CHANGELOG.md` → absent | — |
| 3.12 | Pas de hook de pré-commit | FV | aucun `.git/hooks` actif | — |
| 3.13 | Regard neuf : sous-agent qui n'a vu que la constitution rejoue la démonstration | A | — (le présent audit en tient partiellement lieu) | — |
| 3.14 | Fin de construction : retirer la reprise, CHANGELOG, protections | A | consigne de reprise toujours dans `CLAUDE.md` | Voir constat A2 |

### §4 Principes de fonctionnement

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 4.1 | Mustafa ne fait que converser | P | lanceur, hooks, initiative | Brief non affiché sans un premier message (critère 1) |
| 4.2 | Tout ce qu'il dit est capturé et classé, sauf « entre nous » | FV/FNV | capture Stop → inbox (test + banc : 2 lignes capturées) ; greffier haiku | Classement réel par le greffier non vérifié ici (modèle) |
| 4.3 | L'associé ne narre jamais la mécanique, ne cite ni chemin, outil, skill, agent | P | `associe.md` règle zéro ; banc : jargon=[] sur 3 réponses | Banc « ouverture » : réponse ultérieure du même tour contenant « **M-001 (mail sur le dividende) :** », « DOC-0005 » (identifiants internes et gras montrés) |
| 4.4 | Rien ne part seul : brouillons uniquement | FV | aucune commande d'envoi (test_equipe) ; mail produit en `.eml X-Unsent` | — |
| 4.5 | Faits datés et étiquetés `[fait vérifié]` etc. | P | consigne greffier | Non contrôlé par une porte |
| 4.6 | Affirmation de droit vérifiée contre source primaire datée, canton | P | `law article` (BIB, version, URL) ; RD-001…008 vérifiées | Bibliothèque fédérale seulement, absente du poste (A1) |
| 4.7 | Calculs par script sur barèmes versionnés par année et canton | P | `scripts/calcul/` : IA 200 000 → 70 000 / 130 000 (BAR-002) exécuté | Aucun barème cantonal, charges sociales, successions, régime matrimonial, timbre de négociation |
| 4.8 | Toute donnée structurée dans la base via la CLI | FV | CLI 50+ sous-commandes, MCP | — |
| 4.9 | Accès total ; perception jamais recopiée (relecteur) | P | relecteur.md ; MET-012 | Aucune porte script « note interne recopiée » |
| 4.10 | Aucun contenu juridique inventé | FV | barèmes lus dans le texte (`baremes.py`), ⚠ sinon (test IA sans barème) | — |
| 4.11 | Données sur le poste + git privé, pushes sans question | FV | `t_commit_push` | — |
| 4.12 | Aucune restriction de contenu, décision consignée une fois | FV | DOSSIER-TECHNIQUE §1 | — |
| 4.13 | Aucun sujet interdit, pas de moralisation | FNV | consigne identite/associe | — |
| 4.14 | Organisé par client et croisé ; croisement adverse signalé | P | `conflict-check`, `croisements()` | Voir §9.2 |
| 4.15 | Se maintient et s'étend seul (intendant, fabrique, construction) | P | intendant script | Fabrique et construction non autonomes (A5) |
| 4.16 | Aucun livrable sans contrôle ; important → appel adverse groupé | P | portes + panel-adverse.md | Orchestration du panel laissée à l'associé (aucun script) |
| 4.17 | Réponses schématiques d'abord | FV (banc) | réponses « Bonjour » et société commencent par un tableau | — |
| 4.18 | « Ce que vous n'avez pas demandé » ; contrôle de ce que Mustafa dépose | P | banc : rubrique présente et pertinente (Luca Rochat) ; ingesteur → file `ingestion_commentaire` | Commentaire effectif dépend de l'initiative (non vérifié) |
| 4.19 | Découverte continue | A | voir §6.4 | — |
| 4.20 | Économie de contexte | P | budgets d'injection respectés | Coût fixe 42 k tokens (A3) |
| 4.21 | Humanité, voix de la maison, sans trace de machine | P | humanizer fr/de/it, porte tics | — |
| 4.22 | Tenue à l'échelle (paliers, budgets mesurés) | P | budgets find/summary mesurés | Paliers chaud/tiède/froid absents |
| 4.23 | Efficience d'abord | P | script avant modèle (horloges, portes, ingestion) | Associé lit des fichiers entiers (banc) |
| 4.1.a | Règle zéro : aucun vocabulaire de mécanique ; confirmations interdites | P | `associe.md` ; banc confirm=0 | Fuite d'identifiants (voir 4.3) |
| 4.1.b | Intendant : incidents résolus seuls | P | `intendant.py traiter_incidents()` ; INC-001/002 résolus | Résolution limitée (relance/constat) |
| 4.1.c | Filtre de sortie qui journalise | FV | `hook.py:194-197`, test OK | — |
| 4.1.d | Deux actions seulement demandées à Mustafa (glisser, autoriser) | FV (consigne) | INSTALLATION / associe | — |
| 4.2.a | Chaque mail reçu a sa réponse en brouillon | P | initiative traite `type=mail statut=attente` ; banc : brouillon M-001 créé | Aucun accès à une messagerie : seuls des mails déposés/saisis |
| 4.2.b | Chaque délai son document prêt avant l'échéance | P | `event taxation` → DL + DOC « à préparer » (stub de 2 sections) ; initiative le rédige à J-3 | Document réel non vérifié (modèle) ; stub marqué à tort « ⟦donnée externe⟧ » |
| 4.2.c | Chaque RDV : fiche la veille, compte rendu après | P | initiative : RDV des prochaines 24 h → fiche | Compte rendu après RDV : rien ne le déclenche |
| 4.2.d | Chaque changement de droit → alerte client | P | `alerte_changement` dans la collecte initiative ; `mise_a_jour.py` crée `changement_droit` | Table `changements_de_droit`/`impacts` jamais alimentée ; tâche `alerte_changement` jamais créée par un script |
| 4.2.e | Revue hebdomadaire préparée | A | cadence `revue_hebdomadaire` en file, jamais exécutée | — |
| 4.2.f | Opportunités → mail et proposition | A | pipeline listé au brief seulement | — |
| 4.2.g | Livrables au format final ouverts automatiquement | FNV | `produire.py` : `os.startfile`/`open`/`xdg-open` | I : pas d'affichage ici |

### §5 Substrat Claude Code

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 5.1 | CLAUDE.md court (< 2 000 tokens), imports chargés à la demande | P | CLAUDE.md 1 257 car. + imports `@bloc-cardinal.md` 1 717 + `@associe.md` 6 426 = 9 400 car. ≈ 2 600 tokens, chargés à chaque session | Les `@` sont chargés d'office, pas à la demande ; dépasse 2 000 tokens |
| 5.2 | settings.json : hooks, mode permissif, aucune deny | FV | fichier lu | — |
| 5.3 | Hooks : contexte, capture, journal, fond ; anti-récursion `CEREBRO_BACKGROUND` ; try global | FV | `hook.py:8-9`, `:304-320` ; tests plomberie 1-15 OK | — |
| 5.4 | Sous-agents `.claude/agents/` (name, description, tools, model) | FV | 37 fichiers, test YAML OK ; `claude -p` les liste (rapport équipe) | — |
| 5.5 | Skills `.claude/skills/<nom>/SKILL.md` | FV | 26 skills actives + 6 « dormantes » dans `.equipe/skills-dormantes/` | — |
| 5.6 | Plugins des marketplaces officielles (claude-for-legal, financial-services, skills) | P | marketplaces ajoutées en portée utilisateur du conteneur ; skills extraites et adaptées (revue-tabulaire, chronologie-faits, historique-avenants, audit-tableur) ; installateur (modif. non commitée) installe `document-skills` | Rien n'installe les marketplaces sur le poste hors document-skills |
| 5.7 | MCP ; cerebro exposé comme serveur local | FV | `.mcp.json` ; `claude mcp list` → cerebro, playwright, markitdown « Connected » ; appel `tools/call find` OK (13 outils) | — |
| 5.8 | Mode non interactif pour les rôles de fond, outils limités, `CEREBRO_BACKGROUND=1` | FV | `greffier.py:84`, `initiative.py:55` (`--allowedTools`, `env_fond`) | Seuls 2 rôles de fond lancés |
| 5.9 | Lanceur « Mon équipe » qui démarre aussi l'entretien | FV/FNV | `Mon-equipe.ps1` lance `cycle.py --rattrapage` puis Claude ; test lanceur Linux OK | Windows non exécuté |
| 5.10 | Première ouverture : au plus « Entrée » | FNV | `skipDangerousModePermissionPrompt`, `hasTrustDialogAccepted` posés par l'installateur | Connexion au compte reste une étape navigateur |
| 5.1.a | Commandes de référence vérifiées dans la version | FV | DOSSIER-TECHNIQUE §2 | — |

### §6.1 Pôle juridique

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 6.1.1 | Associé : une voix, langue de Mustafa, « relève d'un avocat » | FV (consigne) | `associe.md` | — |
| 6.1.2 | Associé signale à la découverte les compétences manquantes | P | consigne `capability propose` → file `decouverte` | File jamais consommée |
| 6.1.3 | Conseiller d'anticipation : revue mensuelle par client, 5 clients / 30 j | P | `.claude/agents/conseiller-anticipation.md`, skill `revue-anticipation` | Aucune cadence ne le déclenche |
| 6.1.4 | 12 spécialistes de domaine | FV | 12 fichiers `specialiste-*.md` (sociétés-RC, fiscalité entreprises, personnes physiques, TVA, successions, contrats, travail, LBA, immobilier/Lex Koller, poursuites, fiscalité internationale, droit étranger) | Contenu méthodologique non éprouvé |
| 6.1.5 | Chercheur, documentaliste, avocat-plaideur, rédacteur, calculateur, officier de conformité, secrétaire de société | FV | 7 fichiers présents | — |

### §6.2 Contrôle avant livraison

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 6.2.1 | Vérifiable (chiffres, dates, délais, citations, renvois, gabarit, tics, règle zéro) vérifié par scripts | P | portes liens, sources, typo, tics, jargon, présentation, couverture, visuel, budget | Pas de vérification script des chiffres (recalcul), des délais cités contre `delais`, des renvois internes, des termes définis |
| 6.2.2 | Appel adverse groupé unique (6 voix) pour livrables importants | P | `panel-adverse.md` : 6 voix dans un passage, JSON par constat | Aucun script ne déclenche ni ne compte l'appel ; repose sur l'associé |
| 6.2.3 | Relecteur après le panel | FV (rôle) | `relecteur.md` | — |
| 6.2.4 | Mail court : lecteur humain dans l'appel de rédaction | FNV | skill redaction-mail | — |
| 6.2.5 | Contrôle impossible → livrable avec réserves | FV | `portes.py` : `reserves`, code 0 | — |

### §6.3 Rédaction, design, influence, support

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 6.3.1 | Éditeur humain, directeur artistique, visualiseur | FV | 3 fichiers agents | — |
| 6.3.2 | **Responsable d'expérience** | A | aucun fichier (rapport équipe : « non créé ») | Créer `.claude/agents/responsable-experience.md` (§7 : lecteur humain, parcours Mustafa, règle zéro) |
| 6.3.3 | Stratège, commercial, négociateur, marketeur, communicant | FV | 5 fichiers | — |
| 6.3.4 | Chef de cabinet (brief) | P | agent + mission de fond `.equipe/roles/chef-de-cabinet.md` | Mission jamais lancée ; le brief est un script (acceptable) |
| 6.3.5 | Greffier : capture par script à chaque échange, classement groupé léger à la fermeture ou tous les 15 | FV/FNV | `hook.py:198-204` (15), `fin_session.py` ; test « greffier tous les 15 échanges » OK ; banc : un greffier haiku lancé | Classement réel non contrôlé |
| 6.3.6 | Archiviste (index, alias, doublons, condensation, vues, croisements, santé) | P | scripts `coverage`, `gc`, `croisements`, `vues_client`, `health` au cycle | Condensation absente ; mission archiviste jamais lancée ; doublons non réparés |
| 6.3.7 | Veilleur | P | agent + mission | Jamais lancé ; aucune source de veille |
| 6.3.8 | Ingesteur | FV | `ingerer.py` : txt → DOC rattaché C-001 confiance 1.0, original vers `Bureau/Deposes/<date>/`, consigne piégée → `journal_audit consigne_externe_ignoree` (exécuté) | — |
| 6.3.9 | Intendant | FV | `intendant.py` + tests | — |
| 6.3.10 | Tuteur (note hebdomadaire) | A | mission non lancée | Cadence + lancement |
| 6.3.11 | Producteur | FV | `produire.py`, test_production 45/45 | — |
| 6.3.12 | Fabricant | P | agent + mission | Voir §6.5 |

### §6.4 Outillage et découverte continue

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 6.4.1 | Skills Anthropic docx/pptx/xlsx/pdf | P | non copiées (licence propriétaire, rapport production) ; installateur en cours : `claude plugin install document-skills@…` | Non vérifié ; générateurs maison couvrent la production |
| 6.4.2 | Python + python-docx, openpyxl, python-pptx, reportlab, pandas | FV/FNV | présents ici ; installateur `pip install --user` | — |
| 6.4.3 | OCR si installable en mode utilisateur | A | aucun tesseract/ocrmypdf/easyocr ; PDF scanné → `pdf_scanne` → modèle | Repli « lecture par le modèle » non câblé (tâche `lecture_modele` seulement par l'initiative) |
| 6.4.4 | MarkItDown MCP, Playwright MCP | FV | `claude mcp list` Connected | — |
| 6.4.5 | Mermaid CLI, matplotlib, plotly | P | matplotlib OK ; Mermaid indisponible ici (repli matplotlib) | plotly non installé |
| 6.4.6 | Un serveur de recherche web officiel d'éditeur | A | aucun ; `WebSearch` intégré autorisé | — |
| 6.4.7 | OpenAlex, Semantic Scholar, CrossRef (scripts si pas de serveur) | A | `grep -ri openalex\|crossref` → seulement DOSSIER-TECHNIQUE | Scripts `scripts/recherche/academique.py` |
| 6.4.8 | Fedlex SPARQL, Zefix | FV | test_bibliotheque « Fedlex SPARQL », « Zefix (LINDAS) » OK (réseau) | — |
| 6.4.9 | CourtListener, legislation.gov.uk, BAILII | A | grep → rien | — |
| 6.4.10 | Git avec remote privé | FV | origin configuré | — |
| 6.4.11 | LibreOffice sans affichage (portable) | P | soffice ici ; installateur cherche portable | Installation portable non automatisée |
| 6.4.12 | Transcription vocale locale, sinon par le modèle | A | audio → `lecture_modele` ; le modèle ne lit pas l'audio | faster-whisper/whisper.cpp en mode utilisateur, ou service ; tâche dédiée |
| 6.4.13 | Skills design/rédaction officielles (frontend-design, canvas-design, brand-guidelines réécrite, theme-factory, doc-coauthoring, internal-comms, skill-creator) | P | copiées avec SOURCE/LICENSE ; 6 mises « en sommeil » hors `.claude/skills` par 18e435d ; skill-creator active | brand-guidelines (charte de la maison) n'est plus active |
| 6.4.14 | Voix de marque (plugins Anthropic travail du savoir) | A | — | — |
| 6.4.15 | humanizer (blader) + variantes fr/de/it | FV | 4 skills ; source et commit notés | — |
| 6.4.16 | Style The Economist (EN), skill anti-« AI slop », sous-agents awesome-claude-code-subagents un par un | A | — | — |
| 6.4.17 | Messagerie, agenda, contacts (M365/Google) lecture + brouillons | A | aucun connecteur, aucun script Graph/IMAP/ICS ; Q-011 en file | Préparer la connexion (MCP officiel M365/Google ou connecteur claude.ai), écrire INSTALLATION, tester en lecture seule |
| 6.4.18 | Word, Excel, PowerPoint, PDF lus et produits | FV | ingesteur lit docx/xlsx/pptx/pdf/eml ; producteur produit les 4 + eml (45/45) | `.msg` Outlook non lu |
| 6.4.19 | Formulaires PDF remplis | A | grep AcroForm → rien | — |
| 6.4.20 | Comparaison de versions, suivi des modifications Word lu et produit | P | lecture : drapeau `[document avec suivi des modifications]` | Production de suivi des modifications et comparaison : absentes |
| 6.4.21 | Schémas aussi en draw.io | FV | `produire.py` écrit `.drawio` (rapport production) | — |
| 6.4.22 | Gestion documentaire, logiciel de la fiduciaire | A | — | — |
| 6.4.23 | Bases Swisslex, Weblaw… quand identifiants | P | Q-004 ; `acces.bases_recherche` | — |
| 6.4.24 | Signature électronique en préparation seulement | A | — | — |
| 6.4.25 | Chaque catégorie inventoriée (LOCAL/EXTERNE, sort, vers qui, licence) | P | `capacites` : 39 lignes (base du conteneur) | Inventaire perdu sur clone (A1) |
| 6.4.26 | Découverte : début de session, chaque semaine, question hors compétence, sources (marketplaces, registre MCP…) | A | `capability_propose` met en file `decouverte` ; aucun script de découverte | Script hebdomadaire (registre MCP officiel, marketplaces, `claude plugin marketplace list`), évaluation par un appel, installation, inscription, désinstallation |

### §6.5 La fabrique

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 6.5.1 | Déclencheurs (3×/30 j sans skill, correction ×2, canton nouveau ×2, demande explicite « désormais ») | A | `types_de_tache` alimentée seulement par l'ingesteur (`depot:.ext`) ; aucun détecteur de « désormais » hors consigne associé | Script de comptage (greffier → `task-seen`), détecteur de règles dans les captures |
| 6.5.2 | Fabrication tous les 7 jours au premier cycle venu, méthode skill-creator, fixtures réelles | A | aucune cadence `fabrique` dans `cycle.py`, aucun lancement de `roles/fabricant.md` | `t_fabrique` : `claude -p` avec fabricant.md sur la file `fabrique` |
| 6.5.3 | Déploiement essai (5 usages) → actif → dormant 90 j ; ≤ 1 création/semaine | P | décrit dans fabricant.md ; mécanisme de réveil des skills dormantes évoqué | Aucun compteur d'usage des skills |
| 6.5.4 | Écrit dans `.claude/skills/` et `.claude/agents/` | P | la mission le prévoit | L'équipe ne peut créer seule un agent, une skill ou un serveur MCP qu'à l'intérieur d'une conversation où l'associé décide d'appeler le fabricant |

### §6.6 Modèles et effort

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 6.6.1 | Plus capable pour associé, chercheur, spécialistes, panel… | FV | test_equipe « modèle selon §6.6 » OK ; settings `opus` | Effort « maximal » non réglé (`high`) |
| 6.6.2 | Intermédiaire / léger selon la liste | FV | sonnet/haiku dans les en-têtes ; greffier haiku, initiative sonnet | — |
| 6.6.3 | Noms exacts au dossier technique ; intendant abaisse un palier | P | alias notés | Aucun ajustement automatique |

### §7 Livrables, rédaction, design, efficience

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 7.1.1 | Forme structurée d'abord dans la conversation | FV (banc) | tableaux en tête | — |
| 7.1.2 | Fichiers dans `Bureau/Livrables/<client>/<date>-<objet>/`, ouverts automatiquement | FV/FNV | test_production ; ouverture non observable ici | — |
| 7.1.3 | Standards mail, mémo, Excel, PowerPoint, documents de société, schémas | FV | gabarits GAB-001…006 ; structure contrôlée par `p_presentation` | Arbre familial, machine à états, carte des parties prenantes : non vérifiés |
| 7.1.4 | Langues FR/DE/IT/EN, glossaire, relecture de langue | P | glossaire ~120 notions (11 articles reliés) ; humanizer-de/it | Bibliothèque sans italien ; libellés IT/EN non relus |
| 7.1.5 | Mails lisibles Outlook/Gmail, signature, pièces nommées | FV | `mail.py` (.eml texte brut, X-Unsent, pièces `client-objet-date-vN`) | — |
| 7.2 | Rédaction humaine : interdits listés, voix de Mustafa | P | porte `p_tics` FR/DE/IT/EN ; humanizer | Profil de style de Mustafa appris : aucun mécanisme (pas de corpus) |
| 7.3.1 | Système de design et gabarits Word, Excel, PowerPoint, PDF | FV | `design/systeme.yaml`, `gabarits.py`, `Bureau/Modeles/` (6) | Construit sans modèle de la maison (défaut sobre) |
| 7.3.2 | TdM > 10 pages, pagination, version et date d'état en pied, confidentialité en en-tête | FV | rapport production + test « présentation » | — |
| 7.3.3 | Typographie par langue vérifiée par script | FV | `p_typo.py` (CHF 1'234.50, « », „“) | — |
| 7.3.4 | Contrôle visuel par rendu en images + regard de modèle dans l'appel groupé | P | `p_visuel.py` (soffice + pdftoppm, heuristiques) | Débordements verticaux non détectés ; le regard modèle sur images n'est pas orchestré |
| 7.4 | Interne pour la machine (formats compacts, lexique) | FV | rôles en format compact, `lexique.md` | — |
| 7.5.1 | Portes : efficience | P | `p_budget` (longueur) | « pas d'appel de modèle là où un script suffisait, pas de travail refait » non mesuré |
| 7.5.2 | Porte liens | FV | `p_liens.py` ; test production | — |
| 7.5.3 | Porte sources (⚠ inséré) | FV | `p_sources.py` + `--corriger` | Motifs regex, faux positifs (rapport production) |
| 7.5.4 | **Porte sommaires (objets touchés régénérés)** | A | aucune `p_sommaires` dans `PORTES` (`portes.py:18`) | Porte qui vérifie `a_regenerer=0` pour les IDs cités/touchés |
| 7.5.5 | Porte présentation | FV | `p_presentation.py` | — |
| 7.5.6 | **Porte contexte (injection sous budget)** | A | absente de `PORTES` | Porte lisant `etat.injectes`/longueur du contexte du tour |
| 7.5.7 | Porte couverture | FV | `p_couverture.py` | — |
| 7.5.8 | Porte fermée → rôle responsable, puis réserves ; jamais retenu | FV | `RESPONSABLE` dict, `a_renvoyer`, code 0 | — |
| 7.5.9 | **Tableau de bord des principes à chaque cycle** ; révision par la fabrique après 2 cycles en écart ; version incrémentée | P | `tableau.py` + table `portes_passages` ; calcule taux et écarts < 80 % | Non appelé par le cycle, aucune sortie dans `health`, aucun lien à la fabrique |
| 7.5.10 | Chaque rôle/skill déclare principes et portes dans son en-tête | FV | test_equipe OK | — |
| 7.6.1 | Script d'abord (identifiants, sommaires, horloges, brief, portes, ingestion…) | FV | ensemble des scripts | Embeddings locaux = trigrammes (pas sémantique) |
| 7.6.2 | Échelle script → léger → intermédiaire → plus capable, promotion sur échec | P | paliers fixés par rôle | Aucune promotion automatique |
| 7.6.3 | Profil frugal : un appel par échange, greffier groupé, panel unique, veille hebdo, découverte 1/mois, anticipation 5 clients/30 j, fabrique 1/sem | P | greffier groupé, initiative unique | Associé multiplie les appels (9 outils + sous-agent au « Bonjour ») ; cadences veille/découverte/anticipation absentes |
| 7.6.4 | Mesure tokens par rôle, tâche, palier, jour au rapport de santé | P | `health.tokens_jour` depuis `mesures` | Associé et sous-agents non mesurés ; `mesures` vide en base réelle |
| 7.6.5 | Rationnement 60 % / 85 % ; « je ralentis un peu aujourd'hui » | A | grep → rien ; `budget_fond_quotidien_appels: 3` jamais lu | Compteur quotidien + seuils dans `cycle.py` |

### §8 Arborescence

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 8.1 | Bureau/ (À déposer, Déposés, Livrables, Modèles, Informatique) | P | `Bureau/A-deposer`, `Deposes`, `Livrables`, `Modeles`, `Informatique` | Noms ASCII sans accents (choix consigné, écart de libellé) |
| 8.2 | .equipe/ (config, cerebro, sommaires, cerveau/…, bibliotheque, inbox, archives, roles, scripts, tests) | FV | `ls .equipe` | `cerveau/doctrine/` sans dossier par canton ni par pays |
| 8.3 | .claude/ (settings, agents, skills, hooks) | FV | présent | — |
| 8.4 | Agents n'écrivent dans Bureau que livrables, gabarits, dossiers techniques ; ramasse-miettes vérifie | FV | `zombies().bureau_egares` ; test B6 | — |
| 8.5 | Attribut caché posé par l'installateur | FNV | installer.ps1 §10 | I : Windows |

### §9.1 SQLite + CLI

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 9.1.1 | Base SQLite, CLI à sous-commandes, serveur MCP | FV | `cerebro.py`, `mcp_server.py` (13 outils), tests 50/50 | — |
| 9.1.2 | Export JSON/CSV commité à chaque cycle complet | P | `export()` existe, appelé par cycle complet et fin de session | Jamais exécuté dans le dépôt (aucun export commité) ; exporte 25 Mo de tables FTS (A4) |
| 9.1.3 | 30 tables listées | FV (schéma) | `core.py:129-174` : toutes présentes | Vides et non alimentées : publications_fosc, correspondants, rulings, changements_de_droit, impacts, positions, temps (sauf commande), types_de_tache (partiel), mesures |
| 9.1.4 | 30 commandes listées | FV | `cerebro.py:20-67` : client show, entity show/organs/chain, deadlines, extensions due, commitments due, matter new, conflict-check, clock start, lba review due, question add/list, time add, pipeline, links, law ingest/search/asof, rates get, capability list/propose, incident add/resolve, deliverable register, find, summary, open --section, config set/get/gaps, trace, gc, coverage, brief, context, export, health, reprocess --since | Pas de commande `correspondant`, `fosc`, `ruling`, ni d'opération dédiée de changement de règle (§12) |

### §9.2 Identification, classement, croisement

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 9.2.1 | Rattachement par alias puis contexte, score de confiance ; `[à confirmer]` + question | FV/P | ingesteur : `confiance: 1.0` ; audio `confiance 0.0, client null` | Question métier non créée automatiquement par l'ingesteur pour un rattachement nul |
| 9.2.2 | Vue 360 (`vue.md`) régénérée à chaque cycle et injectée quand le client est cité | FV | `vues_client` au cycle ; injection : « vue 360 : cerebro open C-001-VUE » | — |
| 9.2.3 | Croisements : même personne deux sociétés ✓, même ayant droit, même notaire/banque, même question tranchée deux fois, changement de droit multi-clients, collisions de délais ✓ | P | `metier.py:179-215` : personne multi-clients, homonymes, collisions de délais ; brief « CROISEMENTS » (Luca Rochat) | Ayant droit commun, notaire/banque commun, question tranchée deux fois, changement de droit multi-clients |

### §9.3 Modèle d'information

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 9.3.1 | Identifiants stables, redirection des anciens | FV | test c25 « ancien identifiant redirigé » OK | — |
| 9.3.2 | Alias multilingues | P | table `alias` (champ langue) | Peu d'alias DE/IT réels |
| 9.3.3 | Bitemporalité, « état au » calculé | FV | tests I5 OK | — |
| 9.3.4 | En-tête : id, type, statut, maj, prochaine_action, risque_principal, chiffre_clé, résumé 280, mots_clés, liens, source | FV | en-tête E-001 généré (tous les champs) | `mots_clés`, `risque_principal` souvent vides |
| 9.3.5 | Niveau 0 ≤ 2 000 car. | FV | test OK ; 369 car. réel | — |
| 9.3.6 | Niveau 1 par client et par domaine, 160 car./ligne, subdivision > 150 lignes | P | `sommaires/clients/`, `domaines/<type>.md` ; subdivision testée (relecture) | « Domaine » = type d'objet, pas domaine juridique |
| 9.3.7 | Niveau 2 = en-têtes | FV | en-têtes YAML | — |

### §9.4 Retrouver, charger peu, capturer, entretenir

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 9.4.1 | `find` : alias, ID, plein texte multilingue, embeddings locaux, graphe, temps, « presque » ; `--deep` archives | P | `recherche.py:37-135` | « Embeddings » = vecteurs de trigrammes (pas de rappel sémantique ni translinguistique) |
| 9.4.2 | Auto-test de rappel : 20 faits reformulés, > 95 %, sinon reconstruction | P | exécuté : `{"echantillon":20,"rappel":0.95}` | Pas de reformulation (mots du résumé mélangés : test circulaire) ; 0,95 n'est pas > 95 % |
| 9.4.3 | **Début de session ≤ 8 000 car.** | FV (injection) / P (coût réel) | SessionStart simulé : 803 car. ; tronqué à 8 000 (`hook.py:37`) | Socle fixe réel ~42 k tokens (A3) |
| 9.4.4 | **Injection par tour en delta ≤ 6 000 car.** | FV | simulé : 2 200 car. puis 114 octets au même message (delta) ; test I6 | — |
| 9.4.5 | Lecture ciblée ; jamais de listing ; > 5 ouvertures par tour journalisées | P | `recherche.py:154-160` journalise > 5 | Lectures hors CLI (cat, head, sed, find) invisibles au compteur ; observées au banc |
| 9.4.6 | Lectures longues déléguées à un sous-agent (≤ 1 500 car., rapport enregistré) | FV (consigne) | associe.md « Déléguer » | Non mesuré |
| 9.4.7 | **État de session tous les dix tours** et avant compaction | P | PreCompact → `etat.md` (test OK) | Aucun déclenchement tous les dix tours |
| 9.4.8 | Capture totale par script dans inbox/ | FV | Stop → `inbox/<date>.jsonl` (test + banc) | — |
| 9.4.9 | Détecteur de nouveaux sujets ; domaine nouveau → sommaire, spécialiste, file d'ingestion | P | consigne greffier (étape 5) ; test c26 | Spécialiste jamais créé (fabrique) ; file `bibliotheque <domaine>` non consommée |
| 9.4.10 | Double lecture hebdomadaire | A | grep → rien | — |
| 9.4.11 | Hook après outil → « à régénérer » | FV | test PostToolUse OK | — |
| 9.4.12 | Réconciliation base ↔ fichiers à chaque cycle complet | P | `regen` ; restauration d'un fichier supprimé (I9) | Pas de reconstruction base ← en-têtes (pourtant la seule voie de survie au clone, A1) |
| 9.4.13 | Condensation sans perte (différentiel vérifié) | A | — | — |
| 9.4.14 | Zéro zombie (orphelins, liens morts, dossiers vides, doublons) | P | `gc` répare liens morts et dossiers vides (test c28) | Orphelins et doublons signalés, jamais réparés |
| 9.4.15 | Couverture (vue, délais, documents, prochaine action, propriétaire, lien, double chemin) | P | `coverage()` | Propriétaire et double chemin non vérifiés (relecture M14) |
| 9.4.16 | Drapeau « à revoir » à 90 jours ; audit mensuel | P | prochaine_date par défaut +90 j | Audit mensuel absent |
| 9.4.17 | git ne suit que config, constitution, rôles, skills, tests, scripts, exports, narratif | P | `.gitignore` correct pour bibliothèque, base, inbox, archives, Bureau | Exports FTS non exclus (A4) |
| 9.4.18 | Sauvegarde chiffrée locale de ce qui n'est pas dans git | P | `t_sauvegarde` : base + config chiffrées Fernet, 14 copies, restauration testée | Bibliothèque, inbox, archives, livrables non sauvegardés |
| 9.4.19 | Palier froid compressé, doublons par empreinte, alerte disque 80 % | P | `intendant.disque()` 80 % ; empreinte des dépôts (ingesteur) | Paliers chaud/tiède/froid absents |
| 9.4.20 | Budgets find < 2 s, summary < 1 s, passe < 1 h ; test de croissance mensuel ×10 | P | find 0,11 s, summary 0,08 s (base réelle, 201 objets) ; relecture : 15 000 objets testés une fois | Test de croissance mensuel non automatisé |
| 9.4.21 | Trois opérations atomiques (créer, réviser, archiver avec redirection) | FV | `new`, `update`, `archive --vers` | — |
| 9.5 | Enrichissement continu : source consultée ingérée le jour même ; leçons → pièges/pratiques ; semaine vide signalée | P | `health.enrichissement_semaine` | Aucun signalement « semaine vide » ; aucune ingestion automatique des sources web consultées |

### §10 Couche narrative, méthodes, bibliothèque

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 10.1 | cabinet/ : identité, confort, styles, modèles, glossaire FR/DE/IT/EN | FV | 9 fichiers CAB- | — |
| 10.2 | 16 fiches méthodes listées | FV | `cerveau/cabinet/methodes/` MET-001…016 (titres conformes à la liste) | En base du conteneur seulement |
| 10.3 | doctrine/ : fédéral, un dossier par canton suivi, étranger par pays | P | `doctrine/regles-delais/`, DOCT-001 | Dossiers VD, GE, pays : absents |
| 10.4 | Bibliothèque : RS 3 langues, ordonnances, FF, jurisprudence fédérale, circulaires AFC, OFAS, FINMA, CDI, cantons, OAR, étranger | P | 23 actes RS en FR, CO et LIFD en DE, 3 versions antérieures ; index article par article (7 813 articles) | Aucun IT, FF, jurisprudence, circulaire, CDI, texte cantonal ; et rien n'existe sur le poste au départ |
| 10.5 | Pipeline `law ingest` (juridiction, type, ID pérenne, langue, dates, version, texte, source, licence) | FV | `juridique.py:14-21` ; test « verify 2 passes » OK | — |
| 10.6 | Versions dans le temps ; `asof` | FV | test « asof LTVA 2024-06-30 » OK | Trous de versions signalés (LIFD 2025) |
| 10.7 | Mise à jour à chaque cycle complet, reliée aux positions et clients | P | `t_bibliotheque_mise_a_jour` (ajout NON COMMITÉ en cours) → `fedlex.py priorites` si vide + `mise_a_jour.py` | Non commité ; liaison aux clients via `changements_de_droit` absente |
| 10.8 | Ancienne version en PDF seulement → extraction PDF ; source injoignable → journal + rattrapage | P | file `bibliotheque_rattrapage` | Repli PDF non exercé |
| 10.9 | Concordance des notions entre cantons et langues | P | glossaire multilingue | Concordance intercantonale absente |
| 10.10 | Zefix (web, LINDAS), Fedlex SPARQL JOLux | FV | `zefix.py`, `fedlex.py` (tests réseau OK) | — |
| 10.11 | Liste blanche des sources officielles | FV (consigne) | rôles (chercheur, documentaliste) | « S'enrichit seule » : non |

### §11 Hooks et boucle automatique

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 11.1 | Début de session : date réelle Europe/Zurich, brief, reprise de construction, découverte rapide en fond | P | SessionStart simulé : date, niveau 0, brief, ligne construction ; lance `cycle.py --rattrapage` | Pas de découverte rapide ; la reprise de construction tourne au coût de l'associé (A2) |
| 11.2 | Brief : délais dans leur préavis avec documents, engagements, horloges, LBA, assemblées, FOSC, RDV avec fiche, mails avec brouillons, changements de droit, croisements, opportunités, anticipations, questions ≤ 3 | P | `brief.py:29-100` (délais, engagements, LBA, RDV, mails, changements, croisements, opportunités, anticipations, question, conseil, rattrapé) | Assemblées et FOSC absentes ; documents déposés traités absents |
| 11.3 | Soumission : objets cités → injection delta ; « entre nous » hors registre ; date | FV | simulé : injection 2 200 car. ; « entre nous » → consigne, aucune capture | — |
| 11.4 | Fin de réponse : extraction inbox, filtre journalisant, greffier tous les 15 avec anti-récursion et verrou | FV | tests plomberie 3, 5, 10 OK | — |
| 11.5 | Avant compaction : snapshot ; fin de session : consolidation, commit, push | FV/FNV | PreCompact testé ; `fin_session.py` : greffier, export, commit_push, cycle court | Push réel non testé |
| 11.6 | Après outil : « à régénérer » | FV | test OK | — |
| 11.7 | Hooks try global, succès toujours ; > 2 s → optimisé ou déplacé | FV | garde-fou 1,7 s (`hook.py:15,42-48`) | — |
| 11.8 | **Boucle d'initiative** : à chaque ouverture et cycle complet, un appel groupé intermédiaire, mails < 48 h, délais sous préavis ; brouillons « à relire » affinés par l'associé | P | `initiative.py` (collecte, un appel sonnet, verrou) ; banc : brouillon M-001 et fiche RDV créés par l'associé lui-même | Pas de messagerie/agenda réels ; compte rendu après RDV absent ; opportunités absentes |
| 11.9 | **Cycle d'entretien** : ouverture, temps morts (2 min), fermeture, planificateur ; file unique triée 1-6 ; verrou ; pause quand Mustafa écrit ; cadences 7/30 j ; ligne « rattrapé » | P | `cycle.py` ; tests plomberie 22-25 OK (file triée, verrou, pause, sauvegarde) | Priorité 5 (veille, découverte, enrichissement) et 6 (construction, tests complets, croissance) sans exécutant hors bibliothèque/tests_cerebro (en cours) |
| 11.10 | Mode « entre nous » : rien n'est écrit ; transcript noté au dossier technique | FV | banc réel : « Entre nous, ce client Rochat me fatigue » → aucune ligne inbox, aucune occurrence dans `.equipe/` ni `Bureau/` ; DOSSIER-TECHNIQUE §1 | Mode non persistant (par message) ; un sous-agent lancé dans ce tour pourrait écrire |

### §12 Sécurité et protections

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 12.1 | Pendant la construction : aucune protection | FV | — | — |
| 12.2 | Empreinte de la constitution en base et tag ; restauration au démarrage | A | aucune empreinte de fichier ni tag (`git tag` vide) | Étape 11 non atteinte |
| 12.3 | Bloc cardinal signé, régénéré quand périmé | P | version = empreinte §1/§0 ter | Pas de signature d'intégrité |
| 12.4 | Journal d'audit en ajout seul | P | table `journal_audit` (287 lignes) | Rien n'empêche/détecte une réécriture ; export réécrit tout |
| 12.5 | Retour au tag en cas d'altération | A | — | — |
| 12.6 | Rôles ne connaissent que des commandes de brouillon ; connecteurs sans droit d'envoi | FV | test « aucune commande d'envoi » | Pas de connecteurs (rien à vérifier) |
| 12.7 | Injections signalées au journal d'audit, sans effet | FV | ingestion piégée → `consigne_externe_ignoree` ; injection marquée « ⟦donnée externe⟧ » | Captures et pages web : seulement consigne |
| 12.8 | Seule voie de changement des règles : opération dédiée (phrase, date, différentiel, régénération, tag) | A | aucune commande CLI dédiée | `cerebro regle appliquer` |
| 12.9 | Sauvegarde chiffrée à chaque cycle complet, restauration testée | FV | test plomberie « Cycle --complet : sauvegarde chiffrée, restauration testée » OK | Périmètre limité (9.4.18) |
| 12.10 | Disque non chiffré : une phrase, une fois | A | aucune détection BitLocker/FileVault | — |

### §13 Confidentialité

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 13.1 | Décision consignée une fois avec ce qui sort et vers qui | FV | DOSSIER-TECHNIQUE §1, tableau « Ce qui sort » | — |
| 13.2 | Aucun rôle ne la rediscute | FNV | — | — |

### §14 Fiduciaire suisse

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 14.1 | Fédéral + cantons suivis = compétence ; autres cantons « pratique à vérifier » ; avocat pour justice/pénal | FV (consigne) | associe, spécialistes | — |
| 14.2 | Horloges : réclamation et recours ✓, IA après dividende ✓, TVA ✓, annonce ayant droit ✓, AG 6 mois ✓, déclarations fiscales par canton et prolongations ✗, LBA ✓ (maison), poursuites ✓, résiliations ✓, FOSC ✗ | P | `regles_delais` RD-001…011, sources BIB vérifiées | Déclarations et prolongations cantonales, FOSC, réclamation ICC cantonale (une décision VD utilise la règle IFD) |
| 14.3 | Chaque horloge a son document préparé d'avance | P | DOC « à préparer » créé avec chaque délai | Stub de deux sections jusqu'à l'initiative à J-3 |
| 14.4 | Formes et organes tirés du registre | P | `zefix.py` | Non branché automatiquement à `entity new`/onboarding |
| 14.5 | LBA : signaler, documenter, préparer, jamais communiquer | FV | `event relation` → LBA-001 ; skill dossier-lba | — |
| 14.6 | Événements de vie = horloges et opportunités | P | — | Aucun type d'horloge « événement de vie » |

### §15 Onboarding et apprentissage

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 15.1 | Pas de questionnaire ; déduction depuis À déposer, messagerie, agenda | P | ingesteur ; skill onboarding-client | Pas de messagerie ni d'agenda |
| 15.2 | Modèles déposés deviennent les gabarits | P | tâche `gabarits` sur `config set cabinet.*` | Aucune détection d'un modèle déposé dans À déposer |
| 15.3 | Chaque correction devient une règle | P | consigne associé → note + file fabrique | File non consommée |
| 15.4 | Revue hebdomadaire préparée | A | — | — |
| 15.5 | Prénom, tutoiement réglés dès les premiers échanges | P | `mustafa.tutoiement` | Question « On se tutoie ? » existe mais ne sera pas posée (A2) |

### §16 Première session et démonstration

| # | Exigence | Statut | Preuve | Ce qui manque |
|---|---|---|---|---|
| 16.1-2 | Salutation, persistance, commit | FNV | commit 7386692 | Non observable |
| 16.3 | Aucune question ni conseil pendant la session | FV | — | — |
| 16.4 | Une phrase par étape | I | conversation de construction non disponible | — |
| 16.5 | Messagerie : pas pendant la session ; INSTALLATION + question en file | FV | Q-011 ; INSTALLATION « Plus tard » | — |
| 16.6 | Redémarrage : phrase simple | FNV | — | — |
| 16.7 | « On peut travailler » quand noyau + rédaction OK | FNV | — | — |
| 16.8 | **Démonstration de dix minutes** (mail, droit cantonal, délai + réclamation, schéma ouvert) | A | aucune trace de démonstration ; fixtures `*_demo.md` servent aux tests | Rejouer la démonstration sur le dossier fictif, consigner les résultats ; le banc montre que la question de droit cantonal reste sans texte cantonal ingéré |
| 16.9 | Push final + INSTALLATION en langage simple | P | INSTALLATION.md présent | Lacunes 2.6 |

### §18 Ordre de travail (avancement réel)

| Étape | Statut | Commentaire |
|---|---|---|
| 0 | FV | sauf socle inventorié seulement dans la base du conteneur |
| 1 | P | noyau, MCP, hooks, filtre, permissions, intendant, greffier, lanceurs, installateurs : présents ; plomberie encore en cours (diffs non commités) |
| 2 | P | ingesteur et vues OK ; onboarding par initiative partiel |
| 3 | P | brief, horloges, initiative, cycle : présents ; priorités 5-6 sans exécutant |
| 4 | P | bibliothèque fédérale FR partielle, non livrée au poste |
| 5 | P | méthodes, producteur, design, skills, spécialistes, calculateur partiel |
| 6 | P | portes (7/9 attendues), panel en rôle, relecteur, conformité, secrétaire |
| 7 | FV (rôles) | pipeline : commande, pas de relances |
| 8 | P/A | plugins partiels ; recherche académique, veilleur actif, connecteurs : absents |
| 9 | P | correspondants (table vide, pas de commande), temps (commande), onboarding et LBA (skills) |
| 10 | A | fabrique non câblée |
| 11 | A | tests complets, retrait de la reprise, protections, démonstration |

---

## C. Les 39 critères d'acceptation (§17)

| # | Critère | Statut | Preuve (exécutée quand possible) | Ce qui manque |
|---|---|---|---|---|
| 1 | Raccourci → Claude en mode automatique et brief apparaît sans action | P | lanceur `--dangerously-skip-permissions` ; test lanceur Linux OK ; brief injecté au SessionStart | Le brief n'apparaît qu'après un premier message : le lanceur ne passe aucun message initial ; Windows non testé (I) |
| 2 | Message citant une société → contexte sans demande | FV | hook simulé « holding Rochat » → 2 200 car. (E-001, C-001, délais) ; banc « menuiserie Rochat » : réponse juste en 38 s | — |
| 3 | Capture par script ; greffier a classé avant le brief suivant ; rien ne bloque | P | capture OK (test + banc) ; greffier lancé à la fin de session | Classement réel non vérifié ; aucun contrôle « tout classé avant le brief » |
| 4 | « Entre nous » sans trace | FV | banc réel : aucune ligne d'inbox, aucune occurrence dans `.equipe/`/`Bureau/` | Transcript de Claude Code hors contrôle (consigné) |
| 5 | Mémo : confort, sources datées avec canton, portes, un appel adverse, relecteur | P | test_production : mémo produit, portes passées | Appel adverse et relecteur non orchestrés ni vérifiés ; pas de mémo réel au banc |
| 6 | Taxation → horloge + projet de réclamation ; dividende → horloge IA ; relation → LBA | P | test_cerebro c6 ×3 OK ; fictif : DL-001 + DOC-0001 | « Projet » = stub tant que l'initiative n'a pas tourné ; règle IFD appliquée à une décision ICC VD |
| 7 | Nouveau mandat → contrôle de conflit | FV | test c7 OK (`matter new` → conflit signalé) | — |
| 8 | Cycle complet : export, brief, santé, sauvegarde, commit, push, poursuite de la construction | P | test plomberie « Cycle --complet » OK (sauvegarde, export, santé, brief) | « Poursuite de la construction » mise en file sans exécutant ; export pollué (A4) ; push non testé |
| 9 | Aucune demande de permission, aucun chemin ni nom d'outil à l'écran | P | banc : `refus=[]`, jargon=[] sur 3 réponses | Identifiants internes (M-001, DOC-0005) et gras dans la réponse d'ouverture |
| 10 | Rien ne part sans le mot de Mustafa ; push, connexions, installations sans question | FV | test « aucune commande d'envoi » ; `t_commit_push` | — |
| 11 | Chaque outil installé inventorié | P | 39 capacités (conteneur) | Perdu au clone ; plotly, poppler, plugin document-skills à inscrire |
| 12 | Personne liée à deux clients dans les deux vues ; brief le signale | FV | test c12 ×2 OK ; brief fictif « Luca Rochat (P-003) ↔ C-001, C-002 » | — |
| 13 | Tous les rôles lisent tout ; aucune perception recopiée | P | outils `Read` partout | Aucune porte script contre la recopie |
| 14 | Associé répond à toute question sur le cerebro sans refus | FNV | — | — |
| 15 | Question de droit → texte officiel, version, langue, canton/pays, date, ou ⚠ | P | `law article LIFD art. 132` → BIB-003, version 2026-09-02, URL (base du conteneur) | Sur clone : ⚠ systématique ; aucun texte cantonal |
| 16 | Besoin récurrent ou demande explicite → skill ou rôle testé et catalogué | A | banc « Désormais, chaque lundi… » : note de règle (en double) + 2 entrées `fabrique` en file, jamais traitées ; promesse « première liste lundi 5 octobre » sans mécanisme | Exécutant de la file `fabrique` + tâche hebdomadaire planifiée |
| 17 | Panne simulée d'un connecteur → résolue ou contournée, une phrase | P | intendant (MCP, config) ; incidents | Aucun test de panne de connecteur |
| 18 | Mail → brouillon ; RDV → fiche ; délai → document ; fichier déposé → lu, classé, commenté | P | banc ouverture : brouillon M-001 et fiche RDV créés ; ingestion fichier : lu, classé | Commentaire du dépôt = tâche en file (modèle) ; document de délai = stub |
| 19 | Analyse d'abord en tableau puis texte ; fichiers ouverts seuls | FV/I | banc : tableaux d'abord ; ouverture non observable | — |
| 20 | Session interrompue → reprise silencieuse ; aucun rapport perdu | P | CLAUDE.md + construction.md ; rapports en fichiers | Reprise ≠ silencieuse en coût (A2) ; rapport plomberie absent |
| 21 | Hors compétences → recherche d'outils en fond ; rôles génériques en attendant | P | `capability propose` | File `decouverte` jamais consommée |
| 22 | « Ce que vous n'avez pas demandé » pertinent ; document déposé relu sans demande | P | banc : rubrique pertinente (deux réponses) | Relecture du dépôt dépend de l'initiative |
| 23 | Chaque catégorie lue et produite (mail, Word, Excel, PowerPoint, PDF, note vocale) | P | Word/Excel/PPT/PDF/eml lus et produits (tests) | Note vocale : ni lue ni transcrite ; `.msg` non lu |
| 24 | Injection ≤ 6 000 en delta ; début ≤ 8 000 ; ≤ 5 ouvertures par question | P | 2 200 / 114 car. ; 803 car. | Banc : 9 appels Bash multi-ouvertures au « Bonjour » ; socle fixe 42 k tokens |
| 25 | Rappel > 95 % ; objet renommé atteignable ; lecture longue déléguée ≤ 1 500 | P | rappel 0,95 (circulaire) ; renommage OK (test) | Vrai test par paraphrases |
| 26 | Nouveau sujet → ID, ligne, [à confirmer], brief ; domaine nouveau → sommaire, spécialiste, file | P | test c26 OK | Spécialiste et ingestion du domaine non exécutés |
| 27 | Rien de perdu après condensation d'un mois ; double lecture rattrape un fait omis | A | condensation et double lecture absentes | — |
| 28 | Zéro zombie et couverture complète après une semaine simulée | P | test c28 (liens morts) | Orphelins/doublons non réparés ; pas de semaine simulée |
| 29 | Demande semblable → nouvelle version de l'existant ; reprise après compaction | P | `livrables.version` ; PreCompact → etat.md relu au démarrage | Non testé de bout en bout |
| 30 | Enrichissement : source → bibliothèque ; leçon → liste de contrôle ; outil → évalué ; semaine vide signalée | A | — | — |
| 31 | Aucune trace de machine ; réponse courte sans titre ni puces | P | porte tics ; banc entre-nous : réponse courte | Échantillon systématique non exécuté |
| 32 | Tout livrable sort d'un gabarit ; contrôle visuel ; typographie | FV | test_production 45/45 (gabarits, visuel, typo) | Heuristique visuelle limitée |
| 33 | Échelle ×10 : find < 2 s, rappel > 95 %, injection sous budget, passe < 1 h, niveau 0 stable | P | relecture noyau : 15 000 objets testés une fois | Test mensuel non automatisé |
| 34 | Bloc cardinal à jour partout ; livrable sans source / ID mort / sans prochaine action → correction puis réserves ; tableau de bord des principes | P | `cardinal check` vide ; portes sources/liens/couverture ; `tableau.py` | Tableau non tenu par le cycle |
| 35 | Budget frugal : un appel par échange, ≤ 3 appels de fond légers, aucun appel de fond sur le plus capable hors mémo, aucun réveil à vide, aucun journal chargé | A (contredit) | banc : « Bonjour » → sous-agent général (modèle de session, opus) en arrière-plan ; aucune limite quotidienne codée | Voir écart n° 2 et 3 |
| 36 | Prêt à l'emploi, questions différées (aucune en 1re session ; défauts dès l'étape 0 ; réponse → recalcul ; ≤ 1/message, ≤ 3/jour ; ≤ 1 conseil/jour) | P | tests c36 OK ; banc q=0 | Recalcul seulement mis en file ; questions jamais posées tant que construction non achevée |
| 37 | Sommaire central et config à trous | P | test c37 OK ; banc société conforme | Banc ouverture non conforme ; `config set` ne met pas à jour le sommaire |
| 38 | Lancement garanti : session de contrôle, brief, « bonjour » ; settings corrompu ou hook en échec restaurés | FV (Linux) | `valider_config.py` exécuté : control session OK ; tests plomberie 18-20 OK | Windows non testé (I) |
| 39 | Non-blocage (hooks, deny, erreurs, filtre, portes, sources, consigne déposée, règle par opération dédiée) | P | tous OK sauf le dernier point | « Règle demandée par Mustafa appliquée par l'opération dédiée » : opération absente |

---

## D. Banc de bout en bout (exécuté par l'auditeur)

Commande : `python3 .equipe/tests/e2e/banc.py --scenarios scratchpad/audit-scen.yaml --garder` (copie jetable des fichiers suivis par git + dossier fictif, base sans bibliothèque ni rôles enregistrés = situation d'un poste neuf).

| Scénario | Durée | Tokens entrée / sortie | Outils | Observations |
|---|---|---|---|---|
| « Bonjour » | 298 s (arrêté par l'auditeur) | 133 820 / 2 855 | 9 Bash (dont `head`, `sed`, `cat`, `ls` sur fichiers entiers) + **Agent general-purpose en fond « Reprise de la construction »** (47 appels avant arrêt : lecture de la constitution, `find . -type f`, tests complets, tentative de commit) | Réponse de bonne facture (tableau, rubrique « pas demandé ») ; aucune question ; suite du tour : brouillon M-001 et fiche RDV créés, réponse affichant « **M-001** », « DOC-0005 » |
| « Où en est-on avec la menuiserie Rochat ? » | 38 s | 137 981 / 3 285 | 2 Bash via `cerebro summary/open --section` | Conforme au protocole ; bail échu repéré en premier ; tableau puis texte |
| « Entre nous, ce client Rochat me fatigue » | 11 s | 42 508 / 685 | 0 | Aucune capture ; coût fixe ≈ 42 k tokens |
| « Taxation ICC vaudoise : délai de réclamation et base ? » | 56 s | **504 220** / 4 098 | 6 appels cerebro + recherche web | Réponse juste et honnête (art. 186 al. 1 LI-VD trouvé via un arrêt cantonal sur entscheidsuche.ch, ⚠ « pas encore vérifié sur le texte consolidé ») ; mais aucun texte cantonal en bibliothèque, la source consultée n'est pas ingérée (§9.5), gras dans la réponse, coût d'un demi-million de tokens pour une question |
| « Désormais, chaque lundi, liste des délais de la semaine » | 29 s | 223 372 / 2 145 | 5 appels cerebro | Réponse « C'est noté : votre première liste arrive lundi 5 octobre » ; règle enregistrée **en double** (N-002, N-003) et deux entrées `fabrique` en file ; **aucun exécutant** (ni fabrique, ni planification) : la promesse faite à Mustafa ne sera pas tenue |

Note de lecture : les tokens d'entrée sont cumulés sur tous les appels de modèle du tour, lectures de cache comprises (le cache réduit le prix, pas la consommation de quota) ; « entre nous » (un seul appel, aucun outil) mesure donc le socle fixe.

Défaut du banc lui-même : `banc.py` hérite de `CLAUDE_CODE_SESSION_ID` de la session appelante ; toutes les sessions écrivent dans le même transcript (`0876189b…jsonl`). Les scénarios ne sont donc pas indépendants. Correctif : retirer `CLAUDE_CODE_SESSION_ID` (et variables `CLAUDE_CODE_*` d'enfant) de l'environnement dans `tour()`. La détection de lectures larges (`lect`, `larges`) ignore `cat`/`head`/`sed` dans Bash quand la commande ne commence pas par eux.

---

## E. Les 20 écarts les plus importants, classés par impact sur Mustafa

(utilisateur non technicien, poste Windows vierge, coût en tokens)

1. **Clone vierge = mémoire vide (A1).** Travail : (a) `brief.export()` (`.equipe/cerebro/cb/brief.py:284`) : exclure toute table virtuelle FTS5 et ses tables d'ombre (`articles_fts*`, `noms_tri*`, `objets_fts*`, détecter via `sqlite_master.sql LIKE 'CREATE VIRTUAL TABLE%'`), puis exécuter `cerebro export` et commiter `.equipe/cerebro/exports/` ; (b) `importer_exports()` : reconstruire les index FTS après import et régénérer les sommaires ; (c) ajouter `cerebro reconcile` qui recrée les objets depuis les en-têtes YAML des fichiers (rôles, skills, méthodes, cabinet, gabarits) ; (d) installateur : vérifier le nombre d'objets après import et ne dire « reconstituée » que si > 0.
2. **Construction relancée à chaque session sur l'abonnement de Mustafa (A2).** Travail : marquer `construction: achevée` (ou « livrée, reste en fond ») dans `construction.md` avant livraison ; dans `brief.construction_ligne()` ne rien injecter hors machine de construction (ex. drapeau `.equipe/run/machine-de-construction`) ; retirer la « CONSIGNE DE REPRISE » de `CLAUDE.md` et de `config-valide/CLAUDE.md` ; si une reprise est voulue, la confier à `cycle.py` (priorité 6) via `claude -p` modèle intermédiaire avec budget, jamais à l'associé ; débloquer en conséquence `files.py:37-46` (questions).
3. **Coût fixe ≈ 42 k tokens par message (A3).** Travail : retirer `playwright` (et `markitdown`) de `.mcp.json` du projet principal et ne les donner qu'aux sous-agents qui en ont besoin (config MCP par agent ou `--mcp-config` pour les rôles de fond) ; raccourcir `associe.md` (6,4 k car.) et ne garder dans `CLAUDE.md` que le bloc cardinal + 1 k car. ; réduire les descriptions des 37 agents (déjà amorcé par 18e435d) ; mesurer le socle réel par une session de contrôle (`valider_config.py` : consigner `usage.input_tokens`) et l'inscrire au rapport de santé.
4. **Protocole sommaire non suivi par l'associé et les sous-agents généraux.** Travail : `associe.md` : interdire `cat/head/sed/ls/find` sur `.equipe` et `.claude` (« uniquement `mcp__cerebro__*` ») ; donner à l'outil MCP `open` sans section le menu des sections (`recherche.py open_section`) ; au hook `PostToolUse` (matcher Bash|Read) journaliser les lectures hors CLI dans `ouvertures` ; script d'archiviste au cycle qui calcule la conformité par rôle depuis les transcripts et alimente `fabrique`.
5. **Exports qui pousseraient la bibliothèque dans git (A4).** Travail : même correctif que n° 1 (a) + `.gitignore` : `.equipe/cerebro/exports/*fts*`, `.equipe/cerebro/exports/noms_tri*` ; test de non-régression dans `test_cerebro.py` (taille des exports < 2 Mo sur la base réelle).
6. **Bibliothèque absente du poste au premier lancement.** Travail : committer `t_bibliotheque_mise_a_jour` (en cours) ; la déclencher dès le premier `cycle --rattrapage` si `bibliotheque_vide()` (pas seulement au complet) et exécuter ensuite `baremes.py` et `cerebro law verify` ; dire dans `INSTALLATION.md` que la première mise à jour télécharge ~25 Mo ; tant que vide, le brief n'affiche pas les délais comme vérifiés.
7. **Fabrique et découverte non câblées : l'équipe ne peut pas créer seule agents, skills ou serveurs MCP ; elle promet pourtant des tâches récurrentes (« votre liste arrivera chaque lundi ») qu'aucun mécanisme n'exécute.** Travail : dédoublonner les règles (`find` avant `new note "Règle…"`) ; table ou type `regle_recurrente` (cadence, action) lue par `cycle.planifier()` qui produit le livrable au premier cycle du jour dit ; `cycle.py` : `t_fabrique` (cadence 7 j, priorité 5) qui lance `claude -p` avec `.equipe/roles/fabricant.md` sur la file `fabrique` ; `t_decouverte` (cadence 30 j + file `decouverte`) : script `scripts/decouverte/catalogue.py` (registre MCP officiel, `claude plugin marketplace list`, marketplaces Anthropic) puis un appel d'évaluation, `claude mcp add --scope project`, `capability register`, désinstallation sur échec ; détecteur de déclencheurs (greffier → `cerebro task-seen <type>` ; motif « désormais / à chaque fois / tous les » dans les captures → `queue add fabrique`).
8. **Notes vocales et `.msg` Outlook illisibles.** Travail : `ingerer.py` : `.msg` via `extract-msg` (pip utilisateur, ajouter à `installer.ps1 $libs`) ; audio via `faster-whisper` (modèle `small` dans `.equipe/outils/`, CPU, mode utilisateur) avec repli « transcription impossible » → question simple « pouvez-vous me le dicter ? » ; nouvelle catégorie de capacité inscrite.
9. **Messagerie et agenda non connectés.** Travail : choisir le connecteur officiel (M365 ou Google, lecture + brouillons), préparer la commande `claude mcp add` ou le connecteur claude.ai, l'écrire dans `INSTALLATION.md` (geste « autoriser »), faire alimenter `type=mail`/`type=rdv` par un script de synchronisation lecture seule ; jusque-là, accepter les `.eml/.msg` déposés comme source de la boucle d'initiative.
10. **Recalculs de configuration jamais exécutés.** Travail : ajouter à `cycle.TACHES` : `horloges_recalcul` (recalcul des délais selon les cantons), `doctrine_cantons` (créer `cerveau/doctrine/<canton>/`), `bibliotheque_cantons` (paramétrer `cantons.yaml`), `profil` (réécrire `profil-mustafa.md` depuis `config`) et régénérer le sommaire niveau 0.
11. **Brief absent sans premier message (critère 1).** Travail : `Mon-equipe.ps1`/`mon-equipe.sh` : lancer `claude --dangerously-skip-permissions "Bonjour"` (ou `--append-system-prompt` + message initial) pour que le brief s'affiche à l'ouverture ; vérifier qu'aucune question n'en résulte.
12. **Identifiants internes et gras visibles par Mustafa.** Travail : `associe.md` : interdire explicitement les identifiants (`C-`, `DOC-`, `M-`…) ; filtre `hook.py stop()` : ajouter la détection d'identifiants au journal `vocabulaire` ; porte `p_jargon` sur les réponses de conversation capturées (analyse différée au cycle).
13. **Budget frugal non appliqué (critère 35, §7.6).** Travail : compteur quotidien des appels de fond dans `files.mesure` ; `initiative.py`/`greffier.py` consultent `modeles.budget_fond_quotidien_appels` ; seuils 60 %/85 % dans `cycle.increment()` (priorités 5-6 puis 4 suspendues) ; mesure du coût de l'associé via le transcript au hook `Stop` (`usage`) ; détection des erreurs de limite et phrase « je continue plus tard ».
14. **Portes incomplètes et tableau de bord non tenu.** Travail : `portes/p_sommaires.py` (objets cités/touchés non `a_regenerer`), `portes/p_contexte.py` (injection du tour ≤ 6 000) ; ajouter `tableau.tableau()` à `cycle` (tâche `principes`, cadence complète) et son résumé à `health` ; écart deux cycles → `queue add fabrique "réviser <rôle>"`.
15. **Appel adverse groupé non orchestré.** Travail : dans `produire.py` (ou skill production-livrables), pour `type ∈ {memo, avis, calcul, presentation, pv, convention}` : lancer un seul `claude -p` avec `.claude/agents/panel-adverse.md` + rendu PNG des pages, enregistrer la note « Panel — … », compter l'appel dans `mesures`, puis relecteur ; porte qui vérifie qu'un panel a eu lieu pour ces types.
16. **Horloges cantonales manquantes.** Travail : `horloges.REGLES` : réclamation ICC (LHID art. 48 déjà ingéré, + loi cantonale VD/GE quand ingérée), déclarations fiscales et prolongations par canton, FOSC ; corriger `event_taxation` pour choisir IFD ou ICC selon l'autorité ; ingérer LI VD et LIPP/LIPM GE (`cantons.yaml`).
17. **Données de répétition sans vrais fichiers ; démonstration §16.8 absente.** Travail : `tests/fixtures/depot/` avec un `.eml`, un `.msg`, un PDF texte, un PDF scanné, un `.docx` avec suivi des modifications, un `.m4a` ; script `tests/e2e/demonstration.yaml` (mail, droit cantonal, réclamation, schéma) rejoué et consigné dans un rapport.
18. **Rôle « responsable d'expérience » manquant ; missions de fond jamais lancées (veilleur, tuteur, archiviste, chef de cabinet).** Travail : créer `.claude/agents/responsable-experience.md` (bloc cardinal, §7) ; cadences dans `cycle.py` : veille hebdomadaire (scripts + un appel groupé), tuteur hebdomadaire, conseiller d'anticipation (5 clients / 30 j), revue hebdomadaire.
19. **Recherche académique, sources étrangères, OCR absents.** Travail : `scripts/recherche/academique.py` (CrossRef, Semantic Scholar ; OpenAlex avec pause) et `scripts/recherche/etranger.py` (legislation.gov.uk API, CourtListener API, EUR-Lex SPARQL) ; OCR utilisateur (`ocrmypdf`/tesseract portable si possible, sinon tâche de lecture par le modèle réellement consommée par l'initiative) ; inscrire les capacités.
20. **Fin de construction, protections et traçabilité de projet.** Travail : `CHANGELOG.md`, tags par étape, coût de construction au dossier technique §4, rapport du chantier plomberie, mise à jour de `construction.md`/`backlog.md` ; puis seulement : empreinte de la constitution (base + tag), restauration au démarrage dans `brief.session_start`, opération `cerebro regle appliquer` (phrase, date, différentiel, régénération des blocs, tag), journal d'audit vérifié par empreinte chaînée.

---

## F. Taux global

Sur les 299 lignes d'exigence des tableaux B (hors §18, simple récapitulatif) : **FV strict 111 (37 %)** ; FV de portée limitée (consigne seule, banc, schéma, Linux) 13 (4 %) ; FV/FNV 6 (2 %) ; FNV 12 (4 %) ; **P 116 (39 %)** ; **A 39 (13 %)** ; I 2 (1 %).
Critères §17 : FV 8/39 (2, 4, 7, 10, 12, 32, 38 sous Linux, 19 en partie) ; P 26/39 ; A 4/39 (16, 27, 30, 35) ; FNV 1/39 (14).
Une réserve s'ajoute : plusieurs FV ne tiennent que dans le conteneur de construction (base non livrée, voir A1). Sur un poste neuf, une dizaine d'entre eux (méthodes, inventaire, bibliothèque, règles vérifiées) redeviennent partiels.
