#!/usr/bin/env python3
"""Cycle d'entretien (§11, §12) : un seul processus (verrou PID + péremption), priorité basse, pause quand Mustafa écrit.
File unique persistante (table file_entretien de cerebro), triée par priorité :
  1 sommaires des objets touchés · 2 délais, brouillons (initiative) · 3 classement (greffier, ingesteur)
  4 couverture, zombies, vues client, croisements · 5 bibliothèque, veille, découverte · 6 construction, sauvegarde, export, commit
Incréments d'environ deux minutes, reprenables ; cadences de 7 et 30 jours au premier cycle venu après l'échéance.
La machine est éteinte la nuit : aucune tâche ne suppose une heure donnée.
Usage : cycle.py [--rattrapage | --court | --complet | --increment | --une-passe] [--budget-min N]
  --rattrapage : à l'ouverture (hook SessionStart) ; cycle complet si le dernier date de plus de 20 h
  --court      : après la fin de session (P1 à P3, quelques minutes)
  --complet    : planificateur du système (ouverture de session, sortie de veille, inactivité)
  --increment  : un incrément dans un temps mort (hook Stop) ; sort aussitôt si la file est vide
  --une-passe  : test — planifie puis exécute un seul incrément, sans attendre"""
import sys, os, json, time, argparse, subprocess, shutil, zipfile, sqlite3, datetime as dt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fond
from fond import ROOT, EQ, RUN, SCRIPTS, journal

INCREMENT_S = 120
MODELES = {"initiative", "greffier"}  # tâches qui appellent un modèle : sautées si CEREBRO_SANS_MODELE (tests)
RESEAU = {"bibliotheque_mise_a_jour"}  # tâches longues qui interrogent Internet : sautées si CEREBRO_SANS_RESEAU (tests)
COMPLET_APRES_H = 20
CADENCES = {  # tâche: (jours, priorité)
    "rappel": (7, 4), "cardinal": (7, 4), "revue_hebdomadaire": (7, 5),
    "test_restauration": (30, 6), "decouverte_mensuelle": (30, 5),
}
SAUVEGARDES = EQ / "cerebro" / "sauvegardes"
GARDER_SAUVEGARDES = 14


def C():
    fond.cb()
    from cb import core, objets as O, sommaires as S, brief as B, metier as M, recherche as R, files as F, cardinal as X
    return core, O, S, B, M, R, F, X


# ------------------------------------------------------------------ file
def ajouter(tache, arg="", prio=4):
    core = C()[0]
    core.db().execute("INSERT OR IGNORE INTO file_entretien(priorite,tache,arg,cree_le) VALUES(?,?,?,?)", (prio, tache, arg, core.stamp()))
    core.db().commit()


def terminer(n, statut="fait"):
    """contourne l'unicité (tache,arg,statut) : l'ancienne ligne de même statut est effacée avant la mise à jour"""
    core = C()[0]
    con = core.db()
    r = con.execute("SELECT tache,arg FROM file_entretien WHERE n=?", (n,)).fetchone()
    if r:
        con.execute("DELETE FROM file_entretien WHERE tache=? AND arg=? AND statut=? AND n!=?", (r[0], r[1], statut, n))
        con.execute("UPDATE file_entretien SET statut=?, fait_le=? WHERE n=?", (statut, core.stamp(), n))
        con.commit()


def en_attente(max_prio=6):
    core = C()[0]
    return [dict(r) for r in core.db().execute("SELECT * FROM file_entretien WHERE statut='attente' AND priorite<=? ORDER BY priorite, n", (max_prio,))]


# ------------------------------------------------------------------ planification
def cycle_complet_du():
    core = C()[0]
    d = core.get_etat("dernier_cycle_complet")
    if not d:
        return True
    try:
        return (dt.datetime.now() - dt.datetime.fromisoformat(d)).total_seconds() > COMPLET_APRES_H * 3600
    except Exception:
        return True


