#!/usr/bin/env python3
"""Banc d'essai de bout en bout : vraies sessions Claude Code dans une COPIE JETABLE du dossier livré (jamais dans le dossier
réel), avec les hooks actifs, puis analyse de chaque tour : lectures (ciblées par le sommaire ou non), tokens, jargon,
chemins/outils montrés, questions posées, confirmations demandées. Aucune trace dans le dossier livré.

  python .team/tests/e2e/bench.py --scenarios scenarios.yaml [--modele opus] [--garder]
Sortie : rapport JSON + markdown dans le dossier temporaire (chemin affiché), résumé sur stdout."""
import os, sys, json, re, shutil, subprocess, tempfile, time, argparse
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))

JARGON = re.compile(r"\b(fichiers?|chemins?|scripts?|terminal|hooks?|MCP|tokens?|API|JSON|YAML|SQLite|base de données|git|commit|push|"
                    r"skills?|plugins?|sous-agents?|agents?|prompt|contexte|cerebro|CLI|commande|bash|python|log|erreur technique|"
                    r"configuration|permission|\.md\b|\.py\b|\.team|SOMMAIRE|identifiant)\b", re.I)
CHEMIN = re.compile(r"(\.team/|\.claude/|[A-Za-z]:\\|/home/|/tmp/|\bBureau/[A-Za-z-]+/)")
ID = re.compile(r"\b(?:DOC|POS|LBA|DL|DT|CT|RD|MET|BIB|C|E|P|D|M|N|Q)-\d{3,4}\b")
CONFIRM = re.compile(r"(voulez-vous que je|souhaitez-vous que je|dois-je|je (crée|prépare|rédige|lance)[^.?!]{0,60}\?|on y va \?|je m'en occupe \?)", re.I)

def copie_jetable():
    """copie des fichiers suivis par git (= ce qui est livré) dans un dossier temporaire, puis init comme l'installateur"""
    tmp = Path(tempfile.mkdtemp(prefix="banc-mustafa-"))
    racine = tmp / "jurix"
    files = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True).stdout.decode().split("\0")
    for f in filter(None, files):
        src, dst = REPO / f, racine / f
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    env = env_propre(racine)
    subprocess.run([sys.executable, str(racine / ".team/cerebro/cerebro.py"), "init", "--importer-si-vide"], env=env, capture_output=True)
    subprocess.run(["git", "init", "-q"], cwd=racine)
    etat_final(racine)
    # confiance du dossier (comme l'installateur) — modifie ~/.claude.json du conteneur, pas le livrable
    cj = Path.home() / ".claude.json"
    try:
        d = json.loads(cj.read_text()) if cj.exists() else {}
        d.setdefault("projects", {}).setdefault(str(racine), {})["hasTrustDialogAccepted"] = True
        cj.write_text(json.dumps(d, indent=2))
    except Exception as e:
        print("confiance non posée:", e, file=sys.stderr)
    return tmp, racine

def env_propre(racine, today=None):
    """environnement d'un poste neuf : aucune variable héritée de la session appelante (sessions indépendantes)"""
    env = {k: v for k, v in os.environ.items() if not (k.startswith("CLAUDE_CODE_") or k in ("CLAUDECODE", "CEREBRO_BACKGROUND", "CEREBRO_DB"))}
    env["CEREBRO_ROOT"] = str(racine)
    if today:
        env["CEREBRO_TODAY"] = today
    return env

def etat_final(racine):
    """le dossier tel qu'il sera livré : construction achevée, sans consigne de reprise (constitution §3)"""
    cm = racine / ".team/brain/session/construction.md"
    if cm.exists() and "construction: achevée" not in cm.read_text(encoding="utf-8"):
        cm.write_text(cm.read_text(encoding="utf-8") + "\nconstruction: achevée\n", encoding="utf-8")
    c = racine / "CLAUDE.md"
    t = c.read_text(encoding="utf-8")
    if "CONSIGNE DE REPRISE" in t:
        c.write_text(t.split("## CONSIGNE DE REPRISE")[0].rstrip() + "\n", encoding="utf-8")

def charger_fictif(racine, today):
    env = env_propre(racine, today)
    r = subprocess.run([sys.executable, str(racine / ".team/tests/fixtures/fictional_case.py")], env=env, capture_output=True, text=True)
    return r.stdout

