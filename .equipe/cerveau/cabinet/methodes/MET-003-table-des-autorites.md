---
id: MET-003
type: methode
statut: actif
maj: 2026-10-03
prochaine_action: 2027-01-04 réviser avec les leçons des livrables (fabrique)
risque_principal: 
chiffre_clé: 
résumé: Tableau unique de toutes les autorités d'un dossier : texte, type, niveau, juridiction, date, langue, contraignant ou persuasif, passage exact, sens pour ou contre, identifiant, vérifié le.
mots_clés: méthode cabinet
liens: 
source: constitution §10 ; méthodes des grandes études et fiduciaires
---
# Table des autorités (machine)
usage: annexe de tout mémo, avis, note de recherche, réclamation, recours préparé ; produite par le chercheur, vérifiée par le documentaliste.

## Colonnes
n° | autorité (texte/arrêt/circulaire/doctrine) | type | niveau (MET hiérarchie) | juridiction (CH, CH-VD, FR…) | date (version/arrêt) | langue | contraignant/persuasif/pratique | passage exact (cité, guillemets, ≤ 3 lignes) | pour/contre/neutre | ID BIB- | vérifié le

## Étapes
1 Collecter : bibliothèque d'abord (`cerebro law search`, `cerebro find --type source`), puis sources officielles en liste blanche (§10). Aucune autorité de mémoire.
2 Qualifier chaque ligne (niveau, statut, date) ; écarter ce qui n'est pas applicable dans le temps (le noter).
3 Trier : poids décroissant, puis date décroissante.
4 Autorités contraires : toujours présentes, marquées « contre », avec la réponse prévue (renvoi au § de l'analyse).
5 Vérifier : le documentaliste compare chaque passage au texte (lettre à lettre) et remplit « vérifié le » ; sinon ⚠.
6 Enregistrer : chaque autorité nouvelle → `cerebro law ingest` (texte) ou fiche `source` ; lien vers le livrable (`cerebro link LIV-… BIB-…`).

## Formats de citation
fr : art. 698 al. 2 ch. 4 CO · ATF 1xx II yyy consid. 3.2 · arrêt TF 2C_123/2025 du 1er mars 2025 consid. 4
de : Art. 698 Abs. 2 Ziff. 4 OR · BGE 1xx II yyy E. 3.2 · Urteil 2C_123/2025 vom 1. März 2025 E. 4
it : art. 698 cpv. 2 n. 4 CO · DTF 1xx II yyy consid. 3.2 · sentenza 2C_123/2025 del 1° marzo 2025
(numéros ci-dessus = gabarit de forme, pas des références)

## Contrôle
[ ] aucune ligne sans ID BIB- ou ⚠ · [ ] passages copiés à l'identique · [ ] contraires présents · [ ] dates de version cohérentes avec les faits · [ ] langue de la version lue indiquée · [ ] canton indiqué pour tout texte cantonal

## Pièges
paraphrase présentée comme citation · arrêt cité par ouï-dire (résumé de presse) · consid. erroné · omettre l'arrêt défavorable · confondre ATF publié et arrêt non publié · doctrine sans édition ni année.

## Exemple (court)
| 1 | LIFD art. 132 | loi féd. | 2 | CH | état 2026-01-01 | fr | contraignant | « … » | neutre (délai) | BIB-nnnn | 2026-10-03 |
| 2 | Arrêt TC VD … | jurisp. cant. | 5 | CH-VD | 2024-… | fr | persuasif hors VD | « … » | contre | BIB-nnnn | ⚠ |
