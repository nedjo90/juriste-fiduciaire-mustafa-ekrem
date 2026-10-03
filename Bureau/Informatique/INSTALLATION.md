# Installation sur le poste de Mustafa

Pour la personne qui installe (pas pour Mustafa). Tout est déjà construit et rangé dans le dossier du projet. Il reste trois gestes, une seule fois. Aucun droit d'administrateur n'est nécessaire, et l'installateur ne pose aucune question.

## 1. Récupérer le dossier

Placer le dossier du projet dans `Documents\mon-equipe` (Windows) ou `Documents/mon-equipe` (Mac).

- Le plus simple : télécharger l'archive du dépôt privé (bouton « Code », puis « Download ZIP », branche `ccr-e8f5838b-808ukj`), la décompresser, renommer le dossier obtenu en `mon-equipe` et le placer dans Documents.
- Ou, si Git est déjà installé :
  ```
  git clone -b ccr-e8f5838b-808ukj https://github.com/nedjo90/juriste-fiduciaire-mustafa-ekrem.git "%USERPROFILE%\Documents\mon-equipe"
  ```
  Le clonage est préférable : les sauvegardes automatiques de l'équipe partent alors vers le dépôt privé sans autre réglage (il faudra s'être connecté une fois à GitHub sur ce poste).

## 2. Lancer l'installateur

- **Windows** : double-cliquer sur `Installer.bat`, à la racine du dossier. Si Windows affiche « Windows a protégé votre ordinateur », cliquer sur « Informations complémentaires », puis « Exécuter quand même ».
- **Mac** : double-cliquer sur `installer.command` (dans `.equipe/scripts`, afficher les fichiers cachés avec Cmd+Maj+point). Si le Mac refuse d'ouvrir un fichier téléchargé, faire clic droit, puis « Ouvrir ».

Compter cinq à quinze minutes, selon la connexion. L'installateur installe ou vérifie, en mode utilisateur : Python, les outils de documents (Word, Excel, PowerPoint, PDF, graphiques), Git, Claude. Il déclare le dossier de confiance, supprime les demandes d'autorisation, crée le raccourci « Mon équipe » sur le bureau, programme l'entretien automatique (ouverture de session, sortie de veille, inactivité), cache tout ce qui n'est pas utile à Mustafa et vérifie la configuration. Il affiche à la fin un court bilan.

L'installateur peut être relancé sans risque autant de fois que nécessaire : il ne refait que ce qui manque. Si une étape a échoué faute de connexion, il suffit de le relancer plus tard.

## 3. Ouvrir l'équipe

Double-cliquer sur « Mon équipe » sur le bureau. La toute première fois, Claude demande de se connecter : se connecter avec le compte de Mustafa dans le navigateur qui s'ouvre. Au plus, appuyer sur Entrée. Ensuite, Mustafa n'a plus qu'à parler.

Mustafa ne voit dans le dossier que « Bureau » : `A-deposer` (il y glisse ses documents), `Livrables` (les documents produits), `Modeles`, `Deposes` et `Informatique` (ce dossier-ci).

## Plus tard, au moment utile (l'équipe le proposera elle-même)

- **Messagerie et agenda Outlook (Microsoft 365)** : quand l'équipe le propose, une page Microsoft s'ouvre dans le navigateur. Y coller le code affiché (il est déjà copié : clic droit, Coller), se connecter avec le compte de la fiduciaire si la page le demande, puis cliquer sur « Autoriser ». C'est tout. L'équipe lit alors les mails et l'agenda et prépare les réponses **en brouillon dans Outlook** ; elle n'envoie jamais rien (elle n'en a pas le droit technique), Mustafa envoie lui-même.
- **Notes vocales** : rien à faire. Si la transcription n'a pas pu être installée sur ce poste, l'équipe demandera simplement un résumé en deux phrases.
- **Bases payantes** (Swisslex, Weblaw…) : si la fiduciaire a des identifiants, les indiquer à l'équipe en conversation.

### Pour l'informaticien de la fiduciaire (seulement si Microsoft 365 refuse l'autorisation de Mustafa)

Par défaut, l'équipe se connecte avec l'application publique de Microsoft « Microsoft Graph Command Line Tools » (identifiant `14d82eec-204b-4c2f-b7e8-296a70dab67e`), en permissions **déléguées** et par le flux « code d'appareil ». Si la fiduciaire interdit aux utilisateurs de consentir eux-mêmes, ou bloque cette application, ou si vous préférez une application dédiée (recommandé : traçabilité dans les journaux de connexion, révocation propre, aucun consentement partagé avec d'autres outils), procédez ainsi, en dix minutes :

