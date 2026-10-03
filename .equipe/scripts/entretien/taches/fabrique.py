"""Extension du cycle : la fabrique (§6.5). Cadence 7 jours au premier cycle venu, priorité 5 ; au plus une création par
semaine ; aucun appel sans besoin (loi 3). Entrées par script : file `fabrique` (demandes explicites, révisions),
déclencheurs (type de tâche ≥ 3 fois en 30 jours sans skill, même correction ≥ 2 fois, canton/domaine nouveau ≥ 2 fois,
tickets « fabrique »). Une demande récurrente (« tous les lundis… ») devient une routine par script, sans modèle.
Sinon : UN appel `_mission.py` avec .equipe/roles/fabricant.md + le besoin ; puis contrôle par script de ce qui a été
écrit (.claude/skills/<nom>/SKILL.md, .claude/agents/<nom>.md : YAML, description courte citée, bloc cardinal),
enregistrement (cerebro new skill|role, capability register), `valider_config.py --sans-session`, mise à l'écart si échec."""
import os, re, sys, json, time, shutil, subprocess, datetime as dt
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
sys.path.insert(0, str(ICI.parent))
import fond  # noqa: E402
from fond import ROOT, EQ, journal  # noqa: E402

ROLE = EQ / "roles" / "fabricant.md"
DESC_MAX = 160
CREATION_JOURS = 7


def _cb():
    fond.cb()
    from cb import core, objets as O, files as F, routines as RT, config as K, brief as B, cardinal as X
    return core, O, F, RT, K, B, X


# ------------------------------------------------------------------ déclencheurs (scripts)
def besoins():
    """liste ordonnée des besoins : [{source, texte, cle, files:[n]}] ; explicites d'abord"""
    core, O, F, RT, K, B, X = _cb()
    con = core.db()
    j30 = (core.today() - dt.timedelta(days=30)).isoformat()
    traites = core.get_etat("fabrique_traites", {}) or {}
    out = []
    for r in con.execute("SELECT n, arg FROM file_entretien WHERE tache='fabrique' AND statut='attente' ORDER BY priorite, n"):
        if (r["arg"] or "").strip():
            out.append({"source": "demande", "texte": r["arg"].strip(), "cle": "demande:" + core.slug(r["arg"], 60), "files": [r["n"]]})
    for r in con.execute("SELECT id, nom, resume FROM objets WHERE type='ticket' AND statut NOT IN ('fait','resolu','archive','abandonne') "
                         "AND (prochaine_action LIKE '%fabrique%' OR nom LIKE '%règle à codifier%' OR nom LIKE 'révision %')"):
        out.append({"source": "ticket", "texte": f"{r['nom']} — {r['resume'] or ''} ({r['id']})", "cle": "ticket:" + r["id"], "ticket": r["id"]})
    corr = [dict(r) for r in con.execute("SELECT id, nom, resume FROM objets WHERE type='note' AND enregistre_le>=? AND "
                                         "(lower(nom) LIKE '%correction%' OR lower(COALESCE(mots_cles,'')) LIKE '%correction%')", (j30,))]
    vus = set()
    for i, a in enumerate(corr):
        if a["id"] in vus:
            continue
        groupe = [a] + [b for b in corr[i + 1:] if b["id"] not in vus and RT._similaire(a["resume"] or a["nom"], b["resume"] or b["nom"])]
        if len(groupe) >= 2:
            vus |= {g["id"] for g in groupe}
            out.append({"source": "correction", "texte": f"même correction {len(groupe)} fois : {a['resume'] or a['nom']} ({', '.join(g['id'] for g in groupe)})",
                        "cle": "correction:" + core.slug(a["resume"] or a["nom"], 60)})
    skills = {p.parent.name for p in (ROOT / ".claude" / "skills").glob("*/SKILL.md")}
    for r in con.execute("SELECT type, nb, dernier FROM types_de_tache WHERE nb>=3 AND dernier>=? AND COALESCE(skill,'')=''", (j30,)):
        if core.slug(r["type"]) in skills:
            continue
        out.append({"source": "type_de_tache", "texte": f"type de tâche « {r['type']} » vu {r['nb']} fois (dernier {r['dernier']}) sans skill dédiée",
                    "cle": "type:" + core.slug(r["type"], 60), "type_tache": r["type"]})
    suivis = {str(c).upper() for c in (K.get("mustafa.cantons_suivis") or [])}
    for r in con.execute("SELECT canton, COUNT(*) n FROM objets WHERE enregistre_le>=? AND COALESCE(canton,'')!='' GROUP BY canton HAVING n>=2", (j30,)):
        if r["canton"].upper() not in suivis and r["canton"].upper() not in ("CH", "FED"):
            out.append({"source": "canton", "texte": f"canton {r['canton']} cité {r['n']} fois en 30 jours sans être suivi : dossier de doctrine cantonale, "
                        "fiche des sources officielles, rien d'inventé", "cle": "canton:" + r["canton"].upper()})
    agents = " ".join(p.stem for p in (ROOT / ".claude" / "agents").glob("*.md"))
    for r in con.execute("SELECT domaine, COUNT(*) n FROM objets WHERE enregistre_le>=? AND COALESCE(domaine,'') NOT IN ('','délais') GROUP BY domaine HAVING n>=2", (j30,)):
        mots = [w for w in re.findall(r"[a-z]{4,}", core.fold(r["domaine"]))]
        if mots and not any(w[:6] in agents for w in mots):
            out.append({"source": "domaine", "texte": f"domaine « {r['domaine']} » cité {r['n']} fois sans spécialiste", "cle": "domaine:" + core.slug(r["domaine"], 60)})
    lim = (core.today() - dt.timedelta(days=30)).isoformat()
    return [b for b in out if b["source"] in ("demande", "ticket") or (traites.get(b["cle"]) or "0000") < lim]


