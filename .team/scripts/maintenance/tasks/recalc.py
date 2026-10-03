"""Extension du cycle : recalculs posés par `cerebro config set` (file d'entretien, priorité 2 ; arg = clé modifiée).
Script d'abord (§7.6) ; aucun appel de modèle ici. Une valeur réelle remplace le défaut et tout ce qui en dépend est
recalculé (§0 bis) : horloges, doctrine cantonale (+ entrée de cantons.yaml ; l'ingestion `bibliotheque_cantons`
appartient au chantier bibliothèque), profil, environnement, connecteurs, spécialistes,
modèles des sous-agents, clients principaux, lanceurs, design."""
import os, re, sys, json, subprocess, datetime as dt
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
import background as fond  # noqa: E402
from background import ROOT, EQ, journal  # noqa: E402

CABINET = EQ / "brain" / "firm"
PROFIL = CABINET / "mustafa-profile.md"
ENVIRONNEMENT = CABINET / "environment.md"
CANTONS_YAML = EQ / "scripts" / "library" / "cantons.yaml"
INSTALLATION = ROOT / "Bureau" / "Informatique" / "INSTALLATION.md"

# §6.6 : palier par sous-agent (l'associé n'est pas un sous-agent ; l'intendant est un processus de fond)
PALIER_AGENT = {
    "plus_capable": {"researcher", "litigator", "drafter", "human-editor", "adversarial-panel", "foresight-advisor",
                     "strategist", "negotiator", "builder"},
    "intermediaire": {"source-checker", "proofreader", "calculator", "compliance-officer", "corporate-secretary", "business-developer",
                      "marketer", "communicator", "legal-watch", "ingester", "art-director", "visualizer", "steward",
                      "coach", "producer", "experience-lead", "archivist"},
    "leger": {"chief-of-staff", "clerk"},
}
ALIAS_MODELE = {"plus_capable": "opus", "intermediaire": "sonnet", "leger": "haiku"}
DOMAINES_AGENTS = {  # mot-clé (sans accents) → sous-agent spécialiste existant
    "societ": "company-law-specialist", "registre": "company-law-specialist", "fusion": "company-law-specialist",
    "fiscal": "corporate-tax-specialist", "impot": "corporate-tax-specialist", "tva": "vat-specialist",
    "succession": "estates-specialist", "matrimon": "estates-specialist", "contrat": "contracts-specialist",
    "travail": "employment-specialist", "social": "employment-specialist",
    "lba": "aml-specialist", "blanchiment": "aml-specialist", "conformit": "aml-specialist",
    "immobil": "real-estate-specialist", "koller": "real-estate-specialist", "poursuite": "debt-enforcement-specialist",
    "faillite": "debt-enforcement-specialist", "international": "international-tax-specialist", "cdi": "international-tax-specialist",
    "etranger": "foreign-law-specialist", "personnes physiques": "individual-tax-specialist", "arrivant": "individual-tax-specialist",
}


def _cb():
    fond.cb()
    from cb import core, objects as O, files as F, config as K, brief as B, business as M, clocks as H
    return core, O, F, K, B, M, H


def _marque(e):
    """[défaut] ou [<source>] d'une entrée de configuration"""
    if not isinstance(e, dict) or e.get("valeur") in (None, "", []):
        return "[défaut]"
    s = str(e.get("source") or "déclaré")
    return f"[{s}]"


def _val(K, cle):
    v = K.get(cle)
    return ", ".join(map(str, v)) if isinstance(v, list) else ("" if v is None else str(v))