def planifier(complet=False, mode="rattrapage"):
    core = C()[0]
    con = core.db()
    ajouter("intendant", "", 1)
    if con.execute("SELECT 1 FROM objets WHERE a_regenerer=1 LIMIT 1").fetchone():
        ajouter("regen", "", 1)
    if mode in ("rattrapage", "complet") or complet:
        ajouter("initiative", "", 2)
    if (SCRIPTS / "ingesteur" / "ingerer.py").exists():
        ajouter("ingesteur", "", 3)
    try:
        import greffier
        if greffier.compter() > 0:
            ajouter("greffier", "", 3)
    except Exception as e:
        journal("erreurs-fond", job="cycle", ou="planifier greffier", erreur=repr(e))
    if mode == "court":
        ajouter("export", "", 6)
        return
    ajouter("vues_client", "", 4)
    ajouter("croisements", "", 4)
    ajouter("coverage_gc", "", 4)
    # cadences au premier cycle venu après l'échéance
    cad = core.get_etat("cadences", {}) or {}
    for t, (jours, prio) in CADENCES.items():
        der = cad.get(t)
        if not der or (core.today() - dt.date.fromisoformat(der)).days >= jours:
            ajouter(t, "", prio)
    if complet:
        for t, p in [("sommaires", 1), ("rappel", 4), ("cardinal", 4), ("sante", 4), ("brief", 4),
                     ("bibliotheque_mise_a_jour", 5), ("tests_cerebro", 6),
                     ("sauvegarde", 6), ("export", 6), ("commit_push", 6)]:
            ajouter(t, "", p)
    for m in EXTENSIONS:
        if hasattr(m, "PLANIFIER"):
            try:
                m.PLANIFIER(complet, mode, ajouter)
            except Exception as e:
                journal("erreurs-fond", job="cycle", ou=f"planifier {getattr(m, '__name__', '?')}", erreur=repr(e)[:300])


# ------------------------------------------------------------------ tâches (script d'abord ; renvoient un petit dict)
def t_intendant(arg, fin):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import intendant
    return intendant.verifier(session=False)


def t_regen(arg, fin):
    core, O, S = C()[:3]
    ids = [r[0] for r in core.db().execute("SELECT id FROM objets WHERE a_regenerer=1")]
    n = 0
    for i in ids:
        if time.time() > fin:
            break
        try:
            O.regen(i)
        except Exception as e:
            journal("erreurs-fond", job="regen", id=i, erreur=repr(e))
            core.db().execute("UPDATE objets SET a_regenerer=0 WHERE id=?", (i,))
        n += 1
    S.niveau0()
    return {"regeneres": n, "reste": len(ids) - n, "_partiel": n < len(ids)}


def t_sommaires(arg, fin):
    S = C()[2]
    r = S.tout()
    return {"sommaires": r if isinstance(r, (int, str)) else len(r) if hasattr(r, "__len__") else "ok"}


def t_vues_client(arg, fin):
    core, M = C()[0], C()[4]
    ids = [r[0] for r in core.db().execute("SELECT id FROM objets WHERE type='client' AND statut!='archive'")]
    for c in ids:
        M.vue_client(c)
    return {"vues": len(ids)}


def t_croisements(arg, fin):
    core, M = C()[0], C()[4]
    cr = M.croisements()
    core.set_etat("croisements", {"le": core.iso(), "n": len(cr)})
    return {"croisements": len(cr)}


def t_coverage_gc(arg, fin):
    core, B = C()[0], C()[3]
    cov = B.coverage()
    g = B.gc(True)
    core.set_etat("couverture", {"le": core.iso(), "taux": cov["taux"], "manques": len(cov["manques"])})
    return {"couverture": cov["taux"], "gc": g.get("repare")}


def t_rappel(arg, fin):
    core, R = C()[0], C()[5]
    r = R.autotest_rappel()
    core.set_etat("rappel", r)
    return {"rappel": r.get("taux") if isinstance(r, dict) else r}


def t_cardinal(arg, fin):
    X = C()[7]
    r = X.injecter()
    return {"mis_a_jour": len(r.get("mis_a_jour", []))}


def t_sante(arg, fin):
    core, B = C()[0], C()[3]
    h = B.health()
    core.set_etat("sante", h)
    return {"objets": h.get("objets"), "couverture": h.get("couverture"), "incidents": h.get("incidents_ouverts")}


def t_brief(arg, fin):
    core, B = C()[0], C()[3]
    b = B.brief()
    core.set_etat("brief_prepare", {"le": core.stamp(), "texte": b})
    return {"brief_car": len(b)}


