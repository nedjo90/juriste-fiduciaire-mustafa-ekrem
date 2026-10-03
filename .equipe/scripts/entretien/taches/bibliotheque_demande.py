"""Extension du cycle : la bibliothèque n'est jamais limitée aux textes d'aujourd'hui (§10). Scripts seulement, aucun modèle.

- `bibliotheque_ingest` (file, priorité donnée par l'appelant ; réseau) : un texte demandé mais absent est ajouté.
  Arg = numéro RS (« 642.14 », « RS 221.229.1 ») ou adresse Fedlex (eli/cc/… ou eli/oc/…) → fedlex.py ingest ;
  abréviation d'une loi cantonale connue (« LI-VD ») → cantons.py. Mis en file par `cerebro law article` quand le texte
  manque, par la veille (texte touché par une publication) et par l'enrichissement (source officielle consultée).
- `bibliotheque_cantons_changements` (après chaque passage de la bibliothèque cantonale) : une loi cantonale dont une
  nouvelle version a été ingérée devient un objet `changement_droit` relié à l'ancienne version et aux objets qui la
  citent ; la veille juge ensuite la pertinence par client, comme pour le droit fédéral."""
import re, sys, json, subprocess
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent))
import fond  # noqa: E402
from fond import ROOT, EQ  # noqa: E402

CODE = Path(__file__).resolve().parents[3]
BIB = CODE / "scripts" / "bibliotheque"
RS = re.compile(r"^(?:RS\s*)?(0\.\d+(?:\.\d+)*|\d{3}(?:\.\d+)*)$", re.I)


def _script(nom, *args, timeout=1800):
    r = subprocess.run([fond.python_exe(), str(BIB / nom), *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(ROOT), env=fond.env_fond(), timeout=timeout, stdin=subprocess.DEVNULL)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"erreur": (r.stderr or r.stdout or "")[-300:]}


def _rs_depuis_eli(url):
    """numéro RS d'une adresse Fedlex (consolidée ou publication) par le classement systématique"""
    sys.path.insert(0, str(BIB))
    import fedlex
    base = re.sub(r"(/eli/(?:cc|oc)/[^/]+/[^/]+).*", r"\1", url)
    q = fedlex.PFX + f"""SELECT DISTINCT ?n WHERE {{ <{base}> jolux:classifiedByTaxonomyEntry ?t . ?t skos:notation ?n }}"""
    return [str(r["n"]) for r in fedlex.sparql(q)]


def t_bibliotheque_ingest(arg, fin):
    arg = (arg or "").strip()
    if not arg:
        return {"rien": True}
    m = RS.match(arg)
    if m:
        cibles = [m.group(1)]
    elif "fedlex.admin.ch/eli/" in arg:
        cibles = _rs_depuis_eli(arg)
    else:
        cibles = []
    if cibles:
        res = _script("fedlex.py", "ingest", *cibles)
        return {"ingeres": [x.get("id") for x in (res if isinstance(res, list) else []) if isinstance(x, dict) and x.get("id")],
                "detail": res if not isinstance(res, list) else None}
    canton = re.match(r"^[A-Za-z]+-(VD|GE|VS|FR|NE|JU|BE|ZH|TI)$", arg, re.I)
    if canton:
        return _script("cantons.py", "ingerer", "--canton", canton.group(1).upper(), "--texte", arg)
    if "fedlex.admin.ch/eli/" in arg:
        return {"ignore": arg[:120], "raison": "publication Fedlex sans numéro RS (acte non classé) : rien à ajouter"}
    # autre source (page officielle, circulaire) : copie et lecture par la recherche ; rien à ingérer ici
    return {"ignore": arg[:120], "raison": "ni numéro RS, ni adresse Fedlex, ni loi cantonale connue"}


def t_bibliotheque_cantons_changements(arg, fin):
    fond.cb()
    from cb import core, objets as O
    con = core.db()
    deja = {r[0] for r in con.execute("SELECT source FROM objets WHERE type='changement_droit' AND COALESCE(source,'')!=''")}
    faits = []
    for (ident,) in con.execute("SELECT DISTINCT identifiant FROM bibliotheque WHERE juridiction!='CH'").fetchall():
        v = con.execute("SELECT b.id, b.version, b.url, b.abreviation, b.titre, b.juridiction FROM bibliotheque b WHERE b.identifiant=? "
                        "ORDER BY b.version DESC LIMIT 2", (ident,)).fetchall()
        if len(v) < 2:
            continue
        neuf, ancien = dict(v[0]), dict(v[1])
        cle = f"{neuf['url']}#version={neuf['version']}"
        if cle in deja:
            continue
        citants = [r[0] for r in con.execute("SELECT src FROM liens WHERE dst=?", (ancien["id"],))]
        cid = O.create("changement_droit", core.cut(f"{neuf['abreviation'] or ident} : nouvelle version du {neuf['version']}", 120),
                       source=cle, domaine="veille", liens=[neuf["id"], ancien["id"], *citants],
                       resume=core.cut(f"{neuf['juridiction']} {ident} — la version en vigueur passe du {ancien['version']} au "
                                       f"{neuf['version']}. Relire les règles de délai, positions et modèles liés.", 280),
                       prochaine_action="analyser l'impact (veille)", acteur="bibliotheque")
        faits.append(cid)
    return {"changements": faits}


TACHES = {"bibliotheque_ingest": t_bibliotheque_ingest, "bibliotheque_cantons_changements": t_bibliotheque_cantons_changements}
CADENCES = {"bibliotheque_cantons_changements": (7, 5)}
RESEAU = {"bibliotheque_ingest"}