# ------------------------------------------------------------------ contrôle de ce qui a été écrit
def instantane():
    fichiers = {}
    for pat in (".claude/skills/*/SKILL.md", ".claude/agents/*.md"):
        for p in ROOT.glob(pat):
            fichiers[str(p.relative_to(ROOT)).replace("\\", "/")] = p.stat().st_mtime
    core = _cb()[0]
    routines = {r[0] for r in core.db().execute("SELECT id FROM objets WHERE type IN ('routine','skill','role')")}
    return {"fichiers": fichiers, "objets": routines}


def _entete(p):
    t = p.read_text(encoding="utf-8", errors="replace")
    m = re.match(r"---\n(.*?)\n---", t, re.S)
    return t, (m.group(1) if m else None)


def valider_fichier(p):
    """(erreurs, corrections) ; corrige ce qui se corrige par script (description non citée)"""
    import yaml
    t, head = _entete(p)
    if head is None:
        return ["en-tête YAML absent"], []
    corr = []
    m = re.search(r"^description:[ \t]*([^\"'\s].*)$", head, re.M)
    if m:  # description non citée (un « : » casserait le YAML) : citée par script
        nh = head[:m.start()] + "description: " + json.dumps(m.group(1).strip(), ensure_ascii=False) + head[m.end():]
        t = t.replace(head, nh, 1)
        p.write_text(t, encoding="utf-8")
        head = nh
        corr.append("description citée")
    try:
        y = yaml.safe_load(head) or {}
    except Exception as e:
        return [f"YAML illisible : {repr(e)[:80]}"], corr
    err = []
    nom, desc = str(y.get("name") or ""), str(y.get("description") or "")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", nom):
        err.append(f"nom non conforme : {nom!r}")
    if p.name == "SKILL.md" and nom != p.parent.name:
        err.append(f"nom {nom!r} ≠ dossier {p.parent.name!r}")
    if not desc:
        err.append("description absente")
    elif len(desc) > DESC_MAX:
        err.append(f"description trop longue ({len(desc)} > {DESC_MAX})")
    if p.parent.name == "agents" and str(y.get("model") or "") not in ("opus", "sonnet", "haiku", "inherit", ""):
        err.append(f"modèle inconnu : {y.get('model')}")
    return err, corr


