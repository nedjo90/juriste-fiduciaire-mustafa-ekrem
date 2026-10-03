#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests du chantier « équipe » (T-050, T-052, T-070, T-090 rôles, T-100 structure) — lecture seule, aucune écriture en base.
Lancement : python .team/tests/test_team.py  (Windows : py .team\\tests\\test_team.py). Sortie OK / ÉCHEC par test.
Un échec crée un ticket par le cycle d'entretien ; il ne bloque rien (§0)."""
import json, os, re, sqlite3, subprocess, sys
from pathlib import Path

try:
    import yaml
except ImportError:  # PyYAML attendu ; repli minimal
    yaml = None

ROOT = Path(os.environ.get("CEREBRO_ROOT") or Path(__file__).resolve().parents[2])
DB = Path(os.environ.get("CEREBRO_DB") or ROOT / ".team" / "cerebro" / "cerebro.db")
PY = sys.executable
CEREBRO = [PY, str(ROOT / ".team" / "cerebro" / "cerebro.py")]

AGENTS = sorted((ROOT / ".claude" / "agents").glob("*.md"))
ROLES_FOND = [ROOT / ".team" / "roles" / f"{n}.md" for n in ("builder", "chief-of-staff", "legal-watch", "ingester", "archivist", "coach")]
SKILLS = ["legal-memo", "email-drafting", "tax-objection", "shareholders-agreement", "general-meeting-minutes",
          "circular-resolutions", "sourced-legal-research", "conflict-check", "aml-file", "foresight-review",
          "daily-brief", "inbox-ingestion", "meeting-report", "meeting-prep", "law-change-alert", "client-onboarding",
          "tabular-review", "fact-chronology", "amendment-history", "spreadsheet-audit"]
SKILL_FILES = [ROOT / ".claude" / "skills" / n / "SKILL.md" for n in SKILLS]
ATTENDUS = ["foresight-advisor", "company-law-specialist", "corporate-tax-specialist", "individual-tax-specialist",
            "vat-specialist", "estates-specialist", "contracts-specialist", "employment-specialist",
            "aml-specialist", "real-estate-specialist", "debt-enforcement-specialist",
            "international-tax-specialist", "foreign-law-specialist", "researcher", "source-checker", "litigator",
            "drafter", "calculator", "compliance-officer", "corporate-secretary", "adversarial-panel", "proofreader", "human-editor",
            "art-director", "visualizer", "strategist", "business-developer", "negotiator", "marketer", "communicator",
            "chief-of-staff", "archivist", "legal-watch", "ingester", "coach", "producer", "builder"]
CABINET = ["identity.md", "comfort-levels.md", "styles.md", "deliverable-models.md", "glossary.md", "lexicon.md", "partner.md"]
MODELES = {"opus", "sonnet", "haiku"}
PLUS_CAPABLE = {"foresight-advisor", "researcher", "litigator", "drafter", "human-editor", "adversarial-panel", "strategist",
                "negotiator", "builder"}

resultats = []
def test(nom, ok, detail=""):
    resultats.append(ok)
    print(("OK     " if ok else "ÉCHEC  ") + nom + ("" if ok else f" → {detail}"))

def lire(p):
    return p.read_text(encoding="utf-8")

def front(p):
    t = lire(p)
    if not t.startswith("---\n"):
        return None
    bloc = t[4:t.find("\n---", 4)]
    if yaml:
        return yaml.safe_load(bloc)
    return dict(l.split(": ", 1) for l in bloc.splitlines() if ": " in l)

def cli(*a):
    r = subprocess.run(CEREBRO + list(a), capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
                       env={**os.environ, "CEREBRO_ROOT": str(ROOT), "CEREBRO_BACKGROUND": "1"})
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"erreur": r.stdout[-300:] + r.stderr[-300:]}

