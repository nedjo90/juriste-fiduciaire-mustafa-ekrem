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
# Réutiliser avant de refaire (machine)
usage: avant toute recherche, rédaction, calcul, création d'objet (§0 ter.3, §17 c29).

## Étapes
1 chercher : `cerebro find "<sujet>" --type position --type note --type livrable --type gabarit --type precedent --type methode` ; aussi par client et par domaine
2 juger l'actualité : date d'état du droit de l'objet trouvé vs changements de droit (`cerebro find --type changement_droit "<sujet>"`), faits du client changés ?
3 réutiliser : partir de l'objet ; nouvelle version = `cerebro new <type> "<nom> v2" --lien <ID ancien>` ou `cerebro update <ID>` si révision du même objet ; jamais un doublon parallèle
4 adapter : faits, canton, langue, chiffres recalculés par script ; retirer tout élément propre à un autre client (secret)
5 capitaliser : une réponse de droit réutilisable → position (POS-) ; une correction répétée → règle dans la liste de contrôle du rôle (fabrique) ; un document réussi → précédent/gabarit
6 sortir : liens et prochaine action datée ; `cerebro regen <IDs>`

## Contrôle
[ ] recherche faite et tracée · [ ] actualité vérifiée (droit + faits) · [ ] nouvelle version liée, pas de doublon · [ ] aucune donnée d'un autre client · [ ] capitalisation faite si réutilisable

## Pièges
reprendre un précédent dont le droit a changé · garder le nom de l'ancien client dans un modèle · deux positions contradictoires sur la même question · recalculer à la main au lieu de rejouer le script.

## Exemple (court)
Demande : « Prépare une convention d'actionnaires pour Beta SA. » → find trouve PR-nnn (convention Alpha SA, 2025) et POS-nnn (clause de drag-along). → nouvelle version liée, données Alpha retirées, clauses de transfert revues contre le CO en vigueur, variantes commentées.
