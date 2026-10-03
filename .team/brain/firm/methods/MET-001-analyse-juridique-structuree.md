---
id: MET-001
type: methode
statut: actif
maj: 2026-10-03
prochaine_action: 2027-01-04 réviser avec les leçons des livrables (fabrique)
risque_principal: 
chiffre_clé: 
résumé: Question fermée → faits étiquetés → normes sourcées datées → conditions subsumées une à une → contre-lecture → conclusion avec niveau de confort et suites pratiques.
mots_clés: méthode cabinet
liens: 
source: constitution §10 ; méthodes des grandes études et fiduciaires
---
# Analyse juridique structurée (machine)
usage: toute question de droit (conversation, mémo, avis, réclamation). Style « Gutachten » suisse : Sachverhalt → Rechtsfrage → Rechtsgrundlage → Subsumtion → Ergebnis.

## Étapes
1 QUESTION : une phrase fermée. Qui (P-/E-), quoi, où (canton, commune), quand (date des faits, période fiscale), pour quel usage (conseil, réclamation, acte). Voir MET « quel canton, quelle langue, quel délai ».
2 FAITS : liste datée ; chaque fait étiqueté [fait vérifié]/[déclaré par X le …]/[perception]/[hypothèse] + ID (DOC-, M-, RDV-). Fait manquant décisif → [hypothèse] explicite + `cerebro question add` si la réponse change l'issue.
3 NORMES : `cerebro law search "<notion>"` → `cerebro law article <abrév> "art. N"` ; version applicable aux faits : `cerebro law asof <RS> --date <date des faits>`. Niveau : fédéral / cantonal / communal / conventionnel (CDI) / étranger. Pratique administrative (circulaires) à part de la loi. Absent de la bibliothèque → chercheur/documentaliste ; sinon ⚠.
4 CONDITIONS : découper chaque norme en conditions (éléments constitutifs) et conséquence juridique. Tableau : condition | fait(s) | remplie / non / incertaine | pourquoi | source.
5 CONTRE-LECTURE : meilleure lecture adverse (MET contradiction en deux temps) ; autorités contraires listées, jamais tues.
6 CONCLUSION : réponse en une phrase + niveau de confort (MET niveaux de confort) + ce qui le ferait changer.
7 SUITES : actes, délais (`cerebro clock start`), coûts, qui fait quoi, prochaine action datée.
8 « CE QUE VOUS N'AVEZ PAS DEMANDÉ » : conséquences croisées (fiscal ↔ sociétés ↔ social ↔ LBA ↔ successions), options, opportunités.

## Contrôle
[ ] question fermée, canton et période fixés · [ ] faits étiquetés et datés · [ ] chaque norme : ID BIB- + art./al./let. + version + date d'état + canton · [ ] droit intertemporel traité · [ ] chaque condition subsumée · [ ] autorités contraires mentionnées · [ ] niveau de confort non surélevé · [ ] délais calculés par horloge, jamais en prose · [ ] prochaine action datée

## Pièges
répondre de mémoire · appliquer la version actuelle à des faits anciens · oublier le droit cantonal/communal · traiter une circulaire comme une loi · sauter une condition « évidente » · mêler faits déclarés et vérifiés · conclure sans conséquence pratique · ignorer la compétence (autorité, for) et la forme (écrit, acte authentique, inscription).

## Exemple (court)
Q : « La SA du client peut-elle verser un dividende en cours d'exercice ? » → C-nnn/E-nnn, VD, exercice 2026.
Faits : comptes 2025 approuvés [fait vérifié DOC-nnnn] ; bénéfice 2026 en cours [déclaré par le CFO le 2026-09-30].
Normes : dispositions CO sur le dividende intermédiaire ⚠ (à extraire : `cerebro law search "dividende intermédiaire"`).
Conditions : tableau (comptes intermédiaires ? révision ? décision AG ?) chacune avec article lu.
Conclusion : « devrait être possible si … » (should) — jamais plus haut tant que les conditions ne sont pas toutes lues dans le texte.
Suites : horloge impôt anticipé dès la date d'échéance du dividende ; projet de PV d'AG ; ce que vous n'avez pas demandé : effet sur la réserve légale et sur la planification successorale de l'actionnaire.
