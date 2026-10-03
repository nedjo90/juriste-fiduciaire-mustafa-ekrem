#!/usr/bin/env python3
"""Bibliothèque cantonale (§10, §14) : ingestion des lois des cantons suivis depuis les recueils officiels, puis
vérification des règles de délai cantonales contre le texte ingéré.

Sources (lues par requêtes réelles le 2026-10-03, stdlib seulement, pause entre requêtes) :
- VD, Base législative vaudoise (BLV) : api/recueil-systematique?code=<volume> → atelierId de l'acte (cote) ;
  api/actes/CONSOLIDE?id=<atelierId>&cote=<cote> → versions (versionType ACTUELLE, versionDateMiseEnVigueur) ;
  api/actes/<htmlId>/html → texte Akoma Ntoso rendu (div.akn-article-container, td.akn-num, div.akn-heading, akn-alinea).
- GE, recueil systématique genevois (silgeneve.ch) : page HTML statique par texte (export Word, windows-1252) ;
  « Dernières modifications au … » = état ; p.article = article ; tableau historique ignoré.
Chaque texte devient un markdown « ## Art. N Titre » puis `cerebro law ingest <identifiant> --juridiction VD|GE --abrev …`.
Les cantons suivis viennent de `mustafa.cantons_suivis` (défaut VD, GE) ; textes et règles : cantons.yaml (section
`ingestion` et `regles`). Source injoignable → incident + file de rattrapage (`bibliotheque_cantons`), jamais d'arrêt.
Usage : python cantons.py ingerer [--canton VD] [--texte LI-VD] [--force]
        python cantons.py verifier            (cerebro law verify, puis juridiction des règles cantonales)
        python cantons.py liste"""
import argparse, datetime as dt, html, json, re, sys, time, urllib.request
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fedlex import CACHE, cerebro, journal, utf8_console, UA  # noqa: E402

YAML = Path(__file__).parent / "cantons.yaml"
BLV = "https://prestations.vd.ch/pub/blv-publication/"
PAUSE = 1.5
MOIS = {m: i for i, m in enumerate(["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre",
                                    "octobre", "novembre", "décembre"], 1)}
_dernier = [0.0]


def charger_yaml():
    import yaml
    return yaml.safe_load(YAML.read_text(encoding="utf-8")) or {}


def cantons_suivis():
    r = cerebro("config", "get", "mustafa.cantons_suivis")
    v = r.get("valeur") if isinstance(r, dict) else None
    return [str(x).upper() for x in (v or ["VD", "GE"])]


def http(url, timeout=120):
    d = time.time() - _dernier[0]
    if d < PAUSE:
        time.sleep(PAUSE - d)
    _dernier[0] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _cache(nom, data):
    p = CACHE / "cantons" / nom
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def _nett(s):
    return re.sub(r"[ \t\xa0 ]+", " ", s or "").strip()


def _paragraphes(lignes):
    """fusionne « 1 » / « a. » isolés avec la ligne suivante ; paragraphes séparés par une ligne vide"""
    out, attente = [], ""
    for l in (_nett(x) for x in lignes):
        if not l:
            continue
        if re.fullmatch(r"(\d+[a-z]?|[a-z]\.|[a-z]\)|\d+\.|[ivx]+\.)", l):
            attente = (attente + " " + l).strip()
            continue
        out.append((attente + " " + l).strip() if attente else l)
        attente = ""
    return "\n\n".join(out)


# ------------------------------------------------------------------ VD (BLV)
SAUTER = ("akn-modifiants-container", "akn-modifiant-number", "akn-commentaire-link", "akn-commentaires", "akn-collapsible-icon",
          "akn-chapter-container", "akn-section-container", "akn-title-container", "akn-part-container")
VIDES = ("br", "meta", "img", "link", "input", "hr", "col")


