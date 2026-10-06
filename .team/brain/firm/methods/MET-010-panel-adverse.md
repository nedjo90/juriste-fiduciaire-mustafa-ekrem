---
id: MET-010
type: methode
statut: actif
maj: 2026-10-06
prochaine_action: 2027-01-04 réviser avec les leçons des livrables (fabrique)
risque_principal: 
chiffre_clé: 
résumé: Un seul appel groupé, modèle le plus capable, pour les livrables importants : contradicteur, testeur d'erreurs, client difficile, juge et administration, réviseur, lecteur humain ; constats classés puis corrigés avant le relecteur.
mots_clés: méthode cabinet
liens: 
source: constitution §10 ; méthodes des grandes études et fiduciaires
---
# Adversarial panel (machine)
use: memos, opinions, Excel models, corporate or deal documents, agreements, presentations, réclamations. Never for a short mail (there: human reader built into the drafting call). §6.2.
order: deterministic gates (scripts) → PANEL (one call) → corrections by the authoring role → reviewer → presentation (with reservations if a correction does not succeed).

## The six voices (one single call, subagent adversarial-panel)
1 contradictor: MET two-step contradiction (argues the other side, then critiques)
2 error tester: figures, dates, deadlines, calculations (redone by script if possible), internal cross-references, IDs, consistency of defined terms
3 difficult client: « et alors ? combien ? quand ? qu'est-ce que je signe ? quel risque pour moi ? »; readability for a non-lawyer executive
4 judge and administration: strict reading, burden of proof, form, competence, deadlines, practice; « qu'est-ce qui serait rejeté ? »
5 auditor: accounting and tax consistency (balance sheet, reserves, impôt anticipé, entries), treatment of amounts
6 human reader: machine tics, tone, length, typography of the language, visual rendering (pages rendered as images if available)

## Call input
deliverable (path) + table of authorities + gate results + mission (recipient, stakes, language); nothing else (summary first).

## Output (machine, one line per finding)
{"voix":"juge","gravite":"majeur|important|mineur","lieu":"§3.2","constat":"…","correction":"…","source":"BIB-…|⚠"}
+ synthesis: count per severity, recommended comfort level, « présentable après corrections : oui/avec réserves ».

## Steps
1 check that the deterministic gates have passed (results attached) · 2 one single call to the adversarial-panel subagent with the minimal input · 3 sort findings by severity · 4 the author fixes majeurs and importants · 5 reviewer · 6 uncorrected findings → explicit reservations in the deliverable

## Checks
[ ] one single call · [ ] six voices present · [ ] each finding located and paired with a correction · [ ] no « taste » finding classified majeur · [ ] internal report not shown to Mustafa unless asked · [ ] uncorrected findings → explicit reservations in the deliverable

## Pitfalls
several calls (cost) · panel that just approves (a model does not judge itself: it must look for the error) · rewriting the deliverable instead of flagging · internal report copied into the deliverable.

## Example (short)
{"voix":"testeur","gravite":"majeur","lieu":"tableau 2","constat":"total CHF 84'250 ≠ somme des lignes CHF 82'450","correction":"recalculer par script calcul","source":"DOC-nnnn"}
