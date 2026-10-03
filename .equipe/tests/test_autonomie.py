#!/usr/bin/env python3
"""Tests du chantier « autonomie » (critères 16, 21, 26, 27, 30, 35, 39 ; écarts 7, 10, 13, 18, 20) : routines, fabrique,
découverte, recalculs, missions de fond, budget frugal, opération dédiée de changement des règles, réconciliation.
Exécution : python .equipe/tests/test_autonomie.py [--avec-modele]   → une ligne OK/ÉCHEC par test, code 0 si tout passe.
Racine jetable (copie de .equipe, .claude, CLAUDE.md, .mcp.json + dossier fictif) : la base réelle n'est jamais touchée.
Aucun appel de modèle : un faux programme « claude » (script Python) joue les réponses. --avec-modele ajoute UN test réel de
la fabrique (modèle intermédiaire) sur le besoin « tous les lundis : liste des délais de la semaine »."""
import os, sys, json, time, shutil, sqlite3, tempfile, subprocess, datetime as dt
from pathlib import Path

REEL = Path(__file__).resolve().parents[2]
PY = sys.executable
AVEC_MODELE = "--avec-modele" in sys.argv
VRAI_HOME = {k: os.environ[k] for k in ("HOME", "USERPROFILE") if k in os.environ}  # identifiants de claude (test réel seulement)
RES, TESTS = [], []
LUNDI = "2026-10-05"


def test(nom):
    def deco(f):
        def run():
            t0 = time.time()
            try:
                f()
                RES.append((nom, True))
                print(f"OK     {nom} ({int((time.time() - t0) * 1000)} ms)")
            except Exception as e:
                RES.append((nom, False))
                print(f"ÉCHEC  {nom} : {e!r}")
        TESTS.append(run)
        return run
    return deco


FAUX_CLAUDE = r'''
import sys, os, json, pathlib
args = sys.argv[1:]
log = os.environ.get("FAUX_CLAUDE_LOG")
entree = "" if (args[:1] in (["plugin"], ["mcp"])) else sys.stdin.read()
if log:
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"args": args, "prompt_car": len(entree)}) + "\n")
mode = os.environ.get("FAUX_CLAUDE_MODE", "ok")
if args[:2] == ["plugin", "list"]:
    print(json.dumps({"installed": [], "available": [
        {"pluginId": "swiss-law@claude-for-legal", "name": "swiss-law", "description": "Swiss legal research: Fedlex statutes, caselaw", "marketplaceName": "claude-for-legal"},
        {"pluginId": "casino@x", "name": "casino", "description": "crypto casino game", "marketplaceName": "x"}]})); sys.exit(0)
if args[:2] == ["plugin", "marketplace"]:
    print("[]"); sys.exit(0)
usage = {"input_tokens": 1000, "output_tokens": 200, "cache_creation_input_tokens": 0}
if mode == "limite":
    print(json.dumps({"type": "result", "subtype": "error_during_execution", "is_error": True, "result": "Claude AI usage limit reached|1760000000", "usage": usage})); sys.exit(1)
res = '{"ok": true}'
if mode == "fabrique" and "Besoin unique" in entree:
    d = pathlib.Path(os.environ["CEREBRO_ROOT"]) / ".claude" / "skills" / "liste-fictive"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text("---\nname: liste-fictive\ndescription: Liste fictive de test : délais de la semaine, déclenchée le lundi.\n---\n\n# liste-fictive (machine)\n\n## Quand l'utiliser\ntest.\n", encoding="utf-8")
    res = '{"forme": "skill", "fichiers": [".claude/skills/liste-fictive/SKILL.md"], "routine": null, "raison": "test"}'
if mode == "fabrique-casse" and "Besoin unique" in entree:
    d = pathlib.Path(os.environ["CEREBRO_ROOT"]) / ".claude" / "skills" / "Mauvais Nom"
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text("---\nname: Mauvais Nom\n---\n# x\n", encoding="utf-8")
    res = '{"forme": "skill"}'
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "fait\n" + res, "usage": usage, "total_cost_usd": 0}))
'''


