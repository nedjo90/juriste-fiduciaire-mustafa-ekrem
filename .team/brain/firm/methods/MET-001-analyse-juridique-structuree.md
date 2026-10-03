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
# Structured legal analysis (machine)
use: any question of law (conversation, memo, opinion, réclamation). Swiss « Gutachten » style: Sachverhalt → Rechtsfrage → Rechtsgrundlage → Subsumtion → Ergebnis.

## Steps
1 QUESTION: one closed sentence. Who (P-/E-), what, where (canton, commune), when (date of facts, tax period), for what use (advice, réclamation, deed). See MET « quel canton, quelle langue, quel délai ».
2 FACTS: dated list; each fact tagged [fait vérifié]/[déclaré par X le …]/[perception]/[hypothèse] + ID (DOC-, M-, RDV-). Decisive missing fact → explicit [hypothèse] + `cerebro question add` if the answer changes the outcome.
3 RULES: `cerebro law search "<notion>"` → `cerebro law article <abrév> "art. N"`; version applicable to the facts: `cerebro law asof <RS> --date <date des faits>`. Level: federal / cantonal / communal / treaty (CDI) / foreign. Administrative practice (circulars) kept separate from the law. Not in the library → researcher/documentalist; otherwise ⚠.
4 CONDITIONS: break each rule into conditions (constituent elements) and legal consequence. Table: condition | fact(s) | met / not / uncertain | why | source.
5 COUNTER-READING: best opposing reading (MET two-step contradiction); contrary authorities listed, never hidden.
6 CONCLUSION: one-sentence answer + comfort level (MET comfort levels) + what would change it.
7 FOLLOW-UP: acts, deadlines (`cerebro clock start`), costs, who does what, dated next action.
8 « CE QUE VOUS N'AVEZ PAS DEMANDÉ »: cross-consequences (tax ↔ companies ↔ social ↔ LBA ↔ estates), options, opportunities.

## Checks
[ ] closed question, canton and period fixed · [ ] facts tagged and dated · [ ] each rule: ID BIB- + art./al./let. + version + date of state + canton · [ ] intertemporal law addressed · [ ] each condition subsumed · [ ] contrary authorities mentioned · [ ] comfort level not inflated · [ ] deadlines computed by clock, never in prose · [ ] dated next action

## Pitfalls
answering from memory · applying the current version to old facts · forgetting cantonal/communal law · treating a circular as a law · skipping an « obvious » condition · mixing declared and verified facts · concluding without practical consequence · ignoring competence (authority, for) and form (writing, acte authentique, registration).

## Example (short)
Q: « La SA du client peut-elle verser un dividende en cours d'exercice ? » → C-nnn/E-nnn, VD, financial year 2026.
Facts: 2025 accounts approved [fait vérifié DOC-nnnn]; 2026 profit in progress [déclaré par le CFO le 2026-09-30].
Rules: CO provisions on the interim dividend ⚠ (to extract: `cerebro law search "dividende intermédiaire"`).
Conditions: table (interim accounts? audit? AG decision?) each with the article read.
Conclusion: « devrait être possible si … » (should) — never higher until all conditions are read in the text.
Follow-up: impôt anticipé clock from the dividend due date; draft PV d'AG; « ce que vous n'avez pas demandé »: effect on the legal reserve and on the shareholder's estate planning.
