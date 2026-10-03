---
id: MET-015
type: methode
statut: actif
maj: 2026-10-03
prochaine_action: 2027-01-04 réviser avec les leçons des livrables (fabrique)
risque_principal: 
chiffre_clé: 
résumé: Entrer par le sommaire, cibler par find, summary et open --section, déléguer les lectures longues avec rapport court, ne relire que ce qui a changé.
mots_clés: méthode cabinet
liens: 
source: constitution §10 ; méthodes des grandes études et fiduciaires
---
# Read without re-reading everything (machine)
use: every agent, every task. Applies the summary protocol (§0 ter) and law 4.

## Steps
1 SUMMARY: `.team/summaries/SUMMARY.md` then level 1 of the client (`.team/summaries/clients/<C>.md`) or domain
2 TARGET: `cerebro find "<termes>"` (aliases, former names included) → `cerebro summary <ID>` → `cerebro open <ID> --section "<titre>"`
3 LAW: `cerebro law article <abrév> "art. N"` — never the whole law
4 LONG DOCUMENT: read the table of contents/header; keyword search (Grep); open only useful sections; beyond ~15 pages → reading delegated to a subagent, report ≤ 1 500 characters with sections and IDs
5 DELTA: compare the object's `maj` with the last reading (`cerebro trace <ID>`); re-read only what changed
6 NOTE: each useful reading → ID + section in the work produced (traceability)
budget: ≤ 5 openings for an ordinary question (§17 c24)

## Checks
[ ] entry via the summary · [ ] no folder listing · [ ] no whole file without its header read · [ ] ≤ 5 openings for an ordinary question · [ ] sections read cited

## Pitfalls
loading a complete client folder « pour avoir le contexte » · re-reading an already summarised document · reading a raw log outside `trace` · losing the precise reference of what was read.

## Example (short)
Question: « Où en est la réclamation Dupont SA ? » → find "Dupont réclamation" → summary DL-nnn (next action, status) → open DOC-nnnn --section "Conclusions" → two-sentence answer with date. Three openings.