def preparer():
    tmp = Path(tempfile.mkdtemp(prefix="autonomie-"))
    R = tmp / "racine"
    R.mkdir()
    ign = shutil.ignore_patterns("cerebro.db*", "__pycache__", "run", "sauvegardes", "*.jsonl", "archives", "cache", "copies", "exports")
    shutil.copytree(REEL / ".equipe", R / ".equipe", ignore=ign)
    biblio = R / ".equipe" / "bibliotheque"
    for p in list(biblio.iterdir()) if biblio.exists() else []:
        shutil.rmtree(p) if p.is_dir() else p.unlink()  # textes officiels : inutiles ici
    shutil.copytree(REEL / ".claude", R / ".claude", ignore=shutil.ignore_patterns("__pycache__", "settings.local.json"))
    for f in (".mcp.json", "CLAUDE.md"):
        if (REEL / f).exists():
            shutil.copy2(REEL / f, R / f)
    (R / "Bureau" / "Informatique").mkdir(parents=True)
    for f in (REEL / "Bureau" / "Informatique").glob("*.md"):
        shutil.copy2(f, R / "Bureau" / "Informatique")
    (R / ".equipe" / "run").mkdir(parents=True, exist_ok=True)
    (tmp / "home").mkdir()
    faux = tmp / "faux_claude.py"
    faux.write_text(FAUX_CLAUDE, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CEREBRO_", "CLAUDE_CODE_"))}
    env.update({"CEREBRO_ROOT": str(R), "CEREBRO_SANS_MODELE": "1", "CEREBRO_SANS_RESEAU": "1", "CEREBRO_TODAY": LUNDI,
                "CEREBRO_CLE_SAUVEGARDE": str(tmp / "cle.key"), "CEREBRO_CLAUDE": str(faux), "FAUX_CLAUDE_LOG": str(tmp / "appels.jsonl"), "CEREBRO_CALME_MIN": "0",
                "PYTHONIOENCODING": "utf-8", "HOME": str(tmp / "home"), "USERPROFILE": str(tmp / "home")})
    r = subprocess.run([PY, str(R / ".equipe/tests/fixtures/dossier_fictif.py")], env=env, capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-300:]
    return tmp, R, env


TMP, R, ENV = preparer()
os.environ.clear()
os.environ.update(ENV)
sys.path.insert(0, str(R / ".equipe" / "scripts" / "entretien"))
sys.path.insert(0, str(R / ".equipe" / "scripts" / "entretien" / "taches"))
sys.path.insert(0, str(R / ".equipe" / "cerebro"))
import cycle  # noqa: E402  (charge les extensions de la racine jetable)
from cb import core, objets as O, routines as RT, config as K, files as F  # noqa: E402
import _mission as MI  # noqa: E402
EXT = {getattr(m, "__name__", ""): m for m in cycle.EXTENSIONS}
FIN = lambda: time.time() + 120


def cerebro(*a):
    r = subprocess.run([PY, str(R / ".equipe/cerebro/cerebro.py"), *a], env=ENV, capture_output=True, text=True, encoding="utf-8", timeout=300)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"brut": r.stdout[-300:], "err": r.stderr[-300:]}


def appels():
    p = Path(ENV["FAUX_CLAUDE_LOG"])
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def mesures_du_jour():
    return core.db().execute("SELECT COUNT(*) FROM mesures WHERE substr(le,1,10)=?", (core.iso(),)).fetchone()[0]


def vider_mesures():
    core.db().execute("DELETE FROM mesures")
    core.db().commit()
    core.set_etat("ralentir", None)


def set_today(d):
    os.environ["CEREBRO_TODAY"] = d
    ENV["CEREBRO_TODAY"] = d


# ------------------------------------------------------------------ 1. routines (critère 16)
@test("extensions chargées sans collision de noms de tâches (routines, fabrique, découverte, recalculs, missions)")
def _():
    attendues = {"routines", "fabrique_hebdo", "fabrique_routines", "decouverte_mensuelle", "profil", "modeles_roles", "veille_hebdo",
                 "tuteur_hebdo", "revue_hebdomadaire", "anticipation_mensuelle", "condensation", "double_lecture", "enrichissement", "reconcile"}
    manque = attendues - set(cycle.TACHES)
    assert not manque, manque
    assert {"taches_routines", "taches_fabrique", "taches_decouverte", "taches_recalculs", "taches_missions"} <= set(EXT), list(EXT)


@test("cadence déduite d'un énoncé (FR/DE/EN) et normalisée")
def _():
    cas = {"Désormais, chaque lundi, la liste des délais": "lundi", "tous les jours un point": "quotidien", "jeden Montag die Fristen": "lundi",
           "every week a summary": "hebdo", "chaque mois les revues LBA": "mensuel", "à chaque fois qu'une décision de taxation arrive": "evenement:decision_taxation",
           "merci beaucoup": None}
    faux = {k: RT.cadence_depuis_texte(k) for k, v in cas.items() if RT.cadence_depuis_texte(k) != v}
    assert not faux, faux
    assert RT.normaliser_cadence("Lundi") == "lundi" and RT.normaliser_cadence("evenement:taxation") == "evenement:decision_taxation"


