#!/usr/bin/env python3
"""Intendant (§4.1 (2), §0.4, §15) : résout seul les incidents techniques, sans jamais rien bloquer.
- vérifie configuration, hooks et serveurs MCP (validate_config --sans-session) ;
- désactive tout mécanisme bloquant (liste deny, hook PreToolUse/PermissionRequest, disableAllHooks, mode d'autorisation
  restrictif) et le remplace par une version qui journalise ; hook en échec répété → validation, sinon restauration ;
- traite les incidents ouverts simples (relance, constat de résolution) ;
- surveille l'espace disque (alerte à 80 %) ; restaure valid-config si la configuration est cassée.
Usage : steward.py [--avec-session] [--json]"""
import sys, os, json, time, shutil, subprocess, argparse, datetime as dt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import background as fond
from background import ROOT, EQ, SCRIPTS, journal

SEUIL_DISQUE = 0.80
ECHECS_HOOK_24H = 5
OBSERVER = lambda ev: {"type": "command", "command": "python3", "args": ["${CLAUDE_PROJECT_DIR}/.claude/hooks/hook.py", "Observer"], "timeout": 5}


def _lire(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _ecrire(p, d):
    tmp = Path(str(p) + ".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def desarmer(p):
    """retire d'un fichier de réglages tout ce qui peut bloquer ; renvoie la liste des corrections"""
    p = Path(p)
    if not p.exists():
        return []
    d = _lire(p)
    if not isinstance(d, dict):
        return ["illisible"]
    fait = []
    perm = d.get("permissions")
    if isinstance(perm, dict):
        if perm.get("deny"):
            journal("steward", action="liste deny retirée", fichier=p.name, contenu=perm["deny"])
            perm.pop("deny")
            fait.append("deny retiré")
        if perm.get("ask"):
            journal("steward", action="liste ask retirée", fichier=p.name, contenu=perm["ask"])
            perm.pop("ask")
            fait.append("ask retiré")
        if p.name == "settings.json" and perm.get("defaultMode") not in (None, "bypassPermissions"):
            fait.append(f"mode {perm.get('defaultMode')} → bypassPermissions")
            perm["defaultMode"] = "bypassPermissions"
    if d.get("disableAllHooks"):
        d.pop("disableAllHooks")
        fait.append("disableAllHooks retiré")
    hooks = d.get("hooks") or {}
    py = None
    for ev in ("PreToolUse", "PermissionRequest"):
        if ev in hooks:
            journal("steward", action=f"hook {ev} remplacé par une observation", fichier=p.name, contenu=hooks[ev])
            # même interpréteur que les autres hooks du fichier
            for g in sum((v for v in hooks.values() if isinstance(v, list)), []):
                for h in (g.get("hooks") or []):
                    if h.get("args") and str(h["args"][0]).endswith("hook.py"):
                        py = h.get("command")
            obs = OBSERVER(ev)
            if py:
                obs["command"] = py
            hooks[ev] = [{"hooks": [obs]}] if ev == "PreToolUse" else []
            if not hooks[ev]:
                hooks.pop(ev)
            fait.append(f"hook {ev} neutralisé")
    if fait and fait != ["illisible"]:
        _ecrire(p, d)
    return fait


def echecs_hooks_recents():
    p = EQ / "brain" / "log" / "hooks-erreurs.jsonl"
    if not p.exists():
        return {}
    lim = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=24))
    n = {}
    for l in p.read_text(encoding="utf-8", errors="ignore").splitlines()[-500:]:
        try:
            x = json.loads(l)
            t = dt.datetime.fromisoformat(x["le"])
            if t.tzinfo is None:
                t = t.astimezone()
            if t >= lim:
                n[x.get("evenement")] = n.get(x.get("evenement"), 0) + 1
        except Exception:
            continue
    return {k: v for k, v in n.items() if v >= ECHECS_HOOK_24H}


def valider(session=False):
    cmd = [fond.python_exe(), str(SCRIPTS / "validate_config.py")] + ([] if session else ["--sans-session"])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=300, cwd=str(ROOT),
                           stdin=subprocess.DEVNULL, env={k: v for k, v in os.environ.items() if k != "CEREBRO_BACKGROUND"})
        return json.loads((r.stdout or "{}").strip().splitlines()[-1])
    except Exception as e:
        return {"ok": False, "erreur": repr(e)}


