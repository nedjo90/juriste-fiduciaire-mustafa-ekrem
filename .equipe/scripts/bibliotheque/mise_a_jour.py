#!/usr/bin/env python3
"""Mise à jour de la bibliothèque fédérale, à chaque cycle complet (§10, §9.5). Job de fond idempotent, jamais bloquant.

1. Rattrapage : retente chaque tâche `bibliotheque_rattrapage` en attente (source injoignable lors d'un cycle précédent).
2. Pour chaque texte ingéré (RS × langue, version la plus récente) et chaque texte de priorites.yaml pas encore ingéré :
   interroge Fedlex (SPARQL) ; si une consolidation plus récente est en vigueur, l'ingère (l'ancienne reste disponible à sa
   date : cerebro tient `valide_au`), crée un objet `changement_droit` relié à l'ancienne et à la nouvelle source et aux
   objets qui citaient l'ancienne (règles de délais, positions, notes), puis inscrit `bibliotheque_maj` (priorité 5) dans la
   file d'entretien pour le cycle d'entretien.
3. Après tout changement : relance `cerebro law verify` (règles de délais) et `baremes.py` (barèmes), dont les résultats
   sont journalisés.
Journal début/fin/durée/résultat : .equipe/bibliotheque/cache/journal.jsonl.
Usage : python mise_a_jour.py [--langues fr de] [--sans-priorites] [--max 50]"""
import argparse, json, os, sqlite3, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fedlex  # noqa: E402
from fedlex import cerebro, journal, utf8_console  # noqa: E402


def chemin_db():
    if os.environ.get("CEREBRO_DB"):
        return Path(os.environ["CEREBRO_DB"])
    return fedlex.EQ / "cerebro" / "cerebro.db"


def textes_ingeres():
    """(rs, langue) → dernière version ingérée et son identifiant"""
    p = chemin_db()
    if not p.exists():
        return {}
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    out = {}
    for r in con.execute("SELECT id, identifiant, langue, version, abreviation FROM bibliotheque WHERE juridiction='CH' ORDER BY version"):
        out[(r["identifiant"], r["langue"])] = dict(r)
    con.close()
    return out


def textes_absents():
    """versions connues de la base dont le texte manque sur ce poste : la base est rechargée depuis les exports livrés par git,
    mais la bibliothèque (textes) n'est pas dans git → premier cycle d'un poste neuf, ou dossier copié sans la bibliothèque"""
    p = chemin_db()
    if not p.exists():
        return []
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    out = []
    for r in con.execute("SELECT b.identifiant, b.langue, b.version, b.chemin FROM bibliotheque b WHERE b.juridiction='CH' ORDER BY b.version DESC"):
        ch = Path(r["chemin"] or "")
        if not ch.is_absolute():
            ch = fedlex.EQ.parent / ch
        if not r["chemin"] or not ch.exists():
            out.append(dict(r))
    con.close()
    return out


def restaurer(langues, maximum):
    faits = []
    for r in textes_absents()[:maximum]:
        if langues and r["langue"] not in langues:
            continue
        res = fedlex.ingerer(r["identifiant"], r["langue"], date=r["version"])
        faits.append({"rs": r["identifiant"], "langue": r["langue"], "version": r["version"], "ok": "erreur" not in res})
    return faits


def objets_citant(bid):
    l = cerebro("links", bid)
    inc = l.get("entrants", []) if isinstance(l, dict) else []
    return sorted({x["src"] for x in inc if isinstance(x, dict) and x.get("src")})


def changement(rs, langue, ancien, nouveau):
    nom = f"{nouveau.get('abrev') or 'RS ' + rs} ({langue}) : nouvelle consolidation du {nouveau['version']}"
    resume = (f"RS {rs} — la version consolidée en vigueur passe du {ancien['version']} ({ancien['id']}) au {nouveau['version']} ({nouveau['id']}). "
              f"Entrée en vigueur de la nouvelle version : {nouveau['version']}. Relire les règles, barèmes et positions liés ; diff à établir au cycle d'entretien.")
    touches = objets_citant(ancien["id"])
    args = ["new", "changement_droit", nom, "--resume", resume, "--date", fedlex.aujourdhui(), "--source", nouveau["url"],
            "--domaine", "bibliothèque", "--prochaine-action", "analyser l'impact (bibliotheque_maj)", "--lien", nouveau["id"], "--lien", ancien["id"]]
    for t in touches:
        args += ["--lien", t]
    r = cerebro(*args)
    cid = r.get("id") if isinstance(r, dict) else None
    cerebro("queue", "add", "bibliotheque_maj", f"{rs}:{langue}:{nouveau['version']}" + (f":{cid}" if cid else ""), "--priorite", "5")
    return {"changement": cid, "objets_touches": touches}


