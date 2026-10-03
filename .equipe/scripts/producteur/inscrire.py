"""Inscription idempotente dans cerebro des skills de production/design, des gabarits et des capacités du chantier
producteur + portes (T-051, T-060). Équivaut à `cerebro new skill <nom> --source …` + `cerebro update <ID> chemin=…`
+ `cerebro capability register …`, mais sans créer de fichier d'objet parasite (chemin posé dès la création).
python inscrire.py → JSON {skills, capacites, gabarits}"""
import sys, json, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import commun as C

SKILLS = {
    "frontend-design": ("anthropics/skills · Apache-2.0", "Design d'interface : tableaux de bord, calculateurs, rendus HTML de la maison (avec brand-guidelines)"),
    "canvas-design": ("anthropics/skills · Apache-2.0 (polices OFL)", "Pièces visuelles statiques PNG/PDF (affiches, couvertures, visuels de newsletter)"),
    "theme-factory": ("anthropics/skills · Apache-2.0", "Thèmes de couleurs et polices ; base de travail du système de design"),
    "brand-guidelines": ("anthropics/skills · Apache-2.0, réécrite", "Charte de la maison : palette, typographies, grille, tableaux, légendes, graphiques (résumé de systeme.yaml)"),
    "doc-coauthoring": ("anthropics/skills · Apache-2.0 présumée", "Rédaction structurée de documents longs (contexte, structure, test lecteur)"),
    "internal-comms": ("anthropics/skills · Apache-2.0", "Notes et comptes rendus internes"),
    "skill-creator": ("anthropics/skills · Apache-2.0", "Méthode de fabrication et d'évaluation des skills (fabrique §6.5)"),
    "humanizer": ("blader/humanizer · MIT", "Détection et réécriture des tics de machine (anglais), base des variantes FR/DE/IT et de la porte tics"),
    "humanizer-fr": ("maison, dérivée de humanizer · MIT", "Tics de machine en français romand : relecture et réécriture dans la voix de la maison"),
    "humanizer-de": ("maison, dérivée de humanizer · MIT", "Tics de machine en allemand (usage suisse) : relecture et réécriture"),
    "humanizer-it": ("maison, dérivée de humanizer · MIT", "Tics de machine en italien (usage suisse) : relecture et réécriture"),
    "production-livrables": ("maison", "Produire un livrable : markdown structuré → produire.py → portes.py → corrections → présentation avec réserves"),
}

CAPACITES = [
    ("producteur-livrables (produire.py)", "script", "Rien (local) ; ouverture du fichier dans l'application par défaut", "-", "maison", ".equipe/scripts/producteur/produire.py"),
    ("portes-deterministes (portes.py)", "script", "Rien (local)", "-", "maison", ".equipe/scripts/portes/portes.py"),
    ("gabarits-maison (gabarits.py)", "script", "Rien (local)", "-", "maison", ".equipe/scripts/producteur/gabarits.py"),
    ("python-docx", "bibliotheque-python", "Rien", "-", "MIT", "pypi:python-docx"),
    ("openpyxl", "bibliotheque-python", "Rien", "-", "MIT", "pypi:openpyxl"),
    ("python-pptx", "bibliotheque-python", "Rien", "-", "MIT", "pypi:python-pptx"),
    ("reportlab", "bibliotheque-python", "Rien", "-", "BSD", "pypi:reportlab"),
    ("matplotlib", "bibliotheque-python", "Rien", "-", "PSF/BSD", "pypi:matplotlib"),
    ("LibreOffice sans affichage (soffice --convert-to pdf)", "outil", "Rien", "-", "MPL-2.0", "soffice"),
    ("poppler (pdftoppm, pdftotext)", "outil", "Rien", "-", "GPL-2.0", "pdftoppm"),
    ("Mermaid CLI (npx @mermaid-js/mermaid-cli)", "outil", "Texte du schéma vers le registre npm au premier téléchargement seulement", "registre npm", "MIT", "npx -y @mermaid-js/mermaid-cli"),
    ("anthropics document-skills (docx, pptx, xlsx, pdf)", "skill-plugin", "Rien (skills chargées par Claude Code)", "-", "propriétaire Anthropic, source disponible : copie interdite hors des Services", "plugin document-skills@anthropic-agent-skills"),
]


def main():
    core, objets, _, files = C.cb()
    con = core.db()
    res = {"skills": {}, "capacites": {}, "gabarits": {}}
    racine = C.ROOT / ".claude" / "skills"
    for nom, (origine, resume) in SKILLS.items():
        chemin = f".claude/skills/{nom}/SKILL.md"
        if not (C.ROOT / chemin).exists():
            continue
        r = con.execute("SELECT id FROM objets WHERE type='skill' AND nom=?", (nom,)).fetchone()
        if r:
            objets.update(r[0], chemin=chemin, resume=f"{resume} · {origine}")
            res["skills"][nom] = r[0]
        else:
            res["skills"][nom] = objets.create("skill", nom, resume=f"{resume} · {origine}", source=chemin, chemin=chemin, statut="actif",
                                               prochaine_action="réviser selon le tableau de bord des principes", mots_cles="skill production design " + nom)
    for nom, cat, sort, vers, lic, src in CAPACITES:
        statut = "a-installer" if "document-skills" in nom else ("indisponible-ici" if "Mermaid" in nom else "actif")
        res["capacites"][nom] = files.capability_register(nom, cat, "LOCAL" if "Mermaid" not in nom else "EXTERNE", sort, vers, lic, "", statut, src)
    import gabarits
    res["gabarits"] = gabarits.generer(C.MODELES, inscrire=True).get("_ids", {})
    return res


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False))
