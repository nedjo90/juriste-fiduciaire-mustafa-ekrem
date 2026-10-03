# Rapport chantier production — T-051 (producteur, design, gabarits) + T-060 (portes, partie scripts)
date: 2026-10-03 · statut: livré, testé (45/45) · non commité (orchestrateur)

## IDs créés (base réelle)
- skills : SK-017 frontend-design, SK-022 canvas-design, SK-023 theme-factory, SK-024 brand-guidelines (réécrite), SK-025 doc-coauthoring, SK-026 internal-comms, SK-027 skill-creator, SK-028 humanizer, SK-029/030/031 humanizer-fr/de/it, SK-032 production-livrables
- gabarits : GAB-001 memo.docx, GAB-002 lettre.docx, GAB-003 pv-assemblee.docx, GAB-004 modele-calcul.xlsx, GAB-005 presentation.pptx, GAB-006 gabarit-rapport.pdf (Bureau/Modeles/)
- capacités : CAP-013 produire.py, CAP-014 portes.py, CAP-015 gabarits.py, CAP-016..020 python-docx/openpyxl/python-pptx/reportlab/matplotlib, CAP-021 LibreOffice, CAP-022 poppler, CAP-023 Mermaid CLI (indisponible ici), CAP-024 document-skills Anthropic (à installer par plugin)
- bloc cardinal injecté (cardinal check : 0 périmé). Réinscription idempotente : `python .equipe/scripts/producteur/inscrire.py`.

