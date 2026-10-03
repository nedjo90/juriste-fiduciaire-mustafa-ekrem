#!/usr/bin/env python3
"""Validation de configuration (constitution §0.10, critère 38) : le lancement suivant ne peut jamais casser.
(a) JSON de .claude/settings.json et .mcp.json relus et analysés ; aucune liste deny, aucun hook de refus ;
(b) chaque hook exécuté seul sur une entrée simulée : succès en moins de 2 s, sortie vide ou JSON valide ;
(c) session de contrôle non interactive (claude -p "ok", CEREBRO_BACKGROUND non défini) : réponse sans refus ni erreur,
    et preuve que les hooks ont tourné ;
(d) seulement alors, copie dans .equipe/scripts/config-valide/ (--sans-session : pas de copie, sauf --copier). Sinon : restauration de la copie précédente + incident.
Usage : valider_config.py [--sans-session] [--lancement] [--restaurer] [--confiance] [--adapter-poste] [--json]
  --lancement     : contrôle rapide au démarrage (JSON + interpréteur des hooks) ; restaure si cassé (lanceurs)
  --restaurer     : remet la dernière configuration valide
  --confiance     : déclare le dossier de confiance dans ~/.claude.json (préserve le reste du fichier)
  --adapter-poste : fait pointer les hooks sur l'interpréteur Python de ce poste (installateur)"""
import sys, os, json, time, shutil, subprocess, argparse, tempfile, hashlib, uuid
from pathlib import Path

ICI = Path(__file__).resolve().parent
ROOT = ICI.parents[1]
EQ = ROOT / ".equipe"
VALIDE = ICI / "config-valide"
# fichier vivant → copie dans config-valide (noms sans point ni accent)
FICHIERS = {
    ".claude/settings.json": "settings.json",
    ".mcp.json": "mcp.json",
    "CLAUDE.md": "CLAUDE.md",
    ".claude/hooks/hook.py": "hooks/hook.py",
    ".claude/hooks/vocabulaire-technique.txt": "hooks/vocabulaire-technique.txt",
    ".equipe/scripts/entretien/fond.py": "entretien/fond.py",
}
EVENEMENTS_BLOQUANTS = {"PreToolUse", "PermissionRequest"}  # jamais utilisés (§0.3) : remplacés par une observation
LIMITE_HOOK_S = 2.0
NOMS_PYTHON = {"python", "python3", "python.exe", "python3.exe", "py"}

sys.path.insert(0, str(EQ / "scripts" / "entretien"))
try:
    import fond
    journal = fond.journal
except Exception:  # socle absent : journal minimal
    fond = None

    def journal(nom, **rec):
        try:
            d = EQ / "cerveau" / "journal"
            d.mkdir(parents=True, exist_ok=True)
            with open(d / f"{nom}.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"le": time.strftime("%Y-%m-%dT%H:%M:%S"), **rec}, ensure_ascii=False) + "\n")
        except Exception:
            pass


def incident(desc, repli=""):
    if fond:
        fond.incident(desc, "configuration", repli)
    else:
        journal("incidents-config", description=desc, repli=repli)


def lire_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def ecrire_json(p, data):
    p = Path(p)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, p)


# ------------------------------------------------------------------ (a) analyse
def analyser():
    """renvoie (erreurs, settings) ; erreurs = liste de textes"""
    err = []
    s = None
    p = ROOT / ".claude" / "settings.json"
    try:
        s = lire_json(p)
        if not isinstance(s, dict):
            err.append("settings.json n'est pas un objet")
    except Exception as e:
        err.append(f"settings.json illisible : {e}")
    try:
        if (ROOT / ".mcp.json").exists():
            m = lire_json(ROOT / ".mcp.json")
            if not isinstance(m.get("mcpServers", {}), dict):
                err.append(".mcp.json : mcpServers n'est pas un objet")
    except Exception as e:
        err.append(f".mcp.json illisible : {e}")
    if isinstance(s, dict):
        perm = s.get("permissions") or {}
        if perm.get("deny"):
            err.append("liste deny présente")
        for ev in EVENEMENTS_BLOQUANTS & set((s.get("hooks") or {}).keys()):
            err.append(f"hook {ev} présent (interdit, §0.3)")
        if s.get("disableAllHooks"):
            err.append("disableAllHooks actif")
        if (s.get("env") or {}).get("CEREBRO_BACKGROUND"):
            err.append("CEREBRO_BACKGROUND défini dans settings.json : tous les hooks seraient muets")
    return err, s