def _reecrire(chemin, corps_sections, garder=()):
    """réécrit les sections données (titre → lignes) ; garde l'en-tête YAML et les sections listées dans `garder`"""
    core = _cb()[0]
    t = chemin.read_text(encoding="utf-8") if chemin.exists() else "---\n---\n"
    head, body = "", t
    if t.startswith("---\n") and t.find("\n---", 4) != -1:
        k = t.find("\n---", 4) + 4
        head, body = t[:k], t[k:]
    anciens = {}
    for m in re.finditer(r"^## (.+?)\n(.*?)(?=^## |\Z)", body, re.S | re.M):
        anciens[m.group(1).strip()] = m.group(2).rstrip("\n")
    head = re.sub(r"^maj: .*$", f"maj: {core.iso()}", head, count=1, flags=re.M)
    out = []
    for titre, lignes in corps_sections:
        out.append(f"## {titre}\n" + "\n".join(lignes))
    for g in garder:
        if g in anciens:
            out.append(f"## {g}\n{anciens[g]}")
    nt = head.rstrip("\n") + "\n" + "\n".join(out) + "\n"
    if nt != t:
        chemin.write_text(nt, encoding="utf-8")
        return True
    return False


def _toucher_objet(chemin):
    core, O = _cb()[:2]
    rel = str(chemin.relative_to(ROOT)).replace("\\", "/")
    r = core.db().execute("SELECT id FROM objets WHERE chemin=?", (rel,)).fetchone()
    if r:
        O.update(r[0], acteur="recalcul")  # maj + sommaire
        return r[0]
    return None


# ------------------------------------------------------------------ tâches
def t_profil(arg, fin):
    core, O, F, K = _cb()[:4]
    g = K.get_full
    secs = [
        ("Identité", ["- nom: Mustafa Ekrem [déclaré par la constitution]",
                      "- fonction: juriste au sein d'une fiduciaire en Suisse [déclaré par la constitution]",
                      f"- prénom d'usage: {_val(K, 'mustafa.prenom')} {_marque(g('mustafa.prenom'))} · {_val(K, 'mustafa.tutoiement')} {_marque(g('mustafa.tutoiement'))}"]),
        ("Langues", [f"- {_val(K, 'mustafa.langues')} {_marque(g('mustafa.langues'))}"]),
        ("Cantons suivis", [f"- {_val(K, 'mustafa.cantons_suivis')} {_marque(g('mustafa.cantons_suivis'))}"]),
        ("Domaines", [f"- {_val(K, 'mustafa.domaines')} {_marque(g('mustafa.domaines'))}"]),
        ("Style", [f"- {_val(K, 'mustafa.style')} {_marque(g('mustafa.style'))} ; profil de style à apprendre de ses mails et documents"]),
    ]
    change = _reecrire(PROFIL, secs, garder=("Habitudes",))
    oid = _toucher_objet(PROFIL) if change else None
    return {"profil": "réécrit" if change else "inchangé", "objet": oid, "cle": arg}


def t_environnement(arg, fin):
    core, O, F, K = _cb()[:4]
    g = K.get_full
    secs = [
        ("Poste de Mustafa", [f"- système: {_val(K, 'workstation.systeme')} {_marque(g('workstation.systeme'))} · messagerie: {_val(K, 'workstation.messagerie')} "
                              f"{_marque(g('workstation.messagerie'))} · agenda: {_val(K, 'workstation.agenda')} {_marque(g('workstation.agenda'))}",
                              f"- Office: {_val(K, 'workstation.office')} {_marque(g('workstation.office'))} · navigateur: {_val(K, 'workstation.navigateur')} "
                              f"{_marque(g('workstation.navigateur'))} · logiciel de la fiduciaire: {_val(K, 'workstation.logiciel_fiduciaire') or 'inconnu'} "
                              f"{_marque(g('workstation.logiciel_fiduciaire'))}"]),
        ("Comptes et accès", [f"- bases de recherche: {_val(K, 'access.bases_recherche') or 'aucune connue'} {_marque(g('access.bases_recherche'))}",
                              f"- connecteurs: {_val(K, 'access.connecteurs') or 'aucun'} {_marque(g('access.connecteurs'))} · dépôt git: "
                              f"{_val(K, 'access.depot_git') or 'local'} {_marque(g('access.depot_git'))} · DeepL: {_val(K, 'access.deepl') or 'non'} {_marque(g('access.deepl'))}"]),
        ("Abonnements", [f"- Claude : {_val(K, 'access.abonnement_claude') or 'inconnu'} {_marque(g('access.abonnement_claude'))} → profil "
                         f"{_val(K, 'models.profil')} {_marque(g('models.profil'))}"]),
    ]
    change = _reecrire(ENVIRONNEMENT, secs, garder=("Machine de construction",))
    oid = _toucher_objet(ENVIRONNEMENT) if change else None
    return {"environnement": "réécrit" if change else "inchangé", "objet": oid}