def t_export(arg, fin):
    return C()[3].export()


def _cle_sauvegarde():
    """clé Fernet propre au poste, hors du dépôt (~/.cerebro/cle-sauvegarde.key) ; à recopier lors d'un changement de poste"""
    from cryptography.fernet import Fernet
    p = Path(os.environ.get("CEREBRO_CLE_SAUVEGARDE") or (Path.home() / ".cerebro" / "cle-sauvegarde.key"))
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(Fernet.generate_key())
        try:
            os.chmod(p, 0o600)
        except Exception:
            pass
    return Fernet(p.read_bytes().strip())


def t_sauvegarde(arg, fin):
    core = C()[0]
    SAUVEGARDES.mkdir(parents=True, exist_ok=True)
    jour = dt.datetime.now().strftime("%Y-%m-%d-%H%M")
    tmp = SAUVEGARDES / f".copie-{os.getpid()}.db"
    src = sqlite3.connect(str(core.DB_PATH))
    dst = sqlite3.connect(str(tmp))
    src.backup(dst)  # copie cohérente même base ouverte
    dst.close(); src.close()
    zp = SAUVEGARDES / f".cerebro-{jour}.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(tmp, "cerebro.db")
        cfg = EQ / "config"
        for f in cfg.glob("*.yaml") if cfg.exists() else []:
            z.write(f, f"config/{f.name}")
    tmp.unlink()
    try:
        f = _cle_sauvegarde()
        out = SAUVEGARDES / f"cerebro-{jour}.zip.chiffre"
        out.write_bytes(f.encrypt(zp.read_bytes()))
        zp.unlink()
        chiffre = True
    except ImportError:
        out = SAUVEGARDES / f"cerebro-{jour}.zip"
        zp.replace(out)
        chiffre = False
        fond.incident("sauvegarde non chiffrée : bibliothèque de chiffrement absente, copie datée simple en attendant", "securite",
                      "pip install --user cryptography (fait par l'installateur)")
    anciens = sorted([p for p in SAUVEGARDES.glob("cerebro-*") if p.is_file()])
    for p in anciens[:-GARDER_SAUVEGARDES]:
        p.unlink()
    core.set_etat("derniere_sauvegarde", {"le": core.stamp(), "fichier": out.name, "chiffre": chiffre})
    return {"sauvegarde": out.name, "chiffre": chiffre, "octets": out.stat().st_size}


def restaurer_sauvegarde(fichier, vers):
    """déchiffre et extrait une sauvegarde vers `vers` (dossier) ; renvoie le chemin de la base restaurée"""
    p = Path(fichier)
    data = p.read_bytes()
    if p.name.endswith(".chiffre"):
        data = _cle_sauvegarde().decrypt(data)
    import io
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(vers)
    return Path(vers) / "cerebro.db"


def t_test_restauration(arg, fin):
    import tempfile
    core = C()[0]
    der = sorted([p for p in SAUVEGARDES.glob("cerebro-*") if p.is_file()]) if SAUVEGARDES.exists() else []
    if not der:
        t_sauvegarde(arg, fin)
        der = sorted([p for p in SAUVEGARDES.glob("cerebro-*") if p.is_file()])
    with tempfile.TemporaryDirectory() as d:
        db = restaurer_sauvegarde(der[-1], d)
        con = sqlite3.connect(str(db))
        ok = con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        n = con.execute("SELECT COUNT(*) FROM objets").fetchone()[0]
        con.close()
    core.set_etat("test_restauration", {"le": core.iso(), "ok": ok, "objets": n, "fichier": der[-1].name})
    if not ok:
        fond.incident("test de restauration de la sauvegarde en échec", "securite", "nouvelle sauvegarde au cycle suivant")
    return {"restauration": ok, "objets": n}


def git(*args, timeout=60):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8", errors="ignore",
                          timeout=timeout, stdin=subprocess.DEVNULL)


