#!/usr/bin/env python3
"""Serveur MCP local (stdio, JSON-RPC 2.0, sans dépendance) exposant la CLI cerebro (§5, §9.1).
Inscription : claude mcp add --scope project cerebro -- python .team/cerebro/mcp_server.py"""
import sys, os, json, io, contextlib, shlex
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cerebro as CLI

PROTO = "2025-06-18"

def T(name, desc, props, req=()):
    return {"name": name, "description": desc, "inputSchema": {"type": "object", "properties": props, "required": list(req)}}

S = {"type": "string"}
I = {"type": "integer"}
TOOLS = [
    T("cerebro", "Commande cerebro libre (ex: 'find Rochat dividende', 'summary C-001', 'open D-001 --section Analyse', 'deadlines --days 30'). Voir 'cerebro --help'.", {"commande": S}, ["commande"]),
    T("find", "Retrouver un objet (alias, identifiant, plein texte, vecteurs, graphe). Renvoie des lignes de sommaire.", {"q": S, "limit": I, "asof": S}, ["q"]),
    T("summary", "En-tête et menu des sections d'un objet (à lire avant open).", {"id": S}, ["id"]),
    T("open", "Ouvre une seule section d'un objet.", {"id": S, "section": S}, ["id", "section"]),
    T("deadlines", "Délais ouverts à N jours.", {"days": I, "client": S, "canton": S}),
    T("brief", "Brief du jour (texte compact).", {}),
    T("context", "Contexte delta pour un message (objets cités, liens, horloges).", {"message": S}, ["message"]),
    T("config_get", "Lire une clé de configuration (valeur sinon défaut).", {"cle": S}, ["cle"]),
    T("config_set", "Renseigner une clé apprise (recalcule ce qui en dépend).", {"cle": S, "valeur": S, "source": S}, ["cle", "valeur"]),
    T("law_article", "Texte officiel d'un article (bibliothèque), avec version et date.", {"loi": S, "article": S, "date": S, "langue": S}, ["loi", "article"]),
    T("clock_start", "Démarrer une horloge (délai + document préparé).", {"type": S, "date": S, "client": S, "canton": S, "objet": S}, ["type", "date"]),
    T("new", "Créer un objet (identifiant, en-tête, fichier, liens, sommaire).", {"type": S, "nom": S, "client": S, "resume": S, "prochaine_action": S, "date": S, "liens": {"type": "array", "items": S}}, ["type", "nom"]),
    T("regen", "Régénérer en-têtes et lignes de sommaire des objets touchés.", {"ids": {"type": "array", "items": S}}),
]

def run(argv):
    """exécute une commande dans le processus ; transaction toujours close (jamais de verrou gardé après une erreur)"""
    buf, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            CLI.main(argv)
        CLI.core.db().commit()
    except SystemExit:
        try:
            CLI.core.db().rollback()
        except Exception:
            pass
        if not buf.getvalue().strip():
            return json.dumps({"erreur": "commande invalide", "detail": err.getvalue()[-400:]}, ensure_ascii=False)
    except Exception as e:
        try:
            CLI.core.db().rollback()
        except Exception:
            pass
        return json.dumps({"erreur": repr(e)[:300]}, ensure_ascii=False)
    return buf.getvalue().strip()

def call(name, a):
    g = lambda k, d=None: a.get(k, d)
    if name == "cerebro":
        return run(shlex.split(g("commande", ""), posix=(os.name != "nt")))
    if name == "find":
        return run(["find", g("q")] + (["--limit", str(g("limit"))] if g("limit") else []) + (["--asof", g("asof")] if g("asof") else []))
    if name == "summary":
        return run(["summary", g("id")])
    if name == "open":
        return run(["open", g("id"), "--section", g("section")])
    if name == "deadlines":
        return run(["deadlines", "--days", str(g("days", 30))] + (["--client", g("client")] if g("client") else []) + (["--canton", g("canton")] if g("canton") else []))
    if name == "brief":
        return run(["brief"])
    if name == "context":
        return run(["context", g("message")])
    if name == "config_get":
        return run(["config", "get", g("cle")])
    if name == "config_set":
        return run(["config", "set", g("cle"), g("valeur")] + (["--source", g("source")] if g("source") else []))
    if name == "law_article":
        return run(["law", "article", g("loi"), g("article")] + (["--date", g("date")] if g("date") else []) + (["--langue", g("langue")] if g("langue") else []))
    if name == "clock_start":
        return run(["clock", "start", g("type"), "--date", g("date")] + sum([[f"--{k}", g(k)] for k in ("client", "canton", "objet") if g(k)], []))
    if name == "new":
        argv = ["new", g("type"), g("nom")] + sum([[f"--{k.replace('_', '-')}", g(k)] for k in ("client", "resume", "prochaine_action", "date") if g(k)], [])
        for l in g("liens", []) or []:
            argv += ["--lien", l]
        return run(argv)
    if name == "regen":
        return run(["regen"] + (g("ids") or []))
    return json.dumps({"erreur": f"outil inconnu {name}"})

def main():
    for st in (sys.stdin, sys.stdout):
        try:
            st.reconfigure(encoding="utf-8")
        except Exception:
            pass
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            continue
        mid, meth = msg.get("id"), msg.get("method")
        if mid is None:
            continue  # notification
        try:
            if meth == "initialize":
                res = {"protocolVersion": msg.get("params", {}).get("protocolVersion", PROTO), "capabilities": {"tools": {}},
                       "serverInfo": {"name": "cerebro", "version": "1.0.0"}}
            elif meth == "tools/list":
                res = {"tools": TOOLS}
            elif meth == "tools/call":
                p = msg.get("params", {})
                txt = call(p.get("name"), p.get("arguments") or {})
                res = {"content": [{"type": "text", "text": txt[:50000]}], "isError": txt.startswith('{"erreur"')}
            elif meth == "ping":
                res = {}
            else:
                sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "méthode inconnue"}}) + "\n"); sys.stdout.flush()
                continue
        except Exception as e:
            res = {"content": [{"type": "text", "text": json.dumps({"erreur": repr(e)[:300]})}], "isError": True}
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": res}) + "\n")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
