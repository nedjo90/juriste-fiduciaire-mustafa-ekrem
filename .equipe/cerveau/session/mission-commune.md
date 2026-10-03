# Mission commune à tout sous-agent de construction (machine)

Lis d'abord, dans cet ordre, sans tout charger : `.equipe/constitution.md` section 0 (règle d'or), section 0 ter (protocole sommaire), section 1 (dix lois), puis les sections citées dans ta mission. La constitution est la spécification ; elle prime.

## Environnement (vérifié le 2026-10-03)
- Racine du dépôt : `/home/user/juriste-fiduciaire-mustafa-ekrem`. Machine distante Linux (Ubuntu 24.04, Python 3.11, Node 22, LibreOffice `soffice`, PyYAML, python-docx, openpyxl, python-pptx, reportlab, matplotlib). Claude Code 2.1.288. Réseau : fedlex.data.admin.ch OK, zefix OK, pypi/npm OK, bger.ch KO, OpenAlex 429.
- Le poste final de Mustafa est **Windows probable** (macOS en variante) : tout script doit tourner sous Windows (Python stdlib + PyYAML + libs documentaires ; chemins via `pathlib` ; pas de bash obligatoire ; encodage UTF-8 explicite).
- Fiche substrat : `Bureau/Informatique/DOSSIER-TECHNIQUE.md` §2 (hooks testés, événements disponibles, formats des sous-agents et skills, modes d'autorisation).

## La CLI cerebro (déjà construite, ne pas réécrire ; tu peux y AJOUTER une sous-commande si indispensable, en le signalant)
`.equipe/bin/cerebro <cmd>` (Windows : `.equipe\bin\cerebro.cmd`). Code : `.equipe/cerebro/cerebro.py` + `.equipe/cerebro/cb/*.py`. Sortie JSON.
- `find <q>` · `summary <ID>` · `open <ID> --section <titre>` · `trace <ID>` · `regen [IDs]`
- `new <type> <nom> [--client C-001] [--resume ..] [--prochaine-action ..] [--date AAAA-MM-JJ] [--lien ID]... [--alias ..] [--source ..] [--corps-fichier f.md] [--statut ..]` → crée identifiant + fichier avec en-tête + ligne de sommaire. Types usuels : methode, gabarit, role, skill, capacite, source, position, note, document, livrable, ticket.
- Objets dont le fichier est tenu ailleurs (role, skill, ticket, capacite, gabarit, cabinet) : passer `--source <chemin>` ; pour pointer le fichier : `cerebro update <ID> chemin=<chemin relatif>`.
- `capability register <nom> --categorie .. --localisation LOCAL|EXTERNE --sort "ce qui sort" --vers "vers qui" --licence .. --version .. --source ..` (inventaire obligatoire de tout outil installé, §6.4).
- `incident add "<description>" --categorie .. --repli ..` (s'inscrit aussi dans DOSSIER-TECHNIQUE §3).
- `law ingest <identifiant> --fichier f.md --juridiction CH --type loi --titre .. --langue fr --version AAAA-MM-JJ --date-etat AAAA-MM-JJ --url .. --abrev CO` (texte en markdown, un article = une section `## Art. N …`) · `law article <RS|abrév> "art. 132"` · `law verify` · `law asof`.
- `config get|set|gaps`, `question add|next`, `conseil add`, `queue add|next|done`, `brief`, `context <message>` / `context --debut`, `health`, `coverage`, `gc`, `export`, `cardinal show|inject|check`, `deadlines`, `clock start`, `event taxation|dividende|relation`, `deliverable register`.
- Variables : `CEREBRO_ROOT` (autre racine, pour tests), `CEREBRO_DB` (autre base), `CEREBRO_TODAY` (date simulée), `CEREBRO_BACKGROUND=1` (anti-récursion des hooks et rôles de fond).

## Règles de chantier
1. **Rien ne bloque** : aucun hook de refus, aucune liste deny, aucun pré-commit, toute erreur journalisée puis succès. Scripts idempotents. Jobs de fond : journal début/fin/durée/résultat.
2. **Tests** : teste dans une racine jetable (`CEREBRO_ROOT=$(mktemp -d)` après copie de `.equipe`, ou `CEREBRO_DB=/tmp/x.db`), jamais en polluant la base réelle avec des données fictives. Données fictives disponibles : `.equipe/tests/fixtures/dossier_fictif.py`. Écris tes tests automatiques dans `.equipe/tests/` (pytest non requis : scripts `test_*.py` exécutables par `python`, sortie `OK`/`ÉCHEC`).
3. **Enregistre** ce que tu crées de durable dans la base réelle (rôles, skills, gabarits, méthodes, capacités) via `cerebro new` / `capability register`, puis `cerebro regen`. Ce qui n'a pas d'identifiant n'existe pas.
4. **Ne commite pas, ne pousse pas** : l'orchestrateur commite. Ne touche qu'aux fichiers de ton périmètre ; si tu dois modifier un fichier hors périmètre, décris le changement dans ton rapport au lieu de le faire.
5. **Rapport** : écris ton rapport complet dans `.equipe/cerveau/session/rapports/<chantier>.md` (fait, testé, écarts, dette, ce qui reste à faire sur le poste Windows) AVANT de rendre la main, puis rends un résumé de 1 500 caractères au plus.
6. N'invente aucun contenu juridique (taux, article, délai, barème) : tout vient d'un texte officiel ingéré, sinon ⚠.
7. Langue : les fichiers destinés aux agents en français compact ; tout ce qui est destiné à Mustafa en français soigné, sans jargon.