@test("routine add : objet routine, ligne de sommaire, dédoublonnage d'un énoncé proche")
def _():
    a = cerebro("routine", "add", "Désormais, chaque lundi, la liste des délais de la semaine", "--cadence", "lundi",
                "--mission", "liste des délais des 30 prochains jours")
    b = cerebro("routine", "add", "chaque lundi : liste des délais de la semaine", "--cadence", "lundi")
    assert a.get("id", "").startswith("ROUT-") and a["existant"] is False, a
    assert b.get("id") == a["id"] and b["existant"] is True, b
    assert O.get(a["id"])["data"]["mission"] == "liste des délais des 30 prochains jours"  # mission non écrasée par le doublon
    assert (R / ".equipe/sommaires/domaines/routine.md").read_text(encoding="utf-8").count(a["id"]) == 1


@test("routine due → document produit par script (aucun appel), lié, ligne au brief ; plus due ensuite")
def _():
    n0 = len(appels())
    due = cerebro("routine", "due")
    rid = due[0]["id"]
    r = cycle.TACHES["routines"]("", FIN())
    assert r["executees"] == 1 and r["documents"], r
    doc = O.get(r["documents"][0])
    assert doc["type"] == "document" and doc["statut"] == "prêt" and "Délais" in doc["nom"], doc["nom"]
    assert core.db().execute("SELECT 1 FROM liens WHERE src=? AND dst=?", (rid, doc["id"])).fetchone()
    assert "DL-001" in (R / doc["chemin"]).read_text(encoding="utf-8") or "Réclamation" in (R / doc["chemin"]).read_text(encoding="utf-8")
    e = core.get_etat("routines_du_jour")
    assert e["le"] == LUNDI and doc["id"] in e["lignes"][0], e
    assert cerebro("routine", "due") == [] and len(appels()) == n0


@test("routine : lundi manqué (machine éteinte) → rattrapée au premier cycle venu, une seule fois")
def _():
    set_today("2026-10-13")  # mardi : le lundi 12 a été manqué
    try:
        d = RT.routine_due()
        assert len(d) == 1, d
        cycle.TACHES["routines"]("", FIN())
        assert RT.routine_due() == []
        set_today("2026-10-15")
        assert RT.routine_due() == []
    finally:
        set_today(LUNDI)


@test("routine sans recette → mission de fond (modèle intermédiaire, priorité 2) ; document créé")
def _():
    r = RT.routine_add("Désormais, chaque lundi, un mot sur la conjoncture des PME romandes", "lundi", "note sur la conjoncture des PME")
    n0 = len(appels())
    out = cycle.TACHES["routines"]("", FIN())
    a = appels()[n0:]
    assert len(a) == 1 and "--model" in a[0]["args"] and a[0]["args"][a[0]["args"].index("--model") + 1] == (K.get("modeles.intermediaire") or "sonnet"), a
    assert out["executees"] == 1, out
    vider_mesures()


# ------------------------------------------------------------------ 2. budget (critère 35)
@test("budget à 90 % → seules les priorités 1 à 3 ; 60 % → priorités 5-6 en attente ; 100 % → rien")
def _():
    vider_mesures()
    K.set_("modeles.budget_fond_quotidien_appels", "10", source="test")
    con = core.db()
    for k in range(9):
        con.execute("INSERT INTO mesures(le,role,tache,palier,tokens,duree_ms,ok) VALUES(?,?,?,?,?,?,1)", (f"{core.iso()}T10:0{k}:00+02:00", "test", "x", "leger", 10, 1))
    con.execute("INSERT INTO mesures(le,role,tache,palier,tokens,duree_ms,ok) VALUES(?,?,?,?,?,?,1)", (f"{core.iso()}T11:00:00+02:00", "associe", "x", "plus_capable", 10, 1))
    con.commit()
    b = MI.budget()
    assert b["utilises"] == 9 and b["ratio"] == 0.9, b  # l'associé n'est pas compté
    assert [MI.autorise(p, b)[0] for p in range(1, 7)] == [True, True, True, False, False, False]
    n0 = len(appels())
    r = MI.lancer("mission de test", palier="leger", priorite=5, nom="test")
    assert r.get("rationne") and len(appels()) == n0, r
    con.execute("DELETE FROM mesures WHERE role='test' AND rowid IN (SELECT rowid FROM mesures WHERE role='test' LIMIT 3)")
    con.commit()
    assert [MI.autorise(p)[0] for p in range(1, 7)] == [True, True, True, True, False, False]
    for k in range(4):
        con.execute("INSERT INTO mesures(le,role,tache,palier,tokens,duree_ms,ok) VALUES(?,?,?,?,?,?,1)", (f"{core.iso()}T12:0{k}:00+02:00", "test", "x", "leger", 10, 1))
    con.commit()
    assert not any(MI.autorise(p)[0] for p in range(1, 7))
    vider_mesures()
    K.set_("modeles.budget_fond_quotidien_appels", "3", source="test")


