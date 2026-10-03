# Rapport chantier bibliothèque juridique — T-040 + T-053 (partie données)
date: 2026-10-03 · statut: livré, testé (10/10) · non commité (orchestrateur)

## IDs créés / touchés (base réelle)
- sources bibliothèque : BIB-001…BIB-028 (23 actes RS, 28 versions-langues). FR : CO 220 (BIB-001), LFus 221.301 (002), LIFD 642.11 (003), LHID 642.14 (004), LIA 642.21 (005), OIA 642.211 (006), LT 641.10 (007), LTVA 641.20 (008), LBA 955.0 (009), LTPM 955.3 (010), LPD 235.1 (011), LP 281.1 (012), LTF 173.110 (013), 173.110.3 (014), ORC 221.411 (017), OT 641.101 (018), OTVA 641.201 (019), OBA 955.01 (020), OBA-FINMA 955.033.0 (021), OTPM 955.31 (022), CC 210 (023), LPGA 830.1 (024), LAVS 831.10 (025). DE : OR (015), DBG (016). Versions antérieures (état 2024) : LIA 2024-01-01 (026), LIFD 2024-05-16 (027), LTVA 2024-01-01 (028).
- règles de délais : RD-001…RD-008 toutes vérifiées (2 corrigées), corps régénérés avec extrait, version et source.
- barèmes : BAR-001…BAR-024 (impot_anticipe, tva, droit_emission, ifd_personnes_morales).
- capacités : CAP-001 Fedlex SPARQL, CAP-002 Fedlex filestore, CAP-003 LINDAS Zefix, CAP-004 Zefix web, CAP-005 BLV (repéré), CAP-006 SIL GE (repéré), CAP-007 LexFind (repéré), CAP-008 fedlex.py, CAP-009 mise_a_jour.py, CAP-010 baremes.py, CAP-011 zefix.py, CAP-012 calculs.
- doctrine : DOCT-001 « Bibliothèque fédérale : état et mode d'emploi » (cerveau/doctrine/), point d'entrée des agents.

## Règles de délais (cerebro law verify, 2 passes OK)
| règle | article exact (texte ingéré) | extrait contrôlé | issue |
|---|---|---|---|
| RD-001 réclamation IFD | RS 642.11 art. 132 al. 1 (v. 2026-09-02) | « 30 jours » | vérifiée |
| RD-002 recours IFD | RS 642.11 art. 140 al. 1 | « 30 jours » | vérifiée |
| RD-003 IA dividende | RS 642.21 art. 16 al. 1 let. c + art. 12 al. 1 (v. 2025-01-01) | « trente jours après la naissance de la créance fiscale » | **corrigée** (extrait « 30 jours » absent : le texte dit « trente jours ») |
| RD-004 décompte TVA | RS 641.20 art. 71 al. 1 (v. 2025-03-31) | « 60 jours » | vérifiée |
| RD-005 AG ordinaire | RS 220 art. 699 al. 2 (v. 2026-10-01) | « six mois » | vérifiée |
| RD-006 annonce ayant droit | RS 955.3 (LTPM) art. 13 al. 3 (v. 2026-10-01) | « un mois à compter de la création du contrôle » | **corrigée** : art. 697j CO abrogé avec effet au 1.10.2026 (annexe ch. 2 LTPM) |
| RD-007 opposition | RS 281.1 art. 74 al. 1 (v. 2026-01-01) | « dix jours » | vérifiée |
| RD-008 recours TF | RS 173.110 art. 100 al. 1 (v. 2026-04-01) | « 30 jours » | vérifiée |
Aucune retirée. Corrections faites dans `.equipe/cerebro/cb/horloges.py` (liste REGLES, lignes RD-003 et RD-006 : RS, article, extrait ; seul changement dans ce fichier) et dans la table `regles_delais`.

