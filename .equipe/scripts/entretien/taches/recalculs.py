"""Extension du cycle : recalculs posés par `cerebro config set` (file d'entretien, priorité 2 ; arg = clé modifiée).
Script d'abord (§7.6) ; aucun appel de modèle ici. Une valeur réelle remplace le défaut et tout ce qui en dépend est
recalculé (§0 bis) : horloges, doctrine et bibliothèque cantonales, profil, environnement, connecteurs, spécialistes,
modèles des sous-agents, clients principaux, lanceurs, design."""
import os, re, sys, json, subprocess, datetime as dt
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
import fond  # noqa: E402
from fond import ROOT, EQ, journal  # noqa: E402

CABINET = EQ / "cerveau" / "cabinet"
PROFIL = CABINET / "profil-mustafa.md"
ENVIRONNEMENT = CABINET / "environnement.md"
CANTONS_YAML = EQ / "scripts" / "bibliotheque" / "cantons.yaml"
INSTALLATION = ROOT / "Bureau" / "Informatique" / "INSTALLATION.md"

# §6.6 : palier par sous-agent (l'associé n'est pas un sous-agent ; l'intendant est un processus de fond)
PALIER_AGENT = {
    "plus_capable": {"chercheur", "avocat-plaideur", "redacteur", "editeur-humain", "panel-adverse", "conseiller-anticipation",
                     "stratege", "negociateur", "fabricant"},
    "intermediaire": {"documentaliste", "relecteur", "calculateur", "officier-conformite", "secretaire-societe", "commercial",
                      "marketeur", "communicant", "veilleur", "ingesteur", "directeur-artistique", "visualiseur", "intendant",
                      "tuteur", "producteur", "responsable-experience", "archiviste"},
    "leger": {"chef-de-cabinet", "greffier"},
}
ALIAS_MODELE = {"plus_capable": "opus", "intermediaire": "sonnet", "leger": "haiku"}
DOMAINES_AGENTS = {  # mot-clé (sans accents) → sous-agent spécialiste existant
    "societ": "specialiste-societes-rc", "registre": "specialiste-societes-rc", "fusion": "specialiste-societes-rc",
    "fiscal": "specialiste-fiscalite-entreprises", "impot": "specialiste-fiscalite-entreprises", "tva": "specialiste-tva",
    "succession": "specialiste-successions-regimes", "matrimon": "specialiste-successions-regimes", "contrat": "specialiste-contrats",
    "travail": "specialiste-travail-assurances-sociales", "social": "specialiste-travail-assurances-sociales",
    "lba": "specialiste-lba-conformite", "blanchiment": "specialiste-lba-conformite", "conformit": "specialiste-lba-conformite",
    "immobil": "specialiste-immobilier-lex-koller", "koller": "specialiste-immobilier-lex-koller", "poursuite": "specialiste-poursuites-faillites",
    "faillite": "specialiste-poursuites-faillites", "international": "specialiste-fiscalite-internationale", "cdi": "specialiste-fiscalite-internationale",
    "etranger": "specialiste-droit-etranger", "personnes physiques": "specialiste-personnes-physiques", "arrivant": "specialiste-personnes-physiques",
}


