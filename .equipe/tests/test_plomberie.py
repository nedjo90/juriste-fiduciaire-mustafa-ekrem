#!/usr/bin/env python3
"""Tests de la plomberie (hooks, réglages, validation, entretien, lanceur) — critères 3, 4, 8, 9, 38, 39.
Exécution : python .equipe/tests/test_plomberie.py   → une ligne OK/ÉCHEC par test, code 0 si tout passe.
Tout se passe dans une racine jetable (copie de .equipe, .claude, .mcp.json, CLAUDE.md) : la base réelle n'est jamais touchée.
Aucun appel de modèle (CEREBRO_SANS_MODELE=1, faux programme « claude » pour le lanceur)."""
import os, sys, json, time, shutil, subprocess, tempfile, sqlite3
from pathlib import Path

REEL = Path(__file__).resolve().parents[2]
PY = sys.executable
RES = []


def test(nom):
    def deco(f):
        def run():
            t0 = time.time()
            try:
                f()
                RES.append((nom, True, ""))
                print(f"OK     {nom} ({int((time.time() - t0) * 1000)} ms)")
            except Exception as e:
                RES.append((nom, False, repr(e)))
                print(f"ÉCHEC  {nom} : {e!r}")
        run.__name__ = f.__name__
        TESTS.append(run)
        return run
    return deco


TESTS = []


def preparer():
    tmp = Path(tempfile.mkdtemp(prefix="plomberie-"))
    R = tmp / "racine"
    R.mkdir()
    ign = shutil.ignore_patterns("cerebro.db*", "__pycache__", "run", "sauvegardes", "*.jsonl", "bibliotheque", "archives")
    shutil.copytree(REEL / ".equipe", R / ".equipe", ignore=ign)
    shutil.copytree(REEL / ".claude", R / ".claude", ignore=shutil.ignore_patterns("__pycache__", "skills", "agents", "settings.local.json"))
    for f in (".mcp.json", "CLAUDE.md"):
        if (REEL / f).exists():
            shutil.copy2(REEL / f, R / f)
    (R / "Bureau" / "Informatique").mkdir(parents=True)
    if (REEL / "Bureau" / "Informatique" / "DOSSIER-TECHNIQUE.md").exists():
        shutil.copy2(REEL / "Bureau" / "Informatique" / "DOSSIER-TECHNIQUE.md", R / "Bureau" / "Informatique")
    (R / ".equipe" / "run").mkdir(parents=True, exist_ok=True)
    (R / ".equipe" / "run" / "sans-fond").write_text("tests", encoding="utf-8")  # aucun job de fond pendant les tests de hooks
    env = dict(os.environ)
    for k in ("CEREBRO_BACKGROUND", "CEREBRO_CONTROLE", "CEREBRO_DB", "CEREBRO_HOOK_TEST_ERREUR"):
        env.pop(k, None)
    env.update({"CEREBRO_ROOT": str(R), "CEREBRO_SANS_MODELE": "1", "CEREBRO_CLE_SAUVEGARDE": str(tmp / "cle.key"),
                "CEREBRO_TODAY": "2026-10-01", "PYTHONIOENCODING": "utf-8", "HOME": str(tmp / "home"), "USERPROFILE": str(tmp / "home")})
    (tmp / "home").mkdir()
    subprocess.run([PY, str(R / ".equipe/tests/fixtures/dossier_fictif.py")], env=env, capture_output=True, timeout=120)
    return tmp, R, env


TMP, R, ENV = preparer()
HOOK = R / ".claude" / "hooks" / "hook.py"
J = R / ".equipe" / "cerveau" / "journal"
INBOX = R / ".equipe" / "inbox"


