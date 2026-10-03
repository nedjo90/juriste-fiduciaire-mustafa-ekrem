"""Autonomie (§6.5, §9.4, §12) : routines posées par Mustafa, opération dédiée de changement des règles, réconciliation.
- routine add|list|due|run|stop : « désormais, chaque lundi… » → objet `routine` (cadence, mission), exécuté au premier
  cycle d'entretien venu du jour dit (la machine est éteinte la nuit) par .equipe/scripts/entretien/taches/routines.py ;
- regle appliquer|list : seule voie de changement des règles (§12) : phrase, date, différentiel, application, blocs
  régénérés, audit, tag git léger ;
- reconcile : recrée en base les objets manquants depuis les en-têtes des fichiers (cerveau, sous-agents, skills).
Branché dans cerebro.py par deux lignes (parseurs + dispatch). Rien ne lève vers une session : erreurs → dict."""
import re, json, difflib, subprocess, datetime as dt
from pathlib import Path
from .core import db, ROOT, EQ, CERVEAU, iso, today, stamp, cut, fold, audit, journal, get_etat, set_etat

COMMANDES = {"routine", "regle", "reconcile"}
JOURS = {"lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4, "samedi": 5, "dimanche": 6}
JOURS_ALIAS = {"monday": 0, "montag": 0, "lunedi": 0, "tuesday": 1, "dienstag": 1, "martedi": 1, "wednesday": 2, "mittwoch": 2,
               "mercoledi": 2, "thursday": 3, "donnerstag": 3, "giovedi": 3, "friday": 4, "freitag": 4, "venerdi": 4,
               "saturday": 5, "samstag": 5, "sabato": 5, "sunday": 6, "sonntag": 6, "domenica": 6}
NOMS_JOURS = list(JOURS)
EVENEMENTS = {  # « à chaque fois que … » → type d'objet dont la création déclenche la routine
    "taxation": "decision_taxation", "decision de taxation": "decision_taxation", "depot": "document", "document depose": "document",
    "nouveau client": "client", "client": "client", "mail": "mail", "rendez-vous": "rdv", "rdv": "rdv", "delai": "delai",
    "changement de droit": "changement_droit", "dividende": "delai", "mandat": "dossier", "dossier": "dossier"}
REGLES = CERVEAU / "cabinet" / "regles-maison.md"
IMPORT_REGLES = "@.equipe/cerveau/cabinet/regles-maison.md"


# ================================================================== routines
def normaliser_cadence(c):
    """lundi…dimanche | quotidien | hebdo | mensuel | evenement:<type> ; None si illisible"""
    if not c:
        return None
    f = fold(c).replace(" ", "")
    if f in JOURS:
        return f
    if f in JOURS_ALIAS:
        return NOMS_JOURS[JOURS_ALIAS[f]]
    if f in ("quotidien", "quotidienne", "jour", "chaquejour", "daily", "taglich"):
        return "quotidien"
    if f in ("hebdo", "hebdomadaire", "semaine", "weekly", "wochentlich"):
        return "hebdo"
    if f in ("mensuel", "mensuelle", "mois", "monthly", "monatlich"):
        return "mensuel"
    if f.startswith("evenement:") or f.startswith("event:"):
        t = f.split(":", 1)[1]
        return "evenement:" + EVENEMENTS.get(t, t) if t else None
    return None


def cadence_depuis_texte(t):
    """déduit la cadence d'un énoncé (« désormais, chaque lundi… », « à chaque décision de taxation… ») ; None sinon"""
    f = fold(t)
    for nom, n in list(JOURS.items()) + list(JOURS_ALIAS.items()):
        if re.search(rf"\b{nom}s?\b", f):
            return NOMS_JOURS[n]
    if re.search(r"\b(chaque jour|tous les jours|quotidien\w*|chaque matin|tous les matins|jeden tag|ogni giorno|every day|daily)\b", f):
        return "quotidien"
    if re.search(r"\b(chaque semaine|toutes les semaines|hebdomadaire\w*|jede woche|ogni settimana|every week|weekly)\b", f):
        return "hebdo"
    if re.search(r"\b(chaque mois|tous les mois|mensuel\w*|debut de mois|jeden monat|ogni mese|every month|monthly)\b", f):
        return "mensuel"
    m = re.search(r"\b(a chaque fois qu\w*|chaque fois qu\w*|des qu\w*|quand|lorsqu\w*|a chaque|whenever|jedes mal wenn)\b(.{0,60})", f)
    if m:
        suite = m.group(2)
        for k in sorted(EVENEMENTS, key=len, reverse=True):
            if k in suite:
                return "evenement:" + EVENEMENTS[k]
    return None


def _routines(statuts=("actif",)):
    from .objets import get
    q = "SELECT id FROM objets WHERE type='routine'" + (f" AND statut IN ({','.join('?' * len(statuts))})" if statuts else "")
    return [get(r[0]) for r in db().execute(q + " ORDER BY id", tuple(statuts or ()))]


def _similaire(a, b):
    fa, fb = fold(a), fold(b)
    ta = {w for w in re.findall(r"\w+", fa) if len(w) > 2}
    tb = {w for w in re.findall(r"\w+", fb) if len(w) > 2}
    jac = len(ta & tb) / max(1, len(ta | tb))
    return max(difflib.SequenceMatcher(None, fa, fb).ratio(), jac) >= 0.72


def prochaine(cadence, derniere=None, cree=None, j=None):
    """date de la prochaine exécution (premier cycle venu à partir de cette date)"""
    j = j or today()
    if cadence in JOURS:
        base = dt.date.fromisoformat(derniere) + dt.timedelta(days=1) if derniere else (dt.date.fromisoformat(cree) if cree else j)
        return base + dt.timedelta(days=(JOURS[cadence] - base.weekday()) % 7)
    if cadence == "quotidien":
        return max(j, dt.date.fromisoformat(derniere) + dt.timedelta(days=1)) if derniere else j
    if cadence == "hebdo":
        return dt.date.fromisoformat(derniere) + dt.timedelta(days=7) if derniere else j
    if cadence == "mensuel":
        if not derniere:
            return j
        d = dt.date.fromisoformat(derniere)
        return dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return j  # événement : vérifié à chaque cycle


def est_due(o, j=None):
    j = j or today()
    d = o["data"] or {}
    cad, der = d.get("cadence"), d.get("derniere_execution")
    if not cad or der == j.isoformat():
        return False
    if cad.startswith("evenement:"):
        typ = cad.split(":", 1)[1]
        depuis = d.get("dernier_evenement") or o.get("enregistre_le") or ""
        r = db().execute("SELECT COUNT(*) FROM objets WHERE type=? AND enregistre_le>? AND statut!='archive'", (typ, depuis)).fetchone()[0]
        return r > 0
    return prochaine(cad, der, (o.get("valide_du") or iso()), j) <= j


def routine_add(enonce, cadence=None, mission="", client=None, script=None, acteur="associe"):
    """crée (ou retrouve, si un énoncé proche existe déjà) une routine ; renvoie {id, ligne, existant}"""
    from .objets import create, get, update
    from .sommaires import ligne
    from .recherche import find
    cad = normaliser_cadence(cadence) if cadence else cadence_depuis_texte(enonce)
    if not cad:
        return {"erreur": "cadence illisible : lundi…dimanche, quotidien, hebdo, mensuel ou evenement:<type>"}
    mission = (mission or enonce).strip()
    candidats = {h["id"] for h in find(enonce, limit=8, types=["routine"]) if h.get("id")}
    candidats |= {o["id"] for o in _routines(("actif", "suspendu"))}
    for cid in sorted(candidats):
        o = get(cid)
        if o and o["type"] == "routine" and o["statut"] != "archive" and (o.get("client") or None) == (client or None) \
                and (_similaire(o["data"].get("enonce") or o["nom"], enonce) or _similaire(o["data"].get("mission") or "", mission)):
            maj = {}
            if o["data"].get("cadence") != cad:
                maj["cadence"] = cad
            if mission and o["data"].get("mission") != mission:
                maj["mission"] = mission
            if o["statut"] != "actif":
                maj["statut"] = "actif"
            if maj:
                update(o["id"], acteur=acteur, **maj)
            return {"id": o["id"], "ligne": ligne(get(o["id"])), "existant": True}
    pd = prochaine(cad, None, iso()).isoformat() if not cad.startswith("evenement:") else iso()
    corps = (f"# Routine : {cut(enonce, 120)}\n\n## Énoncé de Mustafa\n{enonce}\n\n## Cadence\n{cad} (au premier cycle d'entretien venu "
             f"du jour dit ; machine éteinte la nuit)\n\n## Ce qu'il faut produire\n{mission}\n\n## Exécution\nscript si une recette "
             "existe (.equipe/scripts/routines/recettes.py), sinon mission de fond sur le modèle intermédiaire ; chaque exécution "
             "produit un objet document lié et une ligne au brief.\n")
    rid = create("routine", cut(enonce, 80), body=corps, client=client, resume=cut(f"{cad} · {mission}", 280),
                 prochaine_action=f"exécuter ({cad})", prochaine_date=pd, statut="actif", source=f"Mustafa, conversation du {iso()}",
                 mots_cles="routine règle récurrente " + cad, acteur=acteur,
                 enonce=enonce, cadence=cad, mission=mission, script=script, derniere_execution=None, executions=0)
    return {"id": rid, "ligne": ligne(get(rid)), "existant": False, "cadence": cad, "prochaine": pd}


def routine_list(tout=False):
    from .sommaires import ligne
    return [{"id": o["id"], "cadence": o["data"].get("cadence"), "mission": cut(o["data"].get("mission"), 120),
             "derniere": o["data"].get("derniere_execution"), "statut": o["statut"], "ligne": ligne(o)}
            for o in _routines(None if tout else ("actif",))]


def routine_due(date=None):
    j = dt.date.fromisoformat(date) if date else today()
    return [{"id": o["id"], "cadence": o["data"].get("cadence"), "mission": cut(o["data"].get("mission"), 160)}
            for o in _routines() if est_due(o, j)]


def routine_marquer(rid, doc_id=None, j=None):
    """après exécution : dernière date, prochaine date, compteur, lien vers le document produit"""
    from .objets import get, update, link
    o = get(rid)
    j = j or today()
    d = o["data"]
    cad = d.get("cadence")
    kw = {"derniere_execution": j.isoformat(), "executions": int(d.get("executions") or 0) + 1}
    if cad and cad.startswith("evenement:"):
        kw["dernier_evenement"] = stamp()
        kw["prochaine_date"] = (j + dt.timedelta(days=1)).isoformat()
    else:
        kw["prochaine_date"] = prochaine(cad, j.isoformat(), None, j + dt.timedelta(days=1)).isoformat()
    if doc_id:
        kw["dernier_document"] = doc_id
        link(rid, doc_id, "produit")
        db().commit()
    return update(rid, **kw)


def routine_stop(rid):
    from .objets import get, update
    o = get(rid)
    if not o or o["type"] != "routine":
        return {"erreur": f"routine inconnue : {rid}"}
    return {"ligne": update(o["id"], statut="suspendu", prochaine_action="suspendue à la demande de Mustafa")}


def _executeur():
    """module d'exécution des routines (scripts) : .equipe/scripts/routines/recettes.py"""
    import importlib.util
    p = EQ / "scripts" / "routines" / "recettes.py"
    spec = importlib.util.spec_from_file_location("routines_recettes", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ================================================================== règles (§12)
def _diff(avant, apres, nom):
    return "".join(difflib.unified_diff(avant.splitlines(True), apres.splitlines(True), f"a/{nom}", f"b/{nom}", n=1))


def _fichier_role(nom):
    for p in (ROOT / ".claude" / "agents" / f"{nom}.md", EQ / "roles" / f"{nom}.md"):
        if p.exists():
            return p
    return None


def _assurer_regles():
    if not REGLES.exists():
        REGLES.parent.mkdir(parents=True, exist_ok=True)
        REGLES.write_text("# Règles de la maison (machine)\nsource: constitution §12 · seule voie de changement : `cerebro regle appliquer` "
                          "(phrase de Mustafa, date, différentiel dans l'objet REGL-…) · lu par l'associé (CLAUDE.md) et par les rôles visés "
                          "(cible `role:<nom>`) · jamais modifié à la main\n\n## Règles de la maison\n", encoding="utf-8")
    return REGLES.read_text(encoding="utf-8")


def _valider_config():
    """valide la configuration de lancement après modification de CLAUDE.md (§0.10) ; (ok, détail)"""
    import sys, os
    p = EQ / "scripts" / "valider_config.py"
    if not p.exists():
        return True, "validateur absent"
    try:
        r = subprocess.run([os.environ.get("CEREBRO_PYTHON") or sys.executable, str(p), "--sans-session"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=180, cwd=str(ROOT), stdin=subprocess.DEVNULL,
                           env={**os.environ, "CEREBRO_BACKGROUND": "1"})
        return r.returncode == 0, cut(r.stdout or r.stderr, 300)
    except Exception as e:
        return False, repr(e)[:200]


def _assurer_import_claude_md():
    """CLAUDE.md importe regles-maison.md (une fois) ; validé, sinon retour à la version précédente"""
    p = ROOT / "CLAUDE.md"
    if not p.exists():
        return None
    t = p.read_text(encoding="utf-8")
    if IMPORT_REGLES in t:
        return None
    ancre = "@.equipe/cerveau/cabinet/associe.md"
    nt = t.replace(ancre, ancre + "\n" + IMPORT_REGLES, 1) if ancre in t else t.rstrip() + "\n\n" + IMPORT_REGLES + "\n"
    p.write_text(nt, encoding="utf-8")
    ok, det = _valider_config()
    if not ok:
        p.write_text(t, encoding="utf-8")
        from .files import incident_add
        incident_add("configuration", "import des règles de la maison dans CLAUDE.md refusé par la validation",
                     "règles tenues dans regles-maison.md ; import retenté à la règle suivante")
        return None
    return _diff(t, nt, "CLAUDE.md")


def _pointeur_role(p, nom):
    """insère une fois, dans le fichier du rôle, la ligne qui lui fait lire ses règles de la maison"""
    ligne_ptr = f"Règles de la maison : lire `.equipe/cerveau/cabinet/regles-maison.md` (lignes « tous » et « role:{nom} ») ; elles priment sur ce fichier."
    t = p.read_text(encoding="utf-8")
    if "regles-maison.md" in t:
        return None
    fin = "<!-- /BLOC-CARDINAL -->"
    if fin in t:
        nt = t.replace(fin, fin + "\n" + ligne_ptr, 1)
    elif t.startswith("---\n") and t.find("\n---", 4) != -1:
        k = t.find("\n---", 4) + 4
        nt = t[:k] + "\n" + ligne_ptr + "\n" + t[k:]
    else:
        nt = ligne_ptr + "\n\n" + t
    p.write_text(nt, encoding="utf-8")
    return _diff(t, nt, str(p.relative_to(ROOT)).replace("\\", "/"))


def _tag_git(nom):
    if not (ROOT / ".git").exists():
        return None
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "tag", nom], capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL)
        return nom if r.returncode == 0 else None
    except Exception:
        return None


def regle_appliquer(phrase, cible="associe", valeur=None, texte=None, acteur="associe"):
    """opération dédiée (§12) : enregistre la phrase de Mustafa, applique, régénère les blocs, audite, tague"""
    from .objets import create, update, get
    from .sommaires import ligne
    from . import cardinal as X
    phrase = (phrase or "").strip()
    if not phrase:
        return {"erreur": "phrase de Mustafa manquante"}
    cible = (cible or "associe").strip()
    texte = (texte or phrase).strip()
    if cible.startswith("config:") and valeur in (None, ""):
        return {"erreur": "cible config : --valeur attendue (ex. --cible config:mustafa.tutoiement --valeur tutoiement)"}
    if cible not in ("associe", "tous") and not cible.startswith(("role:", "config:")):
        return {"erreur": "cible attendue : associe | tous | role:<nom> | config:<clé>"}
    rid = create("regle", cut(texte, 80), resume=cut(f"{cible} · {texte}", 280), statut="actif", acteur=acteur,
                 prochaine_action="appliquée ; revoir si Mustafa la corrige", prochaine_date=(today() + dt.timedelta(days=180)).isoformat(),
                 source=f"Mustafa, conversation du {iso()}", mots_cles="règle maison " + cible,
                 body=f"# Règle : {cut(texte, 120)}\n\n## Phrase de Mustafa\n« {phrase} »\n", phrase=phrase, cible=cible)
    diffs, details = [], {}
    if cible.startswith("config:"):
        from .config import get as cget, set_
        cle = cible.split(":", 1)[1]
        avant = cget(cle)
        r = set_(cle, valeur, source=f"règle posée par Mustafa le {iso()} ({rid})", acteur="mustafa")
        if r.get("erreur"):
            update(rid, statut="echec", prochaine_action="corriger la clé de configuration", prochaine_date=iso())
            return {"id": rid, "erreur": r["erreur"]}
        diffs.append(f"--- config {cle}\n- {json.dumps(avant, ensure_ascii=False)}\n+ {json.dumps(r.get('valeur'), ensure_ascii=False)}\n")
        details["recalculs"] = r.get("recalculs")
    else:
        avant = _assurer_regles()
        etiquette = "associe" if cible == "associe" else cible
        nl = f"- [{rid} · {iso()} · {etiquette}] {texte}" + (f" (« {cut(phrase, 200)} »)" if texte != phrase else "")
        apres = avant.rstrip("\n") + "\n" + nl + "\n"
        REGLES.write_text(apres, encoding="utf-8")
        diffs.append(_diff(avant, apres, ".equipe/cerveau/cabinet/regles-maison.md"))
        if cible in ("associe", "tous"):
            d = _assurer_import_claude_md()
            if d:
                diffs.append(d)
        if cible.startswith("role:"):
            nom = cible.split(":", 1)[1]
            p = _fichier_role(nom)
            if p:
                d = _pointeur_role(p, nom)
                if d:
                    diffs.append(d)
            else:
                details["avertissement"] = f"rôle {nom} introuvable : règle tenue dans regles-maison.md seulement"
    try:
        details["blocs"] = len(X.injecter().get("mis_a_jour", []))
    except Exception as e:
        details["blocs"] = f"échec {repr(e)[:80]}"
    diff = "\n".join(d for d in diffs if d)
    corps = (f"# Règle : {cut(texte, 120)}\n\n## Phrase de Mustafa\n« {phrase} »\n\n## Application\ncible : {cible} · le {stamp()}"
             + (f" · valeur : {valeur}" if valeur not in (None, "") else "") + f"\n\n## Différentiel\n```diff\n{diff.rstrip()}\n```\n")
    tag = _tag_git(f"regle-{rid}-{iso().replace('-', '')}")
    update(rid, body=corps, tag=tag, acteur=acteur)
    audit("regle_appliquer", rid, f"{cible} · {phrase}", "mustafa")
    journal("regles", id=rid, cible=cible, phrase=cut(phrase, 300), tag=tag)
    return {"id": rid, "ligne": ligne(get(rid)), "cible": cible, "tag": tag, "diff_lignes": diff.count("\n"), **details}


def regle_list():
    from .sommaires import ligne
    return [ligne(dict(r)) for r in db().execute("SELECT * FROM objets WHERE type='regle' AND statut!='archive' ORDER BY id")]


# ================================================================== réconciliation (§9.4, écart 1c)
def _entete(texte):
    from .objets import split_file
    head, body = split_file(texte)
    champs = {}
    for l in head.splitlines():
        m = re.match(r"^([\wéèàùç_-]+)\s*:\s?(.*)$", l)
        if m:
            v = m.group(2).strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                try:
                    v = json.loads(v) if v[0] == '"' else v[1:-1]
                except Exception:
                    v = v[1:-1]
            champs[m.group(1)] = v
    return champs, body


def _titre(body, defaut):
    m = re.search(r"^#\s+(.+)$", body or "", re.M)
    return cut(re.sub(r"\s*\(machine\)\s*$", "", m.group(1)).strip(), 80) if m else defaut


def reconcile(simuler=False):
    """objets manquants recréés depuis les en-têtes des fichiers ; liens recréés ensuite ; rien n'est supprimé"""
    from .objets import create, link, relpath, get
    from .core import ID_RE
    con = db()
    connus = {r[0] for r in con.execute("SELECT id FROM objets")} | {r[0] for r in con.execute("SELECT ancien FROM redirections")}
    chemins = {r[0] for r in con.execute("SELECT chemin FROM objets WHERE chemin IS NOT NULL")}
    noms_ext = {(r[0], fold(r[1])) for r in con.execute("SELECT type, nom FROM objets WHERE type IN ('role','skill')")}
    recrees, liens_a_faire, erreurs = [], [], []
    fichiers = sorted(CERVEAU.rglob("*.md")) if CERVEAU.exists() else []
    for p in fichiers:
        if "journal" in p.parts:
            continue
        try:
            champs, body = _entete(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        oid, typ = champs.get("id"), champs.get("type")
        if not oid or not typ or not re.fullmatch(r"[A-Z]{1,5}-\d{3,5}", oid) or oid in connus:
            continue
        pa = champs.get("prochaine_action") or ""
        m = re.match(r"^(\d{4}-\d{2}-\d{2})\s*(.*)$", pa)
        pdate, paction = (m.group(1), m.group(2)) if m else (None, pa)
        kw = dict(id=oid, chemin=relpath(p), statut=champs.get("statut") or "actif", resume=champs.get("résumé") or champs.get("resume") or "",
                  prochaine_action=paction or "revoir", prochaine_date=pdate, source=champs.get("source") or "",
                  mots_cles=champs.get("mots_clés") or champs.get("mots_cles") or "", risque=champs.get("risque_principal") or None,
                  chiffre_cle=champs.get("chiffre_clé") or None, acteur="reconcile")
        if champs.get("client") and champs["client"] in connus:
            kw["client"] = champs["client"]
        nom = _titre(body, cut(kw["resume"] or p.stem, 80))
        if simuler:
            recrees.append(oid)
            continue
        try:
            create(typ, nom, **kw)
            recrees.append(oid)
            connus.add(oid)
            liens_a_faire += [(oid, d) for d in ID_RE.findall(champs.get("liens") or "")]
        except Exception as e:
            erreurs.append(f"{oid}: {repr(e)[:100]}")
    for pat, typ in ((".claude/agents/*.md", "role"), (".claude/skills/*/SKILL.md", "skill")):
        for p in sorted(ROOT.glob(pat)):
            rel = relpath(p)
            if rel in chemins:
                continue
            champs, body = _entete(p.read_text(encoding="utf-8", errors="replace"))
            nom = champs.get("name") or (p.parent.name if typ == "skill" else p.stem)
            if (typ, fold(nom)) in noms_ext:
                continue
            if simuler:
                recrees.append(f"{typ}:{nom}")
                continue
            try:
                oid = create(typ, nom, chemin=rel, source=rel, resume=cut(champs.get("description") or "", 280), statut="actif",
                             prochaine_action="réévaluer (fabrique)", prochaine_date=(today() + dt.timedelta(days=90)).isoformat(),
                             acteur="reconcile")
                recrees.append(oid)
                noms_ext.add((typ, fold(nom)))
            except Exception as e:
                erreurs.append(f"{rel}: {repr(e)[:100]}")
    for src, dst in liens_a_faire:
        if dst in connus or get(dst):
            link(src, dst)
    con.commit()
    if recrees and not simuler:
        from .sommaires import tout
        tout()
    journal("reconcile", recrees=recrees[:50], erreurs=erreurs[:10], simuler=simuler)
    return {"recrees": recrees, "n": len(recrees), "erreurs": erreurs[:10], "simule": simuler}


# ================================================================== CLI
def parseurs(s):
    a = s.add_parser("routine", help="tâches récurrentes posées par Mustafa (« désormais, chaque lundi… »)")
    a.add_argument("action", choices=["add", "list", "due", "run", "stop"])
    a.add_argument("arg", nargs="?", help="énoncé (add) ou identifiant (run, stop)")
    a.add_argument("--cadence", help="lundi…dimanche | quotidien | hebdo | mensuel | evenement:<type>")
    a.add_argument("--mission", default="", help="ce qu'il faut produire")
    a.add_argument("--client")
    a.add_argument("--script", help="recette de script forcée (sinon déduite)")
    a.add_argument("--date", help="date de référence pour due (AAAA-MM-JJ)")
    a.add_argument("--tout", action="store_true")
    a = s.add_parser("regle", help="seule voie de changement des règles (§12)")
    a.add_argument("action", choices=["appliquer", "list"])
    a.add_argument("phrase", nargs="?")
    a.add_argument("--cible", default="associe", help="associe | tous | role:<nom> | config:<clé>")
    a.add_argument("--valeur", help="valeur (cible config)")
    a.add_argument("--texte", help="règle reformulée par l'associé (sinon la phrase telle quelle)")
    a = s.add_parser("reconcile", help="recrée en base les objets manquants depuis les en-têtes des fichiers")
    a.add_argument("--simuler", action="store_true")


def executer(args):
    c = args.cmd
    if c == "routine":
        if args.action == "add":
            return routine_add(args.arg or "", args.cadence, args.mission, args.client, args.script)
        if args.action == "list":
            return routine_list(args.tout)
        if args.action == "due":
            return routine_due(args.date)
        if args.action == "stop":
            return routine_stop(args.arg)
        from .objets import get
        o = get(args.arg or "")
        if not o or o["type"] != "routine":
            return {"erreur": f"routine inconnue : {args.arg}"}
        return _executeur().executer(o)
    if c == "regle":
        return regle_appliquer(args.phrase, args.cible, args.valeur, args.texte) if args.action == "appliquer" else regle_list()
    if c == "reconcile":
        return reconcile(args.simuler)
    return {"erreur": f"commande inconnue : {c}"}