def valider_config():
    p = EQ / "scripts" / "valider_config.py"
    if not p.exists():
        return True, "validateur absent"
    try:
        r = subprocess.run([fond.python_exe(), str(p), "--sans-session"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=300, cwd=str(ROOT), env=fond.env_fond(), stdin=subprocess.DEVNULL)
        return r.returncode == 0, (r.stdout or r.stderr or "")[-300:]
    except Exception as e:
        return False, repr(e)[:200]


def ecarter(rel, raison):
    """fichier fabriqué refusé : mis à l'écart (rien ne se perd), incident"""
    src = ROOT / rel
    dest = EQ / "skills-dormantes" / "_rejets" / f"{_cb()[0].iso()}-{src.parent.name if src.name == 'SKILL.md' else src.stem}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        if src.name == "SKILL.md":
            shutil.move(str(src.parent), str(dest))
        else:
            dest.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest / src.name))
    except Exception as e:
        journal("erreurs-fond", job="fabrique", ou="ecarter", erreur=repr(e)[:200])
    fond.incident(f"fabrique : {rel} mis à l'écart ({raison})", "fabrique", "revu au prochain cycle de fabrique")


def enregistrer(rel):
    """objet skill|role (statut essai) + inventaire ; renvoie l'identifiant"""
    core, O, F, RT, K, B, X = _cb()
    p = ROOT / rel
    import yaml
    _, head = _entete(p)
    y = yaml.safe_load(head or "") or {}
    typ = "skill" if p.name == "SKILL.md" else "role"
    nom = str(y.get("name") or (p.parent.name if typ == "skill" else p.stem))
    r = core.db().execute("SELECT id FROM objets WHERE type=? AND (chemin=? OR lower(nom)=lower(?))", (typ, rel, nom)).fetchone()
    if r:
        version = int((O.get(r[0])["data"] or {}).get("version") or 1) + 1
        O.update(r[0], chemin=rel, resume=core.cut(y.get("description") or "", 280), version=version, acteur="fabrique")
        oid = r[0]
    else:
        oid = O.create(typ, nom, chemin=rel, source=rel, resume=core.cut(y.get("description") or "", 280), statut="essai",
                       prochaine_action="passer actif après 5 utilisations réussies", prochaine_date=(core.today() + dt.timedelta(days=30)).isoformat(),
                       mots_cles="fabrique " + typ, acteur="fabrique", version=1, cree_par="fabrique")
    F.capability_register(nom, typ, "LOCAL", "rien", "-", "maison", "1", "essai", rel)
    return oid


def controler(avant):
    """après l'appel : contrôle, corrige, enregistre ou écarte chaque fichier nouveau ou modifié ; valide la configuration"""
    core, O, F, RT, K, B, X = _cb()
    apres = instantane()
    touches = [rel for rel, m in apres["fichiers"].items() if rel not in avant["fichiers"] or m > avant["fichiers"][rel] + 0.5]
    rapport = {"fichiers": [], "ecartes": [], "enregistres": [], "nouveaux_objets": sorted(apres["objets"] - avant["objets"])}
    if not touches:
        return rapport
    try:
        X.injecter()
    except Exception as e:
        journal("erreurs-fond", job="fabrique", ou="cardinal", erreur=repr(e)[:200])
    for rel in touches:
        err, corr = valider_fichier(ROOT / rel)
        if "BLOC-CARDINAL" not in (ROOT / rel).read_text(encoding="utf-8", errors="replace"):
            err.append("bloc cardinal absent")
        rapport["fichiers"].append({"fichier": rel, "erreurs": err, "corrections": corr})
        if err:
            ecarter(rel, "; ".join(err))
            rapport["ecartes"].append(rel)
        else:
            rapport["enregistres"].append(enregistrer(rel))
    ok, det = valider_config()
    rapport["valider_config"] = ok
    if not ok:
        for rel in touches:
            if rel not in rapport["ecartes"] and (ROOT / rel).exists():
                ecarter(rel, "validation de configuration en échec")
                rapport["ecartes"].append(rel)
        rapport["valider_detail"] = det
    return rapport