def hook(evt, data, env_extra=None, attendu_json=None):
    e = dict(ENV)
    e.update(env_extra or {})
    t0 = time.time()
    r = subprocess.run([PY, str(HOOK), evt], input=json.dumps(data).encode("utf-8"), capture_output=True, env=e, cwd=str(R), timeout=20)
    ms = (time.time() - t0) * 1000
    assert r.returncode == 0, f"code {r.returncode} {r.stderr[-300:]}"
    assert ms < 2000, f"{evt} trop lent : {int(ms)} ms"
    out = r.stdout.decode("utf-8").strip()
    d = json.loads(out) if out else None
    if attendu_json:
        assert d and d["hookSpecificOutput"]["hookEventName"] == evt, out[:200]
    return d, ms


def lignes(p):
    return p.read_text(encoding="utf-8").splitlines() if p.exists() else []


def inbox_lignes():
    return sum(len(lignes(p)) for p in INBOX.glob("*.jsonl")) if INBOX.exists() else 0


def cerebro(*a):
    r = subprocess.run([PY, str(R / ".equipe/cerebro/cerebro.py"), *a], capture_output=True, text=True, env=ENV, timeout=60)
    return r.stdout


# ------------------------------------------------------------------ hooks
@test("SessionStart : contexte injecté ≤ 8 000 car., JSON valide, < 2 s")
def _():
    d, _ = hook("SessionStart", {"session_id": "t1", "source": "startup"}, attendu_json=True)
    ctx = d["hookSpecificOutput"]["additionalContext"]
    assert 0 < len(ctx) <= 8000 and "BRIEF" in ctx


@test("UserPromptSubmit : contexte du client cité ≤ 6 000 car. (critère 2)")
def _():
    d, _ = hook("UserPromptSubmit", {"session_id": "t1", "prompt": "Où en est la holding de Rochat ?"}, attendu_json=True)
    ctx = d["hookSpecificOutput"]["additionalContext"]
    assert len(ctx) <= 6000 and "Rochat" in ctx, ctx[:300]


@test("Stop : échange capturé dans inbox/ (ajout seul) (critère 3)")
def _():
    n0 = inbox_lignes()
    hook("UserPromptSubmit", {"session_id": "t2", "prompt": "Le dividende de la holding est décidé."})
    d, _ = hook("Stop", {"session_id": "t2", "last_assistant_message": "C'est noté, je prépare la déclaration."})
    assert d is None
    assert inbox_lignes() == n0 + 1
    rec = json.loads(lignes(sorted(INBOX.glob("*.jsonl"))[-1])[-1])
    assert rec["prompt"] == "Le dividende de la holding est décidé." and "déclaration" in rec["reponse"]


@test("« Entre nous » : aucune capture, aucune trace (critère 4)")
def _():
    n0 = inbox_lignes()
    v0 = len(lignes(J / "vocabulaire.jsonl"))
    d, _ = hook("UserPromptSubmit", {"session_id": "t3", "prompt": "Entre nous, je trouve ce client peu fiable."}, attendu_json=True)
    assert d["hookSpecificOutput"]["additionalContext"].startswith("MODE « ENTRE NOUS »")
    tour = json.loads((R / ".equipe/run/tour-t3.json").read_text(encoding="utf-8"))
    assert tour["entre_nous"] and tour["prompt"] == ""
    hook("Stop", {"session_id": "t3", "last_assistant_message": "Compris, je garde cela pour moi (fichier, git, hook)."})
    assert inbox_lignes() == n0, "capture écrite en mode entre nous"
    assert not (R / ".equipe/run/tour-t3.json").exists()
    assert len(lignes(J / "vocabulaire.jsonl")) == v0
    assert not any("peu fiable" in l for p in INBOX.glob("*.jsonl") for l in lignes(p))