def hooks_de(s):
    """[(evenement, matcher, entrée hook)]"""
    out = []
    for ev, groupes in ((s or {}).get("hooks") or {}).items():
        for g in groupes or []:
            for h in g.get("hooks") or []:
                if h.get("type", "command") == "command":
                    out.append((ev, g.get("matcher"), h))
    return out


ENTREES = {
    "SessionStart": {"source": "startup"},
    "UserPromptSubmit": {"prompt": "bonjour, contrôle de configuration"},
    "Stop": {"last_assistant_message": "Bonjour.", "stop_hook_active": False},
    "PreCompact": {"trigger": "manual", "custom_instructions": ""},
    "SessionEnd": {"reason": "other"},
    "PostToolUse": {"tool_name": "Write", "tool_input": {"file_path": str(ROOT / "CLAUDE.md")}, "tool_response": {}},
}


def commande(h):
    """reconstruit la commande d'un hook (forme exec ou forme shell)"""
    sub = lambda x: x.replace("${CLAUDE_PROJECT_DIR}", str(ROOT)).replace("$CLAUDE_PROJECT_DIR", str(ROOT))
    if h.get("args") is not None:
        exe = sub(h["command"])
        w = shutil.which(exe) or (exe if Path(exe).exists() else None)
        return ([w or exe] + [sub(a) for a in h["args"]]), False
    return sub(h["command"]), True


# ------------------------------------------------------------------ (b) hooks seuls
def tester_hooks(s, jeton, db_test):
    err, mesures = [], {}
    env = dict(os.environ)
    env.pop("CEREBRO_BACKGROUND", None)
    env.update({"CEREBRO_CONTROLE": jeton, "CEREBRO_DB": str(db_test), "CLAUDE_PROJECT_DIR": str(ROOT), "PYTHONIOENCODING": "utf-8"})
    for ev, matcher, h in hooks_de(s):
        data = {"session_id": "controle-" + jeton[:8], "hook_event_name": ev, "cwd": str(ROOT), "transcript_path": "", **ENTREES.get(ev, {})}
        cmd, shell = commande(h)
        t0 = time.time()
        try:
            r = subprocess.run(cmd, shell=shell, input=json.dumps(data).encode("utf-8"), capture_output=True, cwd=str(ROOT), env=env,
                               timeout=max(LIMITE_HOOK_S * 3, 6))
            ms = int((time.time() - t0) * 1000)
            mesures[ev] = ms
            if r.returncode != 0:
                err.append(f"hook {ev} : code {r.returncode} {r.stderr.decode('utf-8', 'ignore')[-200:]}")
            elif ms > LIMITE_HOOK_S * 1000:
                err.append(f"hook {ev} : {ms} ms (> 2 s)")
            out = r.stdout.decode("utf-8", "ignore").strip()
            if out:
                try:
                    d = json.loads(out)
                    hso = d.get("hookSpecificOutput") or {}
                    if d.get("decision") in ("block", "deny") or hso.get("permissionDecision") in ("deny", "ask") or d.get("continue") is False:
                        err.append(f"hook {ev} renvoie un blocage")
                except Exception:
                    if ev not in ("SessionStart", "UserPromptSubmit"):
                        err.append(f"hook {ev} : sortie non JSON")
        except subprocess.TimeoutExpired:
            err.append(f"hook {ev} : délai dépassé")
        except Exception as e:
            err.append(f"hook {ev} : {e!r}")
    return err, mesures


