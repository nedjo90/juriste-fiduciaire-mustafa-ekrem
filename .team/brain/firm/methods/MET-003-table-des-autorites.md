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
# Table of authorities (machine)
use: annex to every memo, opinion, research note, réclamation, prepared recours; produced by the researcher, verified by the documentalist.

## Columns
n° | authority (text/judgment/circular/doctrine) | type | level (MET hierarchy) | jurisdiction (CH, CH-VD, FR…) | date (version/judgment) | language | contraignant/persuasif/pratique | exact passage (quoted, quotation marks, ≤ 3 lines) | for/against/neutral | ID BIB- | vérifié le

## Steps
1 Collect: library first (`cerebro law search`, `cerebro find --type source`), then whitelisted official sources (§10). No authority from memory.
2 Qualify each row (level, status, date); discard what is not applicable in time (note it).
3 Sort: decreasing weight, then decreasing date.
4 Contrary authorities: always present, marked « contre », with the planned reply (reference to the § of the analysis).
5 Verify: the documentalist compares each passage with the text (letter by letter) and fills « vérifié le »; otherwise ⚠.
6 Record: each new authority → `cerebro law ingest` (text) or `source` record; link to the deliverable (`cerebro link LIV-… BIB-…`).

## Citation formats
fr : art. 698 al. 2 ch. 4 CO · ATF 1xx II yyy consid. 3.2 · arrêt TF 2C_123/2025 du 1er mars 2025 consid. 4
de : Art. 698 Abs. 2 Ziff. 4 OR · BGE 1xx II yyy E. 3.2 · Urteil 2C_123/2025 vom 1. März 2025 E. 4
it : art. 698 cpv. 2 n. 4 CO · DTF 1xx II yyy consid. 3.2 · sentenza 2C_123/2025 del 1° marzo 2025
(numbers above = form template, not references)

## Checks
[ ] no row without ID BIB- or ⚠ · [ ] passages copied identically · [ ] contrary authorities present · [ ] version dates consistent with the facts · [ ] language of the version read stated · [ ] canton stated for any cantonal text

## Pitfalls
paraphrase presented as quotation · judgment cited by hearsay (press summary) · wrong consid. · omitting the unfavourable judgment · confusing published ATF and unpublished judgment · doctrine without edition or year.

## Example (short)
| 1 | LIFD art. 132 | loi féd. | 2 | CH | état 2026-01-01 | fr | contraignant | « … » | neutre (délai) | BIB-nnnn | 2026-10-03 |
| 2 | Arrêt TC VD … | jurisp. cant. | 5 | CH-VD | 2024-… | fr | persuasif hors VD | « … » | contre | BIB-nnnn | ⚠ |
