# rapport chantier « équipe » (machine) — 2026-10-03
tickets: T-050 done · T-052 done · T-070 done · T-090 (rôles) done · T-100 (structure) done
tests: `python .equipe/tests/test_equipe.py` → 18/18 OK ; `cerebro cardinal check` → vide ; session réelle `claude -p` (haiku) liste bien les sous-agents du projet.

## Fait
1 Fiches méthodes (§10) : MET-001…MET-016 via `cerebro new methode` (en-tête, ligne de sommaire, sections Étapes/Contrôle/Pièges/Exemple ; IDs d'exemple neutralisés en « DOC-nnnn » pour ne pas créer de liens morts).
  001 analyse juridique · 002 hiérarchie/datation · 003 table des autorités · 004 pyramide/SCQA · 005 rédaction claire · 006 négociation raisonnée · 007 parties prenantes · 008 pre-mortem · 009 contradiction deux temps · 010 panel adverse · 011 niveaux de confort · 012 ce qu'on n'écrit pas · 013 canton/langue/délai · 014 schéma d'abord · 015 lire sans tout relire · 016 réutiliser.
2 Cabinet (`.equipe/cerveau/cabinet/`, type cabinet, chemin = fichier) : CAB-003 identite.md · CAB-004 niveaux-confort.md · CAB-005 styles.md · CAB-006 modeles-livrables.md · CAB-007 glossaire.md · CAB-008 lexique.md · CAB-009 associe.md. CAB-001 profil-mustafa.md et CAB-002 environnement.md étaient absents de la base alors que leurs en-têtes portaient ces IDs : enregistrés tels quels (fichiers non modifiés).
3 Glossaire FR/DE/IT/EN : ~120 notions + 28 lois (abréviations fr/de/it) ; aucune définition ; article inscrit seulement si vérifié en bibliothèque : 11/120 reliés (définition textuelle à l'al. 1, ex. art. 620 CO BIB-001), le reste « ⚠ à relier ». Script rejouable : `.equipe/scripts/cabinet/relier_glossaire.py` (HORS PÉRIMÈTRE, fichier nouveau, à valider).
4 associe.md : ≈ 1 430 tokens estimés.
5 Sous-agents : 37 fichiers `.claude/agents/*.md` (YAML name/description/tools/model ; opus : conseiller, 12 spécialistes, chercheur, avocat-plaideur, rédacteur, éditeur humain, panel, stratège, négociateur, fabricant ; haiku : chef-de-cabinet ; sonnet : le reste). Chacun : mission, méthodes MET-, étapes, sources (bibliothèque `cerebro law …` puis liste blanche §10), pièges suisses, modèles, liste de contrôle, principes L1-L10 → portes, rapport ≤ 1 500 car., « ne fait jamais ». Enregistrés ROLE-001…ROLE-037.
6 Missions de fond `.equipe/roles/` (prompt `claude -p`) : fabricant, chef-de-cabinet, veilleur, ingesteur, archiviste, tuteur → ROLE-038…ROLE-043 (alias « <nom>-fond »).
7 Skills métier (16) + importées (4) → SK-001…SK-021 sauf SK-017 (autre chantier) : redaction-memo-avis, redaction-mail, reclamation-fiscale, convention-actionnaires, pv-assemblee-decisions, decisions-circulaires, recherche-juridique-sourcee, controle-conflits, dossier-lba, revue-anticipation, brief-quotidien, ingestion-depot, compte-rendu-rdv, fiche-rdv, alerte-changement-droit, onboarding-client ; importées et adaptées (SOURCE.md, original + LICENSE dans reference/) : revue-tabulaire, chronologie-faits, historique-avenants (claude-for-legal), audit-tableur (financial-services) ; dossier-lba reprend la méthode kyc-doc-parse/kyc-rules (références copiées).
8 Plugins : `claude plugin marketplace add anthropics/claude-for-legal` et `anthropics/financial-services` → OK (marketplaces valides, Apache-2.0). Aucun plugin installé : entretiens de démarrage interactifs et contenu US. Ajout d'abord fait en portée projet (créait `.claude/settings.json`, hors périmètre) → retiré, redéclaré en portée utilisateur (machine de construction seulement). Inventaire : CAP-025…CAP-033.
9 `cerebro cardinal inject` (75 cibles, y c. fichiers d'autres chantiers : skills de production, greffier.md — effet voulu du mécanisme) ; `cerebro regen` des 109 objets du chantier.

## Ligne d'import proposée pour CLAUDE.md (non modifié)
`@.equipe/cerveau/cabinet/associe.md`

## Écarts / bugs constatés hors périmètre (non corrigés)
- B1 `cerebro regen` sans ID (et `--sales`) plante : objets question/incident ont chemin=`.equipe/cerebro/cerebro.db` et ne sont pas dans EXTERNES → write_file lit la base comme texte (UnicodeDecodeError). Correctif proposé (objets.py) : ajouter "question","incident" à EXTERNES ou ignorer un chemin non .md dans write_file. Contournement utilisé : regen par IDs.
- B2 `cerebro new <type externe> --source <f>` écrit d'abord un fichier orphelin `cerveau/notes/<type>/…` ; mon script fait `update chemin=` puis supprime l'orphelin. Correctif proposé : si --source désigne un fichier existant, l'utiliser comme chemin.
- « responsable d'expérience » (§6.3) non créé (hors liste de la mission).

## Dette
- générateurs des sous-agents/skills restés dans le bloc-notes de session : les fichiers sont désormais la référence (la fabrique les édite directement).
- missions de fond supposent des types de file (`fabrique`, `veille`, `ingestion_commentaire`, `revue_anticipation`, `gabarit`) que le cycle d'entretien doit produire (chantier entretien).
- nouveaux rôles d'autres chantiers (intendant, entretien) : relancer `cerebro cardinal inject` après leur création.
- glossaire : 109 notions « ⚠ à relier » → documentaliste à chaque ingestion ; libellés IT/EN à relire par un relecteur de langue avant usage externe.

## Poste Windows
rien de spécifique : tests en Python stdlib + PyYAML (`py .equipe\tests\test_equipe.py`) ; missions de fond : `< $null` au lieu de `< /dev/null` ; marketplaces non nécessaires (skills copiées localement).
