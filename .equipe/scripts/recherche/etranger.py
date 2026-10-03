#!/usr/bin/env python3
"""Sources étrangères officielles (§6.1 droit étranger, §6.4, §10 liste blanche) — API publiques, stdlib.
- Royaume-Uni : legislation.gov.uk — recherche (flux Atom /search/data.feed) et texte d'une disposition
  (/<type>/<année>/<n>[/section/<s>]/data.xml, CLML) → markdown « ## Section N … ».
- États-Unis : CourtListener API REST v4 (/api/rest/v4/search/?type=o) ; jeton facultatif COURTLISTENER_TOKEN
  (sans jeton, quota anonyme partagé : 429 → repli propre).
- Union européenne : EUR-Lex via le CELLAR de l'Office des publications — SPARQL public (titre officiel par CELEX et
  langue) et texte XHTML par négociation de contenu (/resource/celex/<CELEX>) ; le site eur-lex.europa.eu oppose un
  contrôle anti-robot (202) : non utilisé.
--ingerer : le texte récupéré est ingéré le jour même (cerebro law ingest, juridiction UK|EU, §9.5).
Usage : python etranger.py uk-recherche "companies act"        python etranger.py uk ukpga/2006/46/section/1 [--ingerer]
        python etranger.py us "fiduciary duty trust" [--n 5]     python etranger.py eu 32016R0679 [--langue fr] [--ingerer]"""
import sys, re, json, argparse, datetime as dt, html as H
import xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from reseau import obtenir, obtenir_json, journal, cerebro, utf8_console, EQ  # noqa: E402

import os
LANGUES_EU = {"fr": "FRA", "de": "DEU", "it": "ITA", "en": "ENG"}
ATOM = {"a": "http://www.w3.org/2005/Atom"}


def _auj():
    return dt.date.today().isoformat()


def _cache(nom, data):
    p = EQ / "bibliotheque" / "cache" / "etranger" / nom
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


# ------------------------------------------------------------------ Royaume-Uni
def uk_recherche(q, n=5):
    code, data, _ = obtenir("https://www.legislation.gov.uk/search/data.feed", {"text": q, "results-count": n})
    if code != 200:
        return {"source": "legislation.gov.uk", "etat": f"indisponible ({code})", "resultats": []}
    out = []
    try:
        root = ET.fromstring(data)
        for e in root.findall("a:entry", ATOM)[:n]:
            lien = next((l.get("href") for l in e.findall("a:link", ATOM) if l.get("rel") in (None, "self", "alternate")), "")
            out.append({"titre": (e.findtext("a:title", "", ATOM) or "").strip(), "id": (e.findtext("a:id", "", ATOM) or "").strip(),
                        "url": lien, "maj": e.findtext("a:updated", "", ATOM), "consulte_le": _auj()})
    except Exception as ex:
        journal("uk recherche analyse", erreur=repr(ex)[:200])
    return {"source": "legislation.gov.uk", "etat": "ok", "resultats": out}


def _txt(el):
    t = re.sub(r"\s+", " ", " ".join(el.itertext())).strip()
    return re.sub(r"\s+([,.;:)\]’”])", r"\1", t)


def uk_texte(ref):
    """ref = ukpga/2006/46[/section/1] → (markdown, méta) ou (None, méta d'erreur)"""
    ref = ref.strip("/").replace("https://www.legislation.gov.uk/", "")
    url = f"https://www.legislation.gov.uk/{ref}/data.xml"
    code, data, _ = obtenir(url, timeout=90)
    if code != 200:
        return None, {"url": url, "etat": f"indisponible ({code})"}
    _cache(re.sub(r"\W+", "_", ref) + ".xml", data)
    root = ET.fromstring(data)
    loc = lambda t: t.split("}")[-1]
    titre = next((_txt(e) for e in root.iter() if loc(e.tag) == "title"), ref)
    valide = next((e.get("RestrictStartDate") or e.get("RestrictEndDate") for e in root.iter() if e.get("RestrictStartDate")), None)
    md = []
    for p1 in (e for e in root.iter() if loc(e.tag) == "P1"):
        num = next((_txt(c) for c in p1 if loc(c.tag) == "Pnumber"), "")
        corps = _txt(p1)
        if num:
            corps = corps[len(num):].strip() if corps.startswith(num) else corps
            md.append(f"## Section {num}\n\n{corps}\n")
    if not md:
        md.append(f"## Texte\n\n{_txt(root)[:20000]}\n")
    return "\n".join(md), {"url": f"https://www.legislation.gov.uk/{ref}", "titre": titre, "etat_du": valide or _auj(), "etat": "ok"}


# ------------------------------------------------------------------ États-Unis
def us_jurisprudence(q, n=5):
    ent = {"Authorization": f"Token {os.environ['COURTLISTENER_TOKEN']}"} if os.environ.get("COURTLISTENER_TOKEN") else {}
    code, d = obtenir_json("https://www.courtlistener.com/api/rest/v4/search/", {"q": q, "type": "o"}, ent, essais=2)
    if not d:
        etat = "quota anonyme atteint (429) : jeton COURTLISTENER_TOKEN conseillé" if code == 429 else f"indisponible ({code})"
        return {"source": "CourtListener", "etat": etat, "resultats": [],
                "repli": "recherche par le navigateur sur courtlistener.com, puis journal"}
    out = []
    for r in d.get("results", [])[:n]:
        out.append({"titre": r.get("caseName"), "juridiction": r.get("court"), "date": r.get("dateFiled"), "citation": r.get("citation"),
                    "url": "https://www.courtlistener.com" + (r.get("absolute_url") or ""), "consulte_le": _auj()})
    return {"source": "CourtListener", "etat": "ok", "resultats": out}


