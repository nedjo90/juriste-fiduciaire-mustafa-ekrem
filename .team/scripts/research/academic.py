#!/usr/bin/env python3
"""Recherche académique (doctrine référencée, §6.4, §10) : CrossRef, Semantic Scholar, OpenAlex — API publiques sans
compte. Ordre : CrossRef (fiable, sans limite stricte), puis Semantic Scholar, puis OpenAlex (pause, nouvel essai espacé
sur 429, puis repli : source marquée « indisponible », les autres résultats suffisent). Doctrine sous licence :
références seulement (titre, auteurs, année, revue, DOI, lien), jamais le texte intégral.
--enregistrer : chaque référence retenue devient un objet `doctrine` (cerebro new) avec sa source datée.
Usage : python academic.py "<question>" [--n 5] [--sources crossref,semanticscholar,openalex] [--enregistrer]
Sortie JSON {question, resultats:[{titre, auteurs, annee, revue, doi, url, source, consulte_le}], sources:{nom: etat}, repli}"""
import sys, json, argparse, datetime as dt, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from network import obtenir_json, journal, cerebro, utf8_console  # noqa: E402

SOURCES = ("crossref", "semanticscholar", "openalex")


def _auj():
    return dt.date.today().isoformat()


def crossref(q, n=5):
    code, d = obtenir_json("https://api.crossref.org/works", {"query": q, "rows": n,
                                                             "select": "DOI,title,author,issued,container-title,URL,type"})
    if not d:
        return code, []
    out = []
    for it in (d.get("message") or {}).get("items", [])[:n]:
        au = [" ".join(x for x in [a.get("given"), a.get("family")] if x) for a in it.get("author", [])[:4]]
        an = ((it.get("issued") or {}).get("date-parts") or [[None]])[0][0]
        out.append({"titre": (it.get("title") or [""])[0], "auteurs": au, "annee": an, "revue": (it.get("container-title") or [""])[0],
                    "doi": it.get("DOI"), "url": it.get("URL") or (f"https://doi.org/{it['DOI']}" if it.get("DOI") else ""),
                    "type": it.get("type"), "source": "crossref", "consulte_le": _auj()})
    return code, out


def semanticscholar(q, n=5):
    code, d = obtenir_json("https://api.semanticscholar.org/graph/v1/paper/search",
                           {"query": q, "limit": n, "fields": "title,year,authors,venue,externalIds,url"}, essais=2)
    if not d:
        return code, []
    out = []
    for it in d.get("data", [])[:n]:
        doi = (it.get("externalIds") or {}).get("DOI")
        out.append({"titre": it.get("title"), "auteurs": [a.get("name") for a in it.get("authors", [])[:4]], "annee": it.get("year"),
                    "revue": it.get("venue"), "doi": doi, "url": it.get("url") or (f"https://doi.org/{doi}" if doi else ""),
                    "source": "semanticscholar", "consulte_le": _auj()})
    return code, out


def openalex(q, n=5):
    code, d = obtenir_json("https://api.openalex.org/works", {"search": q, "per_page": n}, essais=3)
    if not d:
        return code, []
    out = []
    for it in d.get("results", [])[:n]:
        doi = (it.get("doi") or "").replace("https://doi.org/", "") or None
        out.append({"titre": it.get("display_name"), "auteurs": [a.get("author", {}).get("display_name") for a in it.get("authorships", [])[:4]],
                    "annee": it.get("publication_year"), "revue": ((it.get("primary_location") or {}).get("source") or {}).get("display_name"),
                    "doi": doi, "url": it.get("doi") or it.get("id"), "source": "openalex", "consulte_le": _auj()})
    return code, out


FN = {"crossref": crossref, "semanticscholar": semanticscholar, "openalex": openalex}


def rechercher(q, n=5, sources=SOURCES):
    res, etats, vus = [], {}, set()
    for s in sources:
        try:
            code, r = FN[s](q, n)
        except Exception as e:
            code, r = 0, []
            journal("academique erreur", source=s, erreur=repr(e)[:200])
        etats[s] = "ok" if r else ("limite d'accès (429)" if code == 429 else f"indisponible ({code})" if code else "injoignable")
        for x in r:
            cle = (x.get("doi") or re.sub(r"\W+", "", (x.get("titre") or "").lower())[:80])
            if cle and cle not in vus:
                vus.add(cle)
                res.append(x)
    repli = None
    if not res:
        repli = "aucune base académique joignable : recherche par le navigateur (Playwright) puis journal ; la réponse le dit (⚠ doctrine non vérifiée)"
    journal("academique", question=q[:200], n=len(res), sources=etats)
    return {"question": q, "resultats": res, "sources": etats, "repli": repli}


def enregistrer(resultats, max_n=5):
    ids = []
    for x in resultats[:max_n]:
        nom = (x.get("titre") or "référence")[:110]
        au = ", ".join(a for a in (x.get("auteurs") or []) if a)
        r = cerebro("new", "doctrine", nom, "--resume", f"{au} ({x.get('annee')}) · {x.get('revue') or ''} · DOI {x.get('doi') or '-'} · référence seulement (licence)"[:280],
                    "--source", x.get("url") or "", "--prochaine-action", "lire si utile au dossier", "--date", _auj())
        if isinstance(r, dict) and r.get("id"):
            ids.append(r["id"])
    return ids


def main(argv=None):
    utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question"); ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--sources", default=",".join(SOURCES)); ap.add_argument("--enregistrer", action="store_true")
    a = ap.parse_args(argv)
    out = rechercher(a.question, a.n, [s for s in a.sources.split(",") if s in FN])
    if a.enregistrer and out["resultats"]:
        out["enregistres"] = enregistrer(out["resultats"])
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
