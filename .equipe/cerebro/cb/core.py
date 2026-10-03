"""Noyau cerebro : chemins, base SQLite, schéma, identifiants, horloge Europe/Zurich, journaux.
Aucune fonction de ce module ne lève d'erreur bloquante vers une session : les appelants (hooks) enveloppent tout."""
import os, sys, json, sqlite3, re, unicodedata, datetime as dt
from pathlib import Path

ROOT = Path(os.environ.get("CEREBRO_ROOT") or Path(__file__).resolve().parents[3])
EQ = ROOT / ".equipe"
CB = EQ / "cerebro"
def _db_defaut():
    """base dans le projet, sauf dossier synchronisé (OneDrive…) : WAL + synchronisation = verrous et corruption (§9.4)"""
    od = [os.environ.get(k) for k in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer") if os.environ.get(k)]
    synchro = any(str(ROOT).lower().startswith(o.lower()) for o in od) or any(x in str(ROOT).lower() for x in ("onedrive", "dropbox", "icloud", "google drive"))
    if synchro and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "cerebro" / slug(str(ROOT), 60) / "cerebro.db"
    return CB / "cerebro.db"

DB_PATH = None  # résolu à la première connexion (après la définition de slug)
CERVEAU = EQ / "cerveau"
SOMMAIRES = EQ / "sommaires"
JOURNAL = CERVEAU / "journal"
SESSION = CERVEAU / "session"
BUREAU = ROOT / "Bureau"
EXPORTS = CB / "exports"

# --- heure suisse, sans dépendre de tzdata (absent sur Windows) -----------------
def _last_sunday(year, month):
    d = dt.date(year, month + 1, 1) - dt.timedelta(days=1) if month < 12 else dt.date(year, 12, 31)
    return d - dt.timedelta(days=(d.weekday() + 1) % 7)

def now():
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Europe/Zurich")).replace(microsecond=0)
    except Exception:
        u = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        start = dt.datetime.combine(_last_sunday(u.year, 3), dt.time(1), dt.timezone.utc)
        end = dt.datetime.combine(_last_sunday(u.year, 10), dt.time(1), dt.timezone.utc)
        off = 2 if start <= u < end else 1
        return u.astimezone(dt.timezone(dt.timedelta(hours=off)))

def today():
    d = os.environ.get("CEREBRO_TODAY")  # tests : date simulée
    return dt.date.fromisoformat(d) if d else now().date()

def iso(d=None):
    return (d or today()).isoformat()

def stamp():
    return now().isoformat()

# --- utilitaires texte ------------------------------------------------------------
def slug(s, n=40):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s[:n].strip("-") or "objet"

def fold(s):
    """minuscule sans accents, pour comparaisons multilingues"""
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower()).strip()

def date_iso(s):
    """accepte AAAA-MM-JJ, JJ.MM.AAAA, JJ/MM/AAAA, JJ.MM.AA ; renvoie AAAA-MM-JJ ou lève ValueError lisible"""
    if s in (None, ""):
        return None
    if isinstance(s, (dt.date, dt.datetime)):
        return s.isoformat()[:10]
    t = str(s).strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", t) or None
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = re.fullmatch(r"(\d{1,2})[./](\d{1,2})[./](\d{2,4})", t)
        if not m:
            raise ValueError(f"date illisible : {t} (attendu AAAA-MM-JJ ou JJ.MM.AAAA)")
        d, mo, y = map(int, m.groups())
        y = y + 2000 if y < 100 else y
    try:
        return dt.date(y, mo, d).isoformat()
    except ValueError:
        raise ValueError(f"date impossible : {t}")

def lire(p):
    """lecture tolérante : BOM, UTF-8, puis cp1252 (fichiers réenregistrés sous Windows), sinon remplacement"""
    b = Path(p).read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return b.decode(enc).replace("\r\n", "\n")
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", "replace").replace("\r\n", "\n")

def cut(s, n):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"

