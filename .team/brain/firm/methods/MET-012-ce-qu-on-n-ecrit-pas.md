---
id: MET-012
type: methode
statut: actif
maj: 2026-10-03
prochaine_action: 2027-01-04 réviser avec les leçons des livrables (fabrique)
risque_principal: 
chiffre_clé: 
résumé: Liste de ce qui ne figure jamais dans un document pour un tiers : perceptions, notes internes, identifiants, mécanique, données d'autres clients, soupçons LBA, aveux, menaces, affirmations non sourcées.
mots_clés: méthode cabinet
liens: 
source: constitution §10 ; méthodes des grandes études et fiduciaires
---
# What we do not write (machine)
use: every deliverable or draft intended for a third party (client, administration, registry, colleague, opposing party, bank). Verified by the reviewer and the gates.

## Never in an outgoing document
- perceptions and internal notes ([perception], unowned [hypothèse], assessments of people)
- « entre nous » content (no trace, no reuse)
- internal IDs (C-nnn, DOC-nnnn, MET-…), machine tags, paths, tool names, mention of AI
- another client's information (professional secrecy); internal overlaps
- LBA suspicions, analyses or steps vis-à-vis the client or third parties (prohibition of information: rule to read in the LBA ⚠ via `cerebro law search "information"`)
- negotiation strategy, MESORE, reservation price, in a writing intended for the other side
- admissions, acknowledgements of debt or fault not intended by the client
- statement of law without verified source (otherwise ⚠ and cautious rewording)
- threats, pressure, statements that may be criminally relevant
- unverified figures, rates from memory
- commitments Mustafa has not authorised
- in a mail: content one would not want forwarded to the other side

## Write with care
« sous réserve de … »: once, precise · factual reservations (« sur la base des pièces reçues au [date] ») · confidentiality in memo headers.

## Steps (reviewer)
1 search for machine patterns: ID regex, « [perception] », « [hypothèse] », unresolved « ⚠ », paths, tool names · 2 compare with the client view: another client's data? · 3 check linked LBA file: nothing of it shows through · 4 re-read commitment passages.

## Checks
[ ] zero internal ID · [ ] zero perception · [ ] zero data from another client · [ ] zero LBA trace · [ ] commitments authorised (ID of the instruction) · [ ] reservations present and precise

## Pitfalls
copy-pasting from an internal note · meeting prep sheet turned into a client report without cleaning · forwarded mail with the internal history below.

## Example (short)
Internal note: « [perception] le CFO semble cacher les avances au directeur. » → in the letter: nothing; in the file: question to document, documents requested neutrally (« merci de nous remettre le détail du compte courant actionnaire au 31.12.2025 »).