def tour(racine, message, nouvelle_session, modele, today, timeout=900):
    """un message ; nouvelle_session=False → --continue (même conversation)"""
    cmd = ["claude", "-p", message, "--output-format", "stream-json", "--verbose", "--dangerously-skip-permissions"]
    if modele:
        cmd += ["--model", modele]
    if not nouvelle_session:
        cmd.insert(1, "--continue")
    env = env_propre(racine, today)
    t0 = time.time()
    r = subprocess.run(cmd, cwd=racine, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
    ms = int((time.time() - t0) * 1000)
    evs = []
    for l in r.stdout.decode("utf-8", "ignore").splitlines():
        try:
            evs.append(json.loads(l))
        except Exception:
            pass
    return analyser(evs, message, ms, r.stderr.decode("utf-8", "ignore")[-1500:])

def analyser(evs, message, ms, stderr):
    lectures, bash, cerebro, autres, sous_agents = [], [], [], [], 0
    texte, usage, resultat, refus = "", {}, None, []
    for e in evs:
        if e.get("type") == "assistant":
            for c in e.get("message", {}).get("content", []):
                if c.get("type") == "tool_use":
                    n, i = c.get("name"), c.get("input", {})
                    if n == "Read":
                        lectures.append({"fichier": i.get("file_path", ""), "cible": bool(i.get("offset") or i.get("limit"))})
                    elif n == "Bash":
                        cmd = i.get("command", "")
                        (cerebro if "cerebro" in cmd else bash).append(cmd[:200])
                    elif n.startswith("mcp__cerebro"):
                        cerebro.append(n)
                    elif n in ("Task", "Agent"):
                        sous_agents += 1
                    else:
                        autres.append(n)
        if e.get("type") == "result":
            resultat = e
            texte = e.get("result") or ""
            usage = e.get("usage") or {}
            refus = e.get("permission_denials") or []
    larges = [l for l in lectures if not l["cible"] and not re.search(r"(SUMMARY|summaries/|SKILL\.md|\.claude/agents/)", l["fichier"])]
    listing = [b for b in bash if re.search(r"(^|[;&|]\s*)(ls|find|tree|dir|cat|head|tail|sed|grep|rg|less|more)\b", b)]
    questions = [q.strip() for q in re.findall(r"[^.!?\n]*\?", texte) if len(q.strip()) > 12]
    tok_in = int(usage.get("input_tokens", 0)) + int(usage.get("cache_read_input_tokens", 0)) + int(usage.get("cache_creation_input_tokens", 0))
    return {
        "message": message, "ms": ms, "texte": texte,
        "tokens_entree": tok_in, "tokens_sortie": int(usage.get("output_tokens", 0)), "cout_usd": (resultat or {}).get("total_cost_usd"),
        "lectures": len(lectures), "lectures_larges": larges, "listings": listing, "appels_cerebro": len(cerebro), "sous_agents": sous_agents,
        "jargon": sorted({m.group(0).lower() for m in JARGON.finditer(texte)}), "chemins_montres": CHEMIN.findall(texte),
        "identifiants_montres": sorted(set(ID.findall(texte))), "questions": questions, "confirmations": [m.group(0) for m in CONFIRM.finditer(texte)],
        "refus_permission": refus, "erreur": bool((resultat or {}).get("is_error")) or resultat is None, "stderr": stderr if resultat is None else "",
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", required=True)
    ap.add_argument("--modele", default=None)
    import datetime as _dt
    ap.add_argument("--today", default=_dt.date.today().isoformat(), help="jour simulé (défaut : aujourd'hui, cohérent avec la date que voit le modèle)")
    ap.add_argument("--garder", action="store_true")
    ap.add_argument("--seulement", default=None, help="ids de scénarios séparés par des virgules")
    a = ap.parse_args()
    import yaml
    sc = yaml.safe_load(open(a.scenarios, encoding="utf-8"))
    tmp, racine = copie_jetable()
    print("racine jetable:", racine, flush=True)
    if sc.get("fictif", True):
        charger_fictif(racine, a.today)
    res = []
    for s in sc["scenarios"]:
        if a.seulement and s["id"] not in a.seulement.split(","):
            continue
        if s.get("preparer_depot"):
            import docx
            d = docx.Document()
            d.add_heading("Procès-verbal de l'assemblée générale ordinaire de Rochat Holding SA (FICTIF)", 1)
            for t in ["Date : 30 septembre 2026, Échallens. Présents : Jean-Marc Rochat (60 %), Sandrine Vuilleumier (40 %), 100 % du capital représenté.",
                      "1. Approbation du rapport de gestion et des comptes annuels 2025 : approuvés à l'unanimité.",
                      "2. Emploi du bénéfice : dividende de CHF 200'000.– brut, payable le 30 septembre 2026 ; solde reporté.",
                      "3. Décharge au conseil d'administration : donnée à l'unanimité, les administrateurs ne prenant pas part au vote.",
                      "4. Organe de révision : renonciation (opting-out) confirmée."]:
                d.add_paragraph(t)
            (racine / "Bureau" / "A-deposer").mkdir(parents=True, exist_ok=True)
            d.save(str(racine / "Bureau" / "A-deposer" / "PV-AG-2026-Rochat-Holding.docx"))
        for k, m in enumerate(s["messages"]):
            nouvelle = (k == 0 and s.get("nouvelle_session", True)) or (isinstance(m, dict) and m.get("nouvelle_session"))
            txt = m["texte"] if isinstance(m, dict) else m
            day = (m.get("today") if isinstance(m, dict) else None) or s.get("today") or a.today
            r = tour(racine, txt, nouvelle, a.modele, day)
            r.update(scenario=s["id"], tour=k + 1, nouvelle_session=bool(nouvelle), attendu=s.get("attendu", ""))
            res.append(r)
            print(f"[{s['id']} t{k+1}] {r['ms']//1000}s in={r['tokens_entree']} out={r['tokens_sortie']} lect={r['lectures']} larges={len(r['lectures_larges'])} "
                  f"cerebro={r['appels_cerebro']} jargon={r['jargon']} q={len(r['questions'])} confirm={len(r['confirmations'])} err={r['erreur']}", flush=True)
    out = tmp / "rapport-banc.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("rapport:", out)
    if not a.garder:
        shutil.rmtree(racine, ignore_errors=True)

if __name__ == "__main__":
    main()
