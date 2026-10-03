---
id: MET-002
type: methode
statut: actif
maj: 2026-10-03
prochaine_action: 2027-01-04 réviser avec les leçons des livrables (fabrique)
risque_principal: 
chiffre_clé: 
résumé: Classer chaque source par poids (constitution, loi, ordonnance, cantonal, traité, jurisprudence, pratique, doctrine) et la dater (version, état, consultation, langue) avant tout usage.
mots_clés: méthode cabinet
liens: 
source: constitution §10 ; méthodes des grandes études et fiduciaires
---
# Hierarchy and dating of sources (machine)
use: whenever a source is cited, compared or contradicted.

## Weight (usual order; a real conflict is settled by the applicable conflict rule, itself sourced)
1 Federal Constitution · treaties (CDI, agreements) according to their rank
2 Federal law (RS) · 3 federal ordinance
4 Cantonal law: constitution > law > implementing regulation > published practice; then communal
5 Case law: TF (published ATF > unpublished judgments) > TAF/TPF > higher cantonal courts > first instances
6 Administrative practice: AFC, OFAS, FINMA circulars and notices, cantonal administrations → bind the administration, not the judge; « que dirait l'administration »
7 Doctrine (commentaries, journals, books) → persuasive; references only without subscription
8 Foreign: official text of the country; interpretation = local counsel possible; comfort level lowered

## Dating (mandatory fields of any citation)
id BIB- · abbr/RS · art. al. let. ch. · version (entry into force) · date of state (« état le ») · language of the version read · canton/country · official URL · vérifié_le (consultation date) · statut [contraignant|persuasif|pratique|doctrine]
- past facts → version in force at the date of the facts / tax period: `cerebro law asof <RS> --date AAAA-MM-JJ`
- text amended since → cite both versions and the transitional rule (article read, otherwise ⚠)
- official language versions: if meaning is in doubt, compare fr/de/it and flag it
- cantonal source often in German: cite the original, working translation marked [trad. de travail]

## Steps
1 rank each source found on the weight scale above (one label per source)
2 date: version applicable to the facts (`cerebro law asof <RS> --date <date des faits>`), date of state, consultation date
3 fill the 10 citation fields; missing field → documentalist
4 conflict between two sources → conflict rule read (lex superior, specialis, posterior, treaty rank) and cited
5 enter the source in the table of authorities (MET-003) and link it to the deliverable (`cerebro link`)

## Checks
[ ] each source has the 10 fields · [ ] version applicable to the facts verified · [ ] practice distinguished from law · [ ] doctrine never presented as a rule · [ ] source without primary text → ⚠ · [ ] consultation date < 90 d for a deliverable (otherwise re-verify: documentalist)

## Pitfalls
citing a renumbered article · citing a summary instead of the text · confusing a repealed circular with one in force · taking a judgment from another canton as binding · forgetting the commune (multipliers, regulations) · translation presented as official text.

## Example (short)
« art. 132 al. 1 LIFD [BIB-nnnn, RS 642.11, état 2026-01-01, fr, vérifié le 2026-10-03, contraignant] »; « Circ. AFC n° xx [BIB-nnnn, pratique, vérifié le …] » — fictitious numbers, to be replaced from the library.
