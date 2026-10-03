"""Système de design de la maison (§7.3) : lecture de system.yaml + surcharge par firm.yaml.
python design.py            → affiche le design effectif (JSON)
python design.py --verifier → contrastes WCAG de toutes les paires déclarées (ok/ko)"""
import sys, json, copy
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import yaml
from common import DESIGN_YAML, config_get, config_renseigne

_CACHE = None
CLES_CABINET = ["raison_sociale", "adresse", "logo", "signature", "langues"]


def charger(force=False):
    global _CACHE
    if _CACHE is not None and not force:
        return copy.deepcopy(_CACHE)
    d = yaml.safe_load(DESIGN_YAML.read_text(encoding="utf-8"))
    d["_origine_identite"] = {}
    for k in CLES_CABINET:
        if config_renseigne(f"firm.{k}"):
            d["identite"][k] = config_get(f"firm.{k}", d["identite"].get(k))
            d["_origine_identite"][k] = "firm.yaml"
        else:
            d["_origine_identite"][k] = "défaut"
    _CACHE = d
    return copy.deepcopy(d)


def couleur(d, nom):
    """nom de palette ou hex → '#RRGGBB'"""
    if isinstance(nom, str) and nom.startswith("#"):
        return nom
    v = d["palette"].get(nom)
    return v["hex"] if isinstance(v, dict) else v


def rgb(d, nom):
    h = couleur(d, nom).lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lum(hexa):
    h = hexa.lstrip("#")
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contraste(a, b):
    la, lb = sorted([_lum(a), _lum(b)], reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)


def verifier_contrastes(d=None):
    d = d or charger()
    seuils = d["contrastes_minimaux"]
    res = []
    for fg, bg, kind in d["paires_a_verifier"]:
        c = contraste(couleur(d, fg), couleur(d, bg))
        res.append({"paire": f"{fg}/{bg}", "ratio": c, "seuil": seuils[kind], "ok": c >= seuils[kind]})
    for h in d["palette"]["graphiques"]:
        c = contraste(h, couleur(d, "blanc"))
        res.append({"paire": f"graphique {h}/blanc", "ratio": c, "seuil": seuils["graphique"], "ok": c >= seuils["graphique"]})
    return res


def mention_confidentialite(d, langue):
    m = d["identite"]["mention_confidentialite"]
    return m.get(langue) or m["fr"]


def premier_fichier(liste):
    for p in liste or []:
        if Path(p).exists():
            return p
    return None


def police_mpl(d):
    """première police du thème disponible pour matplotlib"""
    try:
        from matplotlib import font_manager
        dispo = {f.name for f in font_manager.fontManager.ttflist}
        for p in d["graphiques"]["police"]:
            if p in dispo:
                return p
    except Exception:
        pass
    return "DejaVu Sans"


if __name__ == "__main__":
    d = charger()
    if "--verifier" in sys.argv:
        r = verifier_contrastes(d)
        print(json.dumps({"ok": all(x["ok"] for x in r), "contrastes": r}, ensure_ascii=False))
    else:
        print(json.dumps({k: d[k] for k in ("version", "identite", "_origine_identite", "palette", "typographie")}, ensure_ascii=False))
