# Installation sur le poste de Mustafa

Pour la personne qui installe (pas pour Mustafa). Tout le système est déjà construit et rangé dans le dépôt privé. Il reste trois gestes à faire sur le poste.

## 1. Récupérer le dossier
Copier le dossier du projet sur le poste (par exemple dans `Documents\Mon équipe`), ou le cloner :
```
git clone -b ccr-e8f5838b-808ukj https://github.com/nedjo90/juriste-fiduciaire-mustafa-ekrem.git "%USERPROFILE%\Documents\Mon équipe"
```

## 2. Lancer l'installateur, une seule fois
- **Windows** : clic droit sur `.equipe\scripts\installer.ps1` → « Exécuter avec PowerShell ».
- **macOS** : double-cliquer sur `.equipe/scripts/installer.command` (ou lancer `sh .equipe/scripts/installer.sh`).

L'installateur fonctionne sans droits d'administrateur. Il installe ou vérifie Python, les bibliothèques de documents et Claude Code en mode utilisateur. Il déclare le dossier de confiance, règle le mode sans demande d'autorisation, crée le raccourci « Mon équipe » sur le bureau, programme l'entretien automatique (ouverture de session, sortie de veille) et cache la zone machine.

## 3. Première ouverture
Double-cliquer sur « Mon équipe ». Si Claude Code demande de se connecter, se connecter avec le compte de Mustafa. Au plus, appuyer sur Entrée.

## Plus tard, au moment utile (l'équipe le proposera elle-même)
- **Messagerie et agenda** : cliquer « autoriser » dans le navigateur quand l'équipe propose de connecter Outlook ou Google. Une messagerie professionnelle Microsoft 365 peut exiger l'accord de l'informaticien de la fiduciaire (consentement administrateur de l'application) ; l'équipe fonctionne sans en attendant.
- **Bases payantes** (Swisslex, Weblaw…) : si la fiduciaire a des identifiants, les indiquer à l'équipe en conversation.

## Optionnel (exige un administrateur, sinon repli automatique)
- Aucun élément obligatoire. Les éléments optionnels sont listés ici par l'équipe au fil des découvertes.
