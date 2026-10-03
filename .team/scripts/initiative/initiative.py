#!/usr/bin/env python3
"""Boucle d'initiative (§11) : à chaque ouverture et à chaque cycle complet, UN appel groupé sur le modèle intermédiaire,
limité aux mails qui attendent une réponse sous 48 h, aux rendez-vous des prochaines 24 h, aux documents de délais
entrés dans leur préavis, aux dépôts à commenter et aux changements de droit récents. Rien à faire → aucun appel (loi 3).
Usage : initiative.py [--simuler] [--max 8]"""
import sys, os, json, subprocess, time, datetime as dt, tempfile
from pathlib import Path

ROOT = Path(os.environ.get("CEREBRO_ROOT") or Path(__file__).resolve().parents[3])
sys.path.insert(0, str(ROOT / ".team" / "cerebro"))
os.environ.setdefault("CEREBRO_ROOT", str(ROOT))
import shutil
from cb import core, config as K, files as F, brief as B, cardinal as X
core.utf8_io()
from cb.core import db, iso, today, cut, journal
from cb.summaries import ligne
from cb.objects import get

VERROU = ROOT / ".team" / "run" / "initiative.lock"

def collecter(maxi=8):
    con = db()
    t, d1, d2, d3 = iso(), (today() + dt.timedelta(days=1)).isoformat(), (today() + dt.timedelta(days=2)).isoformat(), (today() + dt.timedelta(days=3)).isoformat()
    items = []
    for r in con.execute("SELECT * FROM objets WHERE type='mail' AND statut='attente' AND COALESCE(prochaine_date,?)<=? ORDER BY prochaine_date", (t, d2)):
        items.append(("mail en attente", dict(r)))
    for r in con.execute("SELECT * FROM objets WHERE type='rdv' AND statut IN ('fiche à préparer','actif') AND prochaine_date BETWEEN ? AND ?", (t, d1)):
        items.append(("rendez-vous dans les 24 h", dict(r)))
    for r in con.execute("SELECT * FROM objets WHERE type='document' AND statut='à préparer' AND prochaine_date<=? ORDER BY prochaine_date", (d3,)):
        items.append(("document à préparer pour un délai", dict(r)))
    q = [dict(r) for r in con.execute("SELECT * FROM file_entretien WHERE statut='attente' AND tache IN ('ingestion_commentaire','lecture_modele','alerte_changement') ORDER BY priorite, n LIMIT 10")]
    for j in q:
        o = get(j["arg"])
        if o:
            items.append(({"ingestion_commentaire": "document déposé à commenter", "lecture_modele": "document déposé à commenter",
                           "alerte_changement": "changement de droit"}[j["tache"]], {**o, "_files": [j["n"]]}))
    seen, out = {}, []
    for k, o in items:
        if o["id"] in seen:
            seen[o["id"]].setdefault("_files", []).extend(o.get("_files", []))
            continue
        seen[o["id"]] = o; out.append((k, o))
    return out[:maxi]

def prompt(items):
    mission = (Path(__file__).parent / "mission.md").read_text(encoding="utf-8")
    lignes = [f"- {k} : {ligne(o)}" + (f" · client {o['client']}" if o.get("client") else "") for k, o in items]
    return (X.bloc() + "\n\n" + mission + f"\n\nToday: {iso()} (Europe/Zurich). Items to handle ({len(items)}):\n" + "\n".join(lignes)
            + "\n\nCall the CLI with: " + ("python .team/cerebro/cerebro.py" if os.name == "nt" else ".team/bin/cerebro") + " <commande>.")