@test("Filtre de vocabulaire : journalise sans bloquer ni réécrire (§4.1 (4), critère 39)")
def _():
    v0 = len(lignes(J / "vocabulaire.jsonl"))
    rep = "J'ai mis à jour le fichier settings.json et poussé sur git."
    hook("UserPromptSubmit", {"session_id": "t4", "prompt": "Merci pour le mémo."})
    d, _ = hook("Stop", {"session_id": "t4", "last_assistant_message": rep})
    assert d is None, "le hook Stop ne doit rien renvoyer"
    l = lignes(J / "vocabulaire.jsonl")
    assert len(l) == v0 + 1 and "git" in json.loads(l[-1])["termes"]
    rec = json.loads(lignes(sorted(INBOX.glob("*.jsonl"))[-1])[-1])
    assert rec["reponse"] == rep, "réponse réécrite"


@test("Filtre de vocabulaire : ignoré si l'interlocuteur est technicien")
def _():
    v0 = len(lignes(J / "vocabulaire.jsonl"))
    hook("UserPromptSubmit", {"session_id": "t5", "prompt": "Je suis informaticien : vérifie le settings.json et fais un git status."})
    hook("Stop", {"session_id": "t5", "last_assistant_message": "Le fichier settings.json est valide, git est propre."})
    assert len(lignes(J / "vocabulaire.jsonl")) == v0


@test("PreCompact : snapshot de l'état de session")
def _():
    hook("PreCompact", {"session_id": "t2", "trigger": "auto"})
    t = (R / ".equipe/cerveau/session/etat.md").read_text(encoding="utf-8")
    assert "État de session" in t and len(t) <= 1300


@test("PostToolUse : fichier à en-tête id: → marqué « à régénérer »")
def _():
    con = sqlite3.connect(str(R / ".equipe/cerebro/cerebro.db"))
    oid, chemin = con.execute("SELECT id, chemin FROM objets WHERE chemin LIKE '%.md' AND type='personne' LIMIT 1").fetchone()
    con.execute("UPDATE objets SET a_regenerer=0 WHERE id=?", (oid,)); con.commit()
    hook("PostToolUse", {"session_id": "t6", "tool_name": "Edit", "tool_input": {"file_path": str(R / chemin)}})
    assert con.execute("SELECT a_regenerer FROM objets WHERE id=?", (oid,)).fetchone()[0] == 1
    con.close()


@test("SessionEnd : succès vide, job de fond demandé (non lancé en test)")
def _():
    d, _ = hook("SessionEnd", {"session_id": "t2", "reason": "exit"})
    assert d is None
    assert any('"fin-de-session"' in l for l in lignes(J / "fond.jsonl"))


@test("Stop : greffier groupé déclenché tous les 15 échanges")
def _():
    (R / ".equipe/run/compteur-echanges.json").write_text('{"n": 13}', encoding="utf-8")
    n0 = sum('"greffier"' in l for l in lignes(J / "fond.jsonl"))
    hook("Stop", {"session_id": "t7", "last_assistant_message": "ok"})
    assert sum('"greffier"' in l for l in lignes(J / "fond.jsonl")) == n0
    hook("Stop", {"session_id": "t7", "last_assistant_message": "ok"})
    assert sum('"greffier"' in l for l in lignes(J / "fond.jsonl")) == n0 + 1


@test("Erreur interne simulée → succès vide + journal (critère 39)")
def _():
    n0 = len(lignes(J / "hooks-erreurs.jsonl"))
    for evt in ("SessionStart", "UserPromptSubmit", "Stop", "PreCompact", "SessionEnd", "PostToolUse"):
        d, _ = hook(evt, {"session_id": "t8", "prompt": "x"}, {"CEREBRO_HOOK_TEST_ERREUR": "1"})
        assert d is None
    assert len(lignes(J / "hooks-erreurs.jsonl")) == n0 + 6


@test("Base illisible → succès vide + journal (aucun blocage)")
def _():
    n0 = len(lignes(J / "hooks-erreurs.jsonl"))
    d, _ = hook("SessionStart", {"session_id": "t9"}, {"CEREBRO_DB": str(R / ".equipe")})  # un dossier n'est pas une base
    assert d is None and len(lignes(J / "hooks-erreurs.jsonl")) == n0 + 1


