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

- **Messagerie et agenda** : cliquer sur « autoriser » dans le navigateur quand l'équipe propose de connecter Outlook ou Google. Une messagerie professionnelle Microsoft 365 peut exiger l'accord de l'informaticien de la fiduciaire (consentement de l'administrateur pour l'application) ; l'équipe fonctionne sans en attendant.
- **Bases payantes** (Swisslex, Weblaw…) : si la fiduciaire a des identifiants, les indiquer à l'équipe en conversation.

## Optionnel (l'équipe s'en passe ; un administrateur peut l'ajouter)

- **LibreOffice** : améliore certaines conversions de documents en PDF. Sans lui, les documents sont produits directement.
- **Node.js** : permet à l'équipe de piloter un navigateur pour consulter certains sites. L'installateur essaie de l'installer en mode utilisateur ; sinon l'équipe consulte les sites autrement.
- **Chiffrement du disque** (BitLocker sous Windows, FileVault sous Mac) : recommandé pour le secret professionnel. Les sauvegardes de l'équipe sont déjà chiffrées.

## En cas de souci

- Le raccourci a disparu ou ne s'ouvre plus : relancer l'installateur.
- Changement d'ordinateur : copier tout le dossier `mon-equipe` et, pour pouvoir relire les anciennes sauvegardes, le fichier `cle-sauvegarde.key` du dossier `.cerebro` de l'utilisateur ; puis lancer l'installateur sur le nouveau poste.
- Le détail technique (journal d'installation, réglages, incidents) se trouve dans `.equipe/run/installation.log` et dans `DOSSIER-TECHNIQUE.md`.