# --- identifiants -----------------------------------------------------------------
PREFIXES = {
    "client": "C", "entite": "E", "personne": "P", "dossier": "D", "document": "DOC",
    "position": "POS", "delai": "DL", "ruling": "R", "lba": "LBA", "contrat": "CT",
    "decision_taxation": "DT", "fosc": "FOSC", "correspondant": "CO", "engagement": "ENG",
    "temps": "TPS", "pipeline": "PL", "livrable": "LIV", "question": "Q", "conseil": "CONS",
    "incident": "INC", "source": "BIB", "capacite": "CAP", "role": "ROLE", "skill": "SK",
    "ticket": "T", "methode": "MET", "gabarit": "GAB", "changement_droit": "CHG", "note": "N",
    "rdv": "RDV", "mail": "M", "horloge": "H", "regle_delai": "RD", "bareme": "BAR",
    "cabinet": "CAB", "precedent": "PR", "doctrine": "DOCT", "relation": "REL",
    "anticipation": "ANT", "chantier": "CH", "rapport": "RAP", "vue": "VUE", "alerte": "AL",
}
WIDTH = {"C": 3, "E": 3, "P": 3, "D": 3, "DOC": 4, "POS": 3, "DL": 3, "R": 3, "T": 3}

def new_id(con, typ):
    pre = PREFIXES.get(typ, re.sub(r"[^A-Z]", "", unicodedata.normalize("NFKD", typ).upper())[:4] or "OBJ")
    if not con.in_transaction:
        con.execute("BEGIN IMMEDIATE")  # verrou d'écriture tenu jusqu'au commit de l'appelant : pas de collision entre processus
    row = con.execute("SELECT n FROM compteurs WHERE prefixe=?", (pre,)).fetchone()
    n = (row[0] if row else 0) + 1
    while True:
        oid = f"{pre}-{n:0{WIDTH.get(pre, 3)}d}"
        if not con.execute("SELECT 1 FROM objets WHERE id=?", (oid,)).fetchone():
            break
        n += 1
    con.execute("INSERT INTO compteurs(prefixe,n) VALUES(?,?) ON CONFLICT(prefixe) DO UPDATE SET n=excluded.n", (pre, n))
    return oid

ID_RE = re.compile(r"\b[A-Z]{1,5}-\d{3,5}\b")  # tout identifiant de la forme PREFIXE-000 ; l'existence est vérifiée à l'usage

# --- schéma -------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS compteurs(prefixe TEXT PRIMARY KEY, n INTEGER);
CREATE TABLE IF NOT EXISTS objets(
  id TEXT PRIMARY KEY, type TEXT NOT NULL, nom TEXT NOT NULL, statut TEXT DEFAULT 'actif',
  client TEXT, maj TEXT, prochaine_action TEXT, prochaine_date TEXT, proprietaire TEXT DEFAULT 'equipe',
  risque TEXT, chiffre_cle TEXT, resume TEXT, mots_cles TEXT, source TEXT, chemin TEXT,
  domaine TEXT, canton TEXT, langue TEXT,
  valide_du TEXT, valide_au TEXT, enregistre_le TEXT, data TEXT DEFAULT '{}', a_regenerer INTEGER DEFAULT 1);