def t_horloges_recalcul(arg, fin):
    """recalcule l'échéance des délais ouverts depuis leur règle et leur déclencheur (règles, cantons, jours fériés)"""
    core, O, F, K, B, M, H = _cb()
    con = core.db()
    H.seed()
    changes = []
    for d in [dict(r) for r in con.execute("SELECT * FROM delais WHERE statut='ouvert' AND regle IS NOT NULL AND declencheur_date IS NOT NULL")]:
        r = con.execute("SELECT * FROM regles_delais WHERE id=?", (d["regle"],)).fetchone()
        if not r:
            continue
        ech = H.echeance(dict(r), d["declencheur_date"]).isoformat()
        if ech != d["echeance"]:
            con.execute("UPDATE delais SET echeance=? WHERE id=?", (ech, d["id"]))
            con.commit()
            O.update(d["id"], chiffre_cle=f"échéance {ech}", acteur="recalcul")
            core.audit("horloge_recalcul", d["id"], f"{d['echeance']}→{ech} ({arg})", "recalcul")
            changes.append(f"{d['id']}:{d['echeance']}→{ech}")
    suivis = {str(c).upper() for c in (K.get("mustafa.cantons_suivis") or [])}
    hors = [r["id"] for r in con.execute("SELECT id, canton FROM delais WHERE statut='ouvert' AND COALESCE(canton,'')!=''")
            if r["canton"].upper() not in suivis]
    return {"recalcules": changes, "hors_cantons_suivis": hors}


def t_doctrine_cantons(arg, fin):
    core, O, F, K = _cb()[:4]
    cr = []
    for c in [str(x).upper() for x in (K.get("mustafa.cantons_suivis") or [])]:
        d = EQ / "brain" / "doctrine" / c
        d.mkdir(parents=True, exist_ok=True)
        r = core.db().execute("SELECT id FROM objets WHERE type='doctrine' AND canton=? AND statut!='archive'", (c,)).fetchone()
        if r:
            continue
        corps = (f"# Doctrine cantonale {c}\n\n## Rôle\nDossier de la doctrine et de la pratique du canton {c} : positions, pratiques de "
                 "l'administration fiscale, jurisprudence cantonale, concordances. Rien n'y entre sans source datée (loi 7).\n\n"
                 f"## Sources officielles\nVoir .team/scripts/library/cantons.yaml (canton {c}) ; textes ingérés : cerebro law search --juridiction {c}.\n\n"
                 "## Positions\n(aucune pour l'instant)\n")
        oid = O.create("doctrine", f"Doctrine cantonale {c}", body=corps, canton=c, chemin=f".team/brain/doctrine/{c}/README.md",
                       resume=f"Dossier de doctrine et pratique du canton {c} (créé quand le canton est devenu suivi)", domaine="doctrine",
                       prochaine_action="alimenter (veille, recherches sourcées)", prochaine_date=(core.today() + dt.timedelta(days=30)).isoformat(),
                       source=f"config mustafa.cantons_suivis ({arg})", acteur="recalcul")
        cr.append(oid)
    return {"doctrines_creees": cr, "cantons_yaml": cantons_yaml(arg)}