@test("jamais le plus capable en fond hors mémo ; aucun appel à vide ; appel mesuré")
def _():
    assert MI.modele_pour("plus_capable")[0] == "intermediaire" and MI.modele_pour("plus_capable", memo=True)[0] == "plus_capable"
    n0 = len(appels())
    assert MI.lancer("x", elements=[]).get("saute") and len(appels()) == n0
    r = MI.lancer("mission réelle", palier="plus_capable", priorite=2, nom="test")
    assert r["ok"] and r["palier"] == "intermediaire" and r["tokens"] == 1200, r
    assert core.db().execute("SELECT palier, tokens FROM mesures WHERE role='test' ORDER BY n DESC LIMIT 1").fetchone()[1] == 1200
    vider_mesures()


@test("limite d'usage détectée → état « ralentir », plus aucun appel de fond ce jour")
def _():
    os.environ["FAUX_CLAUDE_MODE"] = "limite"
    try:
        r = MI.lancer("mission", priorite=2, nom="test")
    finally:
        os.environ.pop("FAUX_CLAUDE_MODE", None)
    assert r["limite"] and not r["ok"], r
    e = core.get_etat("ralentir")
    assert e["le"] == core.iso() and "ralentis" in e["phrase"], e
    n0 = len(appels())
    assert MI.lancer("autre", priorite=1, nom="test").get("saute") and len(appels()) == n0
    vider_mesures()


# ------------------------------------------------------------------ 3. fabrique (critère 16, §6.5)
@test("fabrique sans besoin → aucun appel, aucune mesure")
def _():
    core.db().execute("DELETE FROM file_entretien WHERE tache='fabrique'")
    core.db().commit()
    n0, m0 = len(appels()), mesures_du_jour()
    r = cycle.TACHES["fabrique_hebdo"]("", FIN())
    assert r.get("rien") and len(appels()) == n0 and mesures_du_jour() == m0, r


@test("fabrique : demande « tous les lundis… » en file → routine par script, sans modèle, dès le cycle suivant")
def _():
    core.db().execute("INSERT INTO file_entretien(priorite,tache,arg,cree_le) VALUES(2,'fabrique','Tous les jeudis, la liste des rendez-vous de la semaine',?)", (core.stamp(),))
    core.db().commit()
    plan = []
    EXT["taches_fabrique"].PLANIFIER(False, "rattrapage", lambda t, a="", p=4: plan.append(t))
    assert "fabrique_routines" in plan, plan
    n0 = len(appels())
    r = cycle.TACHES["fabrique_routines"]("", FIN())
    assert r["routines"] and O.get(r["routines"][0])["data"]["cadence"] == "jeudi" and len(appels()) == n0, r
    assert not core.db().execute("SELECT 1 FROM file_entretien WHERE tache='fabrique' AND statut='attente'").fetchone()


@test("fabrique : besoin réel → un appel, skill écrite contrôlée (YAML, description citée, bloc cardinal), enregistrée, config validée")
def _():
    vider_mesures()
    core.set_etat("fabrique_derniere_creation", None)
    core.db().execute("INSERT INTO file_entretien(priorite,tache,arg,cree_le) VALUES(5,'fabrique','liste fictive des délais pour test',?)", (core.stamp(),))
    core.db().commit()
    os.environ["FAUX_CLAUDE_MODE"] = "fabrique"
    try:
        r = cycle.TACHES["fabrique_hebdo"]("", FIN())
    finally:
        os.environ.pop("FAUX_CLAUDE_MODE", None)
    assert r.get("enregistres") and not r.get("ecartes"), r
    sk = O.get(r["enregistres"][0])
    assert sk["type"] == "skill" and sk["statut"] == "essai" and sk["chemin"] == ".claude/skills/liste-fictive/SKILL.md", sk
    t = (R / sk["chemin"]).read_text(encoding="utf-8")
    assert 'description: "Liste fictive' in t and "BLOC-CARDINAL" in t
    assert core.db().execute("SELECT 1 FROM capacites WHERE nom='liste-fictive'").fetchone()
    assert core.get_etat("fabrique_derniere_creation") == core.iso()
    assert O.get(r["rapport"])["type"] == "rapport"
    vider_mesures()