## Fait
1. `scripts/bibliotheque/fedlex.py` : chaîne JOLux découverte par requêtes réelles (documentée en tête) : RS → `skos:notation` de la taxonomie → `ConsolidationAbstract` (inForceStatus/0) → `Consolidation` (dateApplicability/dateEndApplicability) → Expression par langue → Manifestation xml/html → `isExemplifiedBy` (URL filestore). XML Akoma Ntoso → markdown « ## Art. N titre marginal » (alinéas numérotés, lettres et chiffres en listes, tableaux, structure en « ### », notes de bas de page en fin ; article abrogé : la note officielle reste dans l'article). Repli HTML (non exercé : tous les textes avaient du XML). Pause 1 s (SPARQL) / 2 s (fichier), cache `.equipe/bibliotheque/cache/`, journal `cache/journal.jsonl`. Échec → `incident add` + `queue add bibliotheque_rattrapage <RS> --priorite 5`. Fin d'applicabilité publiée → `valide_au` (lendemain, exclusif).
2. `priorites.yaml` : 23 textes, RS et titres officiels vérifiés par SPARQL (OBA, OBA-FINMA, OT, LTPM, OTPM ajoutés). LTPM découverte en vérifiant RD-006.
3. Barèmes : `baremes.yaml` (valeurs lues dans le texte) + `baremes.py` qui relit l'article et vérifie l'extrait avant `cerebro rates set` (idempotent ; échec → non inscrit + incident). Source : « RS x art. y, version v (BIB) : « extrait » ». Années : année en cours + années entières couvertes par la version.
4. `scripts/calcul/` : commun.py (barème via `cerebro rates get`, une expression = Python et formule Excel), impot_anticipe.py (brut/IA/net, option --net), tva.py (HT↔TTC, 3 taux), droit_emission.py (base max(apport, nominal), franchise art. 6 al. 1 let. h). JSON + `--excel` (Hypothèses / Calcul / Sources, formules vérifiées par recalcul LibreOffice). Barème absent → ⚠, `resultat: null`.
5. `mise_a_jour.py` : rattrapage, contrôle de chaque texte ingéré et des priorités manquantes, nouvelle consolidation → ingestion + `changement_droit` lié (ancienne/nouvelle source + objets qui citaient l'ancienne) + `bibliotheque_maj` priorité 5 + relance verify et barèmes. Testé en racine jetable (LIA 2022 → 2025 : CHG créé, file alimentée, asof correct). Sur la base réelle : 25/25 à jour, 50 s.
6. `cantons.yaml` : VD (BLV, API JSON publique non documentée ; cotes LI 642.11, loi d'impôt 2026, LICom 650.11 lues dans l'API), GE (SIL, pages HTML statiques ; LIPP D 3 08, LIPM D 3 15, LPFisc D 3 17 vérifiées), LexFind (API JSON accessible). Rien d'ingéré.
7. `zefix.py` : LINDAS (graphe foj/zefix) par nom ou IDE → raison sociale, forme (eCH-0097), siège, canton, adresse, but. Statut absent du jeu LINDAS → complété par la recherche publique de l'application web zefix.ch (sans compte, ehraid identique), sinon ⚠. Testé : Nestlé S.A. (CHE-105.909.036, Vevey, SA, inscrite), Swisscom AG.
8. `juridique.py` (bogues corrigés, signalés) : (a) `verify_rules` relisait la source réécrite après vérification (« RS 642.11 (BIB-…) ») → 2e passe en échec ; extraction du n° RS par regex ; une règle qui n'est plus confirmée perd `verifie_le` ; sortie enrichie (id, extrait, version). (b) `asof` ignorait `valide_au` → renvoyait une version périmée pour une date non couverte ; filtre ajouté (renvoie None → ⚠). (c) `ingest` d'une version antérieure après la suivante : `valide_au` posé.

## Mesures
- Ingestion réseau : 14 textes FR 62 s ; CO+LIFD DE et 9 textes FR 99 s ; 3 versions 2024 15 s ; réingestion depuis cache 74 s. ~2,5 s/texte en cache, ~5 s sinon.
- Volume : `.equipe/bibliotheque` 25 Mo (ch/ 6,0 Mo de markdown ingéré ; cache/ 18,8 Mo dont XML sources et markdown intermédiaire). Base : +1 à 2 Mo estimés (index FTS ~0,5 Mo ; base partagée avec d'autres chantiers, 0,4 → 3,2 Mo au total).

## Tests
`python .equipe/tests/test_bibliotheque.py` → 10/10 : law article 642.11 art. 132 (texte, version, URL) ; asof (LTVA 2024-06-30 → version 2024-01-01, trou 2025-02 → rien) ; verify 2 passes en racine jetable ; IA sans barème → ⚠ ; IA avec barème = texte LIA art. 13 ; TVA, droit d'émission, Excel en formules ; baremes.py sans texte → rien d'inscrit ; conversion AKN hors réseau ; SPARQL ; Zefix.

## Écarts, dettes, signalements hors périmètre
- **Bogue hors périmètre (cerebro)** : `cerebro regen` sans argument plante (UnicodeDecodeError) car `incident_add` et `question add` donnent aux objets `chemin=.equipe/cerebro/cerebro.db` ; `write_file` tente de lire la base comme markdown (Q-001…Q-011, INC-001). Aucun dégât (la lecture échoue avant écriture) mais c'est une mine : corriger dans files.py (chemin vide ou fichier dédié) et/ou objets.write_file (ignorer un chemin non .md). J'ai régénéré mes objets par ID.
- **Index plein texte** : `objets.index_fts` tronque le corps à 20 000 caractères → seul le début de chaque loi est cherchable par `find`/`law search`. Proposition : indexer par article (table dédiée) ou relever la limite pour type source.
- Brancher `python .equipe/scripts/bibliotheque/mise_a_jour.py` dans le cycle complet (`scripts/entretien/cycle.py`, autre chantier) et traiter `bibliotheque_maj` au cycle d'entretien (diff, positions touchées, alerte-changement-droit).
- `changements_de_droit` (table typée) non alimentée : `cerebro new changement_droit` ne crée que l'objet ; entrée en vigueur mise dans le résumé.
- Droit d'émission : lecture « franchise imputée » de l'art. 6 al. 1 let. h marquée ⚠ (pratique AFC non ingérée). IA --net : reconstitution du brut marquée ⚠.
- Trous de versions : LTVA 2025-01-01/2025-02-27 et LIFD 2025-01-01…2026-09-01 non ingérées → asof renvoie rien (⚠) sur ces périodes ; à ingérer si un dossier le demande (`fedlex.py ingest 641.20 --date AAAA-MM-JJ`).
- Non fait : italien, circulaires AFC, FF, jurisprudence ; ingestion cantonale (convertisseur GE à écrire, API VD à paramétrer) ; repli PDF des anciennes versions.
- Abréviation officielle absente pour RS 173.110.3 : aucune inventée (dossier `ch/173-110-3`).

## Poste Windows
Stdlib + PyYAML + openpyxl ; pathlib ; sous-processus `sys.executable` + PYTHONIOENCODING/PYTHONUTF8 ; stdout reconfiguré en UTF-8. Lancer : `python .equipe\scripts\bibliotheque\mise_a_jour.py`, `python .equipe\tests\test_bibliotheque.py`. Le cache (25 Mo) n'est pas suivi par git : premier cycle sur le poste = retéléchargement (~3 min) ou copie du dossier `.equipe\bibliotheque`.