@test("Entrée vide ou non JSON → succès")
def _():
    for raw in (b"", b"pas du json"):
        r = subprocess.run([PY, str(HOOK), "Stop"], input=raw, capture_output=True, env=ENV, timeout=10)
        assert r.returncode == 0 and not r.stdout.strip()


@test("CEREBRO_BACKGROUND défini → sortie immédiate, rien écrit (anti-récursion)")
def _():
    n0 = inbox_lignes()
    d, ms = hook("Stop", {"session_id": "t10", "last_assistant_message": "x"}, {"CEREBRO_BACKGROUND": "1"})
    assert d is None and inbox_lignes() == n0 and ms < 1000


@test("Lancement détaché : le hook rend la main sans attendre le job (< 2 s)")
def _():
    (R / ".equipe/run/sans-fond").unlink()
    try:
        d, ms = hook("SessionStart", {"session_id": "t11", "source": "startup"}, attendu_json=True)
        assert ms < 2000
        assert any('"cycle-rattrapage"' in l and '"lancé"' in l for l in lignes(J / "fond.jsonl"))
    finally:
        (R / ".equipe/run/sans-fond").write_text("tests", encoding="utf-8")
        for _ in range(600):  # laisse le cycle de fond démarrer puis finir avant les tests suivants
            fins = [l for l in lignes(J / "entretien.jsonl") if '"rattrapage"' in l and ('"fin"' in l or "déjà en cours" in l)]
            if fins and not (R / ".equipe/run/entretien.lock").exists():
                break
            time.sleep(0.2)


# ------------------------------------------------------------------ réglages
@test("settings.json : JSON valide, bypassPermissions, aucune liste deny, aucun hook de refus (critère 39)")
def _():
    s = json.loads((REEL / ".claude/settings.json").read_text(encoding="utf-8"))
    p = s["permissions"]
    assert p["defaultMode"] == "bypassPermissions" and not p.get("deny") and not p.get("ask")
    for x in ("Read", "Edit", "Write", "Bash(cerebro:*)", "Bash(git:*)", "Bash(python:*)", "Bash(claude:*)", "Bash(npx:*)",
              "Bash(uvx:*)", "Bash(pip:*)", "Bash(npm:*)", "mcp__cerebro"):
        assert x in p["allow"], x
    ev = set(s["hooks"])
    assert ev == {"SessionStart", "UserPromptSubmit", "Stop", "PreCompact", "SessionEnd", "PostToolUse"}, ev
    assert not ev & {"PreToolUse", "PermissionRequest"}
    for groupes in s["hooks"].values():
        for g in groupes:
            for h in g["hooks"]:
                assert h["args"][0].endswith(".claude/hooks/hook.py") and h["timeout"] <= 15
    m = json.loads((REEL / ".mcp.json").read_text(encoding="utf-8"))
    assert "cerebro" in m["mcpServers"]


@test("Validation (§0.10) sans session : JSON + hooks seuls en succès < 2 s, copie valide")
def _():
    r = subprocess.run([PY, str(R / ".equipe/scripts/valider_config.py"), "--sans-session", "--copier"], capture_output=True, text=True, env=ENV, timeout=120)
    d = json.loads(r.stdout.strip().splitlines()[-1])
    assert d["ok"], d
    assert all(ms < 2000 for ms in d["etapes"]["b_hooks"].values())
    assert (R / ".equipe/scripts/config-valide/settings.json").exists()


@test("settings.json corrompu → restauré au lancement (critère 38)")
def _():
    bon = (R / ".claude/settings.json").read_text(encoding="utf-8")
    (R / ".claude/settings.json").write_text('{"permissions": {"deny": ["Bash"]}, "hooks": ', encoding="utf-8")
    r = subprocess.run([PY, str(R / ".equipe/scripts/valider_config.py"), "--lancement"], capture_output=True, text=True, env=ENV, timeout=60)
    d = json.loads(r.stdout.strip().splitlines()[-1])
    assert d["ok"] and ".claude/settings.json" in d["restaures"], d
    assert (R / ".claude/settings.json").read_text(encoding="utf-8") == bon


