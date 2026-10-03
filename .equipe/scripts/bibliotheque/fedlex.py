#!/usr/bin/env python3
"""Client Fedlex (§10) : endpoint SPARQL public https://fedlex.data.admin.ch/sparqlendpoint, ontologie JOLux.

Chaîne découverte par requêtes réelles (2026-10-03) :
  numéro RS --skos:notation--> entrée de taxonomie <vocabulary/legal-taxonomy/N>
  ConsolidationAbstract (eli/cc/…) --jolux:classifiedByTaxonomyEntry--> taxonomie ; jolux:inForceStatus <enforcement-status/0> = en vigueur
  Consolidation (eli/cc/…/AAAAMMJJ) --jolux:isMemberOf--> ConsolidationAbstract ; jolux:dateApplicability / dateEndApplicability
  Consolidation --jolux:isRealizedBy--> Expression (…/fr) --jolux:isEmbodiedBy--> Manifestation (…/fr/xml|html|pdf-a|docx)
  Manifestation --jolux:isExemplifiedBy--> URL publique filestore (fichier courant)
  Expression : jolux:title, jolux:titleShort (abréviation propre à la langue) ; typeDocument 21 = loi, 29 = ordonnance.
Le texte (XML Akoma Ntoso de préférence, HTML en repli) est converti en markdown « ## Art. N titre » puis ingéré par
`cerebro law ingest`. Pause entre requêtes, cache local des téléchargements. Source injoignable → incident + file de
rattrapage, jamais d'arrêt. Stdlib seulement (Windows/macOS/Linux).

Usage : python fedlex.py resolve 220 642.11
        python fedlex.py versions 642.11
        python fedlex.py ingest 220 642.11 --langue fr de [--date 2026-10-03]
        python fedlex.py priorites [--niveau 1] [--langue fr]
"""
import argparse, datetime as dt, html, json, os, re, subprocess, sys, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ENDPOINT = "https://fedlex.data.admin.ch/sparqlendpoint"
UA = "bibliotheque-fiduciaire/1.0 (usage interne, requetes espacees)"
PAUSE_SPARQL = 1.0
PAUSE_FICHIER = 2.0
JOLUX = "http://data.legilux.public.lu/resource/ontology/jolux#"
LANGUES = {"fr": "FRA", "de": "DEU", "it": "ITA", "en": "ENG", "rm": "ROH"}
TYPES = {"21": "loi", "29": "ordonnance"}


def racine_equipe():
    r = os.environ.get("CEREBRO_ROOT")
    return Path(r) / ".equipe" if r else Path(__file__).resolve().parents[2]


EQ = racine_equipe()
CACHE = EQ / "bibliotheque" / "cache"
CEREBRO = Path(__file__).resolve().parents[2] / "cerebro" / "cerebro.py"
_dernier = {"t": 0.0}


def _pause(s):
    d = time.time() - _dernier["t"]
    if d < s:
        time.sleep(s - d)
    _dernier["t"] = time.time()


