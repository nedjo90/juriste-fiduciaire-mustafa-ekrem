#!/usr/bin/env python3
"""Droit de timbre d'émission sur droits de participation (fondation ou augmentation de capital d'une SA, SCA ou Sàrl).
Taux et franchise lus dans la table `bareme` (droit_emission.*, source RS 641.10 art. 8 al. 1 et art. 6 al. 1 let. h).
Base : montant reçu par la société, au moins la valeur nominale (art. 8 al. 1 let. a).
Usage : python stamp_duty.py --apport 1500000 --nominal 1000000 [--deja-verse 0] [--annee 2026] [--excel f.xlsx]"""
import argparse, datetime as dt, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import Calcul, sortir  # noqa: E402


def calculer(apport, nominal, deja_verse=0.0, annee=None):
    annee = annee or dt.date.today().year
    c = Calcul("Droit d'émission sur droits de participation", annee)
    c.taux("taux", "Taux du droit d'émission", "droit_emission", "taux_pct_droits_participation")
    c.taux("franchise", "Montant de l'art. 6 al. 1 let. h LT (versements totaux)", "droit_emission", "franchise_chf_fondation_augmentation", unite="CHF")
    c.entree("apport", "Montant reçu par la société pour les droits émis", float(apport))
    c.entree("nominal", "Valeur nominale des droits émis", float(nominal))
    c.entree("deja", "Versements antérieurs déjà imputés sur la franchise", float(deja_verse))
    c.ligne("base", "Base (montant reçu, au moins le nominal)", "MAX({apport}, {nominal})")
    c.ligne("franchise_dispo", "Franchise encore disponible", "MAX({franchise} - {deja}, 0)")
    c.ligne("imposable", "Montant imposable après franchise", "MAX({base} - {franchise_dispo}, 0)")
    c.ligne("droit", "Droit d'émission", "ROUND({imposable} * {taux} / 100, 2)")
    c.reserve("Lecture de l'art. 6 al. 1 let. h LT comme franchise imputée sur les versements cumulés : à confirmer par la pratique AFC "
              "(circulaire non ingérée) ⚠ ; autres exceptions de l'art. 6 (restructurations, assainissement) non examinées.")
    c.reserve("Naissance de la créance : inscription au registre du commerce (RS 641.10 art. 7 al. 1 let. a).")
    return c


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--apport", type=float, required=True)
    p.add_argument("--nominal", type=float, required=True)
    p.add_argument("--deja-verse", type=float, default=0.0)
    p.add_argument("--annee", type=int)
    p.add_argument("--excel")
    a = p.parse_args(argv)
    return sortir(calculer(a.apport, a.nominal, a.deja_verse, a.annee), a.excel)


if __name__ == "__main__":
    main()