## Fait
1. Skills officielles : clone git anthropics/skills commit 8a1541c4 (2026-09-28). Licences lues dossier par dossier. Copiées avec SOURCE.md : frontend-design, canvas-design (polices OFL), theme-factory, brand-guidelines, internal-comms, skill-creator (Apache-2.0, LICENSE.txt), doc-coauthoring (aucun LICENSE dans le dossier ; Apache-2.0 présumée d'après le README du dépôt, noté). **docx/pptx/xlsx/pdf NON copiées** : licence propriétaire Anthropic (« may not … retain copies outside the Services / reproduce or copy ») ; voie conforme = plugin officiel `document-skills@anthropic-agent-skills` (CAP-024, statut a-installer). Nos générateurs (python-docx, openpyxl, python-pptx, reportlab) couvrent la production sans elles. brand-guidelines réécrite pour la charte de la maison. humanizer (blader/humanizer, commit 225a6f39, MIT) copiée, code lu (consigne seule, aucun exécutable repris) ; variantes humanizer-fr/de/it écrites.
2. Design : `.equipe/cerveau/cabinet/design/systeme.yaml` (palette 9 couleurs + 6 graphiques, contrastes WCAG vérifiés par `design.py --verifier`, Calibri/Cambria/Consolas + replis, grille A4 et 16:9, en-têtes/pieds, titres numérotés, tableaux, légendes FR/DE/IT/EN, thème matplotlib, schémas, conventions typo par langue, structure attendue par type, alias de sections multilingues). `design.py` surcharge l'identité par cabinet.yaml (valeur renseignée seulement, via cb.config = cerebro config get).
3. Gabarits générés par `gabarits.py [--inscrire]` (régénérables) : mémo (page de titre, 10 sections + annexe des sources, en-tête Confidentiel, pied « Version · État du droit au », Page x/y, titres numérotés multiniveaux liés aux styles), lettre, PV, modèle de calcul (Hypothèses/Calculs/Sensibilités/Sources, noms définis, zéro littéral), présentation (thème couleurs/polices de la maison, 16:9), spécimen PDF reportlab.
4. `produire.py <md>` : front matter → corrections sûres (⚠ + typo) → rendu depuis gabarit (memo/note/lettre/pv docx, calcul xlsx, presentation pptx, rapport pdf, mail .eml X-Unsent + .txt) → PDF soffice sinon reportlab → BIB-… en renvois [n] + annexe des sources depuis la bibliothèque → blocs ```mermaid (PNG/SVG + .drawio) et ```graphique (message/unité/source) → TdM avec numéros de page exacts au-delà de 10 pages (2 passes) → portes → `deliverable register` → ouverture (startfile/open/xdg-open, silencieuse). Chemins `Bureau/Livrables/<client-slug>/<date>-<objet>/client-objet-date-vN.ext` (ASCII kebab-case, version auto). Source corrigée et rendus PNG côté machine : `.equipe/run/` (ignoré par git).
5. Portes `.equipe/scripts/portes/` : p_liens, p_sources, p_typo (correction auto), p_tics (FR/DE/IT/EN + mesures structurelles), p_jargon (règle zéro), p_presentation, p_couverture, p_visuel (soffice + pdftoppm, encre dans les marges, titres orphelins, tableaux trop larges, formes pptx hors cadre), p_budget ; `portes.py <fichier> [--corriger]` → JSON {porte: etat, details, corrections}, code 0 toujours, `a_renvoyer` = rôle responsable. `tableau.py` : table `portes_passages` (créée par le module) + `cerebro mesure` → taux de premier passage par rôle/skill/porte, écarts < 80 %.
6. Skill production-livrables (workflow complet, tableau des portes, bloc cardinal).
7. Tests `.equipe/tests/test_production.py` (racine jetable, dossier fictif, source BIB fictive) : 45/45 OK en ~20 s. Fixtures : `.equipe/tests/fixtures/{memo,lettre,mail,calcul,presentation,pv}_demo.md`.

## Écarts / dette
- Mermaid CLI échoue ici (Chrome de puppeteer absent) → repli matplotlib (organigrammes simples) ; échec mémorisé 7 jours (`.equipe/run/mmdc-indisponible`).
- Contrôle visuel : heuristique simple (marges latérales, orphelins) ; débordements verticaux et tableaux coupés en milieu de ligne non détectés par l'image (lignes insécables + en-tête répété imposés par le gabarit). Polices Calibri absentes de Linux : rendu de contrôle avec substitution.
- Portes sources/tics : motifs regex ; faux positifs possibles (ex. « CO » isolé, « IA » en sujet de mémo). Le producteur ne réécrit pas la prose : tics/jargon/structure reviennent au rôle.
- Présentation : titres-affirmations contrôlés par nombre de mots (≥ 4), pas par analyse grammaticale.

## Hors périmètre — changements à faire par l'orchestrateur
1. **Bug cerebro** : `cerebro regen` (sans ID) plante sur Q-… et INC-… (chemin = cerebro.db, types absents de `EXTERNES` → `write_file` lit la base comme texte). Corriger `objets.EXTERNES` (+ "question", "incident") ou ne pas poser ce chemin dans files.py.
2. `cerebro new skill … --source` crée un fichier d'objet parasite (chemin non posé pour les types EXTERNES) ; proposer `--chemin` ou chemin = source pour ces types. J'ai utilisé l'API (inscrire.py) pour l'éviter.
3. `core.new_id` : collision sous écritures concurrentes (IntegrityError vue avec un autre chantier) → réessayer.
4. Entretien : la tâche de file `gabarits` (posée par `config set cabinet.*`) doit lancer `python .equipe/scripts/producteur/gabarits.py --inscrire`.
5. Installateur / settings : `claude plugin marketplace add anthropics/skills` puis `claude plugin install document-skills@anthropic-agent-skills` (skills docx/pptx/xlsx/pdf officielles, sans copie).

## À faire sur le poste Windows
- LibreOffice (portable accepté : chemin `.equipe/outils/LibreOfficePortable/…` déjà cherché) ; poppler portable (pdftoppm/pdftotext) ou `pip install pypdf` sinon contrôle visuel en réserve ; Node pour Mermaid CLI (télécharge Chromium au premier usage).
- Vérifier ouverture auto (os.startfile), rendu Calibri/Cambria, .eml ouvert comme brouillon par Outlook.
- Rejouer `python .equipe/tests/test_production.py`.
