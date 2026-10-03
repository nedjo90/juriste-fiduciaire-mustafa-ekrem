#!/usr/bin/env python3
"""Zefix (registre du commerce) par le jeu de données ouvert LINDAS — sans compte, sans identifiants (§10, §14).

Source principale : endpoint SPARQL public https://lindas.admin.ch/query, graphe <https://lindas.admin.ch/foj/zefix>
(structure découverte par requêtes réelles le 2026-10-03) :
  <register.ld.admin.ch/zefix/company/{EHRAID}> a schema:Organization, :ZefixOrganisation ;
    schema:legalName (raison sociale) ; schema:name (variantes linguistiques) ; schema:description (but) ;
    schema:additionalType <ld.admin.ch/ech/97/legalforms/NNNN> (forme juridique, schema:name) ;
    schema:identifier [schema:name "CompanyUID" ; schema:value "CHE…"] ; schema:address [streetAddress, postalCode,
    addressLocality, addressRegion] ; <schema.ld.admin.ch/municipality> <ld.admin.ch/municipality/N> (commune du siège).
Le jeu LINDAS ne publie pas le statut (inscrite, en liquidation, radiée) : il est complété, quand c'est possible, par la
recherche publique de l'application web zefix.ch (sans identifiants), à défaut marqué ⚠.
Usage : python zefix.py "Nestlé S.A."   ·   python zefix.py --ide CHE-105.909.036   [--limite 10]"""
import argparse, datetime as dt, json, re, sys, time, urllib.parse, urllib.request

LINDAS = "https://lindas.admin.ch/query"
WEB = "https://www.zefix.ch/ZefixREST/api/v1/firm/search.json"
UA = "bibliotheque-fiduciaire/1.0 (usage interne, requetes espacees)"
_t = {"t": 0.0}


def _pause(s=1.0):
    d = time.time() - _t["t"]
    if d < s:
        time.sleep(s - d)
    _t["t"] = time.time()


def sparql(q):
    _pause()
    data = urllib.parse.urlencode({"query": q}).encode()
    req = urllib.request.Request(LINDAS, data=data, headers={"Accept": "application/sparql-results+json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        res = json.load(r)
    return [{k: v["value"] for k, v in b.items()} for b in res["results"]["bindings"]]


def norm_ide(s):
    d = re.sub(r"\D", "", s or "")
    return f"CHE{d}" if len(d) == 9 else None


def fmt_ide(s):
    d = re.sub(r"\D", "", s or "")
    return f"CHE-{d[:3]}.{d[3:6]}.{d[6:]}" if len(d) == 9 else s


def _lit(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _filtre(nom=None, ide=None):
    if ide:
        return f"?s schema:identifier ?idn . ?idn schema:value {_lit(ide)} ."
    return f"?s schema:legalName ?ln . FILTER(CONTAINS(LCASE(?ln), LCASE({_lit(nom)})))"


def chercher(nom=None, ide=None, limite=10, statut=True):
    ide = norm_ide(ide) if ide else None
    if not nom and not ide:
        raise ValueError("nom ou IDE requis")
    q = f"""PREFIX schema: <http://schema.org/>
SELECT ?s ?raison ?but ?forme ?formeNom ?uid ?rue ?npa ?lieu ?canton ?commune WHERE {{
 GRAPH <https://lindas.admin.ch/foj/zefix> {{
  {{ SELECT DISTINCT ?s WHERE {{ {_filtre(nom, ide)} }} LIMIT {int(limite)} }}
  ?s schema:legalName ?raison .
  OPTIONAL {{ ?s schema:description ?but }}
  OPTIONAL {{ ?s schema:additionalType ?forme }}
  OPTIONAL {{ ?s schema:identifier ?i . ?i schema:name "CompanyUID" ; schema:value ?uid }}
  OPTIONAL {{ ?s schema:address ?a . OPTIONAL {{ ?a schema:streetAddress ?rue }} OPTIONAL {{ ?a schema:postalCode ?npa }}
             OPTIONAL {{ ?a schema:addressLocality ?lieu }} OPTIONAL {{ ?a schema:addressRegion ?canton }} }}
 }}
 OPTIONAL {{ ?forme schema:name ?formeNom FILTER(lang(?formeNom)="fr" || lang(?formeNom)="") }}
 OPTIONAL {{ ?s <https://schema.ld.admin.ch/municipality> ?m . ?m schema:name ?commune }}
}}"""
    rows = sparql(q)
    out = {}
    for r in rows:
        e = out.setdefault(r["s"], {"ehraid": r["s"].rsplit("/", 1)[-1], "raison_sociale": r["raison"], "forme": r.get("formeNom"),
                                     "forme_code_ech97": (r.get("forme") or "").rsplit("/", 1)[-1] or None, "ide": fmt_ide(r.get("uid")),
                                     "siege": r.get("commune") or r.get("lieu"), "canton": r.get("canton"),
                                     "adresse": " ".join(x for x in [r.get("rue"), r.get("npa"), r.get("lieu")] if x) or None,
                                     "but": r.get("but"), "uri": r["s"]})
    res = list(out.values())
    if statut:
        for e in res:
            e.update(statut_web(e))
    for e in res:
        if not e.get("statut") or e["statut"].startswith("⚠"):
            if re.search(r"\b(in Liquidation|en liquidation|in liquidazione)\b", e["raison_sociale"], re.I):
                e["statut"] = "en liquidation (d'après la raison sociale) ⚠ à confirmer"
    return {"requete": {"nom": nom, "ide": ide}, "source": "LINDAS SPARQL, graphe foj/zefix (OFRC, données ouvertes)",
            "consulte_le": dt.date.today().isoformat(), "resultats": res}


STATUTS = {"EXISTIEREND": "inscrite", "GELOESCHT": "radiée", "AUFGELOEST": "dissoute (en liquidation)"}


def statut_web(e):
    """statut par la recherche publique de l'application web zefix.ch (sans compte) ; repli ⚠"""
    try:
        _pause()
        corps = json.dumps({"name": e["ide"] or e["raison_sociale"], "languageKey": "fr", "maxEntries": 30, "deletedFirms": True}).encode()
        req = urllib.request.Request(WEB, data=corps, headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            lst = json.load(r).get("list", [])
        for f in lst:
            if str(f.get("ehraid")) == str(e["ehraid"]):
                return {"statut": STATUTS.get(f.get("status"), f.get("status")), "fosc_derniere_publication": f.get("shabDate"),
                        "radiee_le": f.get("deleteDate"), "extrait_cantonal": f.get("cantonalExcerptWeb"), "statut_source": "zefix.ch (application web publique)"}
    except Exception as x:
        return {"statut": f"⚠ non disponible ({type(x).__name__})"}
    return {"statut": "⚠ non disponible (absent de la recherche web)"}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("nom", nargs="?")
    p.add_argument("--ide")
    p.add_argument("--limite", type=int, default=10)
    p.add_argument("--sans-statut", action="store_true")
    a = p.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")  # Windows
        except Exception:
            pass
    try:
        r = chercher(a.nom, a.ide, a.limite, not a.sans_statut)
    except Exception as e:
        r = {"erreur": f"Zefix/LINDAS injoignable : {e!r}", "reserve": "⚠ forme et organes à tirer du registre ; ne rien supposer"}
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return r


if __name__ == "__main__":
    main()