# ------------------------------------------------------------------ la tâche
def mission_texte(b):
    cli = "python .equipe/cerebro/cerebro.py" if os.name == "nt" else ".equipe/bin/cerebro"
    skills = ", ".join(sorted(p.parent.name for p in (ROOT / ".claude" / "skills").glob("*/SKILL.md")))
    return (f"Besoin unique de cette semaine (source : {b['source']}) : {b['texte']}\n\n"
            f"Skills existantes : {skills}.\n"
            "Choisis la forme la plus légère qui répond durablement : (a) révision d'une skill ou d'un sous-agent existant ; "
            f"(b) une tâche récurrente → `{cli} routine add \"<énoncé>\" --cadence <lundi…|quotidien|hebdo|mensuel|evenement:<type>> --mission \"<à produire>\"` "
            "(exécutée par script ou par le cycle, pas de skill) ; (c) une skill `.claude/skills/<nom>/SKILL.md` ; (d) un sous-agent `.claude/agents/<nom>.md`. "
            "Pour (c)/(d) : en-tête YAML `name` (ASCII minuscules-tirets, = nom du dossier pour une skill) et `description` entre guillemets, ≤ 160 caractères "
            "(verbe d'usage + déclencheur) ; sous-agent : `tools` et `model` (opus|sonnet|haiku selon §6.6) ; corps sur le modèle des skills existantes "
            "(Quand l'utiliser, Étapes avec commandes cerebro, Structure du livrable, Ne fait jamais) ; aucun taux, article, délai ni barème de mémoire "
            "(renvoi à la bibliothèque : cerebro law article). Ajoute la description dans .equipe/scripts/cabinet/descriptions.py (AGENTS ou SKILLS). "
            f"N'enregistre pas toi-même en base : le script de contrôle le fait (YAML, bloc cardinal, inventaire, validation de la configuration). "
            "Ne modifie ni CLAUDE.md, ni .claude/settings.json, ni la constitution. "
            'Dernière ligne : {"forme": "revision|routine|skill|role|aucune", "fichiers": ["…"], "routine": "ROUT-…|null", "raison": "…"}')


def convertir_demandes(bs=None):
    """demandes récurrentes explicites (« tous les lundis… ») → routines par script, sans modèle ; renvoie (routines, besoins restants)"""
    core, O, F, RT, K, B, X = _cb()
    bs = besoins() if bs is None else bs
    traites = core.get_etat("fabrique_traites", {}) or {}
    routines = []
    if os.environ.get("CEREBRO_FABRIQUE_SANS_RACCOURCI"):
        return routines, bs
    for b in [b for b in bs if b["source"] == "demande"]:
        cad = RT.cadence_depuis_texte(b["texte"])
        if cad:
            r = RT.routine_add(b["texte"], cad, b["texte"], acteur="fabrique")
            if r.get("id"):
                routines.append(r["id"])
                for n in b.get("files", []):
                    B.queue_done(n)
                traites[b["cle"]] = core.iso()
                bs.remove(b)
    core.set_etat("fabrique_traites", traites)
    return routines, bs


def t_fabrique_routines(arg, fin):
    routines, _ = convertir_demandes()
    return {"routines": routines}