@test("Hook volontairement en échec → validation refusée, hook restauré (critère 38)")
def _():
    bon = HOOK.read_text(encoding="utf-8")
    HOOK.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    r = subprocess.run([PY, str(R / ".equipe/scripts/valider_config.py"), "--sans-session"], capture_output=True, text=True, env=ENV, timeout=60)
    d = json.loads(r.stdout.strip().splitlines()[-1])
    assert not d["ok"] and ".claude/hooks/hook.py" in d["restaures"], d
    assert HOOK.read_text(encoding="utf-8") == bon


@test("Lanceur Linux : configuration corrompue restaurée, Claude lancé en mode automatique (critères 1, 38)")
def _():
    fb = TMP / "faux-bin"
    fb.mkdir(exist_ok=True)
    trace = TMP / "claude-args.txt"
    (fb / "claude").write_text(f'#!/bin/sh\necho "$@" >> "{trace}"\nexit 0\n', encoding="utf-8")
    os.chmod(fb / "claude", 0o755)
    bon = (R / ".claude/settings.json").read_text(encoding="utf-8")
    (R / ".claude/settings.json").write_text("{ cassé", encoding="utf-8")
    e = dict(ENV)
    e["PATH"] = str(fb) + os.pathsep + e["PATH"]
    e["CEREBRO_PYTHON"] = PY
    r = subprocess.run(["bash", str(R / ".equipe/scripts/lanceurs/mon-equipe.sh")], capture_output=True, text=True, env=e, timeout=120, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stderr[-300:]
    assert (R / ".claude/settings.json").read_text(encoding="utf-8") == bon
    assert "--dangerously-skip-permissions" in trace.read_text(encoding="utf-8")


@test("Intendant : liste deny et hook PreToolUse neutralisés (remplacés par une observation)")
def _():
    sys.path.insert(0, str(R / ".equipe/scripts/entretien"))
    os.environ["CEREBRO_ROOT"] = str(R)
    import intendant
    p = TMP / "settings-test.json"
    p.write_text(json.dumps({"permissions": {"defaultMode": "default", "deny": ["Bash(rm:*)"]},
                             "hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "exit 2"}]}],
                                       "PermissionRequest": [{"hooks": [{"type": "command", "command": "x"}]}]}}), encoding="utf-8")
    p = p.rename(TMP / "settings.json")
    f = intendant.desarmer(p)
    d = json.loads(p.read_text(encoding="utf-8"))
    assert "deny" not in d["permissions"] and d["permissions"]["defaultMode"] == "bypassPermissions", d
    assert "PermissionRequest" not in d["hooks"]
    assert d["hooks"]["PreToolUse"][0]["hooks"][0]["args"][-1] == "Observer"
    assert f


# ------------------------------------------------------------------ entretien
@test("Cycle --une-passe : file triée, tâches de base, ligne « rattrapé », verrou rendu (critère 8)")
def _():
    con = sqlite3.connect(str(R / ".equipe/cerebro/cerebro.db"))
    con.execute("UPDATE objets SET a_regenerer=1 WHERE type='personne'"); con.commit()
    r = subprocess.run([PY, str(R / ".equipe/scripts/entretien/cycle.py"), "--une-passe"], capture_output=True, text=True, env=ENV, timeout=300)
    d = json.loads(r.stdout.strip().splitlines()[-1])
    assert d.get("taches") and d["taches"][0] == "intendant" and "regen" in d["taches"], (d, lignes(J / "entretien.jsonl")[-4:], (R / ".equipe/run/entretien.lock").read_text() if (R / ".equipe/run/entretien.lock").exists() else None)
    assert con.execute("SELECT COUNT(*) FROM objets WHERE a_regenerer=1").fetchone()[0] == 0
    ratt = con.execute("SELECT valeur FROM etat WHERE cle='rattrape'").fetchone()
    assert ratt and "fiches mises à jour" in ratt[0]
    assert not (R / ".equipe/run/entretien.lock").exists()
    con.close()


