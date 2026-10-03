#!/usr/bin/env python3
"""TVA : passage HT ↔ TTC selon le taux (normal, réduit, spécial hébergement) lu dans la table `bareme`
(tva.taux_pct_*, source RS 641.20 art. 25).
Usage : python tva.py --montant 1000 --mode ht  [--taux normal|reduit|special_hebergement] [--annee 2026] [--excel f.xlsx]
        python tva.py --montant 1081 --mode ttc"""
import argparse, datetime as dt, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from commun import Calcul, sortir  # noqa: E402

TAUX = {"normal": "taux_pct_normal", "reduit": "taux_pct_reduit", "special_hebergement": "taux_pct_special_hebergement"}


def calculer(montant, mode="ht", taux="normal", annee=None):
    annee = annee or dt.date.today().year
    c = Calcul(f"TVA au taux {taux.replace('_', ' ')}", annee)
    c.taux("taux", f"Taux de TVA ({taux.replace('_', ' ')})", "tva", TAUX[taux])
    if mode == "ht":
        c.entree("ht", "Montant hors taxe", float(montant))
        c.ligne("tva", "TVA", "ROUND({ht} * {taux} / 100, 2)")
        c.ligne("ttc", "Montant TTC", "ROUND({ht} + {tva}, 2)")
    else:
        c.entree("ttc", "Montant TTC", float(montant))
        c.ligne("ht", "Montant hors taxe", "ROUND({ttc} / (1 + {taux} / 100), 2)")
        c.ligne("tva", "TVA comprise", "ROUND({ttc} - {ht}, 2)")
    c.reserve("Arrondi au centime ; l'arrondi aux 5 centimes et le choix du taux applicable à la prestation (art. 25 LTVA) restent à vérifier par opération.")
    if taux == "special_hebergement":
        c.reserve("Taux spécial applicable jusqu'au 31 décembre 2027 au plus tard (RS 641.20 art. 25 al. 4).")
    return c


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--montant", type=float, required=True)
    p.add_argument("--mode", choices=["ht", "ttc"], default="ht")
    p.add_argument("--taux", choices=sorted(TAUX), default="normal")
    p.add_argument("--annee", type=int)
    p.add_argument("--excel")
    a = p.parse_args(argv)
    return sortir(calculer(a.montant, a.mode, a.taux, a.annee), a.excel)


if __name__ == "__main__":
    main()