def t_commit_push(arg, fin):
    if not (ROOT / ".git").exists() or not shutil.which("git"):
        return {"git": "absent"}
    v = fond.Verrou("git", peremption=600)
    if not v.prendre():
        return {"git": "occupé", "_partiel": True}
    try:
        git("add", "-A")
        st = git("status", "--porcelain")
        commit = None
        if st.stdout.strip():
            r = git("commit", "-q", "-m", f"entretien : sauvegarde automatique du {dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")
            commit = r.returncode == 0
            if not commit:
                fond.incident("commit automatique en échec", "git", (r.stderr or r.stdout)[-200:])
        br = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "HEAD"
        # Le dépôt d'origine (« origin ») est public : il sert à livrer et mettre à jour l'équipe, JAMAIS à recevoir le travail
        # de Mustafa (secret professionnel). Les données restent sur le poste (commits locaux + sauvegarde chiffrée).
        # Envoi uniquement vers un dépôt PRIVÉ explicitement configuré sous le nom « sauvegarde ».
        if "sauvegarde" not in git("remote").stdout.split():
            return {"commit": commit, "push": "local seulement (aucun dépôt privé de sauvegarde configuré)"}
        p = git("push", "-q", "sauvegarde", br, timeout=120)
        if p.returncode != 0:
            fond.incident("envoi sur le dépôt privé en échec (réseau ou accès)", "git", "nouvel essai au prochain cycle")
            return {"commit": commit, "push": False}
        C()[0].set_etat("dernier_push_ok", C()[0].stamp())
        return {"commit": commit, "push": True}
    finally:
        v.rendre()


def _script(chemin, *args, timeout=900):
    if not Path(chemin).exists():
        return {"absent": str(Path(chemin).name)}
    r = subprocess.run([fond.python_exe(), str(chemin), *args], capture_output=True, text=True, encoding="utf-8", errors="ignore",
                       timeout=timeout, cwd=str(ROOT), env=fond.env_fond(), stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise RuntimeError(f"{Path(chemin).name} code {r.returncode}: {(r.stderr or r.stdout)[-300:]}")
    return {"sortie": (r.stdout or "").strip()[-300:]}


def t_ingesteur(arg, fin):
    return _script(SCRIPTS / "ingesteur" / "ingerer.py", timeout=600)


def t_initiative(arg, fin):
    return _script(SCRIPTS / "initiative" / "initiative.py", timeout=1200)


def t_greffier(arg, fin):
    return _script(Path(__file__).resolve().parent / "greffier.py", timeout=1200)


def t_gabarits(arg, fin):
    """posée par cerebro config set cabinet.* : régénère et inscrit les gabarits de la maison"""
    return _script(SCRIPTS / "producteur" / "gabarits.py", "--inscrire", timeout=600)


def bibliotheque_vide():
    """textes officiels absents du poste (ils ne sont pas dans git) : la LIFD sert de témoin"""
    from cb import juridique as L
    from cb.objets import abspath
    try:
        r = L.asof("642.11")
    except Exception:
        return True
    return not r or not r.get("chemin") or not abspath(r["chemin"]).exists()


def t_bibliotheque_mise_a_jour(arg, fin):
    C()
    r = {}
    if bibliotheque_vide():
        r["ingestion"] = _script(SCRIPTS / "bibliotheque" / "fedlex.py", "priorites", timeout=3600)
    r["mise_a_jour"] = _script(SCRIPTS / "bibliotheque" / "mise_a_jour.py", timeout=3600)
    return r


def t_tests_cerebro(arg, fin):
    t = EQ / "tests" / "test_cerebro.py"
    if not t.exists():
        return {"absent": True}
    p = subprocess.run([fond.python_exe(), str(t)], capture_output=True, text=True, encoding="utf-8", errors="ignore",
                       timeout=1800, cwd=str(ROOT), env=fond.env_fond(), stdin=subprocess.DEVNULL)
    der = (p.stdout or "").strip().splitlines()[-1:] or [""]
    if p.returncode != 0:
        echecs = [l for l in (p.stdout or "").splitlines() if l.startswith("ÉCHEC")][:5]
        fond.incident("tests de la mémoire (test_cerebro) en échec : " + "; ".join(echecs)[:200], "tests", "ticket ouvert pour la fabrique")
        try:
            from cb import objets as O
            import datetime as _d
            O.create("ticket", "Tests cerebro en échec au cycle complet", resume="; ".join(echecs)[:280],
                     prochaine_action="corriger (fabrique)", prochaine_date=(_d.date.today() + _d.timedelta(days=2)).isoformat())
        except Exception as e:
            journal("erreurs-fond", job="tests_cerebro", erreur=repr(e))
    return {"code": p.returncode, "bilan": der[0][:200]}


TACHES = {"gabarits": t_gabarits, "bibliotheque_mise_a_jour": t_bibliotheque_mise_a_jour, "tests_cerebro": t_tests_cerebro,
          "intendant": t_intendant, "regen": t_regen, "sommaires": t_sommaires, "vues_client": t_vues_client,
          "croisements": t_croisements, "coverage_gc": t_coverage_gc, "rappel": t_rappel, "cardinal": t_cardinal,
          "sante": t_sante, "brief": t_brief, "export": t_export, "sauvegarde": t_sauvegarde,
          "test_restauration": t_test_restauration, "commit_push": t_commit_push, "ingesteur": t_ingesteur,
          "initiative": t_initiative, "greffier": t_greffier}

# ------------------------------------------------------------------ extensions
# Chaque module .equipe/scripts/entretien/taches/*.py peut définir :
#   TACHES = {"nom": fonction(arg, fin) -> dict}   CADENCES = {"nom": (jours, priorité)}
#   MODELES = {"nom", …} (appellent un modèle)      RESEAU = {"nom", …} (interrogent Internet)
#   def PLANIFIER(complet, mode, ajouter): …          (ajoute ses tâches à la file à chaque cycle)
# Un module en erreur est journalisé et ignoré : il n'empêche jamais le cycle (§0).
EXTENSIONS = []
def _charger_extensions():
    import importlib.util
    d = Path(__file__).resolve().parent / "taches"
    for f in sorted(d.glob("*.py")) if d.exists() else []:
        if f.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"taches_{f.stem}", f)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            TACHES.update(getattr(m, "TACHES", {}))
            CADENCES.update(getattr(m, "CADENCES", {}))
            MODELES.update(getattr(m, "MODELES", set()))
            RESEAU.update(getattr(m, "RESEAU", set()))
            EXTENSIONS.append(m)
        except Exception as e:
            journal("erreurs-fond", job="cycle", ou=f"extension {f.name}", erreur=repr(e)[:300])