# 1 YAML des sous-agents
mauvais = []
for p in AGENTS:
    try:
        y = front(p)
        ok = y and all(y.get(k) for k in ("name", "description", "tools", "model")) and y["name"] == p.stem \
            and re.fullmatch(r"[a-z0-9-]+", y["name"]) and y["model"] in MODELES
        if not ok:
            mauvais.append(p.name)
    except Exception as e:
        mauvais.append(f"{p.name}:{e}")
test("sous-agents : YAML valide (name = fichier, description, tools, model opus|sonnet|haiku)", not mauvais and AGENTS, mauvais)
manquants = [n for n in ATTENDUS if not (ROOT / ".claude" / "agents" / f"{n}.md").exists()]
test("sous-agents : les 37 rôles attendus existent", not manquants, manquants)
mod = [p.stem for p in AGENTS if p.stem in PLUS_CAPABLE and front(p)["model"] != "opus"] + \
      [p.stem for p in AGENTS if p.stem.startswith("specialiste-") and front(p)["model"] != "opus"] + \
      [p.stem for p in AGENTS if p.stem == "chief-of-staff" and front(p)["model"] != "haiku"]
test("sous-agents : modèle selon §6.6", not mod, mod)

# 2 skills : YAML, nom = dossier
mauvais = []
for p in SKILL_FILES:
    y = front(p) if p.exists() else None
    if not y or y.get("name") != p.parent.name or not y.get("description") or not re.fullmatch(r"[a-z0-9-]+", p.parent.name):
        mauvais.append(p.parent.name)
test("skills métier : YAML valide, name = dossier ASCII", not mauvais, mauvais)
src = [n for n in ("tabular-review", "fact-chronology", "amendment-history", "spreadsheet-audit", "aml-file")
       if not (ROOT / ".claude" / "skills" / n / "SOURCE.md").exists()]
test("skills importées : SOURCE.md présent", not src, src)

# 3 bloc cardinal à jour partout
r = cli("cardinal", "check")
test("bloc cardinal : `cerebro cardinal check` vide", isinstance(r, dict) and r.get("perimes") == [], r)
sans = [str(p.relative_to(ROOT)) for p in AGENTS + ROLES_FOND + SKILL_FILES if "<!-- BLOC-CARDINAL v" not in lire(p) or "SUMMARY PROTOCOL" not in lire(p)]
test("bloc cardinal + protocole sommaire présents dans chaque rôle et skill", not sans, sans)

# 4 aucune commande d'envoi hors interdiction explicite
ENVOI = re.compile(r"\bsend\b(?!-)|send_message|\bsubmit\b|envoyer le mail|envoie le mail|\.send\(|gmail.*send|mail.*--send", re.I)
NEG = re.compile(r"jamais|interdit|aucun|ne fait jamais|never|sans droit d'envoi|n'envoie|pas d'envoi|sans effet", re.I)
fautes = []
for p in AGENTS + ROLES_FOND + SKILL_FILES:
    section_jamais = False
    for i, l in enumerate(lire(p).splitlines(), 1):
        if l.startswith("## "):
            section_jamais = "jamais" in l.lower() or "never" in l.lower()
        if ENVOI.search(l) and not section_jamais and not NEG.search(l):
            fautes.append(f"{p.name}:{i}")
test("aucune commande d'envoi hors interdiction explicite", not fautes, fautes)
sans_jamais = [p.name for p in AGENTS + ROLES_FOND + SKILL_FILES if not re.search(r"## Never does\n.*(send|envoy|envoi)", lire(p), re.S)]
test("chaque rôle et skill déclare « ne fait jamais » (envoi compris)", not sans_jamais, sans_jamais)

# 5 principes et portes déclarés
PORTE = re.compile(r"P-(SRC|LIEN|SOM|CTX|COUV|PRES|EFF)|PANEL|RELEC|journal d'audit")
sans = [p.name for p in AGENTS + ROLES_FOND + SKILL_FILES
        if "## Principles applied and gates" not in lire(p) or not re.search(r"\bL\d+\b", lire(p).split("## Principles applied and gates", 1)[-1])
        or not PORTE.search(lire(p).split("## Principles applied and gates", 1)[-1])]