def lancer(p):
    modele = K.get("models.intermediaire") or "sonnet"
    env = {**os.environ, "CEREBRO_BACKGROUND": "1", "CEREBRO_ROOT": str(ROOT)}
    sys.path.insert(0, str(ROOT / ".team" / "scripts" / "maintenance"))
    import background as fond  # vrai programme Claude, jamais la commande de l'équipe (.team/bin, qui ouvrirait une session)
    exe = os.environ.get("CEREBRO_CLAUDE") or fond.claude_exe() or "claude"
    ok_m, raison = fond.modele_permis()  # réserve d'usage de Mustafa et activité en cours : jamais sacrifiées au fond
    if not ok_m:
        journal("initiative", statut="reportée", raison=raison)
        return {"is_error": True, "reporte": raison, "result": raison}, 0, 0
    cmd = [exe, "-p", "--model", modele, "--output-format", "json", "--permission-mode", "bypassPermissions",
           "--max-budget-usd", str(fond._reglage("background.plafond_initiative", 1.0)),
           "--allowedTools", "Read,Write,Edit,Bash(cerebro:*),Bash(.team/bin/cerebro:*),Bash(python:*),Bash(python3:*)"]
    t0 = time.time()
    sortie, err, code, arret = fond.appeler_claude(cmd, p, str(ROOT), env, 1500)
    ms = int((time.time() - t0) * 1000)
    if arret:
        if "délai" in arret:
            F.incident_add("initiative", "boucle d'initiative trop longue (25 min)", "reprise au prochain cycle")
        return {"is_error": True, "reporte": arret, "result": arret}, ms, 0
    try:
        res = json.loads(sortie)
    except Exception:
        res = {"is_error": True, "result": (sortie or "")[-500:], "stderr": (err or "")[-500:]}
    u = res.get("usage") or {}
    tok = int(u.get("input_tokens", 0)) + int(u.get("output_tokens", 0)) + int(u.get("cache_creation_input_tokens", 0))
    F.mesure("initiative", "boucle", modele, tok, ms, 0 if res.get("is_error") else 1)
    return res, ms, tok

def main():
    simuler = "--simuler" in sys.argv
    maxi = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 8
    VERROU.parent.mkdir(parents=True, exist_ok=True)
    if VERROU.exists() and time.time() - VERROU.stat().st_mtime < 1800:
        print(json.dumps({"statut": "déjà en cours"})); return
    items = collecter(maxi)
    if not items:
        journal("initiative", statut="rien à faire")
        print(json.dumps({"statut": "rien à faire"})); return
    p = prompt(items)
    if simuler:
        print(json.dumps({"statut": "simulé", "elements": [o["id"] for _, o in items], "prompt_car": len(p)}, ensure_ascii=False)); return
    VERROU.write_text(str(os.getpid()))
    try:
        journal("initiative", statut="début", elements=[o["id"] for _, o in items])
        res, ms, tok = lancer(p)
        if res.get("reporte"):  # Mustafa travaille ou sa réserve baisse : rien n'est perdu, reprise au prochain temps mort
            journal("initiative", statut="reportée", raison=res["reporte"])
            print(json.dumps({"statut": "reporté", "raison": res["reporte"]}, ensure_ascii=False))
            return
        ok = not res.get("is_error")
        if ok:
            for _, o in items:
                for n in o.get("_files", []):
                    B.queue_done(n)
        else:
            F.incident_add("initiative", "boucle d'initiative en échec", cut(str(res.get("result")), 200))
        journal("initiative", statut="fin", ok=ok, ms=ms, tokens=tok)
        print(json.dumps({"statut": "fait" if ok else "échec", "elements": len(items), "ms": ms, "tokens": tok}, ensure_ascii=False))
    finally:
        VERROU.unlink(missing_ok=True)

if __name__ == "__main__":
    if os.environ.get("CEREBRO_BACKGROUND") and "--force" not in sys.argv and "--simuler" not in sys.argv:
        pass  # lancé par un rôle de fond : on reste permis (le verrou empêche la récursion)
    try:
        main()
    except Exception as e:
        journal("initiative", erreur=repr(e))
        print(json.dumps({"erreur": repr(e)}))