# ------------------------------------------------------------------ confiance du dossier (~/.claude.json)
def declarer_confiance(root=ROOT, serveurs=None):
    p = Path(os.environ.get("CLAUDE_CONFIG_JSON") or (Path.home() / ".claude.json"))
    try:
        d = lire_json(p) if p.exists() else {}
    except Exception:
        shutil.copy2(p, p.with_name(p.name + ".illisible-" + time.strftime("%Y%m%d%H%M%S")))
        d = {}
    projets = d.setdefault("projects", {})
    cles = {str(root)}
    if os.name == "nt":
        cles.add(str(root).replace("\\", "/"))
    for k in cles:
        e = projets.setdefault(k, {})
        e["hasTrustDialogAccepted"] = True
        e.setdefault("allowedTools", [])
        if serveurs:
            e["enabledMcpjsonServers"] = sorted(set(e.get("enabledMcpjsonServers") or []) | set(serveurs))
            e["disabledMcpjsonServers"] = [x for x in (e.get("disabledMcpjsonServers") or []) if x not in serveurs]
    ecrire_json(p, d)
    return sorted(cles)


def serveurs_mcp():
    try:
        return list((lire_json(ROOT / ".mcp.json").get("mcpServers") or {}).keys())
    except Exception:
        return []


def hooks_suspendus_localement():
    try:
        return bool(((lire_json(ROOT / ".claude" / "settings.local.json") or {}).get("env") or {}).get("CEREBRO_BACKGROUND"))
    except Exception:
        return False


# ------------------------------------------------------------------ (c) session de contrôle
def session_controle(jeton, db_test, timeout=120):
    claude = (fond.claude_exe() if fond else None) or shutil.which("claude")
    if not claude:
        return ["programme claude introuvable"], {}
    env = dict(os.environ)
    env.pop("CEREBRO_BACKGROUND", None)
    env.update({"CEREBRO_CONTROLE": jeton, "CEREBRO_DB": str(db_test), "PYTHONIOENCODING": "utf-8"})
    t0 = time.time()
    try:
        cmd = [claude, "-p", "ok", "--output-format", "json", "--max-turns", "2", "--no-session-persistence",
               "--append-system-prompt", "Session de contrôle technique automatique : réponds seulement « ok », sans utiliser d'outil ni reprendre aucun travail."]
        sources = ["user", "project", "local"]
        if os.environ.get("CLAUDE_CODE_REMOTE"):
            # machine de construction distante : ses réglages d'environnement (hook Stop « commit and push ») sont hors projet ;
            # on valide la configuration du projet seule. Sur le poste, toutes les sources sont chargées.
            sources.remove("user")
        if hooks_suspendus_localement():
            # settings.local.json (non suivi) suspend les hooks pendant la construction : le contrôle porte sur la configuration livrée
            sources.remove("local")
        if sources != ["user", "project", "local"]:
            cmd += ["--setting-sources", ",".join(sources)]
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                           cwd=str(ROOT), env=env, timeout=timeout, encoding="utf-8", errors="ignore")
    except subprocess.TimeoutExpired:
        return ["session de contrôle : délai dépassé"], {}
    info = {"ms": int((time.time() - t0) * 1000), "code": r.returncode}
    err = []
    try:
        d = json.loads((r.stdout or "").strip().splitlines()[-1])
    except Exception:
        return [f"session de contrôle : sortie illisible (code {r.returncode}) {(r.stderr or '')[-300:]}"], info
    info.update({"resultat": (d.get("result") or "")[:80], "cout_usd": d.get("total_cost_usd"), "modele": list((d.get("modelUsage") or {}).keys())})
    if d.get("subtype") == "error_max_turns" and (d.get("num_turns") or 0) >= 1:
        pass  # la session a démarré, tourné et répondu ; la limite de tours borne seulement le coût du contrôle
    elif r.returncode != 0 or d.get("is_error") or d.get("subtype") != "success":
        err.append(f"session de contrôle en erreur : {d.get('subtype')} {(d.get('result') or '')[:200]}")
    if d.get("permission_denials"):
        err.append(f"demandes d'autorisation refusées : {d['permission_denials'][:3]}")
    if r.stderr and any(m in r.stderr.lower() for m in ("settings error", "invalid settings", "hook error", "failed to parse")):
        err.append(f"avertissement au démarrage : {r.stderr[-300:]}")
    # preuve que les hooks ont tourné
    vus = set()
    try:
        for l in (EQ / "cerveau" / "journal" / "controle.jsonl").read_text(encoding="utf-8").splitlines()[-200:]:
            x = json.loads(l)
            if x.get("jeton") == jeton:
                vus.add(x.get("evenement"))
    except Exception:
        pass
    info["hooks_vus"] = sorted(vus)
    info["sources"] = ",".join(sources)
    attendus = {"SessionStart", "UserPromptSubmit"}
    if not attendus <= vus:
        err.append(f"hooks non exécutés pendant la session de contrôle : {sorted(attendus - vus)}")
    return err, info


