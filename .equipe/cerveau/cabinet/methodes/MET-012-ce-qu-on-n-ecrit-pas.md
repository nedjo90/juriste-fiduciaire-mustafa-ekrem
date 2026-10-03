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
# Ce qu'on n'écrit pas (machine)
usage: tout livrable ou brouillon destiné à un tiers (client, administration, registre, confrère, partie adverse, banque). Vérifié par le relecteur et les portes.

## Jamais dans un document sorti
- perceptions et notes internes ([perception], [hypothèse] non assumée, appréciations sur des personnes)
- contenu « entre nous » (aucune trace, aucune réutilisation)
- identifiants internes (C-nnn, DOC-nnnn, MET-…), étiquettes machine, chemins, noms d'outils, mention de l'IA
- informations d'un autre client (secret professionnel) ; croisements internes
- soupçons, analyses ou démarches LBA vis-à-vis du client ou de tiers (interdiction d'informer : règle à lire dans la LBA ⚠ via `cerebro law search "information"`)
- stratégie de négociation, MESORE, prix de réserve, dans un écrit destiné à l'adverse
- aveux, reconnaissances de dette ou de faute non voulus par le client
- affirmation de droit sans source vérifiée (sinon ⚠ et reformulation prudente)
- menaces, pressions, propos pouvant être pénalement relevants
- chiffres non vérifiés, taux de mémoire
- engagements que Mustafa n'a pas autorisés
- dans un mail : contenu qu'on ne voudrait pas voir transféré à l'adverse

## À écrire avec soin
« sous réserve de … » : une fois, précise · réserves de faits (« sur la base des pièces reçues au [date] ») · confidentialité en en-tête des mémos.

## Étapes (relecteur)
1 rechercher les motifs machine : regex identifiants, « [perception] », « [hypothèse] », « ⚠ » non résolus, chemins, noms d'outils · 2 comparer avec la vue client : données d'un autre client ? · 3 vérifier dossier LBA lié : rien n'en transparaît · 4 relire les passages d'engagement.

## Contrôle
[ ] zéro identifiant interne · [ ] zéro perception · [ ] zéro donnée d'un autre client · [ ] zéro trace LBA · [ ] engagements autorisés (ID de la consigne) · [ ] réserves présentes et précises

## Pièges
copier-coller depuis une note interne · fiche RDV transformée en compte rendu client sans nettoyage · mail de transfert avec l'historique interne en dessous.

## Exemple (court)
Note interne : « [perception] le CFO semble cacher les avances au directeur. » → dans la lettre : rien ; dans le dossier : question à documenter, pièces demandées de façon neutre (« merci de nous remettre le détail du compte courant actionnaire au 31.12.2025 »).
