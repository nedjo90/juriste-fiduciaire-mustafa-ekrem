"""Génère .equipe/config/*.yaml (fichiers à trous, §0 bis). Idempotent : ne remplace jamais une `valeur` déjà renseignée."""
import os, yaml
D = os.path.join(os.path.dirname(__file__), "..", "config")
# clé: (defaut, question, effet 1-5)
SPEC = {
 "cabinet": {
  "raison_sociale": ("[fiduciaire de Mustafa]", "Comment s'appelle exactement la fiduciaire, telle qu'elle figure sur vos lettres ?", 4),
  "adresse": ("", "Quelle adresse doit figurer en pied de page de vos documents ?", 2),
  "logo": ("", "Pouvez-vous glisser le logo de la fiduciaire dans le dossier que je vous montre ?", 2),
  "charte": ("sobre et neutre", "Avez-vous un modèle de lettre de la maison à me donner ?", 4),
  "signature": ("Mustafa Ekrem, juriste", "Comment signez-vous vos mails d'habitude ?", 3),
  "langues": (["fr"], "Vos clients écrivent surtout en français, ou aussi en allemand et en italien ?", 3),
 },
 "mustafa": {
  "prenom": ("Mustafa", "", 1),
  "tutoiement": ("vouvoiement", "On se tutoie ?", 2),
  "langues": (["fr", "de", "en"], "Dans quelles langues travaillez-vous au quotidien ?", 3),
  "cantons_suivis": (["VD", "GE"], "Vos dossiers sont surtout dans quels cantons ?", 5),
  "domaines": (["sociétés", "fiscalité", "contrats"], "Sur quels sujets travaillez-vous le plus ?", 4),
  "style": ("direct, précis, courtois", "", 2),
 },
 "poste": {
  "systeme": ("Windows", "", 4),
  "messagerie": ("Outlook / Microsoft 365", "Votre messagerie, c'est Outlook ?", 5),
  "agenda": ("Outlook / Microsoft 365", "", 3),
  "office": ("Microsoft Office", "", 2),
  "navigateur": ("Edge", "", 1),
  "logiciel_fiduciaire": ("", "Quel logiciel la fiduciaire utilise-t-elle pour la comptabilité des clients ?", 2),
 },
 "acces": {
  "bases_recherche": ([], "Avez-vous un abonnement Swisslex ou Weblaw au cabinet ?", 4),
  "abonnement_claude": ("petit abonnement (profil frugal)", "", 3),
  "connecteurs": ([], "", 2),
  "depot_git": ("github.com/nedjo90/juriste-fiduciaire-mustafa-ekrem (privé)", "", 1),
  "deepl": ("non", "", 1),
 },
 "modeles": {
  "profil": ("frugal", "", 3),
  "plus_capable": ("opus", "", 3),
  "intermediaire": ("sonnet", "", 2),
  "leger": ("haiku", "", 2),
  "effort_associe": ("high", "", 2),
  "budget_fond_quotidien_appels": (3, "", 2),
 },
 "clients": {
  "principaux": ([], "Quels sont vos trois ou quatre clients les plus importants en ce moment ?", 5),
 },
}
def main():
    os.makedirs(D, exist_ok=True)
    for f, keys in SPEC.items():
        p = os.path.join(D, f + ".yaml")
        cur = yaml.safe_load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
        cur = cur or {}
        for k, (dft, q, eff) in keys.items():
            e = cur.get(k) or {}
            cur[k] = {"valeur": e.get("valeur", None), "defaut": dft,
                      "source": e.get("source", "défaut"), "question": q, "effet": eff}
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(f"# {f}.yaml — fichier à trous (§0 bis). Une clé vide applique `defaut`. Modifier via : cerebro config set {f}.<clé> <valeur>\n")
            yaml.safe_dump(cur, fh, allow_unicode=True, sort_keys=False)
if __name__ == "__main__":
    main()
