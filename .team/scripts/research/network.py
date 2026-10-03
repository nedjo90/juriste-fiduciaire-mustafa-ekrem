"""Accès réseau commun de la recherche (§6.4, §0 point 7) : stdlib seulement (Windows/macOS/Linux), pause entre requêtes
par hôte, nouvel essai espacé sur 429/503 (Retry-After respecté jusqu'à un plafond), puis repli propre : jamais
d'exception vers l'appelant, toujours un journal (.team/brain/log/recherche.jsonl)."""
import os, sys, json, time, datetime as dt, urllib.request, urllib.parse, urllib.error
from pathlib import Path

UA = "bibliotheque-fiduciaire/1.0 (recherche documentaire interne ; requetes espacees)"
# chaque site a sa règle (certains refusent les programmes, d'autres les faux navigateurs) : identités honnêtes essayées
# tour à tour sur un refus 403, la première acceptée l'emporte
IDENTITES = (UA, "curl/8.5.0",
             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")
PAUSE = {"api.openalex.org": 2.0, "api.semanticscholar.org": 3.0, "www.courtlistener.com": 2.0}
PAUSE_DEFAUT = 1.0
_dernier = {}


def racine():
    r = os.environ.get("CEREBRO_ROOT")
    return Path(r) if r else Path(__file__).resolve().parents[3]


EQ = racine() / ".team"
CODE_EQ = Path(__file__).resolve().parents[2]


def journal(msg, **kw):
    try:
        d = EQ / "brain" / "journal"
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "recherche.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps({"le": dt.datetime.now().isoformat(timespec="seconds"), "msg": msg, **kw}, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def obtenir(url, params=None, entetes=None, essais=3, timeout=40, plafond_attente=20):
    """→ (code, octets, type) ; code 0 = réseau injoignable. Ne lève jamais."""
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    hote = urllib.parse.urlparse(url).netloc
    err = None
    ident = 0
    essais = max(essais, len(IDENTITES))
    for i in range(essais):
        attente = PAUSE.get(hote, PAUSE_DEFAUT) - (time.time() - _dernier.get(hote, 0))
        if attente > 0:
            time.sleep(attente)
        _dernier[hote] = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": IDENTITES[ident], **(entetes or {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            err = e
            if e.code == 403 and ident < len(IDENTITES) - 1:
                ident += 1
                continue
            if e.code in (429, 503) and i < essais - 1:
                ra = e.headers.get("Retry-After") if e.headers else None
                try:
                    s = float(ra) if ra else 2.0 * (i + 1) ** 2
                except ValueError:
                    s = 2.0 * (i + 1) ** 2
                if s > plafond_attente:
                    break
                time.sleep(s)
                continue
            try:
                corps = e.read()
            except Exception:
                corps = b""
            journal("http", url=url[:300], code=e.code)
            return e.code, corps, ""
        except Exception as e:
            err = e
            time.sleep(1.5 * (i + 1))
    code = getattr(err, "code", 0) or 0
    journal("http repli", url=url[:300], code=code, erreur=repr(err)[:200])
    return code, b"", ""


def obtenir_json(url, params=None, entetes=None, **kw):
    code, data, _ = obtenir(url, params, {"Accept": "application/json", **(entetes or {})}, **kw)
    if code != 200:
        return code, None
    try:
        return code, json.loads(data.decode("utf-8", "replace"))
    except Exception:
        return code, None


def cerebro(*args):
    import subprocess
    exe = CODE_EQ / "cerebro" / "cerebro.py"
    r = subprocess.run([sys.executable, str(exe), *map(str, args)], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"erreur": (r.stdout or r.stderr)[-300:]}


def utf8_console():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:
            pass