def rattrapage(langues):
    faits = []
    file = cerebro("queue", "list")
    for t in file if isinstance(file, list) else []:
        if t.get("tache") != "bibliotheque_rattrapage":
            continue
        rs = (t.get("arg") or "").split(":")[0]
        res = [fedlex.ingerer(rs, lg) for lg in langues[:1]]
        if all("erreur" not in x for x in res):
            cerebro("queue", "done", t["n"], "fait")
        faits.append({"rs": rs, "ok": all("erreur" not in x for x in res)})
    return faits


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--langues", nargs="*", default=None, help="restreindre aux langues (défaut : celles déjà ingérées)")
    p.add_argument("--sans-priorites", action="store_true", help="ne pas ingérer les textes de priorites.yaml absents")
    p.add_argument("--max", type=int, default=100, help="nombre maximal de textes examinés par cycle")
    a = p.parse_args(argv)
    utf8_console()
    t0 = time.time()
    journal("mise_a_jour début")
    bilan = {"examines": 0, "a_jour": 0, "nouvelles_versions": [], "nouveaux_textes": [], "erreurs": [], "rattrapage": []}
    try:
        bilan["rattrapage"] = rattrapage(a.langues or ["fr"])
        bilan["restaures"] = restaurer(a.langues, a.max)
        ing = textes_ingeres()
        cibles = list(ing.items())
        if not a.sans_priorites:
            for t in fedlex.charger_priorites()["textes"]:
                for lg in t.get("langues", ["fr"]):
                    if (t["rs"], lg) not in ing:
                        cibles.append(((t["rs"], lg), None))
        for (rs, lg), anc in cibles[: a.max]:
            if a.langues and lg not in a.langues:
                continue
            bilan["examines"] += 1
            try:
                acte = fedlex.resoudre(rs)
                cons = acte and fedlex.consolidation_a(acte["eli"])
                if not cons:
                    raise LookupError("aucune consolidation en vigueur trouvée")
                if anc and cons["du"] <= anc["version"]:
                    bilan["a_jour"] += 1
                    continue
                res = fedlex.ingerer(rs, lg, acte=acte)
                if "erreur" in res:
                    bilan["erreurs"].append({"rs": rs, "langue": lg, "erreur": res["erreur"]})
                    continue
                if anc:
                    bilan["nouvelles_versions"].append({"rs": rs, "langue": lg, "de": anc["version"], "a": res["version"], **changement(rs, lg, anc, res)})
                else:
                    bilan["nouveaux_textes"].append({"rs": rs, "langue": lg, "version": res["version"], "id": res.get("id")})
            except Exception as e:  # source injoignable : incident + rattrapage, on continue
                fedlex.incident(rs, lg, e)
                bilan["erreurs"].append({"rs": rs, "langue": lg, "erreur": str(e)[:200]})
        if bilan["nouvelles_versions"] or bilan["nouveaux_textes"] or any(r["ok"] for r in bilan["restaures"]):
            v = cerebro("law", "verify")
            bilan["regles_non_confirmees"] = [r["id"] for r in v if isinstance(r, dict) and not r.get("verifie")] if isinstance(v, list) else v
            b = subprocess.run([sys.executable, str(Path(__file__).parent / "baremes.py")], capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
            try:
                bilan["baremes"] = {s: sum(1 for x in json.loads(b.stdout) if x["statut"] == s) for s in ("inscrit", "inchangé", "non confirmé")}
            except Exception:
                bilan["baremes"] = (b.stdout or b.stderr)[:300]
    except Exception as e:
        bilan["erreurs"].append({"cycle": str(e)[:300]})
        cerebro("incident", "add", f"mise à jour bibliothèque interrompue : {str(e)[:200]}", "--categorie", "source", "--repli", "reprise au cycle suivant")
    bilan["duree_s"] = round(time.time() - t0, 1)
    journal("mise_a_jour fin", **{k: (len(v) if isinstance(v, list) else v) for k, v in bilan.items()})
    print(json.dumps(bilan, ensure_ascii=False, indent=1))
    return bilan


if __name__ == "__main__":
    main()
