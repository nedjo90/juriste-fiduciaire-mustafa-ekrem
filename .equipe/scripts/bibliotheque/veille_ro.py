#!/usr/bin/env python3
"""Veille par script des publications officielles fédérales (§10) : le Recueil officiel (RO, actes eli/oc) publié depuis le
dernier passage, filtré sur les domaines d'une fiduciaire et sur les textes déjà dans la bibliothèque.

Pourquoi : la mise à jour de la bibliothèque (mise_a_jour.py) ne voit une réforme qu'au jour de son entrée en vigueur, quand
la nouvelle version consolidée existe. Une loi adoptée et publiée aujourd'hui pour le 1er janvier 2028 doit être connue dès
sa publication : préparation des clients, délais transitoires, conseils.

Chaque publication retenue devient un objet `changement_droit` (source : l'acte officiel, date : entrée en vigueur), relié au
texte de la bibliothèque qu'il modifie et aux objets qui le citent ; le veilleur juge ensuite la pertinence par client
(veille_hebdo) et les alertes partent en file. Dédoublonné par l'URI de l'acte. Aucun modèle, réseau seulement.
Usage : python veille_ro.py [--depuis AAAA-MM-JJ] [--jours 21]"""
import argparse, datetime as dt, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fedlex  # noqa: E402
from fedlex import cerebro, journal, utf8_console, CACHE  # noqa: E402

ETAT = CACHE / "veille_ro.json"
# classement systématique (RS) des domaines d'une fiduciaire : personnes, famille et successions, obligations et sociétés,
# registre du commerce, protection des données, poursuites, droit international privé, fiscalité (TVA, timbre, impôt
# anticipé, IFD, LHID, assistance administrative, échange de renseignements), double imposition, travail, assurances
# sociales, banques et marchés financiers, blanchiment d'argent
DOMAINES = ("210", "211", "220", "221", "231", "235", "281", "291", "641", "642", "651", "652", "653", "0.672", "0.651",
            "0.652", "0.653", "822", "831", "832", "833", "834", "835", "836", "837", "952", "954", "955", "956")


def pertinent(rs, ingeres):
    rs = str(rs or "")
    return any(rs == p or rs.startswith(p + ".") for p in (*DOMAINES, *ingeres))


def publications(depuis):
    q = fedlex.PFX + f"""SELECT DISTINCT ?act ?pub ?eif ?n ?titre WHERE {{
 ?act a jolux:Act ; jolux:publicationDate ?pub .
 FILTER(STRSTARTS(STR(?act), "https://fedlex.data.admin.ch/eli/oc/"))
 FILTER(?pub >= "{depuis}"^^xsd:date)
 ?act jolux:classifiedByTaxonomyEntry ?t . ?t skos:notation ?n .
 OPTIONAL {{ ?act jolux:dateEntryInForce ?eif }}
 OPTIONAL {{ ?act jolux:isRealizedBy ?e . ?e jolux:language <http://publications.europa.eu/resource/authority/language/FRA> ; jolux:title ?titre }}
}} ORDER BY ?pub LIMIT 2000"""
    out = {}
    for r in fedlex.sparql(q):
        a = out.setdefault(r["act"], {"uri": r["act"], "publie": r["pub"][:10], "en_vigueur": (r.get("eif") or "")[:10] or None,
                                      "rs": set(), "titre": r.get("titre") or ""})
        a["rs"].add(str(r["n"]))
        if r.get("titre") and not a["titre"]:
            a["titre"] = r["titre"]
    return list(out.values())


def main(argv=None):
    utf8_console()
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--depuis")
    p.add_argument("--jours", type=int, default=21, help="premier passage : publications des N derniers jours")
    a = p.parse_args(argv)
    auj = fedlex.aujourdhui()
    etat = {}
    try:
        etat = json.loads(ETAT.read_text(encoding="utf-8"))
    except Exception:
        pass
    depuis = a.depuis or etat.get("dernier_passage") or (dt.date.fromisoformat(auj) - dt.timedelta(days=a.jours)).isoformat()
    vus = set(etat.get("actes", []))
    bilan = {"depuis": depuis, "publications": 0, "retenues": [], "erreur": None}
    try:
        sys.path.insert(0, str(fedlex.EQ / "cerebro"))
        from cb import core
        con = core.db()
        ingeres = {r[0]: r[1] for r in con.execute(
            "SELECT b.identifiant, MAX(b.id) FROM bibliotheque b WHERE b.juridiction='CH' GROUP BY b.identifiant")}
        deja = {r[0] for r in con.execute("SELECT source FROM objets WHERE type='changement_droit' AND COALESCE(source,'')!=''")}
        pubs = publications(depuis)
        bilan["publications"] = len(pubs)
        for pb in pubs:
            if pb["uri"] in vus or pb["uri"] in deja:
                continue
            rs = sorted(r for r in pb["rs"] if pertinent(r, ingeres))
            if not rs:
                continue
            eif = pb["en_vigueur"] or pb["publie"]
            a_venir = eif > auj
            titre = core.cut(pb["titre"] or f"Acte publié au RO le {pb['publie']}", 120)
            nom = f"{titre} (RS {', '.join(rs[:3])})"
            resume = (f"Publié au Recueil officiel le {pb['publie']} ; entrée en vigueur le {eif}"
                      + (" (à venir : préparer les clients et les délais transitoires)" if a_venir else "")
                      + f". Textes touchés : RS {', '.join(rs)}. Analyse d'impact par le veilleur.")
            analyse = (dt.date.fromisoformat(auj) + dt.timedelta(days=7)).isoformat()  # analyse dans la semaine, pas à l'échéance
            args = ["new", "changement_droit", nom, "--resume", resume, "--date", analyse, "--source", pb["uri"],
                    "--domaine", "veille", "--prochaine-action",
                    f"analyser l'impact avant l'entrée en vigueur du {eif}" if a_venir else "analyser l'impact (en vigueur)",
                    "--mots-cles", " ".join(["réforme" if a_venir else "modification", *rs])]
            for r in rs:
                if r in ingeres:
                    args += ["--lien", ingeres[r]]
            res = cerebro(*args)
            cid = res.get("id") if isinstance(res, dict) else None
            vus.add(pb["uri"])
            bilan["retenues"].append({"id": cid, "rs": rs, "publie": pb["publie"], "en_vigueur": eif, "a_venir": a_venir, "titre": titre})
        etat = {"dernier_passage": auj, "actes": sorted(vus)[-3000:]}
        CACHE.mkdir(parents=True, exist_ok=True)
        ETAT.write_text(json.dumps(etat, ensure_ascii=False), encoding="utf-8")
    except Exception as e:  # source injoignable : on réessaie au prochain passage depuis la même date
        bilan["erreur"] = str(e)[:300]
        cerebro("incident", "add", f"veille du Recueil officiel indisponible : {str(e)[:150]}", "--categorie", "source",
                "--repli", "nouvel essai au prochain passage, depuis la même date")
    journal("veille_ro", depuis=depuis, publications=bilan["publications"], retenues=len(bilan["retenues"]), erreur=bilan["erreur"])
    print(json.dumps(bilan, ensure_ascii=False, indent=1))
    return bilan


if __name__ == "__main__":
    main()