CREATE INDEX IF NOT EXISTS ix_obj_client ON objets(client);
CREATE INDEX IF NOT EXISTS ix_obj_type ON objets(type);
CREATE TABLE IF NOT EXISTS alias(alias TEXT, alias_fold TEXT, id TEXT, langue TEXT, confiance REAL DEFAULT 1.0, PRIMARY KEY(alias_fold,id));
CREATE TABLE IF NOT EXISTS liens(src TEXT, dst TEXT, type TEXT DEFAULT 'lie', cree_le TEXT, PRIMARY KEY(src,dst,type));
CREATE TABLE IF NOT EXISTS redirections(ancien TEXT PRIMARY KEY, nouveau TEXT, le TEXT);
CREATE TABLE IF NOT EXISTS clients(id TEXT PRIMARY KEY, forme TEXT, canton TEXT, langue TEXT, depuis TEXT);
CREATE TABLE IF NOT EXISTS entites(id TEXT PRIMARY KEY, client TEXT, forme TEXT, ide TEXT, siege TEXT, canton TEXT, cloture TEXT, organes TEXT DEFAULT '[]');
CREATE TABLE IF NOT EXISTS personnes(id TEXT PRIMARY KEY, naissance TEXT, domicile TEXT, canton TEXT, nationalite TEXT);
CREATE TABLE IF NOT EXISTS participations(detenteur TEXT, detenue TEXT, pourcentage REAL, ayant_droit INTEGER DEFAULT 0, valide_du TEXT, valide_au TEXT, source TEXT, PRIMARY KEY(detenteur,detenue,valide_du));
CREATE TABLE IF NOT EXISTS dossiers(id TEXT PRIMARY KEY, client TEXT, objet TEXT, ouvert_le TEXT, clos_le TEXT, parties TEXT DEFAULT '[]');
CREATE TABLE IF NOT EXISTS delais(id TEXT PRIMARY KEY, client TEXT, dossier TEXT, type TEXT, declencheur TEXT, declencheur_date TEXT, echeance TEXT, preavis_jours INTEGER DEFAULT 10, canton TEXT, regle TEXT, document TEXT, prolongeable INTEGER DEFAULT 0, statut TEXT DEFAULT 'ouvert');
CREATE TABLE IF NOT EXISTS regles_delais(id TEXT PRIMARY KEY, type TEXT UNIQUE, libelle TEXT, duree INTEGER, unite TEXT, depuis TEXT, preavis_jours INTEGER, source TEXT, article TEXT, extrait_attendu TEXT, verifie_le TEXT, document_type TEXT, juridiction TEXT DEFAULT 'CH', report TEXT DEFAULT 'suivant');
CREATE TABLE IF NOT EXISTS rulings(id TEXT PRIMARY KEY, client TEXT, autorite TEXT, date TEXT, objet TEXT, echeance TEXT);
CREATE TABLE IF NOT EXISTS dossiers_lba(id TEXT PRIMARY KEY, client TEXT, ouverture TEXT, risque TEXT, derniere_revue TEXT, prochaine_revue TEXT, ayants_droit TEXT DEFAULT '[]');
CREATE TABLE IF NOT EXISTS contrats(id TEXT PRIMARY KEY, client TEXT, parties TEXT, objet TEXT, debut TEXT, fin TEXT, preavis TEXT, resiliation_avant TEXT);
CREATE TABLE IF NOT EXISTS decisions_taxation(id TEXT PRIMARY KEY, client TEXT, contribuable TEXT, autorite TEXT, canton TEXT, periode TEXT, notifiee_le TEXT, montant REAL, impot TEXT);
CREATE TABLE IF NOT EXISTS publications_fosc(id TEXT PRIMARY KEY, entite TEXT, date TEXT, rubrique TEXT, texte TEXT);
CREATE TABLE IF NOT EXISTS relations(a TEXT, b TEXT, type TEXT, valide_du TEXT, valide_au TEXT, source TEXT, PRIMARY KEY(a,b,type));
CREATE TABLE IF NOT EXISTS correspondants(id TEXT PRIMARY KEY, fonction TEXT, organisation TEXT, email TEXT, telephone TEXT, langue TEXT);
CREATE TABLE IF NOT EXISTS positions(id TEXT PRIMARY KEY, question TEXT, reponse TEXT, confort TEXT, canton TEXT, etat_du_droit TEXT, sources TEXT DEFAULT '[]');
CREATE TABLE IF NOT EXISTS engagements(id TEXT PRIMARY KEY, client TEXT, envers TEXT, objet TEXT, du_le TEXT, statut TEXT DEFAULT 'ouvert');
CREATE TABLE IF NOT EXISTS temps(id TEXT PRIMARY KEY, client TEXT, dossier TEXT, date TEXT, minutes INTEGER, libelle TEXT);
CREATE TABLE IF NOT EXISTS pipeline(id TEXT PRIMARY KEY, client TEXT, opportunite TEXT, etape TEXT, valeur REAL, prochaine_relance TEXT);
CREATE TABLE IF NOT EXISTS changements_de_droit(id TEXT PRIMARY KEY, source TEXT, juridiction TEXT, entree_en_vigueur TEXT, resume TEXT);
CREATE TABLE IF NOT EXISTS impacts(changement TEXT, objet TEXT, client TEXT, note TEXT, alerte TEXT, PRIMARY KEY(changement,objet));
CREATE TABLE IF NOT EXISTS questions_ouvertes(id TEXT PRIMARY KEY, type TEXT DEFAULT 'metier', besoin TEXT, defaut_applique TEXT, priorite INTEGER DEFAULT 3, formulation TEXT, cle_config TEXT, sujet TEXT, cree_le TEXT, posee_le TEXT, nb_posee INTEGER DEFAULT 0, statut TEXT DEFAULT 'ouverte', reponse TEXT, canal_pose TEXT);
CREATE TABLE IF NOT EXISTS conseils(id TEXT PRIMARY KEY, texte TEXT, gain INTEGER DEFAULT 3, cle TEXT UNIQUE, cree_le TEXT, presente_le TEXT, nb_ignore INTEGER DEFAULT 0, statut TEXT DEFAULT 'ouvert');
CREATE TABLE IF NOT EXISTS incidents(id TEXT PRIMARY KEY, le TEXT, categorie TEXT, description TEXT, repli TEXT, statut TEXT DEFAULT 'ouvert', resolu_le TEXT, phrase TEXT);
CREATE TABLE IF NOT EXISTS bibliotheque(id TEXT PRIMARY KEY, juridiction TEXT, type TEXT, identifiant TEXT, abreviation TEXT, titre TEXT, langue TEXT, version TEXT, date_etat TEXT, url TEXT, chemin TEXT, licence TEXT, fiabilite TEXT, ingere_le TEXT);
CREATE TABLE IF NOT EXISTS bareme(id TEXT PRIMARY KEY, nom TEXT, juridiction TEXT, annee INTEGER, cle TEXT, valeur TEXT, source TEXT, verifie_le TEXT);
CREATE TABLE IF NOT EXISTS types_de_tache(type TEXT PRIMARY KEY, nb INTEGER DEFAULT 0, dernier TEXT, skill TEXT);
CREATE TABLE IF NOT EXISTS capacites(id TEXT PRIMARY KEY, nom TEXT, categorie TEXT, localisation TEXT, sort_quoi TEXT, vers_qui TEXT, licence TEXT, version TEXT, statut TEXT, teste_le TEXT, source TEXT);
CREATE TABLE IF NOT EXISTS livrables(id TEXT PRIMARY KEY, client TEXT, dossier TEXT, type TEXT, chemin TEXT, version INTEGER DEFAULT 1, portes TEXT DEFAULT '{}', reserves TEXT, cree_le TEXT);
CREATE TABLE IF NOT EXISTS journal_audit(n INTEGER PRIMARY KEY AUTOINCREMENT, le TEXT, acteur TEXT, action TEXT, objet TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS mesures(n INTEGER PRIMARY KEY AUTOINCREMENT, le TEXT, role TEXT, tache TEXT, palier TEXT, tokens INTEGER, duree_ms INTEGER, ok INTEGER);
CREATE TABLE IF NOT EXISTS file_entretien(n INTEGER PRIMARY KEY AUTOINCREMENT, priorite INTEGER, tache TEXT, arg TEXT, cree_le TEXT, fait_le TEXT, statut TEXT DEFAULT 'attente', UNIQUE(tache,arg,statut));
CREATE TABLE IF NOT EXISTS ouvertures(n INTEGER PRIMARY KEY AUTOINCREMENT, le TEXT, tour TEXT, id TEXT, section TEXT, acteur TEXT);
CREATE TABLE IF NOT EXISTS etat(cle TEXT PRIMARY KEY, valeur TEXT);
CREATE TABLE IF NOT EXISTS versions(n INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT, champ TEXT, valeur TEXT, valide_du TEXT, valide_au TEXT, enregistre_le TEXT);
CREATE INDEX IF NOT EXISTS ix_versions ON versions(id, champ);
"""

def _fts(con):
    try:
        con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS noms_tri USING fts5(id UNINDEXED, texte, tokenize='trigram')")
    except sqlite3.OperationalError:
        pass
    try:
        con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS objets_fts USING fts5(id UNINDEXED, nom, resume, mots_cles, corps, tokenize='unicode61 remove_diacritics 2')")
        return True
    except sqlite3.OperationalError:
        return False

_CON = None
_DV = None  # PRAGMA data_version vu en dernier : change quand UN AUTRE processus a validé une écriture

def _ouvrir():
    con = sqlite3.connect(str(DB_PATH), timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=20000")
    return con

def db():
    """connexion unique du processus. Une connexion longue (serveur MCP, entretien, tests) garde sinon une vue périmée de
    l'index FTS5 quand d'autres processus écrivent ; écrire avec cette vue corrompt l'index. On rouvre donc la connexion
    dès que data_version a changé (hors transaction en cours)."""
    global _CON, _DV
    global DB_PATH
    if _CON is not None and not _CON.in_transaction:
        try:
            dv = _CON.execute("PRAGMA data_version").fetchone()[0]
            if _DV is not None and dv != _DV:
                _CON.close()
                _CON = _ouvrir()
                dv = _CON.execute("PRAGMA data_version").fetchone()[0]
            _DV = dv
        except sqlite3.Error:
            _CON = None
    if _CON is None:
        DB_PATH = Path(os.environ.get("CEREBRO_DB") or _db_defaut())
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CON = _ouvrir()
        _CON.executescript(SCHEMA)
        _fts(_CON)
        for t, col in (("questions_ouvertes", "canal_pose TEXT"), ("regles_delais", "report TEXT DEFAULT 'suivant'")):
            try:
                _CON.execute(f"ALTER TABLE {t} ADD COLUMN {col}")
            except sqlite3.OperationalError:
                pass
        _CON.commit()
        _DV = _CON.execute("PRAGMA data_version").fetchone()[0]
    return _CON

from contextlib import contextmanager

@contextmanager
def ecriture():
    """transaction d'écriture réservée d'emblée (BEGIN IMMEDIATE : le délai d'attente s'applique, jamais de BUSY en cours
    de route) ; toute erreur annule tout — jamais de validation partielle (cause de corruption d'index FTS5)"""
    con = db()
    own = not con.in_transaction
    if own:
        con.execute("BEGIN IMMEDIATE")
    try:
        yield con
        if own:
            con.commit()
    except BaseException:
        if own:
            con.rollback()
        raise

_HAS_FTS = None
def has_fts():
    global _HAS_FTS
    if _HAS_FTS is None:
        _HAS_FTS = bool(db().execute("SELECT 1 FROM sqlite_master WHERE name='objets_fts'").fetchone())
    return _HAS_FTS

def has_tri():
    return bool(db().execute("SELECT 1 FROM sqlite_master WHERE name='noms_tri'").fetchone())

def get_etat(k, d=None):
    r = db().execute("SELECT valeur FROM etat WHERE cle=?", (k,)).fetchone()
    return json.loads(r[0]) if r else d

def set_etat(k, v):
    with ecriture() as con:
        con.execute("INSERT INTO etat(cle,valeur) VALUES(?,?) ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur", (k, json.dumps(v, ensure_ascii=False)))

# --- journaux en ajout seul ---------------------------------------------------------
def journal(nom, **rec):
    try:
        JOURNAL.mkdir(parents=True, exist_ok=True)
        rec = {"le": stamp(), **rec}
        with open(JOURNAL / f"{nom}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass

def audit(action, objet="", detail="", acteur="cerebro"):
    try:
        with ecriture() as con:
            con.execute("INSERT INTO journal_audit(le,acteur,action,objet,detail) VALUES(?,?,?,?,?)", (stamp(), acteur, action, objet, cut(detail, 500)))
    except Exception as e:
        journal("audit-echec", action=action, objet=objet, erreur=repr(e)[:200])

def utf8_io():
    for st in (sys.stdin, sys.stdout, sys.stderr):
        try:
            st.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

def out(obj):
    """sortie compacte pour machine (JSON) ou texte"""
    if isinstance(obj, str):
        print(obj)
    else:
        print(json.dumps(obj, ensure_ascii=False, indent=None, default=str))