def cantons_yaml(arg=""):
    """ajoute à cantons.yaml les cantons suivis absents (insertion de texte : commentaires préservés). L'ingestion elle-même
    est la tâche `bibliotheque_cantons` (cantons.py, chantier bibliothèque), déjà mise en file par `config set`."""
    core, O, F, K, B = _cb()[:5]
    import yaml
    suivis = [str(x).upper() for x in (K.get("mustafa.cantons_suivis") or [])]
    if not CANTONS_YAML.exists():
        return {"absent": str(CANTONS_YAML.name)}
    t = CANTONS_YAML.read_text(encoding="utf-8")
    connus = set(((yaml.safe_load(t) or {}).get("cantons") or {}).keys())
    ajoutes = []
    for c in suivis:
        if c in connus or not re.fullmatch(r"[A-Z]{2}", c):
            continue
        bloc = (f"  {c}:\n    recueil: à identifier (recueil systématique du canton {c})\n"
                f"    url: https://www.lexfind.ch/fe/fr\n    langue: à confirmer\n    acces_automatise: inconnu\n"
                f"    detail: >-\n      Ajouté le {core.iso()} quand {c} est devenu canton suivi ({arg or 'configuration'}). Recueil officiel à identifier via LexFind,\n"
                f"      puis convertisseur et cerebro law ingest --juridiction {c}. En attendant : ⚠ « pratique cantonale à vérifier ».\n"
                f"    ingere: false\n    textes_prioritaires: []\n")
        lignes = t.split("\n")
        try:
            i = lignes.index("cantons:")
        except ValueError:
            break
        k = i + 1
        while k < len(lignes) and (lignes[k].startswith(" ") or lignes[k].startswith("#") or not lignes[k].strip()):
            k += 1
        t = "\n".join(lignes[:k]).rstrip("\n") + "\n" + bloc + ("\n".join(lignes[k:]) if k < len(lignes) else "")
        ajoutes.append(c)
    if ajoutes:
        yaml.safe_load(t)  # contrôle : jamais un YAML cassé
        CANTONS_YAML.write_text(t, encoding="utf-8")
    return {"ajoutes": ajoutes}