_charger_extensions()


# ------------------------------------------------------------------ exécution
def increment(bilan, max_prio=6, budget=INCREMENT_S):
    """exécute des tâches connues par priorité pendant ~budget secondes ;
    renvoie « pause » (Mustafa écrit), « vide » (plus rien d'exécutable) ou « budget » (temps écoulé, à reprendre)"""
    core = C()[0]
    fin = time.time() + budget
    vus = set()
    while time.time() < fin:
        if fond.mustafa_ecrit():
            return "pause"
        todo = [t for t in en_attente(max_prio) if t["tache"] in TACHES and t["n"] not in vus
                and not (os.environ.get("CEREBRO_SANS_MODELE") and t["tache"] in MODELES)
                and not (os.environ.get("CEREBRO_SANS_RESEAU") and t["tache"] in RESEAU)]
        if not todo:
            return "vide" if not any(t["n"] in vus for t in en_attente(max_prio)) else "budget"
        t = todo[0]
        vus.add(t["n"])
        t0 = time.time()
        try:
            r = TACHES[t["tache"]](t["arg"], fin) or {}
            partiel = isinstance(r, dict) and r.pop("_partiel", False)
            if not partiel:
                terminer(t["n"], "fait")
            if t["tache"] in CADENCES:
                cad = core.get_etat("cadences", {}) or {}
                cad[t["tache"]] = core.iso()
                core.set_etat("cadences", cad)
            bilan[t["tache"]] = r
            journal("entretien", tache=t["tache"], prio=t["priorite"], ms=int((time.time() - t0) * 1000), resultat=r)
        except Exception as e:
            terminer(t["n"], "echec")
            bilan[t["tache"]] = {"echec": repr(e)[:200]}
            journal("entretien", tache=t["tache"], prio=t["priorite"], ms=int((time.time() - t0) * 1000), erreur=repr(e)[:400])
            echecs = core.get_etat("echecs_entretien", {}) or {}
            echecs[t["tache"]] = echecs.get(t["tache"], 0) + 1
            core.set_etat("echecs_entretien", echecs)
            if echecs[t["tache"]] >= 3:
                fond.incident(f"tâche d'entretien « {t['tache']} » en échec répété", "entretien", repr(e)[:200])
    return "budget"