# ------------------------------------------------------------------ copie / restauration
def empreinte(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:16] if Path(p).exists() else None


def copier_valide():
    VALIDE.mkdir(parents=True, exist_ok=True)
    man = {"le": time.strftime("%Y-%m-%dT%H:%M:%S"), "fichiers": {}}
    for src, dst in FICHIERS.items():
        s = ROOT / src
        if s.exists():
            d = VALIDE / dst
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)
            man["fichiers"][src] = empreinte(s)
    ecrire_json(VALIDE / "manifeste.json", man)
    return man


def restaurer(seulement=None):
    """remet les fichiers de config-valide qui diffèrent ; renvoie la liste restaurée"""
    if not (VALIDE / "manifeste.json").exists():
        return []
    faits = []
    for src, dst in FICHIERS.items():
        if seulement and src not in seulement:
            continue
        v = VALIDE / dst
        if v.exists() and empreinte(v) != empreinte(ROOT / src):
            cible = ROOT / src
            cible.parent.mkdir(parents=True, exist_ok=True)
            if cible.exists():
                arch = EQ / "archives" / "config-rejetee" / time.strftime("%Y%m%d-%H%M%S")
                arch.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cible, arch / dst.replace("/", "_"))
            shutil.copy2(v, cible)
            faits.append(src)
    return faits


# ------------------------------------------------------------------ adaptation au poste
def adapter_poste(python=None):
    """hooks en forme exec : l'interpréteur devient celui de ce poste s'il est introuvable ou différent"""
    python = python or sys.executable
    p = ROOT / ".claude" / "settings.json"
    s = lire_json(p)
    change = False
    for ev, matcher, h in hooks_de(s):
        if h.get("args") is None:
            continue
        exe = h.get("command", "")
        nom = Path(exe).name.lower()
        introuvable = not _resolu(exe)
        if (nom in NOMS_PYTHON or nom.startswith("python")) and (introuvable or os.name == "nt") and exe != python:
            h["command"] = python
            change = True
    if change:
        ecrire_json(p, s)
    # serveur MCP cerebro : même interpréteur
    pm = ROOT / ".mcp.json"
    if pm.exists():
        m = lire_json(pm)
        for nom, srv in (m.get("mcpServers") or {}).items():
            exe = srv.get("command", "")
            if Path(exe).name.lower() in NOMS_PYTHON and (os.name == "nt" or not _resolu(exe)) and exe != python:
                srv["command"] = python
                ecrire_json(pm, m)
                change = True
    return change


def _resolu(exe):
    """chemin réel d'un exécutable, ou None ; l'alias « python » du Microsoft Store (WindowsApps) ne compte pas"""
    w = exe if Path(exe).exists() else shutil.which(exe)
    if not w or "windowsapps" in str(w).lower():
        return None
    return w


def interpreteurs_ok(s):
    for ev, matcher, h in hooks_de(s):
        exe = h.get("command", "") if h.get("args") is not None else None
        if exe and not _resolu(exe):
            return False
    return True