def t_connecteurs(arg, fin):
    core, O, F, K = _cb()[:4]
    mess = core.fold(_val(K, "workstation.messagerie"))
    res = {"messagerie": mess}
    connecte = bool(K.get("workstation.messagerie_connectee"))
    script = EQ / "scripts" / "connectors" / "connect_mail.py"
    if not connecte and script.exists() and any(w in mess for w in ("outlook", "microsoft", "365", "exchange")):
        try:
            r = subprocess.run([fond.python_exe(), str(script), "--etat"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=30, cwd=str(ROOT), env=fond.env_fond(), stdin=subprocess.DEVNULL)
            etat = json.loads((r.stdout or "{}").strip().splitlines()[-1] or "{}")
            connecte = bool(etat.get("connecte") or etat.get("ok"))
        except Exception as e:
            journal("erreurs-fond", job="connecteurs", erreur=repr(e)[:200])
        if not connecte:
            res["question"] = F.question_add("Je peux préparer vos réponses directement dans Outlook (sans jamais rien envoyer) : il suffit de cliquer "
                                             "« Autoriser » une fois. On le fait ?", "brouillons dans la messagerie (boucle d'initiative)",
                                             "brouillons en fichiers", "technique", 3, None, "messagerie")
    elif not connecte and any(w in mess for w in ("gmail", "google")):
        res["installation"] = _ligne_installation("Messagerie Google : connecteur Gmail officiel (lecture + brouillons, sans envoi) à autoriser "
                                                  "une fois depuis claude.ai (Paramètres → Connecteurs) ; en attendant, mails déposés en .eml.")
    res["connecte"] = connecte
    return res


def _ligne_installation(texte):
    if not INSTALLATION.exists():
        return False
    t = INSTALLATION.read_text(encoding="utf-8")
    if texte in t:
        return False
    ancre = "## Plus tard, au moment utile"
    if ancre in t:
        a, b = t.split(ancre, 1)
        nl = b.find("\n")
        t = a + ancre + b[:nl + 1] + f"- {texte}\n" + b[nl + 1:]
    else:
        t = t.rstrip() + f"\n\n- {texte}\n"
    INSTALLATION.write_text(t, encoding="utf-8")
    return True


def t_specialistes(arg, fin):
    core, O, F, K, B = _cb()[:5]
    agents = {p.stem for p in (ROOT / ".claude" / "agents").glob("*.md")}
    couverts, manquants = {}, []
    for d in [str(x) for x in (K.get("mustafa.domaines") or [])]:
        f = core.fold(d)
        a = next((ag for k, ag in DOMAINES_AGENTS.items() if k in f and ag in agents), None)
        if a:
            couverts[d] = a
        else:
            manquants.append(d)
            B.queue_add("fabrique", f"spécialiste pour le domaine « {d} » cité par Mustafa (aucun sous-agent ne le couvre)", 5)
    return {"couverts": couverts, "a_fabriquer": manquants}


def t_modeles_roles(arg, fin):
    """met à jour le champ model: des sous-agents selon §6.6 et models.yaml (alias opus|sonnet|haiku ou nom exact)"""
    core, O, F, K = _cb()[:4]
    faits = []
    for p in sorted((ROOT / ".claude" / "agents").glob("*.md")):
        nom = p.stem
        palier = next((pa for pa, s in PALIER_AGENT.items() if nom in s or (pa == "plus_capable" and nom.startswith("specialiste-"))), None)
        if not palier:
            continue
        modele = str(K.get(f"models.{palier}") or ALIAS_MODELE[palier])
        t = p.read_text(encoding="utf-8")
        m = re.match(r"---\n(.*?)\n---", t, re.S)
        if not m:
            continue
        head = m.group(1)
        nh = re.sub(r"^model:.*$", f"model: {modele}", head, count=1, flags=re.M) if re.search(r"^model:", head, re.M) else head + f"\nmodel: {modele}"
        if nh != head:
            p.write_text("---\n" + nh + "\n---" + t[m.end():], encoding="utf-8")
            faits.append(f"{nom}:{modele}")
    return {"mis_a_jour": faits}


def t_clients_import(arg, fin):
    core, O, F, K, B, M = _cb()[:6]
    from cb.search import find
    cr = []
    for nom in [str(x).strip() for x in (K.get("clients.principaux") or []) if str(x).strip()]:
        hits = [h for h in find(nom, limit=3, types=["client"]) if h.get("id") and not h.get("presque")]
        if hits:
            continue
        cr.append(M.client_new(nom, "", None, "fr", [], f"client principal déclaré par Mustafa ({arg or 'configuration'})"))
    return {"clients_crees": cr}


def t_lanceurs(arg, fin):
    core, O, F, K = _cb()[:4]
    s = core.fold(_val(K, "workstation.systeme"))
    d = EQ / "scripts" / "launchers"
    attendus = {"windows": ["launch-jurix.ps1", "launch-jurix.bat"], "mac": ["launch-jurix.command"], "linux": ["launch-jurix.sh"]}
    cle = "windows" if "win" in s else ("mac" if "mac" in s or "os x" in s else "linux")
    manquants = [f for f in attendus[cle] if not (d / f).exists()]
    if manquants:
        fond.incident(f"lanceur absent pour le poste ({cle}) : {', '.join(manquants)}", "lanceur", "installateur à relancer (INSTALLATION.md)")
    t_environnement(arg, fin)
    return {"systeme": cle, "manquants": manquants}


def t_design(arg, fin):
    core, O, F, K, B = _cb()[:5]
    p = EQ / "scripts" / "producer" / "design.py"
    out = {}
    if p.exists():
        r = subprocess.run([fond.python_exe(), str(p), "--verifier"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=120, cwd=str(ROOT), env=fond.env_fond(), stdin=subprocess.DEVNULL)
        try:
            out["contrastes_ok"] = json.loads((r.stdout or "{}").strip().splitlines()[-1]).get("ok")
        except Exception:
            out["contrastes_ok"] = None
    B.queue_add("gabarits", arg or "design", 2)
    return out


TACHES = {"profil": t_profil, "environnement": t_environnement, "horloges_recalcul": t_horloges_recalcul,
          "doctrine_cantons": t_doctrine_cantons, "connecteurs": t_connecteurs,
          "specialistes": t_specialistes, "modeles_roles": t_modeles_roles, "clients_import": t_clients_import,
          "lanceurs": t_lanceurs, "design": t_design}
