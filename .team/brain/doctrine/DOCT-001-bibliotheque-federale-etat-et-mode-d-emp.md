---
id: DOCT-001
type: doctrine
statut: actif
maj: 2026-10-06
prochaine_action: 2026-10-10 mettre à jour après chaque cycle bibliotheque_maj
risque_principal: 
chiffre_clé: 
résumé: Textes Fedlex ingérés (25 actes, FR ; CO et LIFD en DE), règles de délais RD-001 à RD-008 vérifiées, barèmes sourcés, calculs et entretien
mots_clés: bibliothèque Fedlex RS loi article barème délai
liens: RD-003, RD-006
source: https://fedlex.data.admin.ch
---
# Federal library: state and how to use it

## Résumé
Official Fedlex texts (consolidated, Akoma Ntoso XML) ingested on 2026-10-03, one article = one section « ## Art. N ». Query: `cerebro law article <RS|abrév> "art. N" [--date AAAA-MM-JJ] [--langue de]` → text, version, URL; `cerebro law asof <RS> --date` → version in force. Date not covered by an ingested version → no text (⚠), never an outdated text.

## Texts ingested
| ID | RS | abbr. | language | version (from) | valid until (excluded) |
|---|---|---|---|---|---|
| BIB-013 | 173.110 | LTF | fr | 2026-04-01 | en vigueur |
| BIB-014 | 173.110.3 | — | fr | 1963-10-03 | en vigueur |
| BIB-023 | 210 | CC | fr | 2026-07-01 | en vigueur |
| BIB-015 | 220 | OR | de | 2026-10-01 | 2027-07-01 |
| BIB-001 | 220 | CO | fr | 2026-10-01 | 2027-07-01 |
| BIB-002 | 221.301 | LFus | fr | 2023-01-01 | en vigueur |
| BIB-017 | 221.411 | ORC | fr | 2026-10-01 | en vigueur |
| BIB-011 | 235.1 | LPD | fr | 2025-07-07 | en vigueur |
| BIB-012 | 281.1 | LP | fr | 2026-01-01 | en vigueur |
| BIB-007 | 641.10 | LT | fr | 2024-01-01 | en vigueur |
| BIB-018 | 641.101 | OT | fr | 2023-09-01 | en vigueur |
| BIB-028 | 641.20 | LTVA | fr | 2024-01-01 | 2025-01-01 |
| BIB-008 | 641.20 | LTVA | fr | 2025-03-31 | en vigueur |
| BIB-019 | 641.201 | OTVA | fr | 2025-01-01 | 2027-01-01 |
| BIB-016 | 642.11 | DBG | de | 2026-09-02 | 2027-01-01 |
| BIB-027 | 642.11 | LIFD | fr | 2024-05-16 | 2025-01-01 |
| BIB-003 | 642.11 | LIFD | fr | 2026-09-02 | 2027-01-01 |
| BIB-004 | 642.14 | LHID | fr | 2025-01-01 | 2028-01-01 |
| BIB-026 | 642.21 | LIA | fr | 2024-01-01 | 2025-01-01 |
| BIB-005 | 642.21 | LIA | fr | 2025-01-01 | en vigueur |
| BIB-006 | 642.211 | OIA | fr | 2025-01-01 | en vigueur |
| BIB-024 | 830.1 | LPGA | fr | 2024-01-01 | en vigueur |
| BIB-025 | 831.10 | LAVS | fr | 2026-01-01 | 2027-01-01 |
| BIB-009 | 955.0 | LBA | fr | 2026-10-01 | en vigueur |
| BIB-020 | 955.01 | OBA | fr | 2026-10-01 | en vigueur |
| BIB-021 | 955.033.0 | OBA-FINMA | fr | 2023-01-01 | en vigueur |
| BIB-010 | 955.3 | LTPM | fr | 2026-10-01 | en vigueur |
| BIB-022 | 955.31 | OTPM | fr | 2026-10-01 | en vigueur |
(« en vigueur » = in force, no end date)

## Verified deadline rules (cerebro law verify)
RD-001 LIFD art. 132 al. 1 (30 d) · RD-002 LIFD art. 140 al. 1 (30 d) · RD-003 LIA art. 16 al. 1 let. c + art. 12 al. 1 (thirty days, corrected) · RD-004 LTVA art. 71 al. 1 (60 d) · RD-005 CO art. 699 al. 2 (six months) · RD-006 LTPM art. 13 al. 3 (one month, corrected: art. 697j CO repealed as of 1.10.2026) · RD-007 LP art. 74 al. 1 (ten days) · RD-008 LTF art. 100 al. 1 (30 d). Saturday treated as a public holiday: RS 173.110.3 art. 1.

## Scales (table bareme, cerebro rates get <nom> --annee A)
impot_anticipe (LIA art. 13: 35 / 15 / 8 %) · tva (LTVA art. 25: 8,1 / 2,6 / 3,8 %) · droit_emission (LT art. 8: 1 %; art. 6 al. 1 let. b, h, k: 1 M / 1 M / 10 M CHF) · ifd_personnes_morales (LIFD art. 68: 8,5 %; art. 71: 4,25 %, threshold 5000 CHF). Each row carries RS, article, version, extract and verification date. Entry only via `scripts/library/rates.py` (re-reads the article before entering).

## Calculations
`scripts/calc/withholding_tax.py`, `vat.py`, `stamp_duty.py`: JSON + `--excel` (tabs Hypothèses / Calcul / Sources, formulas). Scale missing → ⚠ without figure.

## Maintenance
`scripts/library/update.py` at each full cycle: new consolidation → ingestion, changement_droit object, task `bibliotheque_maj` (priority 5), re-run verify + scales. Source unreachable → incident + `bibliotheque_rattrapage`. Priorities: `scripts/library/priorities.yaml`. Cantons VD/GE and LexFind: `scripts/library/cantons.yaml` (located, not ingested: cantonal law ⚠). Registre du commerce: `scripts/library/zefix.py`.

## Limits
DE translations only for CO and LIFD; IT absent. AFC circulars, case law, FF not ingested. Cantonal public holidays not taken into account.
