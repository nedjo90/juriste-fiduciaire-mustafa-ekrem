"""Commun au producteur et aux portes : racine, accès cerebro (import direct, repli sous-processus), journal, ouverture.
Tourne sous Windows, macOS et Linux (pathlib, UTF-8 explicite, aucune dépendance à bash)."""
import os, sys, json, re, subprocess, shutil, unicodedata, datetime as dt
from pathlib import Path

HERE = Path(__file__).resolve()
CODE_ROOT = HERE.parents[3]                       # dépôt contenant ce code
ROOT = Path(os.environ.get("CEREBRO_ROOT") or CODE_ROOT)
EQ = ROOT / ".equipe"
BUREAU = ROOT / "Bureau"
MODELES = BUREAU / "Modeles"   # convention : aucun chemin avec accent ni espace
LIVRABLES = BUREAU / "Livrables"
DESIGN_YAML = EQ / "cerveau" / "cabinet" / "design" / "systeme.yaml"
if not DESIGN_YAML.exists():                      # racine jetable sans copie du design : celui du code
    DESIGN_YAML = CODE_ROOT / ".equipe" / "cerveau" / "cabinet" / "design" / "systeme.yaml"

_cb_dir = EQ / "cerebro" if (EQ / "cerebro" / "cb").exists() else CODE_ROOT / ".equipe" / "cerebro"
if str(_cb_dir) not in sys.path:
    sys.path.insert(0, str(_cb_dir))
os.environ.setdefault("CEREBRO_ROOT", str(ROOT))


def today():
    d = os.environ.get("CEREBRO_TODAY")
    return dt.date.fromisoformat(d) if d else dt.date.today()


def slug(s, n=50):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s[:n].strip("-") or "document"


def nom_dossier(s, n=60):
    """nom de dossier : ASCII kebab-case (convention de la maison, aucun accent ni espace dans un chemin)"""
    return slug(s, n) or "divers"


def journal(nom, **rec):
    try:
        d = EQ / "cerveau" / "journal"
        d.mkdir(parents=True, exist_ok=True)
        rec = {"le": dt.datetime.now().isoformat(timespec="seconds"), **rec}
        with open(d / f"{nom}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


# ------------------------------------------------------------------ cerebro
def cb():
    """modules cerebro importés (même base que la CLI : CEREBRO_ROOT / CEREBRO_DB respectés)"""
    from cb import core, objets, config, files  # noqa
    return core, objets, config, files


def cerebro_cli(*args):
    """repli : appel de la CLI (sortie JSON) ; jamais d'exception vers l'appelant"""
    exe = CODE_ROOT / ".equipe" / "cerebro" / "cerebro.py"
    try:
        r = subprocess.run([sys.executable, str(exe), *map(str, args)], capture_output=True, text=True, encoding="utf-8", timeout=60)
        return json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else None
    except Exception as e:
        journal("erreurs-producteur", op="cerebro_cli", args=list(map(str, args)), erreur=repr(e))
        return None


def config_get(cle, defaut=None):
    try:
        _, _, config, _ = cb()
        v = config.get(cle)
    except Exception:
        r = cerebro_cli("config", "get", cle) or {}
        v = r.get("valeur")
    return defaut if v in (None, "", []) else v


def config_renseigne(cle):
    """True si la clé a une valeur réelle (pas seulement un défaut)"""
    try:
        _, _, config, _ = cb()
        e = config.get_full(cle) or {}
        return e.get("valeur") not in (None, "", [])
    except Exception:
        return False


def objet(oid):
    try:
        _, objets, _, _ = cb()
        return objets.get(oid)
    except Exception:
        return None


# ------------------------------------------------------------------ outils système
def soffice():
    for c in ("soffice", "libreoffice", r"C:\Program Files\LibreOffice\program\soffice.exe",
              r"C:\Program Files (x86)\LibreOffice\program\soffice.exe", "/Applications/LibreOffice.app/Contents/MacOS/soffice",
              str(Path.home() / "AppData/Local/Programs/LibreOffice/program/soffice.exe"),
              str(ROOT / ".equipe" / "outils" / "LibreOfficePortable" / "App" / "libreoffice" / "program" / "soffice.exe")):
        p = shutil.which(c) or (c if Path(c).exists() else None)
        if p:
            return p
    return None


def vers_pdf(src, outdir=None, timeout=180):
    """conversion LibreOffice sans affichage ; None si impossible (le repli reportlab est ailleurs)"""
    exe = soffice()
    if not exe:
        return None
    src = Path(src)
    outdir = Path(outdir or src.parent)
    outdir.mkdir(parents=True, exist_ok=True)
    prof = Path(os.environ.get("TMPDIR") or os.environ.get("TEMP") or "/tmp") / f"lo-profil-{os.getpid()}"
    try:
        subprocess.run([exe, f"-env:UserInstallation={prof.as_uri()}", "--headless", "--norestore", "--convert-to", "pdf",
                        "--outdir", str(outdir), str(src)], capture_output=True, timeout=timeout)
    except Exception as e:
        journal("erreurs-producteur", op="soffice", src=str(src), erreur=repr(e))
        return None
    pdf = outdir / (src.stem + ".pdf")
    return pdf if pdf.exists() and pdf.stat().st_size > 0 else None


def ouvrir(chemin):
    """ouverture dans l'application par défaut, silencieuse si impossible (machine distante, test)"""
    if os.environ.get("PRODUCTEUR_SANS_OUVERTURE") or os.environ.get("CEREBRO_BACKGROUND"):
        return False
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(chemin))  # type: ignore[attr-defined]
            return True
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(chemin)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
            if shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", str(chemin)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
    except Exception as e:
        journal("erreurs-producteur", op="ouvrir", chemin=str(chemin), erreur=repr(e))
    return False


MOIS = {
    "fr": ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
    "de": ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"],
    "it": ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
}


def date_longue(d, langue="fr"):
    """date ISO (ou date) → « 3 octobre 2026 » / « 3. Oktober 2026 » ; texte inchangé si non reconnu"""
    try:
        x = d if isinstance(d, dt.date) else dt.date.fromisoformat(str(d)[:10])
    except Exception:
        return str(d or "")
    m = MOIS.get(langue, MOIS["fr"])[x.month - 1]
    if langue == "fr":
        return f"{'1er' if x.day == 1 else x.day} {m} {x.year}"
    if langue == "de":
        return f"{x.day}. {m} {x.year}"
    return f"{x.day} {m} {x.year}"
