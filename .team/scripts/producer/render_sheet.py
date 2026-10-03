"""Rendu Excel depuis modele-calcul.xlsx : Hypothèses (noms définis, sources) / Calculs (formules sur les noms,
aucune valeur en dur) / Sensibilités / Sources. Spécification dans le front matter :
hypotheses: [{nom, libelle, valeur, unite, source, verifie_le}]
calculs:    [{libelle, formule: "montant_base*taux", unite, note}]   # formules sur noms ou {Cn} = résultat de l'étape n
sensibilites: {hypothese: taux, pas: [-2,-1,0,1,2], ecart: variation, etape: 2}"""
import re
from openpyxl import load_workbook
from openpyxl.workbook.defined_name import DefinedName
from common import MODELES


def _effacer(ws, depuis):
    for row in ws.iter_rows(min_row=depuis, max_row=ws.max_row):
        for c in row:
            c.value = None


def rendre(meta, dest, sources=None):
    p = MODELES / "modele-calcul.xlsx"
    if not p.exists():
        import templates as gabarits
        gabarits.generer(MODELES)
    wb = load_workbook(str(p))
    for nom in list(wb.defined_names.keys()):
        del wb.defined_names[nom]
    wh, wc, ws, wr = wb["Hypothèses"], wb["Calculs"], wb["Sensibilités"], wb["Sources"]
    _effacer(wh, 5); _effacer(wc, 4); _effacer(ws, 4); _effacer(wr, 4)
    wh["A1"] = f"Hypothèses — {meta.get('titre', '')}"
    lignes = {}
    for r, h in enumerate(meta.get("hypotheses") or [], 5):
        vals = [h.get("nom"), h.get("libelle", ""), h.get("valeur"), h.get("unite", ""), h.get("source", "⚠ à sourcer"), h.get("verifie_le", "")]
        for i, v in enumerate(vals, 1):
            c = wh.cell(row=r, column=i, value=v); c.style = "Maison Saisie" if i == 3 else "Maison Texte"
        if h.get("unite") == "%":
            wh.cell(row=r, column=3).number_format = "0.00%"
        elif h.get("unite") == "CHF":
            wh.cell(row=r, column=3).number_format = "#,##0.00"
        wb.defined_names[h["nom"]] = DefinedName(h["nom"], attr_text=f"'Hypothèses'!$C${r}")
        lignes[h["nom"]] = r
    for k, c in enumerate(meta.get("calculs") or [], 1):
        r = 3 + k
        f = str(c.get("formule", "")).lstrip("=")
        f = re.sub(r"\{C(\d+)\}", lambda m: f"C{3 + int(m.group(1))}", f)
        vals = [str(k), c.get("libelle", ""), "=" + f, c.get("unite", ""), c.get("lisible") or re.sub(r"\{C(\d+)\}", r"étape \1", str(c.get("formule", ""))), c.get("note", "")]
        for i, v in enumerate(vals, 1):
            cell = wc.cell(row=r, column=i, value=v); cell.style = "Maison Calcul" if i == 3 else "Maison Texte"
        if c.get("unite") == "CHF":
            wc.cell(row=r, column=3).number_format = "#,##0.00"
    s = meta.get("sensibilites")
    if s and s.get("hypothese") in lignes:
        etape = int(s.get("etape", len(meta.get("calculs") or [1])))
        ws["B3"] = f"{s['hypothese']} testé"
        for k, pas in enumerate(s.get("pas", [-2, -1, 0, 1, 2])):
            r = 4 + k
            ws.cell(row=r, column=1, value=pas).style = "Maison Saisie"
            ws.cell(row=r, column=2, value=f"={s['hypothese']}+A{r}*{s.get('ecart', 'variation')}").style = "Maison Calcul"
            # résultat recalculé proportionnellement à l'hypothèse testée (modèle linéaire en cette hypothèse)
            c3 = ws.cell(row=r, column=3, value=f"=Calculs!$C${3 + etape}/{s['hypothese']}*B{r}"); c3.style = "Maison Calcul"; c3.number_format = "#,##0.00"
            ws.cell(row=r, column=2).number_format = "0.00%"
    for k, src in enumerate(sources or [], 4):
        for i, v in enumerate([f"[{src['n']}]", src.get("titre", ""), src.get("etat", ""), src.get("url", ""), src.get("verifie_le", "")], 1):
            wr.cell(row=k, column=i, value=v).style = "Maison Texte"
    wb.properties.title = meta.get("titre", "")
    wb.properties.language = meta.get("langue", "fr")
    wb.properties.category = "calcul"
    wb.save(str(dest))
