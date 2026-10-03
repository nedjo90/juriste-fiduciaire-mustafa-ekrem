"""Extension du cycle : routines posées par Mustafa (« désormais, chaque lundi… »), exécutées au premier cycle venu du
jour dit (machine éteinte la nuit). Script d'abord ; modèle intermédiaire seulement sans recette (priorité 2 : une
routine est un livrable demandé). Produit un document lié + une ligne au brief (état `routines_du_jour`)."""
import importlib.util
from pathlib import Path

_EQ = Path(__file__).resolve().parents[3]


def _recettes():
    spec = importlib.util.spec_from_file_location("routines_recettes", _EQ / "scripts" / "routines" / "recipes.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def t_routines(arg, fin):
    R = _recettes()
    res = R.executer_dues()
    faites = [r for r in res if r.get("document")]
    attente = [r["routine"] for r in res if r.get("_partiel")]
    out = {"executees": len(faites), "documents": [r["document"] for r in faites], "voies": sorted({r.get("voie", "") for r in faites})}
    if attente:
        out.update(attente=attente, _partiel=True)  # reste en file : reprise au cycle suivant quand le budget le permet
    return out


def PLANIFIER(complet, mode, ajouter):
    import background as fond
    fond.cb()
    from cb import routines as RT
    if RT.routine_due():
        ajouter("routines", "", 2)


TACHES = {"routines": t_routines}