def _cb():
    fond.cb()
    from cb import core, objets as O, files as F, config as K, brief as B, metier as M, horloges as H
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
        ("Poste de Mustafa", [f"- système: {_val(K, 'poste.systeme')} {_marque(g('poste.systeme'))} · messagerie: {_val(K, 'poste.messagerie')} "
                              f"{_marque(g('poste.messagerie'))} · agenda: {_val(K, 'poste.agenda')} {_marque(g('poste.agenda'))}",
                              f"- Office: {_val(K, 'poste.office')} {_marque(g('poste.office'))} · navigateur: {_val(K, 'poste.navigateur')} "
                              f"{_marque(g('poste.navigateur'))} · logiciel de la fiduciaire: {_val(K, 'poste.logiciel_fiduciaire') or 'inconnu'} "
                              f"{_marque(g('poste.logiciel_fiduciaire'))}"]),
        ("Comptes et accès", [f"- bases de recherche: {_val(K, 'acces.bases_recherche') or 'aucune connue'} {_marque(g('acces.bases_recherche'))}",
                              f"- connecteurs: {_val(K, 'acces.connecteurs') or 'aucun'} {_marque(g('acces.connecteurs'))} · dépôt git: "
                              f"{_val(K, 'acces.depot_git') or 'local'} {_marque(g('acces.depot_git'))} · DeepL: {_val(K, 'acces.deepl') or 'non'} {_marque(g('acces.deepl'))}"]),
        ("Abonnements", [f"- Claude : {_val(K, 'acces.abonnement_claude') or 'inconnu'} {_marque(g('acces.abonnement_claude'))} → profil "
                         f"{_val(K, 'modeles.profil')} {_marque(g('modeles.profil'))}"]),
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
        d = EQ / "cerveau" / "doctrine" / c
        d.mkdir(parents=True, exist_ok=True)
        r = core.db().execute("SELECT id FROM objets WHERE type='doctrine' AND canton=? AND statut!='archive'", (c,)).fetchone()
        if r:
            continue
        corps = (f"# Doctrine cantonale {c}\n\n## Rôle\nDossier de la doctrine et de la pratique du canton {c} : positions, pratiques de "
                 "l'administration fiscale, jurisprudence cantonale, concordances. Rien n'y entre sans source datée (loi 7).\n\n"
                 f"## Sources officielles\nVoir .equipe/scripts/bibliotheque/cantons.yaml (canton {c}) ; textes ingérés : cerebro law search --juridiction {c}.\n\n"
                 "## Positions\n(aucune pour l'instant)\n")
        oid = O.create("doctrine", f"Doctrine cantonale {c}", body=corps, canton=c, chemin=f".equipe/cerveau/doctrine/{c}/README.md",
                       resume=f"Dossier de doctrine et pratique du canton {c} (créé quand le canton est devenu suivi)", domaine="doctrine",
                       prochaine_action="alimenter (veille, recherches sourcées)", prochaine_date=(core.today() + dt.timedelta(days=30)).isoformat(),
                       source=f"config mustafa.cantons_suivis ({arg})", acteur="recalcul")
        cr.append(oid)
    return {"doctrines_creees": cr}


def t_bibliotheque_cantons(arg, fin):
    """ajoute à cantons.yaml les cantons suivis absents (insertion de texte : commentaires préservés) et met l'ingestion en file"""
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
    for c in suivis:
        B.queue_add("bibliotheque_canton", c, 5)
    return {"ajoutes": ajoutes, "ingestion_en_file": suivis}


def t_connecteurs(arg, fin):
    core, O, F, K = _cb()[:4]
    mess = core.fold(_val(K, "poste.messagerie"))
    res = {"messagerie": mess}
    connecte = bool(K.get("poste.messagerie_connectee"))
    script = EQ / "scripts" / "connecteurs" / "connecter_messagerie.py"
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
    """met à jour le champ model: des sous-agents selon §6.6 et modeles.yaml (alias opus|sonnet|haiku ou nom exact)"""
    core, O, F, K = _cb()[:4]
    faits = []
    for p in sorted((ROOT / ".claude" / "agents").glob("*.md")):
        nom = p.stem
        palier = next((pa for pa, s in PALIER_AGENT.items() if nom in s or (pa == "plus_capable" and nom.startswith("specialiste-"))), None)
        if not palier:
            continue
        modele = str(K.get(f"modeles.{palier}") or ALIAS_MODELE[palier])
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
    from cb.recherche import find
    cr = []
    for nom in [str(x).strip() for x in (K.get("clients.principaux") or []) if str(x).strip()]:
        hits = [h for h in find(nom, limit=3, types=["client"]) if h.get("id") and not h.get("presque")]
        if hits:
            continue
        cr.append(M.client_new(nom, "", None, "fr", [], f"client principal déclaré par Mustafa ({arg or 'configuration'})"))
    return {"clients_crees": cr}


def t_lanceurs(arg, fin):
    core, O, F, K = _cb()[:4]
    s = core.fold(_val(K, "poste.systeme"))
    d = EQ / "scripts" / "lanceurs"
    attendus = {"windows": ["Mon-equipe.ps1", "Mon-equipe.bat"], "mac": ["Mon-equipe.command"], "linux": ["mon-equipe.sh"]}
    cle = "windows" if "win" in s else ("mac" if "mac" in s or "os x" in s else "linux")
    manquants = [f for f in attendus[cle] if not (d / f).exists()]
    if manquants:
        fond.incident(f"lanceur absent pour le poste ({cle}) : {', '.join(manquants)}", "lanceur", "installateur à relancer (INSTALLATION.md)")
    t_environnement(arg, fin)
    return {"systeme": cle, "manquants": manquants}


def t_design(arg, fin):
    core, O, F, K, B = _cb()[:5]
    p = EQ / "scripts" / "producteur" / "design.py"
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
          "doctrine_cantons": t_doctrine_cantons, "bibliotheque_cantons": t_bibliotheque_cantons, "connecteurs": t_connecteurs,
          "specialistes": t_specialistes, "modeles_roles": t_modeles_roles, "clients_import": t_clients_import,
          "lanceurs": t_lanceurs, "design": t_design}
