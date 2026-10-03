#!/usr/bin/env python3
"""Impôt anticipé sur un dividende (rendement de capitaux mobiliers) : brut, impôt anticipé, net versé.
Taux lu dans la table `bareme` (impot_anticipe.taux_pct_capitaux_mobiliers, source RS 642.21 art. 13 al. 1 let. a).
Usage : python impot_anticipe.py --brut 100000 [--annee 2026] [--excel sortie.xlsx]
        python impot_anticipe.py --net 65000   (montant net convenu : brut reconstitué = net / (1 - taux), hypothèse de calcul)"""
import argparse, datetime as dt, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from commun import Calcul, sortir  # noqa: E402


def calculer(brut=None, net=None, annee=None):
    annee = annee or dt.date.today().year
    c = Calcul("Impôt anticipé sur dividende", annee)
    c.taux("taux", "Taux de l'impôt anticipé (revenus de capitaux mobiliers)", "impot_anticipe", "taux_pct_capitaux_mobiliers")
    if net is not None:
        c.entree("net", "Dividende net convenu (versé à l'actionnaire)", float(net))
        c.ligne("brut", "Dividende brut reconstitué", "ROUND({net} / (1 - {taux} / 100), 2)")
        c.ligne("ia", "Impôt anticipé", "ROUND({brut} - {net}, 2)")
        c.ligne("net_verse", "Net versé à l'actionnaire", "{net}")
        c.reserve("Hypothèse : la société prend l'impôt à sa charge (montant net convenu) ; la prestation imposable est alors le brut reconstitué. "
                  "Base légale de la reconstitution non vérifiée dans un texte ingéré ⚠ (pratique AFC à vérifier).")
    else:
        c.entree("brut", "Dividende brut décidé", float(brut))
        c.ligne("brut_r", "Dividende brut", "{brut}")
        c.ligne("ia", "Impôt anticipé", "ROUND({brut} * {taux} / 100, 2)")
        c.ligne("net_verse", "Net versé à l'actionnaire", "ROUND({brut} - {ia}, 2)")
    c.reserve("Échéance : 30 jours après la naissance de la créance fiscale (RS 642.21 art. 16 al. 1 let. c ; règle RD-003).")
    c.reserve("Procédure de déclaration au lieu du paiement, formulaires et remboursement : non traités par ce calcul.")
    return c


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--brut", type=float)
    g.add_argument("--net", type=float)
    p.add_argument("--annee", type=int)
    p.add_argument("--excel")
    a = p.parse_args(argv)
    return sortir(calculer(a.brut, a.net, a.annee), a.excel)


if __name__ == "__main__":
    main()