1. Centre d'administration Microsoft Entra (https://entra.microsoft.com) → Identité → Applications → **Inscriptions d'applications** → **Nouvelle inscription**.
   - Nom : `Mon équipe — Mustafa (lecture et brouillons)`.
   - Types de comptes pris en charge : **Comptes dans cet annuaire organisationnel uniquement**.
   - URI de redirection : plateforme **Client public/natif (mobile et bureau)**, valeur `http://localhost`.
2. **Authentification** → Paramètres avancés → **Autoriser les flux de clients publics : Oui** (nécessaire au flux par code d'appareil).
3. **Autorisations d'API** → Ajouter une autorisation → Microsoft Graph → **Autorisations déléguées**, exactement :
   - `Mail.ReadWrite` (lire les mails et créer ou compléter des brouillons),
   - `Calendars.Read` (lire l'agenda),
   - `User.Read` (identifier le compte connecté),
   - `offline_access` (garder la liaison sans redemander l'autorisation).
   **N'ajoutez aucune permission d'envoi** (`Mail.Send`, `Mail.Send.Shared`) **ni aucune autorisation d'application** : l'équipe ne doit jamais pouvoir envoyer.
4. Cliquer sur **Accorder un consentement d'administrateur pour <votre organisation>**, ou ouvrir l'URL de consentement administrateur (remplacer les deux valeurs) :
   `https://login.microsoftonline.com/<ID-annuaire>/adminconsent?client_id=<ID-application>`
5. Sur le poste de Mustafa, dans un terminal ouvert dans le dossier `mon-equipe`, inscrire l'application (ou les donner à l'équipe en conversation) :
   ```
   python .equipe\cerebro\cerebro.py config set acces.m365_client_id <ID-application> --source "informaticien"
   python .equipe\cerebro\cerebro.py config set acces.m365_annuaire <ID-annuaire> --source "informaticien"
   ```
6. Relancer la connexion (ou laisser l'équipe la reproposer) : `python .equipe\scripts\connecteurs\connecter_messagerie.py`. Mustafa n'a plus qu'à cliquer « Autoriser ».

Si une **stratégie d'accès conditionnel** bloque le flux par code d'appareil, l'équipe essaie d'elle-même une connexion par le navigateur (même application, mêmes permissions) ; à défaut, exclure cette application de la stratégie. Le jeton est conservé chiffré dans le profil Windows de Mustafa (`%LOCALAPPDATA%\MonEquipe\m365`, protection DPAPI), jamais dans le dossier du projet ; « Déconnecter » : `connecter_messagerie.py --deconnecter`, ou révoquer l'application dans Entra.

## Optionnel (l'équipe s'en passe ; un administrateur peut l'ajouter)

- **LibreOffice** : améliore certaines conversions de documents en PDF. Sans lui, les documents sont produits directement.
- **Node.js** : permet à l'équipe de piloter un navigateur pour consulter certains sites. L'installateur essaie de l'installer en mode utilisateur ; sinon l'équipe consulte les sites autrement.
- **Chiffrement du disque** (BitLocker sous Windows, FileVault sous Mac) : recommandé pour le secret professionnel. Les sauvegardes de l'équipe sont déjà chiffrées.

## En cas de souci

- Le raccourci a disparu ou ne s'ouvre plus : relancer l'installateur.
- Changement d'ordinateur : copier tout le dossier `mon-equipe` et, pour pouvoir relire les anciennes sauvegardes, le fichier `cle-sauvegarde.key` du dossier `.cerebro` de l'utilisateur ; puis lancer l'installateur sur le nouveau poste.
- Le détail technique (journal d'installation, réglages, incidents) se trouve dans `.equipe/run/installation.log` et dans `DOSSIER-TECHNIQUE.md`.