@test("fabrique : au plus une création par semaine ; fichier non conforme mis à l'écart")
def _():
    core.db().execute("INSERT INTO file_entretien(priorite,tache,arg,cree_le) VALUES(5,'fabrique','autre besoin fictif',?)", (core.stamp(),))
    core.db().commit()
    n0 = len(appels())
    r = cycle.TACHES["fabrique_hebdo"]("", FIN())
    assert r.get("attente") == "une création par semaine" and len(appels()) == n0, r
    core.set_etat("fabrique_derniere_creation", None)
    os.environ["FAUX_CLAUDE_MODE"] = "fabrique-casse"
    try:
        r = cycle.TACHES["fabrique_hebdo"]("", FIN())
    finally:
        os.environ.pop("FAUX_CLAUDE_MODE", None)
    assert r.get("ecartes") and not (R / ".claude/skills/Mauvais Nom").exists(), r
    assert list((R / ".equipe/skills-dormantes/_rejets").glob("*Mauvais Nom*"))
    vider_mesures()


# ------------------------------------------------------------------ 4. recalculs (écart 10)
@test("config set mustafa.tutoiement tutoiement → recalcul « profil » en file → profil réécrit (en-tête et marques gardés)")
def _():
    r = cerebro("config", "set", "mustafa.tutoiement", "tutoiement")
    assert "profil" in r["recalculs"], r
    q = core.db().execute("SELECT n FROM file_entretien WHERE tache='profil' AND statut='attente'").fetchone()
    assert q
    bilan = {}
    cycle.increment(bilan, max_prio=2, budget=60)
    assert "profil" in bilan, bilan
    t = (R / ".equipe/cerveau/cabinet/profil-mustafa.md").read_text(encoding="utf-8")
    assert t.startswith("---\nid: CAB-001") and "tutoiement [déclaré par Mustafa le" in t and "[défaut]" in t and "## Habitudes" in t, t[:600]


@test("cantons suivis → doctrine cantonale créée + entrée cantons.yaml ; domaines → spécialiste manquant en fabrique ; modèles des sous-agents")
def _():
    cerebro("config", "set", "mustafa.cantons_suivis", "VD,GE,NE")
    cerebro("config", "set", "mustafa.domaines", "sociétés,droit des marques")
    cerebro("config", "set", "modeles.intermediaire", "claude-sonnet-test")
    bilan = {}
    cycle.increment(bilan, max_prio=2, budget=90)
    assert (R / ".equipe/cerveau/doctrine/NE/README.md").exists(), bilan.get("doctrine_cantons")
    assert "  NE:" in (R / ".equipe/scripts/bibliotheque/cantons.yaml").read_text(encoding="utf-8")
    import yaml
    yaml.safe_load((R / ".equipe/scripts/bibliotheque/cantons.yaml").read_text(encoding="utf-8"))
    assert core.db().execute("SELECT 1 FROM file_entretien WHERE tache='fabrique' AND arg LIKE '%droit des marques%'").fetchone()
    assert "model: claude-sonnet-test" in (R / ".claude/agents/relecteur.md").read_text(encoding="utf-8")
    assert "model: opus" in (R / ".claude/agents/chercheur.md").read_text(encoding="utf-8")
    cerebro("config", "set", "modeles.intermediaire", "sonnet")
    cycle.increment({}, max_prio=2, budget=30)


# ------------------------------------------------------------------ 5. règles (§12, critère 39)
@test("regle appliquer (associé) → objet REGL, ligne dans regles-maison.md, import CLAUDE.md validé, audit, différentiel")
def _():
    r = cerebro("regle", "appliquer", "Ne me mets jamais de tableau pour une réponse de deux lignes", "--cible", "associe")
    assert r.get("id", "").startswith("REGL-"), r
    t = (R / ".equipe/cerveau/cabinet/regles-maison.md").read_text(encoding="utf-8")
    assert r["id"] in t and "deux lignes" in t
    assert "@.equipe/cerveau/cabinet/regles-maison.md" in (R / "CLAUDE.md").read_text(encoding="utf-8")
    a = core.db().execute("SELECT acteur, detail FROM journal_audit WHERE action='regle_appliquer' AND objet=?", (r["id"],)).fetchone()
    assert a and a[0] == "mustafa"
    corps = (R / O.get(r["id"])["chemin"]).read_text(encoding="utf-8")
    assert "## Différentiel" in corps and "+- [" in corps and "« Ne me mets jamais" in corps