def journal(msg, **kw):
    CACHE.mkdir(parents=True, exist_ok=True)
    with open(CACHE / "journal.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"le": dt.datetime.now().isoformat(timespec="seconds"), "msg": msg, **kw}, ensure_ascii=False) + "\n")


def cerebro(*args, check=False):
    """appelle la CLI cerebro ; renvoie le JSON de sortie (ou {'erreur':…})"""
    r = subprocess.run([sys.executable, str(CEREBRO), *[str(a) for a in args]], capture_output=True, text=True, encoding="utf-8", env=os.environ.copy())
    try:
        return json.loads(r.stdout or "{}")
    except Exception:
        return {"erreur": (r.stdout or r.stderr or "").strip()[:500]}


# ------------------------------------------------------------------ SPARQL
def sparql(q, essais=3):
    data = urllib.parse.urlencode({"query": q}).encode()
    err = None
    for i in range(essais):
        _pause(PAUSE_SPARQL)
        try:
            req = urllib.request.Request(ENDPOINT, data=data, headers={"Accept": "application/sparql-results+json", "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=90) as r:
                res = json.load(r)
            return [{k: v["value"] for k, v in b.items()} for b in res["results"]["bindings"]]
        except Exception as e:
            err = e
            time.sleep(3 * (i + 1))
    raise ConnectionError(f"SPARQL Fedlex injoignable: {err!r}")


PFX = "PREFIX jolux: <%s>\nPREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n" % JOLUX


def resoudre(rs):
    """numéro RS → acte consolidé en vigueur (URI ELI cc), titre officiel, abréviation et type, par langue"""
    q = PFX + f"""SELECT DISTINCT ?ca ?st ?type ?lang ?titre ?abrev WHERE {{
 ?tax skos:notation ?n . FILTER(STR(?n)="{rs}")
 ?ca jolux:classifiedByTaxonomyEntry ?tax ; a jolux:ConsolidationAbstract .
 OPTIONAL {{ ?ca jolux:inForceStatus ?st }} OPTIONAL {{ ?ca jolux:typeDocument ?type }}
 OPTIONAL {{ ?ca jolux:isRealizedBy ?e . ?e jolux:language ?lang ; jolux:title ?titre . OPTIONAL {{ ?e jolux:titleShort ?abrev }} }}
}}"""
    rows = sparql(q)
    actes = {}
    for r in rows:
        a = actes.setdefault(r["ca"], {"rs": rs, "eli": r["ca"], "en_vigueur": r.get("st", "").endswith("/0"),
                                        "type": TYPES.get(r.get("type", "").rsplit("/", 1)[-1], "autre"), "titres": {}, "abrevs": {}})
        lg = {v: k for k, v in LANGUES.items()}.get(r.get("lang", "").rsplit("/", 1)[-1])
        if lg:
            a["titres"][lg] = r["titre"].strip()
            if r.get("abrev"):
                a["abrevs"][lg] = r["abrev"].strip()
    for a in actes.values():
        if a["type"] == "autre":  # ex. ordonnances d'autorités (FINMA) : type déduit du titre officiel
            a["type"] = "ordonnance" if (a["titres"].get("fr") or "").startswith("Ordonnance") else "loi"
    en = [a for a in actes.values() if a["en_vigueur"]]
    if not en:
        return None
    return en[0] if len(en) == 1 else sorted(en, key=lambda a: len(a["titres"]), reverse=True)[0]


def consolidations(eli):
    q = PFX + f"""SELECT DISTINCT ?c ?d ?f WHERE {{ ?c jolux:isMemberOf <{eli}> ; a jolux:Consolidation ; jolux:dateApplicability ?d .
 OPTIONAL {{ ?c jolux:dateEndApplicability ?f }} }} ORDER BY DESC(?d)"""
    return [{"uri": r["c"], "du": r["d"][:10], "au": (r.get("f") or "")[:10] or None} for r in sparql(q)]


def consolidation_a(eli, date=None):
    """dernière version consolidée en vigueur à la date (défaut : aujourd'hui)"""
    date = date or dt.date.today().isoformat()
    for c in consolidations(eli):
        if c["du"] <= date and (not c["au"] or c["au"] >= date):
            return c
    return None


def manifestations(cons_uri, langue="fr"):
    q = PFX + f"""SELECT DISTINCT ?m ?fmt ?url WHERE {{ <{cons_uri}> jolux:isRealizedBy ?e . ?e jolux:language <http://publications.europa.eu/resource/authority/language/{LANGUES[langue]}> .
 ?e jolux:isEmbodiedBy ?m . ?m jolux:userFormat ?fmt ; jolux:isExemplifiedBy ?url }}"""
    return {r["fmt"].rsplit("/", 1)[-1]: r["url"] for r in sparql(q)}


# ------------------------------------------------------------------ téléchargement (cache)
def telecharger(url):
    CACHE.mkdir(parents=True, exist_ok=True)
    nom = re.sub(r"[^A-Za-z0-9._-]", "_", url.rsplit("/", 1)[-1])[-150:]
    p = CACHE / nom
    if p.exists() and p.stat().st_size > 0:
        return p, True
    _pause(PAUSE_FICHIER)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = r.read()
    p.write_bytes(data)
    return p, False


# ------------------------------------------------------------------ Akoma Ntoso → markdown
AKN = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}"
FED = "{http://fedlex.admin.ch/}"
STRUCT = {"book", "part", "title", "subtitle", "chapter", "subchapter", "section", "subsection", "division", "level", "hcontainer"}


def _l(el):
    return el.tag.replace(AKN, "") if isinstance(el.tag, str) else ""


def _txt(el, notes=None, skip=("authorialNote",)):
    """texte à plat d'un élément ; les notes de bas de page sont retirées (et collectées)"""
    parts = []

    def rec(e):
        t = _l(e)
        if t in skip:
            if notes is not None:
                n = re.sub(r"\s+", " ", "".join(e.itertext())).strip()
                if n:
                    notes.append(n)
            if e.tail:
                parts.append(e.tail)
            return
        if t in ("br", "p", "td", "th", "item"):
            parts.append(" ")
        if e.text:
            parts.append(e.text)
        for c in e:
            rec(c)
        if e.tail:
            parts.append(e.tail)

    if el.text:
        parts.append(el.text)
    for c in el:
        rec(c)
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _bloc(el, notes, prof=0):
    """contenu d'article : alinéas, listes (lettres, chiffres), tableaux → lignes markdown"""
    out = []
    ind = "  " * prof
    for c in el:
        t = _l(c)
        if t in ("num", "heading", "authorialNote", "subheading"):
            if t == "authorialNote":
                notes.append(re.sub(r"\s+", " ", "".join(c.itertext())).strip())
            continue
        if t == "paragraph":
            num = c.find(AKN + "num")
            n = _txt(num, notes) if num is not None else ""
            sous = _bloc(c, notes, prof)
            if sous:
                sous[0] = f"{ind}{n} {sous[0].lstrip()}".rstrip() if n else sous[0]
            out += sous + [""]
        elif t in ("content", "intro", "wrapUp", "alinea", "subparagraph", "list", "point", "indent"):
            out += _bloc(c, notes, prof)
        elif t == "blockList":
            out += _bloc(c, notes, prof)
        elif t in ("listIntroduction", "listWrapUp", "p"):
            s = _txt(c, notes)
            if s:
                out.append(ind + s)
        elif t == "item":
            num = c.find(AKN + "num")
            n = _txt(num, notes) if num is not None else "-"
            sous = _bloc(c, notes, prof + 1)
            first = sous[0].strip() if sous else ""
            out.append(f"{ind}- {n} {first}".rstrip())
            out += sous[1:]
        elif t == "table":
            for tr in c.iter(AKN + "tr"):
                cells = [_txt(td, notes) for td in tr if _l(td) in ("td", "th")]
                out.append(ind + "| " + " | ".join(cells) + " |")
            out.append("")
        elif t in ("article",):
            out += _article(c, notes, "")
        else:
            s = _txt(c, notes)
            if s:
                out.append(ind + s)
    return out


def _article(a, notes_globales, titre_marge):
    notes = []
    num = a.find(AKN + "num")
    n = _txt(num, notes) if num is not None else ""
    h = a.find(AKN + "heading")
    titre = _txt(h, notes) if h is not None else titre_marge
    n = re.sub(r"^Art\.?\s*", "Art. ", n.replace(" ", " ")) if n else f"Art. {a.get('eId', '?')}"
    corps = _bloc(a, notes)
    if not any(l.strip() and l.strip() != "…" for l in corps) and notes:
        corps = [f"[Note officielle] {x}" for x in notes]  # article abrogé ou vide : la note dit pourquoi
        notes = []
    lignes = [f"## {n} {titre}".rstrip(), ""] + [l for i, l in enumerate(corps) if l.strip() or (i and corps[i - 1].strip())]
    if notes:
        notes_globales.append((n, notes))
    return lignes + [""]


def akn_vers_markdown(xml_bytes):
    root = ET.fromstring(xml_bytes)
    meta = {}
    for fn in root.iter(AKN + "FRBRname"):
        meta.setdefault("titres", {})[fn.get("{http://www.w3.org/XML/1998/namespace}lang")] = (fn.get("value"), fn.get("shortForm"))
    for fd in root.iter(AKN + "FRBRdate"):
        meta[fd.get("name")] = fd.get("date")
    num = root.find(f".//{AKN}FRBRnumber")
    meta["rs"] = num.get("value") if num is not None else ""
    out, notes = [], []
    corps = root.find(f".//{AKN}body")
    marge = []

    def visite(el):
        for c in el:
            t = _l(c)
            if t == "article":
                tm = marge[-1] if marge else ""
                out.extend(_article(c, notes, tm))
            elif t in STRUCT:
                n = c.find(AKN + "num")
                h = c.find(AKN + "heading")
                lib = " ".join(x for x in [_txt(n, []) if n is not None else "", _txt(h, []) if h is not None else ""] if x).strip()
                if c.get(FED + "role") == "marginal":
                    marge.append(lib)
                    visite(c)
                    marge.pop()
                else:
                    if lib:
                        out.extend([f"### {lib}", ""])  # niveau de structure (titre, chapitre…), jamais confondu avec un article
                    visite(c)
            elif t in ("num", "heading", "authorialNote"):
                continue
            else:
                visite(c)

    if corps is not None:
        visite(corps)
    pre = root.find(f".//{AKN}preamble")
    if pre is not None:
        p = _txt(pre, [])
        if p:
            out = ["## Préambule", "", p, ""] + out
    for att in root.iter(AKN + "attachment"):
        titre = ""
        for e in att.iter():
            if _l(e) in ("docTitle", "heading"):
                titre = _txt(e, [])
                break
        out += [f"## Annexe {titre}".strip(), ""] + [l for l in _bloc_texte(att)] + [""]
    if notes:
        out += ["## Notes de bas de page", ""]
        for n, ns in notes:
            for i, x in enumerate(ns, 1):
                out.append(f"- {n} [{i}] {x}")
        out.append("")
    md = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"
    return md, meta


def _bloc_texte(el):
    lignes = []
    for e in el.iter():
        t = _l(e)
        if t in ("p", "heading", "listIntroduction"):
            s = _txt(e, None)
            if s:
                lignes.append(s)
        elif t == "tr":
            lignes.append("| " + " | ".join(_txt(td, None) for td in e if _l(td) in ("td", "th")) + " |")
    return lignes


# ------------------------------------------------------------------ HTML (repli)
def html_vers_markdown(h):
    """repli pour les consolidations sans XML : articles <article id="art_N"> du HTML Fedlex"""
    h = h.decode("utf-8", "replace") if isinstance(h, bytes) else h
    h = re.sub(r'<div class="footnotes">.*', "", h, flags=re.S)
    h = re.sub(r"<sup[^>]*>\s*<a[^>]*fn[^>]*>.*?</a>\s*</sup>", "", h, flags=re.S)
    out = []
    for m in re.finditer(r'<article id="(art_[^"]+)"[^>]*>(.*?)</article>', h, flags=re.S):
        body = m.group(2)
        tit = re.search(r"<h6[^>]*>(.*?)</h6>", body, flags=re.S)
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", tit.group(1)))).strip() if tit else m.group(1)
        if tit:
            body = body.replace(tit.group(0), "")
        txt = re.sub(r"</p>|<br\s*/?>|</dd>|</dt>", "\n", body)
        txt = html.unescape(re.sub(r"<[^>]+>", "", txt))
        lignes = [re.sub(r"\s+", " ", l).strip() for l in txt.splitlines()]
        t = re.sub(r"^Art\.?\s*", "Art. ", t)
        out += [f"## {t}", ""] + [l for l in lignes if l] + [""]
    return "\n".join(out)


# ------------------------------------------------------------------ ingestion
def incident(rs, langue, err):
    desc = f"Fedlex : ingestion RS {rs} ({langue}) impossible : {str(err)[:200]}"
    cerebro("incident", "add", desc, "--categorie", "source", "--repli", "file de rattrapage bibliotheque_rattrapage, nouvel essai au cycle suivant")
    cerebro("queue", "add", "bibliotheque_rattrapage", rs, "--priorite", "5")
    journal("incident", rs=rs, langue=langue, erreur=str(err)[:300])


def preparer(rs, langue="fr", date=None, abrev=None, acte=None):
    """résout, télécharge et convertit ; renvoie (chemin_md, métadonnées) sans ingérer"""
    acte = acte or resoudre(rs)
    if not acte:
        raise LookupError(f"RS {rs} : aucun acte consolidé en vigueur trouvé par SPARQL")
    cons = consolidation_a(acte["eli"], date)
    if not cons:
        raise LookupError(f"RS {rs} : aucune consolidation en vigueur au {date or 'jour'}")
    mans = manifestations(cons["uri"], langue)
    url, fmt = (mans.get("xml"), "xml") if mans.get("xml") else (mans.get("html"), "html")
    if not url:
        raise LookupError(f"RS {rs} ({langue}) : ni XML ni HTML pour {cons['uri']} (formats: {sorted(mans)})")
    p, cache = telecharger(url)
    data = p.read_bytes()
    if fmt == "xml":
        md, meta = akn_vers_markdown(data)
    else:
        md, meta = html_vers_markdown(data), {}
    nb = len(re.findall(r"^## Art\. ", md, flags=re.M))
    if nb == 0:
        raise ValueError(f"RS {rs} ({langue}) : aucun article extrait de {url}")
    titre = acte["titres"].get(langue) or acte["titres"].get("fr") or rs
    ab = abrev or acte["abrevs"].get(langue) or acte["abrevs"].get("fr") or ""
    v = cons["du"]
    mdp = CACHE / "md" / f"{rs}-{langue}-{v}.md"
    mdp.parent.mkdir(parents=True, exist_ok=True)
    mdp.write_text(md, encoding="utf-8")
    return mdp, {"rs": rs, "langue": langue, "eli": acte["eli"], "consolidation": cons["uri"], "version": v, "fin": cons["au"],
                 "url": url, "format": fmt, "titre": titre, "abrev": ab, "type": acte["type"], "articles": nb, "cache": cache,
                 "octets_source": len(data), "octets_md": mdp.stat().st_size}


def ingerer(rs, langue="fr", date=None, abrev=None, acte=None):
    """chaîne complète ; jamais d'exception vers l'appelant : un échec devient incident + rattrapage"""
    t0 = time.time()
    try:
        mdp, m = preparer(rs, langue, date, abrev, acte)
        date_etat = m["version"]
        res = cerebro("law", "ingest", rs, "--fichier", mdp, "--juridiction", "CH", "--type", m["type"] if m["type"] in ("loi", "ordonnance") else "loi",
                      "--titre", m["titre"], "--langue", langue, "--version", m["version"], "--date-etat", date_etat, "--url", m["url"], "--abrev", m["abrev"])
        if "erreur" in res:
            raise RuntimeError(res["erreur"])
        m.update(res)
        m["duree_s"] = round(time.time() - t0, 1)
        journal("ingéré", **{k: m[k] for k in ("rs", "langue", "version", "articles", "duree_s")}, statut=res.get("statut"))
        return m
    except Exception as e:
        incident(rs, langue, e)
        return {"rs": rs, "langue": langue, "erreur": str(e)[:300], "duree_s": round(time.time() - t0, 1)}


def charger_priorites():
    import yaml
    return yaml.safe_load((Path(__file__).parent / "priorites.yaml").read_text(encoding="utf-8"))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("action", choices=["resolve", "versions", "ingest", "priorites", "preparer"])
    p.add_argument("rs", nargs="*")
    p.add_argument("--langue", nargs="*", default=["fr"])
    p.add_argument("--date")
    p.add_argument("--niveau", type=int, default=9, help="priorites : ingérer jusqu'à ce niveau")
    a = p.parse_args(argv)
    out = []
    if a.action == "resolve":
        for rs in a.rs:
            try:
                out.append(resoudre(rs) or {"rs": rs, "erreur": "introuvable"})
            except Exception as e:
                out.append({"rs": rs, "erreur": str(e)})
    elif a.action == "versions":
        for rs in a.rs:
            ac = resoudre(rs)
            out.append({"rs": rs, "eli": ac and ac["eli"], "consolidations": consolidations(ac["eli"])[:15] if ac else []})
    elif a.action == "preparer":
        for rs in a.rs:
            for lg in a.langue:
                out.append(preparer(rs, lg, a.date)[1])
    elif a.action == "ingest":
        for rs in a.rs:
            for lg in a.langue:
                out.append(ingerer(rs, lg, a.date))
    else:
        pr = charger_priorites()
        for t in pr["textes"]:
            if t.get("niveau", 9) > a.niveau:
                continue
            for lg in t.get("langues", a.langue):
                if lg in a.langue or a.langue == ["toutes"]:
                    out.append(ingerer(t["rs"], lg, a.date, t.get("abrev") if lg == "fr" else t.get(f"abrev_{lg}")))
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
