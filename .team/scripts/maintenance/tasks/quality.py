"""Extension du cycle : qualité (§7.5, §0 quater 4, §10, §14). Scripts seulement, aucun appel de modèle.
- `principes` (chaque cycle complet, priorité 4) : tableau de bord des principes (portes/dashboard.py) → état `principes`
  (lu par cerebro health) ; un rôle ou une skill en écart deux cycles complets de suite → file `fabrique`
  « réviser <nom> » (la fabrique révise, incrémente la version, enrichit les fixtures du cas fautif).
- `bibliotheque_cantons` (30 jours, et dès qu'un canton suivi n'a aucun texte ingéré ; priorité 5 ; réseau) :
  bibliotheque/cantons.py ingerer (lois des cantons suivis depuis les recueils officiels) puis vérification des règles
  de délai cantonales (cerebro law verify). Un arg « VD:LI-VD » (rattrapage) ne retente que ce texte."""
import sys, json, subprocess
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
import background as fond  # noqa: E402
from background import ROOT, EQ, journal  # noqa: E402

CODE = Path(__file__).resolve().parents[3]          # .team du code
PORTES = CODE / "scripts" / "gates"
CANTONS = CODE / "scripts" / "library" / "cantons.py"


def _cb():
    fond.cb()
    from cb import core, brief as B, config as K
    return core, B, K


def t_principes(arg, fin):
    core, B, _ = _cb()
    for p in (str(PORTES), str(CODE / "scripts" / "producer")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import dashboard as tableau
    tb = tableau.tableau(30)
    ecarts = tb.get("ecarts", [])
    precedent = {e["nom"] for e in (core.get_etat("principes", {}) or {}).get("ecarts", []) if e.get("axe") in ("par_role", "par_skill")}
    revisions = []
    for e in ecarts:
        if e["nom"] in precedent and e["nom"] not in ("?", ""):
            arg_f = f"réviser {e['nom']}"
            B.queue_add("fabrique", arg_f, 5)
            revisions.append(arg_f)
    portes_faibles = sorted(((k, v["taux"]) for k, v in tb.get("par_porte", {}).items() if v.get("taux") is not None and v["taux"] < tableau.SEUIL_ECART),
                            key=lambda x: x[1])[:5]
    resume = {"le": core.stamp(), "periode_jours": tb.get("periode_jours"),
              "passages": sum(v["passages"] for v in tb.get("par_porte", {}).values()),
              "roles": len(tb.get("par_role", {})), "skills": len(tb.get("par_skill", {})),
              "ecarts": ecarts[:20], "portes_faibles": portes_faibles, "revisions_demandees": revisions,
              "ligne": (f"{len(ecarts)} écart(s) de principe" + (f", {len(revisions)} révision(s) demandée(s) à la fabrique" if revisions else "")
                        if ecarts else "aucun écart de principe")}
    core.set_etat("principes", resume)
    journal("qualite", tache="principes", ecarts=len(ecarts), revisions=revisions)
    return {"ecarts": len(ecarts), "revisions": revisions}


def _textes_cantonaux_manquants():
    core, _, K = _cb()
    suivis = [str(c).upper() for c in (K.get("mustafa.cantons_suivis") or ["VD", "GE"])]
    have = {r[0] for r in core.db().execute("SELECT DISTINCT juridiction FROM bibliotheque")}
    return [c for c in suivis if c not in have]


def t_bibliotheque_cantons(arg, fin):
    args = ["ingerer"]
    if arg and ":" in arg:
        c, t = arg.split(":", 1)
        args += ["--canton", c, "--texte", t]
    elif arg:
        args += ["--canton", arg]
    py = fond.python_exe() if hasattr(fond, "python_exe") else sys.executable
    r = subprocess.run([py, str(CANTONS), *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=str(ROOT), env=fond.env_fond(), timeout=1800)
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        return {"erreur": (r.stderr or r.stdout)[-300:]}
    ing = out.get("ingestion", [])
    verif = (out.get("verification") or {}).get("regles_cantonales", [])
    return {"ingeres": [f"{x.get('canton')}:{x.get('abrev')}" for x in ing if x.get("id")],
            "echecs": [f"{x.get('canton')}:{x.get('abrev')}" for x in ing if x.get("erreur")],
            "regles_verifiees": [x["regle"] for x in verif if x.get("verifie")]}


TACHES = {"principes": t_principes, "bibliotheque_cantons": t_bibliotheque_cantons}
CADENCES = {"bibliotheque_cantons": (30, 5)}
RESEAU = {"bibliotheque_cantons"}


def PLANIFIER(complet, mode, ajouter):
    if complet:
        ajouter("principes", "", 4)
    if mode != "court":
        try:
            if _textes_cantonaux_manquants():
                ajouter("bibliotheque_cantons", "", 5)
        except Exception as e:
            journal("erreurs-fond", job="qualite", ou="planifier cantons", erreur=repr(e)[:200])