# ------------------------------------------------------------------ Union européenne
def eu_titre(celex, langue="fr"):
    q = ("PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> SELECT ?t ?d WHERE { ?w cdm:resource_legal_id_celex "
         f"\"{celex}\"^^<http://www.w3.org/2001/XMLSchema#string> . OPTIONAL {{ ?w cdm:work_date_document ?d }} "
         "?e cdm:expression_belongs_to_work ?w ; cdm:expression_title ?t ; cdm:expression_uses_language "
         f"<http://publications.europa.eu/resource/authority/language/{LANGUES_EU.get(langue, 'FRA')}> . }} LIMIT 1")
    code, d = obtenir_json("https://publications.europa.eu/webapi/rdf/sparql", {"query": q},
                           {"Accept": "application/sparql-results+json"})
    b = ((d or {}).get("results") or {}).get("bindings") or []
    return ({"titre": b[0]["t"]["value"], "date": (b[0].get("d") or {}).get("value")} if b else None), code


def eu_texte(celex, langue="fr"):
    meta, code = eu_titre(celex, langue)
    url = f"https://publications.europa.eu/resource/celex/{celex}"
    code, data, typ = obtenir(url, entetes={"Accept": "application/xhtml+xml, text/html;q=0.9",
                                            "Accept-Language": LANGUES_EU.get(langue, "FRA").lower()}, timeout=120)
    if code != 200 or not data:
        return None, {"url": url, "etat": f"indisponible ({code})", **(meta or {})}
    _cache(f"{celex}-{langue}.xhtml", data)
    h = data.decode("utf-8", "replace")
    h = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", h, flags=re.S)
    h = re.sub(r"</(p|div|tr|h\d|li)>", "\n", h)
    t = H.unescape(re.sub(r"<[^>]+>", " ", h))
    lignes = [re.sub(r"[ \t\xa0]+", " ", l).strip() for l in t.split("\n")]
    md, cur = [], None
    for l in lignes:
        if not l:
            continue
        m = re.match(r"^(Article|Artikel|Articolo)\s+(\d+[a-z]*|premier|primo|1er)\s*$", l)
        if m:
            num = "1" if m.group(2) in ("premier", "primo", "1er") else m.group(2)
            cur = [f"## Art. {num}"]
            md.append(cur)
            continue
        if cur is not None:
            if len(cur) == 1 and len(l) < 120 and not l.endswith("."):
                cur[0] += " " + l   # intitulé de l'article
            else:
                cur.append(l)
    texte = "\n\n".join("\n\n".join(a) for a in md) if md else "## Texte\n\n" + "\n\n".join(x for x in lignes if x)[:200000]
    return texte, {"url": f"https://eur-lex.europa.eu/legal-content/{langue.upper()}/TXT/?uri=CELEX:{celex}", "etat": "ok",
                   "titre": (meta or {}).get("titre") or celex, "etat_du": (meta or {}).get("date") or _auj(), "articles": len(md)}


def ingerer(md, juridiction, identifiant, meta, langue, abrev=""):
    nom = re.sub(r"\W+", "_", identifiant)
    p = EQ / "bibliotheque" / "cache" / "etranger" / f"{nom}-{langue}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(md, encoding="utf-8")
    return cerebro("law", "ingest", identifiant, "--fichier", p, "--juridiction", juridiction, "--type", "loi", "--titre", meta.get("titre") or identifiant,
                   "--langue", langue, "--version", meta.get("etat_du") or _auj(), "--date-etat", meta.get("etat_du") or _auj(),
                   "--url", meta.get("url") or "", "--abrev", abrev)


def main(argv=None):
    utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["uk-recherche", "uk", "us", "eu"]); ap.add_argument("arg")
    ap.add_argument("--n", type=int, default=5); ap.add_argument("--langue", default="fr"); ap.add_argument("--ingerer", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.action == "uk-recherche":
            out = uk_recherche(a.arg, a.n)
        elif a.action == "us":
            out = us_jurisprudence(a.arg, a.n)
        elif a.action == "uk":
            md, meta = uk_texte(a.arg)
            out = {**meta, "sections": md.count("## ") if md else 0, "extrait": (md or "")[:600]}
            if md and a.ingerer:
                out["ingestion"] = ingerer(md, "UK", a.arg, meta, "en")
        else:
            md, meta = eu_texte(a.arg, a.langue)
            out = {**meta, "extrait": (md or "")[:600]}
            if md and a.ingerer:
                out["ingestion"] = ingerer(md, "EU", f"CELEX {a.arg}", meta, a.langue)
    except Exception as e:
        journal("etranger erreur", action=a.action, erreur=repr(e)[:300])
        out = {"etat": "erreur", "erreur": repr(e)[:300], "repli": "source consultée par le navigateur, puis journal"}
    journal("etranger", action=a.action, arg=a.arg[:120], etat=out.get("etat"))
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
