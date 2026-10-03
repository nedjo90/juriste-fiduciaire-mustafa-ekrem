---
id: MET-016
type: methode
statut: actif
maj: 2026-10-03
prochaine_action: 2027-01-04 réviser avec les leçons des livrables (fabrique)
risque_principal: 
chiffre_clé: 
résumé: Avant de chercher, rédiger ou calculer, retrouver l'existant (position, note, mémo, modèle, précédent, calcul), vérifier qu'il est à jour, puis en faire une nouvelle version liée plutôt qu'un doublon.
mots_clés: méthode cabinet
liens: 
source: constitution §10 ; méthodes des grandes études et fiduciaires
---
# Reuse before redoing (machine)
use: before any research, drafting, calculation, object creation (§0 ter.3, §17 c29).

## Steps
1 search: `cerebro find "<sujet>" --type position --type note --type livrable --type gabarit --type precedent --type methode`; also by client and by domain
2 judge currency: date of state of the law of the object found vs changes in the law (`cerebro find --type changement_droit "<sujet>"`), client facts changed?
3 reuse: start from the object; new version = `cerebro new <type> "<nom> v2" --lien <ID ancien>` or `cerebro update <ID>` if revising the same object; never a parallel duplicate
4 adapt: facts, canton, language, figures recalculated by script; remove anything specific to another client (secrecy)
5 capitalise: a reusable legal answer → position (POS-); a repeated correction → rule in the role's checklist (factory); a successful document → precedent/template
6 exit: links and dated next action; `cerebro regen <IDs>`

## Checks
[ ] search done and traced · [ ] currency verified (law + facts) · [ ] new version linked, no duplicate · [ ] no data from another client · [ ] capitalised if reusable

## Pitfalls
reusing a precedent whose law has changed · keeping the former client's name in a template · two contradictory positions on the same question · recalculating by hand instead of replaying the script.

## Example (short)
Request: « Prépare une convention d'actionnaires pour Beta SA. » → find returns PR-nnn (convention Alpha SA, 2025) and POS-nnn (drag-along clause). → new linked version, Alpha data removed, transfer clauses reviewed against the CO in force, commented variants.
