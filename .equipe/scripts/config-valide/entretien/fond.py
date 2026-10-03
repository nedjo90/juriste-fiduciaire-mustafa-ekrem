"""Socle commun des hooks et des tâches de fond (§0, §11). Python stdlib uniquement, portable Windows/macOS/Linux.
Chemins, journal en ajout seul, lancement détaché, verrou avec PID et péremption, accès à cerebro (cb.*), exécutables.
Aucune fonction ne lève vers l'appelant sans y être invitée : les appelants enveloppent tout."""
import os, sys, json, time, shutil, subprocess, datetime as dt
from pathlib import Path

ROOT = Path(os.environ.get("CEREBRO_ROOT") or Path(__file__).resolve().parents[3])
EQ = ROOT / ".equipe"
RUN = EQ / "run"                      # verrous, drapeaux, compteurs (non suivi par git)
JOURNAL = EQ / "cerveau" / "journal"
SESSION = EQ / "cerveau" / "session"
INBOX = EQ / "inbox"
SCRIPTS = EQ / "scripts"
CEREBRO_PY = EQ / "cerebro" / "cerebro.py"
WINDOWS = os.name == "nt"


def stamp():
    return dt.datetime.now().astimezone().replace(microsecond=0).isoformat()


def journal(nom, **rec):
    """journal machine en ajout seul ; ne lève jamais"""
    try:
        JOURNAL.mkdir(parents=True, exist_ok=True)
        with open(JOURNAL / f"{nom}.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"le": stamp(), **rec}, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def cb():
    """importe les modules cerebro (même processus : plus rapide qu'un sous-processus)"""
    p = str(EQ / "cerebro")
    if p not in sys.path:
        sys.path.insert(0, p)
    os.environ.setdefault("CEREBRO_ROOT", str(ROOT))
    import cb.core  # noqa: F401
    return sys.modules["cb"]


def lire_json(p, defaut=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return defaut


def ecrire_json(p, data):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    os.replace(tmp, p)


# ------------------------------------------------------------------ exécutables
def python_exe():
    return os.environ.get("CEREBRO_PYTHON") or sys.executable or ("python" if WINDOWS else "python3")


def claude_exe():
    w = shutil.which("claude")
    if w:
        return w
    home = Path.home()
    for c in [home / ".local" / "bin" / ("claude.exe" if WINDOWS else "claude"), home / ".claude" / "local" / "claude",
              Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "claude" / "claude.exe"]:
        if c.exists():
            return str(c)
    return None


def env_fond(**extra):
    """environnement d'un job de fond : anti-récursion, cerebro dans le PATH, interpréteur connu"""
    e = dict(os.environ)
    e["CEREBRO_BACKGROUND"] = "1"
    e["CEREBRO_ROOT"] = str(ROOT)
    e["CEREBRO_PYTHON"] = python_exe()
    e["PYTHONIOENCODING"] = "utf-8"
    b = str(EQ / "bin")
    if b not in e.get("PATH", ""):
        e["PATH"] = b + os.pathsep + e.get("PATH", "")
    e.update({k: str(v) for k, v in extra.items()})
    return e


def fond_suspendu():
    """session de contrôle (CEREBRO_CONTROLE) ou drapeau run/sans-fond : aucun job de fond n'est lancé"""
    return bool(os.environ.get("CEREBRO_CONTROLE")) or (RUN / "sans-fond").exists()


def lancer_detache(script, *args, nom="fond"):
    """lance un script Python en arrière-plan détaché, priorité basse, sans attendre ; renvoie le PID ou None"""
    if fond_suspendu():
        journal("fond", job=nom, statut="non lancé (contrôle ou sans-fond)")
        return None
    cmd = [python_exe(), str(script), *map(str, args)]
    kw = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(ROOT),
              env=env_fond(), close_fds=True)
    if WINDOWS:
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS
        kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000 | 0x00004000
    else:
        kw["start_new_session"] = True
        kw["preexec_fn"] = lambda: os.nice(10)
    p = subprocess.Popen(cmd, **kw)
    journal("fond", job=nom, statut="lancé", pid=p.pid)
    return p.pid


def basse_priorite():
    try:
        if WINDOWS:
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)
        else:
            os.nice(10)
    except Exception:
        pass


# ------------------------------------------------------------------ verrou
def pid_vivant(pid):
    try:
        pid = int(pid)
        if pid <= 0:
            return False
        if WINDOWS:
            import ctypes
            k = ctypes.windll.kernel32
            h = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if not h:
                return False
            code = ctypes.c_ulong()
            k.GetExitCodeProcess(h, ctypes.byref(code))
            k.CloseHandle(h)
            return code.value == 259  # STILL_ACTIVE
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except Exception:
        return False


class Verrou:
    """fichier verrou exclusif {pid, depuis} ; repris si le PID est mort ou si le verrou a plus de `peremption` secondes"""

    def __init__(self, nom, peremption=3600):
        self.p = RUN / f"{nom}.lock"
        self.peremption = peremption
        self.tenu = False

    def prendre(self):
        RUN.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(str(self.p), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump({"pid": os.getpid(), "depuis": time.time(), "le": stamp()}, fh)
                self.tenu = True
                return True
            except FileExistsError:
                d = lire_json(self.p, {}) or {}
                age = time.time() - float(d.get("depuis") or 0)
                if (not pid_vivant(d.get("pid"))) or age > self.peremption:
                    journal("verrous", verrou=self.p.name, action="repris (périmé)", ancien=d)
                    try:
                        self.p.unlink()
                    except Exception:
                        return False
                    continue
                return False
        return False

    def rendre(self):
        if self.tenu:
            try:
                d = lire_json(self.p, {}) or {}
                if d.get("pid") == os.getpid():
                    self.p.unlink()
            except Exception:
                pass
            self.tenu = False

    def __enter__(self):
        return self.prendre()

    def __exit__(self, *a):
        self.rendre()


# ------------------------------------------------------------------ incidents (via cerebro, jamais bloquant)
def incident(description, categorie="technique", repli=""):
    try:
        mod = cb()
        from cb import files as F
        return F.incident_add(categorie, description, repli)
    except Exception as e:
        journal("erreurs-fond", ou="incident", erreur=repr(e), description=description)
        return None


def mustafa_ecrit(fraicheur=900):
    """drapeau posé par UserPromptSubmit, effacé par Stop ; périmé après 15 min (session fermée brutalement)"""
    p = RUN / "mustafa-ecrit"
    try:
        return p.exists() and (time.time() - p.stat().st_mtime) < fraicheur
    except Exception:
        return False