class _BLV(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pile, self.saut, self.arts, self.cur, self.zone = [], 0, [], None, None

    def handle_starttag(self, tag, attrs):
        if tag in VIDES:
            if tag == "br":
                self._t("\n")
            return
        cl = (dict(attrs).get("class") or "").split()
        s = self.saut > 0 or tag in ("script", "style") or any(c in SAUTER for c in cl)
        self.pile.append((tag, s, cl))
        if s:
            self.saut += 1
            return
        if "akn-article-container" in cl:
            self.cur = {"num": "", "titre": "", "corps": []}
            self.arts.append(self.cur)
            self.zone = "tete"
        elif "akn-num" in cl and self.zone == "tete":
            self.zone = "num"
        elif "akn-heading" in cl and self.zone in ("tete", "num"):
            self.zone = "titre"
        elif tag in ("p", "li") or any(c in ("akn-alinea", "akn-point", "akn-list") for c in cl):
            self._t("\n")

    def handle_endtag(self, tag):
        if tag in VIDES:
            return
        while self.pile:
            t, s, cl = self.pile.pop()
            if s:
                self.saut -= 1
            else:
                if "akn-article-container" in cl:
                    self.zone = "corps"
                elif "akn-num" in cl and self.zone == "num":
                    self.zone = "tete"
                elif "akn-heading" in cl and self.zone == "titre":
                    self.zone = "tete"
                elif t in ("p", "div", "li", "tr", "td"):
                    self._t("\n")
            if t == tag:
                break

    def _t(self, s):
        if self.cur is None:
            return
        if self.zone == "num":
            self.cur["num"] += s
        elif self.zone == "titre":
            self.cur["titre"] += s
        elif self.zone == "corps":
            self.cur["corps"].append(s)

    def handle_data(self, d):
        if not self.saut:
            self._t(d)


def blv_html_vers_markdown(h):
    p = _BLV()
    p.feed(h)
    md = []
    for a in p.arts:
        num = _nett(a["num"])
        if not re.match(r"Art\.\s*\d", num):
            continue
        corps = _paragraphes("".join(a["corps"]).split("\n"))
        md.append(f"## {num} {_nett(a['titre'])}".rstrip() + "\n\n" + (corps or "(abrogé ou sans texte)") + "\n")
    return "\n".join(md)


def _chercher_acte(noeuds, cote):
    for n in noeuds or []:
        if n.get("code") == cote and n.get("typeElement") == "ACTE":
            return n
        r = _chercher_acte(n.get("children"), cote)
        if r:
            return r
    return None


def preparer_vd(t):
    vol = t["cote"].split(".")[0][:1]
    arbre = json.loads(http(f"{BLV}api/recueil-systematique?code={vol}"))
    acte = _chercher_acte(arbre, t["cote"])
    if not acte:
        raise LookupError(f"BLV {t['cote']} absent du recueil systématique")
    aid = acte.get("atelierId") or acte.get("id")
    versions = json.loads(http(f"{BLV}api/actes/CONSOLIDE?id={aid}&cote={t['cote']}"))
    v = next((x for x in versions if x.get("versionType") == "ACTUELLE"), None) or versions[0]
    d = v.get("versionDateMiseEnVigueur") or v.get("dateMiseEnVigueur")
    date_etat = dt.datetime.strptime(d, "%d.%m.%Y").date().isoformat()
    brut = http(f"{BLV}api/actes/{v['htmlId']}/html", timeout=240)
    _cache(f"VD-{t['cote']}-{date_etat}.html", brut)
    md = blv_html_vers_markdown(brut.decode("utf-8", "replace"))
    url = f"{BLV}actes/consolide/{t['cote']}?id={aid}"
    titre = t.get("titre") or acte.get("libelle")
    return md, {"date_etat": date_etat, "url": url, "titre": titre, "version_html": v["htmlId"], "statut_acte": v.get("statut")}


# ------------------------------------------------------------------ GE (silgeneve)
def _texte_p(s):
    s = re.sub(r'<a\s[^>]*#FN\d+[^>]*>\s*\(\d+\)\s*</a>', "", s, flags=re.I)
    s = re.sub(r"<sup>\s*(?:<span[^>]*>)?\s*(\d+[a-z]?)\s*(?:</span>)?\s*</sup>", r" \1 ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def silgeneve_html_vers_markdown(h):
    fin = re.search(r"<p class=(?:Tteteadopt|Tteteintit|TIntit)", h)
    corps = h[:fin.start()] if fin else h
    md, cur = [], None
    for m in re.finditer(r"<p class=([A-Za-z0-9]+)[^>]*>(.*?)</p>", corps, flags=re.S | re.I):
        cl, t = m.group(1).lower(), _texte_p(m.group(2))
        if cl == "article":
            mm = re.match(r"Art\.\s*(\d+[A-Za-z]*)\s*(.*)", t)
            if mm:
                cur = {"num": mm.group(1), "titre": mm.group(2).strip(), "corps": []}
                md.append(cur)
            continue
        if cl in ("chapitre", "section", "titre", "partie", "soustitre", "retour1", "retour2", "sousnote", "ligne") or cur is None:
            if cl in ("chapitre", "section", "titre", "partie"):
                cur = None  # titre de structure : l'article précédent est clos
            continue
        if t:
            cur["corps"].append(t)
    out = []
    for a in md:
        out.append(f"## Art. {a['num']} {a['titre']}".rstrip() + "\n\n" + ("\n\n".join(a["corps"]) or "(abrogé ou sans texte)") + "\n")
    return "\n".join(out)


def preparer_ge(t):
    brut = http(t["url"])
    h = brut.decode("cp1252", "replace")
    m = re.search(r"Derni[èe]res\s+modifications\s+au\s*(?:<[^>]+>|\s)*(\d{1,2})\s*(?:<sup>)?(?:er)?(?:</sup>)?\s*([a-zéû]+)\s+(\d{4})", h, re.I)
    if m:
        date_etat = dt.date(int(m.group(3)), MOIS[m.group(2).lower()], int(m.group(1))).isoformat()
    else:  # état introuvable : date de lecture, signalée
        date_etat = dt.date.today().isoformat()
        journal("cantons", msg="état du droit introuvable dans la page : date de lecture retenue", url=t["url"])
    _cache(f"GE-{t['cote'].replace(' ', '_')}-{date_etat}.htm", brut)
    titre = t.get("titre") or _texte_p((re.search(r"<title>(.*?)</title>", h, re.S) or [None, t["cote"]])[1])
    return silgeneve_html_vers_markdown(h), {"date_etat": date_etat, "url": t["url"], "titre": titre}


PREPARER = {"blv": preparer_vd, "silgeneve": preparer_ge}


# ------------------------------------------------------------------ ingestion
def ingerer_texte(canton, t):
    t0 = time.time()
    try:
        md, m = PREPARER[t["methode"]](t)
        nb = len(re.findall(r"^## Art\. ", md, flags=re.M))
        if nb < 5:
            raise ValueError(f"{t['abrev']} : {nb} article(s) extrait(s) seulement")
        mdp = CACHE / "md" / f"{canton}-{t['abrev']}-{m['date_etat']}.md"
        mdp.parent.mkdir(parents=True, exist_ok=True)
        mdp.write_text(md, encoding="utf-8")
        res = cerebro("law", "ingest", t["identifiant"], "--fichier", mdp, "--juridiction", canton, "--type", t.get("type", "loi"),
                      "--titre", m["titre"], "--langue", t.get("langue", "fr"), "--version", m["date_etat"], "--date-etat", m["date_etat"],
                      "--url", m["url"], "--abrev", t["abrev"])
        if not isinstance(res, dict) or "erreur" in res:
            raise RuntimeError((res or {}).get("erreur") if isinstance(res, dict) else str(res))
        out = {"canton": canton, "abrev": t["abrev"], "identifiant": t["identifiant"], "articles": nb, "date_etat": m["date_etat"],
               "url": m["url"], "id": res.get("id"), "statut": res.get("statut"), "duree_s": round(time.time() - t0, 1)}
        journal("cantons ingéré", **out)
        return out
    except Exception as e:
        desc = f"Bibliothèque cantonale : ingestion {canton} {t.get('abrev')} impossible : {str(e)[:200]}"
        cerebro("incident", "add", desc, "--categorie", "source", "--repli",
                "règle cantonale laissée ⚠ ; nouvel essai au cycle suivant (bibliotheque_cantons)")
        cerebro("queue", "add", "bibliotheque_cantons", f"{canton}:{t.get('abrev')}", "--priorite", "5")
        journal("cantons incident", canton=canton, abrev=t.get("abrev"), erreur=str(e)[:300])
        return {"canton": canton, "abrev": t.get("abrev"), "erreur": str(e)[:300], "duree_s": round(time.time() - t0, 1)}


def ingerer(canton=None, texte=None):
    cfg = charger_yaml().get("ingestion") or {}
    cibles = [canton.upper()] if canton else cantons_suivis()
    res = []
    for c in cibles:
        textes = cfg.get(c) or []
        if not textes:
            journal("cantons", canton=c, msg="aucun texte configuré dans cantons.yaml (ingestion) : pratique cantonale à vérifier")
            res.append({"canton": c, "saute": "aucun texte configuré (cantons.yaml)"})
            continue
        for t in textes:
            if texte and t["abrev"] != texte:
                continue
            res.append(ingerer_texte(c, t))
    return res


def verifier():
    """cerebro law verify (fédéral + cantonal), puis juridiction réelle des règles cantonales (cantons.yaml : regles)"""
    regles = charger_yaml().get("regles") or {}
    try:  # les règles du code (horloges.REGLES) entrent en base avant la vérification
        from fedlex import EQ as _EQ
        cb_dir = _EQ / "cerebro" if (_EQ / "cerebro" / "cb").exists() else Path(__file__).resolve().parents[2] / "cerebro"
        sys.path.insert(0, str(cb_dir))
        from cb import horloges
        horloges.seed()
    except Exception as e:
        journal("cantons", msg="horloges.seed impossible", erreur=repr(e)[:200])
    v = cerebro("law", "verify")
    out = []
    import sqlite3, os
    from fedlex import EQ
    p = Path(os.environ.get("CEREBRO_DB") or EQ / "cerebro" / "cerebro.db")
    try:
        con = sqlite3.connect(str(p))
        for typ, canton in regles.items():
            con.execute("UPDATE regles_delais SET juridiction=? WHERE type=? AND COALESCE(juridiction,'CH')<>?", (canton, typ, canton))
        con.commit()
        con.close()
    except Exception as e:
        journal("cantons", msg="juridiction des règles non mise à jour", erreur=repr(e)[:200])
    for r in v if isinstance(v, list) else []:
        if r.get("regle") in regles:
            out.append(r)
    return {"regles_cantonales": out, "toutes": len(v) if isinstance(v, list) else v}


def main(argv=None):
    utf8_console()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["ingerer", "verifier", "liste"])
    ap.add_argument("--canton"); ap.add_argument("--texte")
    a = ap.parse_args(argv)
    t0 = time.time()
    journal("cantons début", action=a.action)
    if a.action == "liste":
        out = {"suivis": cantons_suivis(), "ingestion": charger_yaml().get("ingestion")}
    elif a.action == "ingerer":
        out = {"ingestion": ingerer(a.canton, a.texte)}
        out["verification"] = verifier()
    else:
        out = verifier()
    journal("cantons fin", action=a.action, duree_s=round(time.time() - t0, 1))
    print(json.dumps(out, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