@test("regle appliquer (rôle, config) → pointeur dans le rôle ; valeur de configuration et recalculs")
def _():
    r = cerebro("regle", "appliquer", "Le rédacteur cite toujours la date d'état du droit en pied de page", "--cible", "role:redacteur")
    assert r.get("id"), r
    assert "regles-maison.md" in (R / ".claude/agents/redacteur.md").read_text(encoding="utf-8")
    r2 = cerebro("regle", "appliquer", "Tu peux me tutoyer", "--cible", "config:mustafa.tutoiement", "--valeur", "tutoiement")
    assert r2.get("id") and K.get_full("mustafa.tutoiement")["source"].startswith("règle posée par Mustafa"), r2
    assert cerebro("regle", "appliquer", "x", "--cible", "config:mustafa.tutoiement").get("erreur")


# ------------------------------------------------------------------ 6. réconciliation (écart 1c)
@test("reconcile après suppression d'un objet en base → restauré depuis l'en-tête de son fichier (même identifiant, liens)")
def _():
    oid = "DOC-0001"
    o = O.get(oid)
    assert o and (R / o["chemin"]).exists()
    con = core.db()
    for t, c in (("objets", "id"), ("alias", "id"), ("objets_fts", "id")):
        con.execute(f"DELETE FROM {t} WHERE {c}=?", (oid,))
    con.commit()
    assert not O.get(oid)
    r = cerebro("reconcile")
    assert oid in r["recrees"], r
    n = O.get(oid)
    assert n and n["chemin"] == o["chemin"] and n["type"] == "document"
    assert cerebro("reconcile")["n"] == 0  # idempotent


# ------------------------------------------------------------------ 7. condensation et double lecture (critère 27)
@test("condensation : captures de plus de 30 jours archivées sans perte (différentiel vérifié), non classées gardées, find --deep")
def _():
    inbox = R / ".equipe/inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    vieux, vieux2 = "2026-08-20", "2026-08-21"
    caps = [{"le": f"{vieux}T09:0{k}:00+02:00", "session": "s1", "prompt": f"Le bail Zéphyrin numéro {k} échoit le 30.11.2026", "reponse": "noté"} for k in range(3)]
    (inbox / f"{vieux}.jsonl").write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in caps) + "\n", encoding="utf-8")
    (inbox / f"{vieux2}.jsonl").write_text(json.dumps({"le": vieux2, "prompt": "non classé", "reponse": ""}) + "\n", encoding="utf-8")
    (inbox / "_etat-greffier.json").write_text(json.dumps({f"{vieux}.jsonl": 3}), encoding="utf-8")
    r = cycle.TACHES["condensation"]("", FIN())
    assert r["condenses"] == 1 and r["captures"] == 3 and r["non_classes_gardes"] == 1, r
    assert not (inbox / f"{vieux}.jsonl").exists() and (inbox / f"{vieux2}.jsonl").exists()
    arch = (R / ".equipe/archives/inbox/2026-08.md").read_text(encoding="utf-8")
    assert all(json.dumps(c, ensure_ascii=False) in arch for c in caps)
    hits = cerebro("find", "bail Zéphyrin", "--deep")
    assert any(h.get("via") == "archives" for h in hits), hits


@test("double lecture : l'échantillon retient la capture dont un fait chiffré n'est pas en base (rattrapage)")
def _():
    inbox = R / ".equipe/inbox"
    d = core.iso()
    c1 = {"le": f"{d}T10:00:00+02:00", "session": "s2", "prompt": "Rochat a payé CHF 48'750 d'acompte le 02.10.2026, à noter", "reponse": "Bien noté."}
    c2 = {"le": f"{d}T10:05:00+02:00", "session": "s2", "prompt": "Merci, à demain", "reponse": "À demain."}
    (inbox / f"{d}.jsonl").write_text(json.dumps(c1, ensure_ascii=False) + "\n" + json.dumps(c2, ensure_ascii=False) + "\n", encoding="utf-8")
    e = json.loads((inbox / "_etat-greffier.json").read_text(encoding="utf-8"))
    e[f"{d}.jsonl"] = 2
    (inbox / "_etat-greffier.json").write_text(json.dumps(e), encoding="utf-8")
    ech = EXT["taches_missions"].echantillon_double_lecture()
    assert ech and ech[0][2]["prompt"] == c1["prompt"] and any("48" in f for f in ech[0][3]), [(x[1], x[3]) for x in ech]
    n0 = len(appels())
    r = cycle.TACHES["double_lecture"]("", FIN())
    a = appels()[n0:]
    assert r["echantillon"] >= 1 and len(a) == 1 and a[0]["args"][a[0]["args"].index("--model") + 1] == (K.get("modeles.leger") or "haiku"), (r, a)
    vider_mesures()