@test("Cycle --complet : sauvegarde chiffrée, restauration testée, export, santé, brief (critère 8)")
def _():
    r = subprocess.run([PY, str(R / ".equipe/scripts/entretien/cycle.py"), "--complet", "--budget-min", "3"], capture_output=True, text=True, env=ENV, timeout=400)
    d = json.loads(r.stdout.strip().splitlines()[-1])
    for t in ("sauvegarde", "export", "sante", "brief", "commit_push"):  # test_restauration : cadence 30 j, vérifiée ci-dessous
        assert t in d["taches"], (t, d)
    sv = list((R / ".equipe/cerebro/sauvegardes").glob("cerebro-*.zip.chiffre"))
    assert sv, "aucune sauvegarde chiffrée"
    sys.path.insert(0, str(R / ".equipe/scripts/entretien"))
    os.environ["CEREBRO_CLE_SAUVEGARDE"] = ENV["CEREBRO_CLE_SAUVEGARDE"]
    import cycle
    with tempfile.TemporaryDirectory() as t:
        db = cycle.restaurer_sauvegarde(sorted(sv)[-1], t)
        c = sqlite3.connect(str(db))
        assert c.execute("SELECT COUNT(*) FROM objets").fetchone()[0] > 0
        c.close()
    # file : tâches à modèle sans script laissées en file, rien en échec
    con = sqlite3.connect(str(R / ".equipe/cerebro/cerebro.db"))
    assert con.execute("SELECT COUNT(*) FROM file_entretien WHERE statut='echec'").fetchone()[0] == 0
    con.close()


@test("Verrou : un seul cycle à la fois ; verrou d'un processus mort repris")
def _():
    lock = R / ".equipe/run/entretien.lock"
    lock.write_text(json.dumps({"pid": os.getpid(), "depuis": time.time()}), encoding="utf-8")
    r = subprocess.run([PY, str(R / ".equipe/scripts/entretien/cycle.py"), "--une-passe"], capture_output=True, text=True, env=ENV, timeout=60)
    assert json.loads(r.stdout.strip().splitlines()[-1]).get("deja_en_cours")
    lock.write_text(json.dumps({"pid": 999999, "depuis": time.time()}), encoding="utf-8")
    r = subprocess.run([PY, str(R / ".equipe/scripts/entretien/cycle.py"), "--une-passe"], capture_output=True, text=True, env=ENV, timeout=120)
    assert "taches" in json.loads(r.stdout.strip().splitlines()[-1])
    assert not lock.exists()


@test("Pause : Mustafa écrit → l'incrément s'interrompt")
def _():
    (R / ".equipe/run/mustafa-ecrit").write_text("x", encoding="utf-8")
    try:
        r = subprocess.run([PY, str(R / ".equipe/scripts/entretien/cycle.py"), "--une-passe"], capture_output=True, text=True, env=ENV, timeout=60)
        assert json.loads(r.stdout.strip().splitlines()[-1])["taches"] == []
    finally:
        (R / ".equipe/run/mustafa-ecrit").unlink()


@test("Greffier --simuler : lot préparé depuis les captures non classées, sans appel de modèle")
def _():
    r = subprocess.run([PY, str(R / ".equipe/scripts/entretien/greffier.py"), "--simuler"], capture_output=True, text=True, env=ENV, timeout=60)
    d = json.loads(r.stdout.strip().splitlines()[-1])
    assert d.get("simule") and d["captures"] >= 1, d


if __name__ == "__main__":
    for t in TESTS:
        t()
    ko = [r for r in RES if not r[1]]
    print(f"\n{len(RES) - len(ko)}/{len(RES)} OK" + ("" if not ko else " — ÉCHEC : " + ", ".join(r[0] for r in ko)))
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1 if ko else 0)
