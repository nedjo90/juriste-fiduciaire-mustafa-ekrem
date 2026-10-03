#!/usr/bin/env python3
"""Découverte continue (§6.4) — comparaison par scripts, sans modèle. Sources :
- marketplaces configurées : `claude plugin marketplace list --json` ; plugins disponibles : `claude plugin list --available --json`
  (marketplaces officielles Anthropic : anthropic-plugin-directory, anthropics/skills, anthropics/claude-for-legal,
  anthropics/financial-services) ;
- registre MCP officiel : https://registry.modelcontextprotocol.io/v0.1/servers (vérifié le 2026-10-03 : 200, paramètres
  search, version=latest, limit, cursor ; repli /v0/servers) ;
- inventaire local : table `capacites` (cerebro capability list).
Sortie : candidats triés (pertinence pour une fiduciaire suisse + besoins en file), absents de l'inventaire et jamais évalués.
Usage : catalogue.py [--besoin "texte"]… [--max 10] [--sans-reseau] [--json]"""
import os, re, sys, json, shutil, argparse, subprocess, urllib.request, urllib.parse
from pathlib import Path

ROOT = Path(os.environ.get("CEREBRO_ROOT") or Path(__file__).resolve().parents[3])
EQ = ROOT / ".equipe"
sys.path.insert(0, str(EQ / "cerebro"))
os.environ.setdefault("CEREBRO_ROOT", str(ROOT))
REGISTRE = ("https://registry.modelcontextprotocol.io/v0.1/servers", "https://registry.modelcontextprotocol.io/v0/servers")
OFFICIELS = {"anthropic-plugin-directory", "anthropic-agent-skills", "claude-for-legal", "claude-for-financial-services", "claude-plugins-official"}
MOTS = {  # pertinence métier (sans accents) → poids
    "swiss": 4, "suisse": 4, "schweiz": 4, "fedlex": 6, "zefix": 6, "shab": 4, "fosc": 4, "lexfind": 5, "caselaw": 3, "court": 2,
    "legal": 3, "law": 3, "statute": 3, "contract": 2, "tax": 3, "vat": 3, "accounting": 2, "fiduciary": 3, "compliance": 2,
    "aml": 3, "kyc": 2, "gdpr": 2, "privacy": 1, "document": 1, "docx": 2, "word": 1, "excel": 1, "xlsx": 2, "pdf": 2, "ocr": 3,
    "outlook": 2, "microsoft 365": 2, "calendar": 1, "email": 1, "translation": 1, "deepl": 2, "eur-lex": 4, "legislation": 3,
    "corporate": 2, "registry": 1, "company": 1,
}
EXCLUS = ("crypto", "x402", "usdc", "casino", "nft", "trading", "porn", "game")
ETRANGERS = ("cyprus", "brazil", "korea", "india", "u.s.", "united states", "china", "japan", "australia", "bar prep", "law student",
             "socratic", "philippine", "nigeria", "indonesia")  # juridictions sans lien probable avec une fiduciaire suisse


def _base():
    e = os.environ.get("CEREBRO_CLAUDE") or shutil.which("claude")
    if not e:
        return None
    return [os.environ.get("CEREBRO_PYTHON") or sys.executable, e] if e.lower().endswith(".py") else [e]