# ------------------------------------------------------------------ 8. enrichissement, revue, expérience, découverte (critères 21, 30)
@test("enrichissement : source consultée en ligne → objet source (fiabilité, ingestion en file) ; semaine non vide")
def _():
    inbox = R / ".equipe/inbox"
    d = core.iso()
    c = {"le": f"{d}T11:00:00+02:00", "session": "s3", "prompt": "Et l'art. 132 LIFD ?",
         "reponse": "Voir https://www.fedlex.admin.ch/eli/cc/1991/1184_1184_1184/fr et un blog https://exemple-blog.ch/article."}
    with open(inbox / f"{d}.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(c, ensure_ascii=False) + "\n")
    r = cycle.TACHES["enrichissement"]("", FIN())
    assert len(r["sources"]) == 2 and not r["vide"], r
    fiab = {O.get(s)["data"]["fiabilite"] for s in r["sources"]}
    assert fiab == {"officielle", "secondaire"}, fiab
    assert core.db().execute("SELECT 1 FROM file_entretien WHERE tache='bibliotheque_ingest' AND arg LIKE '%fedlex%'").fetchone()
    assert cycle.TACHES["enrichissement"]("", FIN())["sources"] == []  # déjà connue : pas deux fois


@test("revue hebdomadaire : points à trancher d'un mot, préparés par script, sans appel")
def _():
    n0 = len(appels())
    r = cycle.TACHES["revue_hebdomadaire"]("", FIN())
    assert r.get("document") and r["points"] >= 1 and len(appels()) == n0, r
    assert "(oui / non)" in (R / O.get(r["document"])["chemin"]).read_text(encoding="utf-8")


@test("réserve de Mustafa : aucun appel de fond pendant son travail ni réserve entamée ; tâche reportée, jamais sautée")
def _():
    import time as _t
    fond = cycle.fond
    n0 = len(appels())
    os.environ["CEREBRO_CALME_MIN"] = "20"
    fond.noter_activite()
    try:
        r = cycle.TACHES["veille_hebdo"]("", FIN())
        assert r.get("_partiel") and "Mustafa" in str(r.get("attente")), r
    finally:
        os.environ["CEREBRO_CALME_MIN"] = "0"
    fond.noter_jauge({"status": "allowed", "unifiedWindows": {"five_hour": {"utilization": 0.8, "resetsAt": _t.time() + 3600}}})
    try:
        ok, raison = fond.modele_permis()
        assert not ok and "80 %" in raison, raison
        r = cycle.TACHES["veille_hebdo"]("", FIN())
        assert r.get("_partiel"), r
    finally:
        fond.JAUGE.unlink(missing_ok=True)
    assert len(appels()) == n0, "aucun appel ne doit partir"


@test("missions de fond sans matière → aucun appel (tuteur, anticipation) ; veille sans candidat : seule la recherche active hebdomadaire")
def _():
    n0 = len(appels())
    v = cycle.TACHES["veille_hebdo"]("", FIN())
    assert v.get("candidats") == 0, v
    assert len(appels()) == n0 + 1, "veille : une seule recherche active hebdomadaire (sources officielles), rien d'autre"
    core.set_etat("anticipation_revus", {r[0]: core.iso() for r in core.db().execute("SELECT id FROM objets WHERE type='client'")})
    assert cycle.TACHES["anticipation_mensuelle"]("", FIN()) == {"clients": 0}
    assert len(appels()) == n0 + 1


@test("expérience : identifiants et gras visibles dans les réponses → révision de l'associé mise en file")
def _():
    inbox = R / ".equipe/inbox"
    d = core.iso()
    with open(inbox / f"{d}.jsonl", "a", encoding="utf-8") as fh:
        for k in range(3):
            fh.write(json.dumps({"le": f"{d}T12:0{k}:00+02:00", "prompt": "où en est Rochat ?", "reponse": "**Délai** DL-001 et DOC-0001 à relire."}, ensure_ascii=False) + "\n")
    r = cycle.TACHES["experience_hebdo"]("", FIN())
    assert "identifiants_visibles" in r["ecarts"] and "gras" in r["ecarts"], r
    assert core.db().execute("SELECT 1 FROM file_entretien WHERE tache='fabrique' AND arg LIKE 'révision associé%'").fetchone()


@test("découverte : catalogue par scripts (plugins, inventaire), garde-fous par script, un candidat évalué au plus")
def _():
    sys.path.insert(0, str(R / ".equipe/scripts/decouverte"))
    import catalogue
    c = catalogue.candidats(["recherche de droit suisse"], 5, reseau=False)
    ids = [x["id"] for x in c]
    assert "swiss-law@claude-for-legal" in ids and "casino@x" not in ids, ids
    D = EXT["taches_decouverte"]
    assert D.garde_fous({"retenir": True, "lecture_seule": False, "installation": {"type": "plugin"}}, {}) is not None
    assert D.garde_fous({"retenir": True, "lecture_seule": True, "installation": {"type": "mcp_stdio", "commande": ["bash", "-c", "x"]}}, {}) is not None
    assert D.garde_fous({"retenir": True, "lecture_seule": True, "installation": {"type": "mcp_http", "url": "https://x"}}, {"secrets": True}) is not None
    assert D.garde_fous({"retenir": True, "lecture_seule": True, "installation": {"type": "mcp_http", "url": "https://x"}}, {}) is None
    vider_mesures()
    n0 = len(appels())
    r = cycle.TACHES["decouverte_mensuelle"]("", FIN())  # le faux modèle ne retient rien
    a = [x for x in appels()[n0:] if "-p" in x["args"]]
    assert len(a) == 1 and r.get("refus"), (r, a)
    assert "swiss-law@claude-for-legal" in (core.get_etat("decouverte_evalues") or [])
    vider_mesures()


@test("associé : consigne des règles par cerebro routine add / regle appliquer, fichier ≤ 6 300 caractères")
def _():
    t = (REEL / ".equipe/cerveau/cabinet/associe.md").read_text(encoding="utf-8")
    assert "cerebro routine add" in t and "cerebro regle appliquer" in t and "queue add fabrique" not in t and len(t) <= 6300, len(t)


# ------------------------------------------------------------------ 9. test réel (optionnel)
@test("[--avec-modele] fabrique réelle (modèle intermédiaire) : « tous les lundis : liste des délais de la semaine » → skill ou routine exploitable")
def _():
    if not AVEC_MODELE:
        print("       (sauté : relancer avec --avec-modele)")
        return
    for k in ("CEREBRO_SANS_MODELE", "CEREBRO_CLAUDE"):
        os.environ.pop(k, None)
    os.environ.update(VRAI_HOME)
    os.environ["CEREBRO_FABRIQUE_SANS_RACCOURCI"] = "1"
    vider_mesures()
    K.set_("modeles.budget_fond_quotidien_appels", "10", source="test")
    core.set_etat("fabrique_derniere_creation", None)
    core.db().execute("DELETE FROM file_entretien WHERE tache='fabrique'")
    core.db().execute("INSERT INTO file_entretien(priorite,tache,arg,cree_le) VALUES(2,'fabrique','tous les lundis : liste des délais de la semaine',?)", (core.stamp(),))
    core.db().commit()
    for (rid,) in core.db().execute("SELECT id FROM objets WHERE type='routine' AND statut!='archive'").fetchall():
        O.archive(rid)  # état neuf : le besoin n'est couvert par rien
    avant = {r[0] for r in core.db().execute("SELECT id FROM objets WHERE type IN ('routine','skill','role')")}
    r = cycle.TACHES["fabrique_hebdo"]("", time.time() + 1800)
    print("       fabrique réelle :", json.dumps(r, ensure_ascii=False)[:600])
    nouveaux = {r_[0] for r_ in core.db().execute("SELECT id FROM objets WHERE type IN ('routine','skill','role')")} - avant
    assert nouveaux, r
    rout = [i for i in nouveaux if i.startswith("ROUT-")]
    if rout:
        set_today("2026-10-12")
        out = cycle.TACHES["routines"]("", FIN())
        print("       exécution de la routine :", json.dumps(out, ensure_ascii=False)[:300])
        assert out["executees"] >= 1, out
    else:
        sk = O.get(sorted(nouveaux)[0])
        assert (R / sk["chemin"]).exists() and "BLOC-CARDINAL" in (R / sk["chemin"]).read_text(encoding="utf-8")


if __name__ == "__main__":
    for t in TESTS:
        t()
    ko = [n for n, ok in RES if not ok]
    print(f"{'OK' if not ko else 'ÉCHEC'} ({len(RES) - len(ko)}/{len(RES)}) — racine jetable : {R}")
    if not ko:
        shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1 if ko else 0)