test("chaque rôle et skill déclare ses principes (L1-L10) et les portes qui les vérifient", not sans, sans)

# 6 identifiant en base pour chaque rôle, skill, fichier cabinet
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
chemins = {r[0]: r[1] for r in con.execute("SELECT chemin, id FROM objets WHERE statut!='archive'")}
sans_id = [str(p.relative_to(ROOT)) for p in AGENTS + ROLES_FOND + SKILL_FILES if str(p.relative_to(ROOT)).replace("\\", "/") not in chemins]
sans_id += [f for f in CABINET if f".team/brain/firm/{f}" not in chemins]
test("chaque rôle, skill et fichier cabinet a un identifiant en base", not sans_id, sans_id)

# 7 fiches méthodes : 16, identifiants MET, sections obligatoires
mets = con.execute("SELECT id, chemin FROM objets WHERE type='methode' AND statut!='archive'").fetchall()
mauvais = []
for oid, ch in mets:
    t = lire(ROOT / ch)
    if not all(s in t for s in ("## Steps", "## Checks", "## Pitfalls", "## Example")) or f"id: {oid}" not in t:
        mauvais.append(oid)
test("fiches méthodes : ≥ 16, en-tête et sections (étapes, contrôle, pièges, exemple)", len(mets) >= 16 and not mauvais, (len(mets), mauvais))
ids_met = {m[0] for m in mets}
morts = sorted({m for p in AGENTS + SKILL_FILES for m in re.findall(r"MET-\d{3}", lire(p)) if m not in ids_met})
test("tout MET- cité par un rôle ou une skill existe", not morts, morts)
sans_met = [p.stem for p in AGENTS if not re.search(r"MET-\d{3}", lire(p))]
test("chaque sous-agent cite au moins une fiche méthode", not sans_met, sans_met)

# 8 associé : court (≤ 1 800 tokens estimés) et règles clés
a = lire(ROOT / ".team" / "brain" / "firm" / "partner.md")
cles = ["single voice", "Rule zero", "question next --sujet", "Drafts only", "entre nous", "this is a matter for a lawyer",
        "deliverable-production", "adversarial panel", "1 500 characters", "ce que vous n'avez pas demandé"]
manque = [c for c in cles if c.lower() not in a.lower()]
test("partner.md : ≤ 1 800 tokens (≈ 3,5 car./token) et règles clés présentes", len(a) / 3.5 <= 1800 and not manque, (len(a), manque))

# 9 glossaire : chaque article cité est vérifiable dans la bibliothèque
faux = []
for num, abr, bib in re.findall(r"art\. (\S+) (\S+) \((BIB-\d+), état", lire(ROOT / ".team" / "brain" / "firm" / "glossary.md")):
    r = cli("law", "article", abr, f"art. {num}")
    if not (isinstance(r, dict) and r.get("texte") and r.get("source") == bib):
        faux.append(f"art. {num} {abr}")
test("glossaire : chaque article indiqué est vérifié en bibliothèque (sinon ⚠ à relier)", not faux, faux)

# 10 conventions de chemins ASCII pour la zone humaine
acc = [p.name for p in AGENTS + ROLES_FOND + SKILL_FILES if re.search(r"Bureau/(À|À|Déposés|Modèles)", lire(p))]
test("chemins de la zone humaine en ASCII (Bureau/A-deposer, Deposes, Modeles)", not acc, acc)

# 11 rapport ≤ 1 500 caractères exigé dans chaque sous-agent
sans = [p.stem for p in AGENTS if "1 500 characters" not in lire(p)]
test("chaque sous-agent impose un rapport ≤ 1 500 caractères (IDs + lignes de sommaire)", not sans, sans)

print("OK" if all(resultats) else f"ÉCHEC ({resultats.count(False)}/{len(resultats)})")
sys.exit(0)