def ligne_rattrapage(bilan):
    """une ligne pour le brief (l'associé la reformule pour Mustafa)"""
    m = []
    g = lambda k, f: bilan.get(k, {}).get(f) if isinstance(bilan.get(k), dict) else None
    if g("regen", "regeneres"):
        m.append(f"{g('regen', 'regeneres')} fiches mises à jour")
    if "greffier" in bilan and not bilan["greffier"].get("echec"):
        m.append("échanges classés")
    if "ingesteur" in bilan and not bilan["ingesteur"].get("echec"):
        m.append("documents déposés traités")
    if "initiative" in bilan and not bilan["initiative"].get("echec"):
        m.append("brouillons et fiches préparés")
    if g("vues_client", "vues"):
        m.append(f"{g('vues_client', 'vues')} vues client")
    if "sauvegarde" in bilan and not bilan["sauvegarde"].get("echec"):
        m.append("sauvegarde faite")
    if g("commit_push", "push") is True:
        m.append("copie envoyée sur le dépôt")
    ech = [k for k, v in bilan.items() if isinstance(v, dict) and v.get("echec")]
    if ech:
        m.append(f"{len(ech)} tâche(s) à reprendre")
    return ", ".join(m)


def executer(mode, budget_min):
    core = C()[0]
    complet = mode == "complet" or (mode == "rattrapage" and cycle_complet_du())
    if mode == "increment":
        if not [t for t in en_attente(6) if t["tache"] in TACHES]:
            return {"rien": True}
    else:
        planifier(complet, "court" if mode == "court" else ("complet" if complet else "rattrapage"))
    max_prio = 3 if mode == "court" else 6
    bilan, t0 = {}, time.time()
    if mode in ("une-passe", "increment"):
        increment(bilan, max_prio)
    else:
        limite = t0 + budget_min * 60
        tours_partiels = 0
        while time.time() < limite:
            etat = increment(bilan, max_prio)
            if etat == "vide":
                break
            if etat == "pause":  # Mustafa écrit : on attend un temps mort
                time.sleep(15)
                continue
            tours_partiels += 1
            if tours_partiels > 40:  # garde-fou : une tâche qui ne finit jamais ne retient pas le processus
                break
    if complet and not [t for t in en_attente(6) if t["tache"] in ("sauvegarde", "export", "commit_push")]:
        core.set_etat("dernier_cycle_complet", dt.datetime.now().replace(microsecond=0).isoformat())
    l = ligne_rattrapage(bilan)
    if l:
        core.set_etat("rattrape", f"{dt.datetime.now().strftime('%d.%m %H:%M')} : {l}")
    return {"mode": mode, "complet": complet, "duree_s": int(time.time() - t0), "taches": list(bilan), "rattrape": l,
            "reste": len([t for t in en_attente(6) if t["tache"] in TACHES])}


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    for m in ("rattrapage", "court", "complet", "increment", "une-passe"):
        g.add_argument("--" + m, dest="mode", action="store_const", const=m)
    ap.add_argument("--budget-min", type=float, default=45)
    a = ap.parse_args()
    mode = a.mode or "rattrapage"
    v = fond.Verrou("entretien", peremption=3 * 3600)
    if not v.prendre():
        journal("entretien", mode=mode, statut="déjà en cours")
        print(json.dumps({"deja_en_cours": True}))
        return
    t0 = time.time()
    try:
        fond.basse_priorite()
        journal("entretien", mode=mode, statut="début")
        r = executer(mode, a.budget_min if mode != "court" else min(a.budget_min, 5))
        journal("entretien", mode=mode, statut="fin", duree_s=int(time.time() - t0), resultat=r)
        print(json.dumps(r, ensure_ascii=False, default=str))
    finally:
        v.rendre()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        journal("erreurs-fond", job="cycle", erreur=repr(e))
        print(json.dumps({"erreur": repr(e)}))
