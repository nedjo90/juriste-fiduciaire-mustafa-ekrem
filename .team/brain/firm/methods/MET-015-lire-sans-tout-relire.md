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
# Lire sans tout relire (machine)
usage: tout agent, toute tâche. Applique le protocole sommaire (§0 ter) et la loi 4.

## Étapes
1 SOMMAIRE : `.team/summaries/SUMMARY.md` puis niveau 1 du client (`.team/summaries/clients/<C>.md`) ou du domaine
2 CIBLER : `cerebro find "<termes>"` (alias, anciens noms compris) → `cerebro summary <ID>` → `cerebro open <ID> --section "<titre>"`
3 DROIT : `cerebro law article <abrév> "art. N"` — jamais la loi entière
4 DOCUMENT LONG : lire la table des matières/en-tête ; recherche par mots-clés (Grep) ; ouvrir les seules sections utiles ; au-delà de ~15 pages → lecture déléguée à un sous-agent, rapport ≤ 1 500 car. avec sections et IDs
5 DELTA : comparer `maj` de l'objet à la dernière lecture (`cerebro trace <ID>`) ; ne relire que ce qui a changé
6 NOTER : chaque lecture utile → ID + section dans le travail produit (traçabilité)
budget : ≤ 5 ouvertures pour une question courante (§17 c24)

## Contrôle
[ ] entrée par le sommaire · [ ] aucun listing de dossier · [ ] aucun fichier entier sans en-tête lu · [ ] ≤ 5 ouvertures pour une question courante · [ ] sections lues citées

## Pièges
charger un dossier client complet « pour avoir le contexte » · relire un document déjà résumé · lire un journal brut hors `trace` · perdre la référence précise de ce qu'on a lu.

## Exemple (court)
Question : « Où en est la réclamation Dupont SA ? » → find "Dupont réclamation" → summary DL-nnn (prochaine action, statut) → open DOC-nnnn --section "Conclusions" → réponse en deux phrases avec date. Trois ouvertures.