# ------------------------------------------------------------------ orchestration
def valider(session=True, copier=True):
    t0 = time.time()
    jeton = uuid.uuid4().hex
    rapport = {"etapes": {}, "ok": False}
    err, s = analyser()
    rapport["etapes"]["a_json"] = err or "ok"
    if err:
        return conclure(rapport, err, [".claude/settings.json", ".mcp.json"], t0)
    with tempfile.TemporaryDirectory() as tmp:
        db_test = Path(tmp) / "controle.db"
        reelle = EQ / "cerebro" / "cerebro.db"
        if reelle.exists():
            try:
                import sqlite3
                a, b = sqlite3.connect(str(reelle)), sqlite3.connect(str(db_test))
                a.backup(b); a.close(); b.close()
            except Exception:
                shutil.copy2(reelle, db_test)
        err, mesures = tester_hooks(s, jeton, db_test)
        rapport["etapes"]["b_hooks"] = err or mesures
        if err:
            return conclure(rapport, err, [".claude/settings.json", ".claude/hooks/hook.py", ".claude/hooks/vocabulaire-technique.txt", ".equipe/scripts/entretien/fond.py"], t0)
        if session:
            try:
                declarer_confiance(ROOT, serveurs_mcp())
            except Exception as e:
                journal("valider-config", avertissement=f"confiance non déclarée : {e!r}")
            err, info = session_controle(uuid.uuid4().hex, db_test)
            rapport["etapes"]["c_session"] = err or info
            if err:
                return conclure(rapport, err, None, t0)
        else:
            rapport["etapes"]["c_session"] = "sautée (--sans-session)"
    if copier:
        rapport["etapes"]["d_copie"] = copier_valide()["le"]
    else:
        rapport["etapes"]["d_copie"] = "non (sans session de contrôle, la copie valide n'est pas remplacée)"
    rapport["ok"] = True
    rapport["duree_s"] = round(time.time() - t0, 1)
    journal("valider-config", ok=True, session=session, duree_s=rapport["duree_s"])
    return rapport


def conclure(rapport, err, fichiers, t0):
    rest = restaurer(fichiers)
    rapport["restaures"] = rest
    rapport["erreurs"] = err
    rapport["duree_s"] = round(time.time() - t0, 1)
    journal("valider-config", ok=False, erreurs=err, restaures=rest)
    incident("configuration refusée par la validation : " + "; ".join(err)[:300],
             ("retour à la dernière configuration valide : " + ", ".join(rest)) if rest else "aucune copie valide disponible")
    return rapport


def lancement():
    """contrôle rapide (< 1 s) avant d'ouvrir Claude Code : JSON lisible, pas de deny, interpréteur des hooks présent"""
    err, s = analyser()
    if err:
        rest = restaurer([".claude/settings.json", ".mcp.json"])
        incident("configuration cassée détectée au lancement : " + "; ".join(err)[:200], "restauration : " + (", ".join(rest) or "aucune copie"))
        err2, s = analyser()
        return {"ok": not err2, "restaures": rest, "erreurs": err}
    if not interpreteurs_ok(s):
        try:
            adapter_poste()
            return {"ok": True, "adapte": True}
        except Exception as e:
            return {"ok": False, "erreur": repr(e)}
    return {"ok": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sans-session", action="store_true")
    ap.add_argument("--lancement", action="store_true")
    ap.add_argument("--restaurer", action="store_true")
    ap.add_argument("--confiance", action="store_true")
    ap.add_argument("--adapter-poste", action="store_true")
    ap.add_argument("--python")
    ap.add_argument("--copier", action="store_true", help="copier aussi sans session de contrôle (déconseillé)")
    a = ap.parse_args()
    if a.lancement:
        r = lancement()
    elif a.restaurer:
        r = {"restaures": restaurer()}
    elif a.confiance:
        r = {"confiance": declarer_confiance(ROOT, serveurs_mcp())}
    elif a.adapter_poste:
        r = {"adapte": adapter_poste(a.python)}
    else:
        r = valider(session=not a.sans_session, copier=(not a.sans_session) or a.copier)
    print(json.dumps(r, ensure_ascii=False, default=str))
    return 0 if r.get("ok", True) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # jamais de trace brute ni de blocage
        journal("valider-config", erreur=repr(e))
        print(json.dumps({"ok": False, "erreur": repr(e)}))
        sys.exit(1)