def _json_cmd(args, timeout=90):
    base = _base()
    if not base:
        return None
    try:
        r = subprocess.run([*base, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           stdin=subprocess.DEVNULL, cwd=str(ROOT))
        return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None
    except Exception:
        return None


def marketplaces():
    return _json_cmd(["plugin", "marketplace", "list", "--json"]) or []


def plugins():
    d = _json_cmd(["plugin", "list", "--available", "--json"], timeout=120) or {}
    out = []
    for p in d.get("available") or []:
        out.append({"type": "plugin", "id": p.get("pluginId") or p.get("name"), "nom": p.get("name"), "description": p.get("description") or "",
                    "source": p.get("marketplaceName"), "officiel": p.get("marketplaceName") in OFFICIELS})
    installes = {p.get("pluginId") or p.get("name") for p in d.get("installed") or []}
    return [p for p in out if p["id"] not in installes]


def registre(recherche=None, pages=3, limite=100):
    """serveurs du registre MCP officiel (dernière version), filtrés par recherche ; [] si injoignable"""
    out = []
    for base in REGISTRE:
        curseur, ok = None, False
        for _ in range(pages):
            q = {"limit": limite, "version": "latest"}
            if recherche:
                q["search"] = recherche
            if curseur:
                q["cursor"] = curseur
            try:
                req = urllib.request.Request(base + "?" + urllib.parse.urlencode(q), headers={"User-Agent": "cerebro-decouverte/1.0"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    d = json.loads(r.read().decode("utf-8"))
            except Exception:
                break
            ok = True
            for s in d.get("servers") or []:
                sv = s.get("server") or s
                meta = (s.get("_meta") or {}).get("io.modelcontextprotocol.registry/official") or {}
                if meta.get("status", "active") != "active":
                    continue
                out.append({"type": "mcp", "id": sv.get("name"), "nom": sv.get("title") or sv.get("name"), "description": sv.get("description") or "",
                            "version": sv.get("version"), "depot": (sv.get("repository") or {}).get("url"), "site": sv.get("websiteUrl"),
                            "distant": [x.get("url") for x in sv.get("remotes") or []],
                            "paquets": [{"registre": p.get("registryType"), "nom": p.get("identifier"), "transport": (p.get("transport") or {}).get("type")}
                                        for p in sv.get("packages") or []],
                            "secrets": any(h.get("isSecret") for x in sv.get("remotes") or [] for h in x.get("headers") or [])
                            or any(e.get("isSecret") for p in sv.get("packages") or [] for e in p.get("environmentVariables") or []),
                            "publie_le": meta.get("publishedAt"), "source": "registre MCP officiel", "officiel": False})
            curseur = (d.get("metadata") or {}).get("nextCursor")
            if not curseur:
                break
        if ok:
            break
    return out


def inventaire():
    try:
        from cb import files as F
        return F.capability_list()
    except Exception:
        return []


def _fold(s):
    import unicodedata
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()


def score(c, besoins=()):
    t = _fold(f"{c['id']} {c['nom']} {c['description']}")
    if any(x in t for x in EXCLUS):
        return -1
    s = sum(w for m, w in MOTS.items() if m in t)
    for b in besoins:
        mots = [w for w in re.findall(r"[a-z]{4,}", _fold(b))]
        s += 3 * sum(1 for w in mots if w in t)
    if any(x in t for x in ETRANGERS):
        s -= 6
    if c.get("officiel"):
        s += 4
    if c.get("depot"):
        s += 1
    if c.get("secrets"):
        s -= 3  # exige un compte ou une clé : rarement installable sans question
    return s


def candidats(besoins=(), maxi=10, reseau=True, evalues=()):
    inv = {_fold(x.get("nom")) for x in inventaire()} | {_fold(x.get("source")) for x in inventaire()}
    evalues = {_fold(e) for e in evalues}
    pool = plugins()
    if reseau:
        recherches = {None, "swiss", "legal", "tax"} | {w for b in besoins for w in re.findall(r"[a-z]{5,}", _fold(b))[:2]}
        vus = set()
        for q in recherches:
            for c in registre(q, pages=1 if q else 2):
                if c["id"] not in vus:
                    vus.add(c["id"])
                    pool.append(c)
    out = []
    for c in pool:
        k = _fold(c["id"])
        if k in evalues or _fold(c["nom"]) in inv or k in inv or any(k and k in i for i in inv if i):
            continue
        sc = score(c, besoins)
        if sc >= 5:
            out.append({**c, "score": sc})
    out.sort(key=lambda c: -c["score"])
    return out[:maxi]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--besoin", action="append", default=[])
    ap.add_argument("--max", type=int, default=10)
    ap.add_argument("--sans-reseau", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    c = candidats(a.besoin, a.max, not a.sans_reseau)
    if a.json:
        print(json.dumps(c, ensure_ascii=False))
    else:
        for x in c:
            print(f"{x['score']:>3} {x['type']:6} {x['id']} — {x['description'][:100]}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"erreur": repr(e)[:300]}))