def t_fabrique_hebdo(arg, fin):
    core, O, F, RT, K, B, X = _cb()
    bs = besoins()
    if not bs:
        journal("fabrique", statut="aucun besoin")
        return {"rien": True}
    routines, bs = convertir_demandes(bs)
    traites = core.get_etat("fabrique_traites", {}) or {}
    if not bs:
        return {"routines": routines, "appel": False}
    derniere = core.get_etat("fabrique_derniere_creation", None)
    if derniere and (core.today() - dt.date.fromisoformat(derniere)).days < CREATION_JOURS:
        return {"routines": routines, "appel": False, "attente": "une création par semaine"}
    b = bs[0]
    import _mission as MI
    avant = instantane()
    r = MI.lancer(mission_texte(b), role=str(ROLE), palier="intermediaire", priorite=5, nom="fabrique", tache=b["source"], timeout=1800)
    if not r.get("ok"):
        out = {"routines": routines, "appel": False, "attente": r.get("saute") or r.get("erreur")}
        if r.get("rationne") or r.get("limite"):
            out["_partiel"] = True  # reste en file : reprise au cycle suivant
        return out
    ctrl = controler(avant)
    res = r.get("json") or {}
    cree = bool(ctrl["enregistres"]) or any(i.startswith("ROUT-") for i in ctrl["nouveaux_objets"])
    for n in b.get("files", []):
        B.queue_done(n)
    if b.get("ticket"):
        try:
            O.update(b["ticket"], statut="fait", prochaine_action="traité par la fabrique", prochaine_date=core.iso(), acteur="fabrique")
        except Exception:
            pass
    if b.get("type_tache") and ctrl["enregistres"]:
        nom = (O.get(ctrl["enregistres"][0]) or {}).get("nom")
        core.db().execute("UPDATE types_de_tache SET skill=? WHERE type=?", (nom, b["type_tache"]))
        core.db().commit()
    traites[b["cle"]] = core.iso()
    core.set_etat("fabrique_traites", traites)
    if cree:
        core.set_etat("fabrique_derniere_creation", core.iso())
    corps = (f"# Fabrique du {core.iso()}\n\n## Besoin\n{b['texte']} (source : {b['source']})\n\n## Résultat du rôle\n```json\n"
             f"{json.dumps(res, ensure_ascii=False)}\n```\n\n## Contrôle par script\n```json\n{json.dumps(ctrl, ensure_ascii=False, default=str)}\n```\n")
    rap = O.create("rapport", f"Fabrique {core.iso()} : {core.cut(b['texte'], 50)}", body=corps, statut="fait", acteur="fabrique",
                   resume=core.cut(f"{res.get('forme', '?')} · enregistrés {ctrl['enregistres']} · écartés {ctrl['ecartes']}", 280),
                   prochaine_action="revoir à la prochaine fabrique", prochaine_date=(core.today() + dt.timedelta(days=7)).isoformat(),
                   liens=[i for i in ctrl["enregistres"] + ctrl["nouveaux_objets"] if O.get(i)])
    journal("fabrique", statut="fait", besoin=b["cle"], forme=res.get("forme"), controle=ctrl, rapport=rap, tokens=r.get("tokens"))
    return {"besoin": b["cle"], "forme": res.get("forme"), "enregistres": ctrl["enregistres"], "ecartes": ctrl["ecartes"],
            "routines": routines + [i for i in ctrl["nouveaux_objets"] if i.startswith("ROUT-")], "rapport": rap, "tokens": r.get("tokens")}


def PLANIFIER(complet, mode, ajouter):
    """une demande récurrente en file devient routine dès le cycle suivant (priorité 2), sans attendre la fabrique hebdomadaire"""
    core = _cb()[0]
    from cb import routines as RT
    for (txt,) in core.db().execute("SELECT arg FROM file_entretien WHERE tache='fabrique' AND statut='attente'").fetchall():
        if RT.cadence_depuis_texte(txt or ""):
            ajouter("fabrique_routines", "", 2)
            break


TACHES = {"fabrique_hebdo": t_fabrique_hebdo, "fabrique_routines": t_fabrique_routines}
CADENCES = {"fabrique_hebdo": (7, 5)}
