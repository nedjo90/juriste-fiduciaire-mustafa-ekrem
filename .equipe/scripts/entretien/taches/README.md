# Extensions du cycle d'entretien
Un fichier `<nom>.py` par famille de tâches. Contrat (tout est optionnel) :
- `TACHES = {"nom_tache": fonction(arg, fin) -> dict}` — `fin` = horodatage limite de l'incrément ; renvoyer `{"_partiel": True, …}` pour reprendre plus tard.
- `CADENCES = {"nom_tache": (jours, priorité)}` — planifiée au premier cycle venu après l'échéance.
- `MODELES`, `RESEAU` — ensembles de tâches qui appellent un modèle / Internet (sautées en test).
- `def PLANIFIER(complet, mode, ajouter)` — ajoute des tâches à la file (`ajouter(tache, arg, priorité)`).
Priorités : 1 sommaires · 2 délais, brouillons · 3 classement · 4 couverture, vues · 5 bibliothèque, veille, découverte, fabrique · 6 sauvegarde, export.
Une extension en erreur est journalisée et ignorée ; elle n'arrête jamais le cycle.