def mcp_disponibles():
    d = _lire(ROOT / ".mcp.json") or {}
    manquants = []
    for nom, s in (d.get("mcpServers") or {}).items():
        c = s.get("command")
        if c and not (shutil.which(c) or Path(c).exists()):
            manquants.append(nom)
    return manquants


def disque():
    u = shutil.disk_usage(str(ROOT))
    return round(u.used / u.total, 3), round(u.free / 1e9, 1)


def traiter_incidents():
    fond.cb()
    from cb import files as F, core
    faits = []
    etat = core.get_etat
    for inc in F.incident_list("ouvert"):
        d = (inc.get("description") or "").lower()
        le = inc.get("le") or ""
        try:
            if "clerk" in d:
                ok = etat("greffier_dernier_ok")
                if ok and ok > le:
                    F.incident_resolve(inc["id"], "classement repris avec succès"); faits.append(inc["id"])
                else:
                    core.db().execute("INSERT OR IGNORE INTO file_entretien(priorite,tache,arg,cree_le) VALUES(3,'clerk','',?)", (core.stamp(),)); core.db().commit()
            elif inc.get("categorie") == "git":
                ok = etat("dernier_push_ok")
                if ok and ok > le:
                    F.incident_resolve(inc["id"], "envoi repris avec succès"); faits.append(inc["id"])
                else:
                    core.db().execute("INSERT OR IGNORE INTO file_entretien(priorite,tache,arg,cree_le) VALUES(6,'commit_push','',?)", (core.stamp(),)); core.db().commit()
            elif inc.get("categorie") == "disque":
                if disque()[0] < SEUIL_DISQUE:
                    F.incident_resolve(inc["id"], "espace disque revenu sous 80 %"); faits.append(inc["id"])
            elif inc.get("categorie") == "configuration":
                ok = etat("config_derniere_validation_ok")
                if ok and ok > le:
                    F.incident_resolve(inc["id"], "configuration validée depuis"); faits.append(inc["id"])
        except Exception as e:
            journal("erreurs-fond", job="steward", incident=inc.get("id"), erreur=repr(e))
    return faits


def verifier(session=False):
    t0 = time.time()
    r = {}
    corr = {}
    for p in (ROOT / ".claude" / "settings.json", ROOT / ".claude" / "settings.local.json"):
        f = desarmer(p)
        if f:
            corr[p.name] = f
    if corr:
        r["desarme"] = corr
        fond.incident("mécanisme bloquant trouvé et neutralisé : " + json.dumps(corr, ensure_ascii=False)[:200], "configuration",
                      "remplacé par une version qui journalise")
    # réglages utilisateur : constat seulement (fichier hors du projet)
    u = _lire(Path.home() / ".claude" / "settings.json") or {}
    if (u.get("permissions") or {}).get("deny"):
        journal("steward", constat="liste deny dans les réglages utilisateur (non modifiée)", contenu=u["permissions"]["deny"])
        r["deny_utilisateur"] = True
    ech = echecs_hooks_recents()
    if ech:
        r["hooks_en_echec"] = ech
        fond.incident(f"hook en échec répété : {', '.join(ech)}", "configuration", "validation puis restauration de la configuration valide")
    v = valider(session)
    r["validation"] = v.get("ok")
    if v.get("ok"):
        fond.cb()
        from cb import core
        core.set_etat("config_derniere_validation_ok", core.stamp())
    else:
        r["validation_erreurs"] = v.get("erreurs") or v.get("erreur")
        r["restaures"] = v.get("restaures")
    m = mcp_disponibles()
    if m:
        r["mcp_indisponibles"] = m
        journal("steward", constat="serveurs MCP sans programme de lancement", serveurs=m)
    taux, libre = disque()
    r["disque"] = {"taux": taux, "libre_go": libre}
    if taux >= SEUIL_DISQUE:
        fond.incident(f"disque presque plein ({int(taux * 100)} %, {libre} Go libres)", "disque",
                      "archives condensées ; à défaut, une phrase simple à Mustafa")
    r["incidents_resolus"] = traiter_incidents()
    r["duree_s"] = round(time.time() - t0, 1)
    journal("steward", **r)
    return r


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--avec-session", action="store_true")
    a = ap.parse_args()
    try:
        print(json.dumps(verifier(a.avec_session), ensure_ascii=False, default=str))
    except Exception as e:
        journal("erreurs-fond", job="steward", erreur=repr(e))
        print(json.dumps({"erreur": repr(e)}))
