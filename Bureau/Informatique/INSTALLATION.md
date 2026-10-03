# Installation sur le poste de Mustafa

Pour la personne qui installe (pas pour Mustafa). Tout est déjà construit et rangé dans le dossier du projet. Il reste trois gestes, une seule fois. Aucun droit d'administrateur n'est nécessaire, et l'installateur ne pose aucune question.

## Une seule commande (Windows)

Sur le poste de Mustafa, qu'il ait déjà des outils (Claude, Git, Python) ou rien du tout :

1. Ouvrir **PowerShell** : touche Windows, taper `PowerShell`, Entrée.
2. Coller cette ligne, puis Entrée :

   ```
   irm https://raw.githubusercontent.com/nedjo90/juriste-fiduciaire-mustafa-ekrem/ccr-e8f5838b-808ukj/.equipe/installation/installer-mon-equipe.ps1 | iex
   ```

3. Attendre la fin (quelques minutes). Si Claude n'est pas encore connecté, une page de connexion s'ouvre à la fin : se connecter avec le compte de Mustafa.

La commande fait tout, sans droits d'administrateur et sans aucune question : elle installe Git (version portable officielle, dans le profil de l'utilisateur), récupère le dossier de l'équipe dans `Documents\mon-equipe`, puis installe Python, les outils de documents, Claude et ses extensions, déclare le dossier de confiance, supprime les demandes d'autorisation, crée le raccourci « Mon équipe » sur le bureau et programme l'entretien automatique. Ce qui est déjà installé n'est ni réinstallé ni modifié : le rapport final l'indique (« Claude : déjà installé sur cet ordinateur, gardé tel quel »), et le compte Claude déjà connecté reste connecté. Elle peut être relancée sans risque : elle met à jour au lieu de tout refaire. Les scripts d'installation sont rangés dans la partie cachée du dossier (`.equipe/installation`) : Mustafa ne les voit pas.

## Ensuite

Dans la même fenêtre, taper `claude` : à la fin de la commande, la fenêtre est déjà placée dans le dossier `mon-equipe` et la commande est active. Plus tard : double-cliquer sur « Mon équipe » sur le bureau, ou taper `claude` dans n'importe quelle fenêtre PowerShell (elle se place toujours d'elle-même dans le bon dossier). L'équipe s'ouvre directement, avec son brief du jour ; Mustafa n'a plus qu'à parler. Microsoft 365 (Word, Excel, PowerPoint) est utilisé pour les PDF ; aucun autre logiciel n'est nécessaire.

**Mac** : ouvrir Terminal et lancer `sh ~/Documents/mon-equipe/.equipe/installation/installer.sh` après avoir récupéré le dossier (`git clone https://github.com/nedjo90/juriste-fiduciaire-mustafa-ekrem.git ~/Documents/mon-equipe`), puis taper `claude` dans un nouveau Terminal.

**Confidentialité** : le dépôt de l'équipe est public et ne reçoit jamais le travail de Mustafa ; ses dossiers restent sur son poste (versions locales et sauvegarde chiffrée).

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

## Copie en ligne sur le compte GitHub de Mustafa (facultatif, plus tard)

Rien à faire à l'installation. Après trois semaines d'usage, l'équipe propose une seule fois, dans le brief, une copie privée de son travail sur **son propre** compte GitHub. S'il accepte, elle le guide pas à pas : créer le compte si besoin, créer un dépôt **privé** (page pré-remplie), cliquer « Authorize » dans la fenêtre GitHub. L'équipe fait le reste et vérifie que le dépôt est bien privé avant tout envoi ; s'il devenait public, les envois s'arrêtent d'eux-mêmes. S'il ignore la proposition deux fois, elle n'est plus présentée ; il peut toujours dire « copie en ligne » plus tard.

Les mises à jour de l'équipe continuent d'arriver de ce dépôt-ci : relancer la commande d'installation les applique sans toucher à son travail (en cas de passage modifié des deux côtés, sa version l'emporte).

## Optionnel (l'équipe s'en passe ; un administrateur peut l'ajouter)

- **Node.js** : permet à l'équipe de piloter un navigateur pour consulter certains sites. L'installateur essaie de l'installer en mode utilisateur ; sinon l'équipe consulte les sites autrement.
- **Chiffrement du disque** (BitLocker sous Windows, FileVault sous Mac) : recommandé pour le secret professionnel. Les sauvegardes de l'équipe sont déjà chiffrées.

## En cas de souci

- Le raccourci a disparu ou ne s'ouvre plus : relancer la commande d'installation ci-dessus.
- Changement d'ordinateur : copier tout le dossier `mon-equipe` et, pour pouvoir relire les anciennes sauvegardes, le fichier `cle-sauvegarde.key` du dossier `.cerebro` de l'utilisateur ; puis lancer la commande d'installation sur le nouveau poste.
- Le détail technique (journal d'installation, réglages, incidents) se trouve dans `.equipe/run/installation.log` et dans `DOSSIER-TECHNIQUE.md`.
