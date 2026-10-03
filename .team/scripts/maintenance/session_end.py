#!/usr/bin/env python3
"""Fin de session (hook SessionEnd, en arrière-plan détaché) : consolidation sans jamais bloquer (§11).
1 greffier groupé si des captures ne sont pas classées · 2 export structuré · 3 commit + push (échec = incident)
· 4 cycle d'entretien court. Chaque étape est indépendante : une erreur est journalisée, la suite continue."""
import sys, json, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import background as fond
from background import journal


def etape(nom, f, bilan):
    t0 = time.time()
    try:
        bilan[nom] = f()
    except Exception as e:
        bilan[nom] = {"echec": repr(e)[:200]}
    journal("fin-de-session", etape=nom, ms=int((time.time() - t0) * 1000), resultat=bilan[nom])


def main():
    fond.basse_priorite()
    import clerk as greffier, cycle
    bilan = {}
    journal("fin-de-session", statut="début")

    def classer():
        if greffier.compter() == 0:
            return {"captures": 0}
        v = fond.Verrou("clerk", peremption=1800)
        if not v.prendre():
            return {"deja_en_cours": True}
        try:
            return greffier.lancer()
        finally:
            v.rendre()

    etape("clerk", classer, bilan)
    etape("export", lambda: cycle.t_export("", 0), bilan)
    etape("commit_push", lambda: cycle.t_commit_push("", 0), bilan)

    def court():
        v = fond.Verrou("entretien", peremption=3 * 3600)
        if not v.prendre():
            return {"deja_en_cours": True}
        try:
            return cycle.executer("court", 5)
        finally:
            v.rendre()

    etape("cycle_court", court, bilan)
    journal("fin-de-session", statut="fin")
    print(json.dumps(bilan, ensure_ascii=False, default=str))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        journal("erreurs-fond", job="fin-de-session", erreur=repr(e))
