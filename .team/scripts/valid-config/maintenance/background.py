"""Socle commun des hooks et des tâches de fond (§0, §11). Python stdlib uniquement, portable Windows/macOS/Linux.
Chemins, journal en ajout seul, lancement détaché, verrou avec PID et péremption, accès à cerebro (cb.*), exécutables.
Aucune fonction ne lève vers l'appelant sans y être invitée : les appelants enveloppent tout."""
import os, sys, json, time, shutil, subprocess, datetime as dt
from pathlib import Path

ROOT = Path(os.environ.get("CEREBRO_ROOT") or Path(__file__).resolve().parents[3])
EQ = ROOT / ".team"
RUN = EQ / "run"                      # verrous, drapeaux, compteurs (non suivi par git)
JOURNAL = EQ / "brain" / "log"
SESSION = EQ / "brain" / "session"
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
    """le VRAI programme Claude, jamais la commande de l'équipe (.team/bin/claude, placée en tête du PATH,
    qui ouvre une session) : variable CEREBRO_CLAUDE posée par l'installateur, puis PATH sans .team/bin,
    puis emplacements usuels (installateur officiel, ancienne installation npm)"""
    bin_equipe = os.path.normcase(os.path.abspath(str(EQ / "bin")))
    def _hors_equipe(c):
        return c and Path(c).exists() and os.path.normcase(os.path.abspath(os.path.dirname(str(c)))) != bin_equipe
    e = os.environ.get("CEREBRO_CLAUDE")
    if _hors_equipe(e):
        return e
    chemins = [d for d in os.environ.get("PATH", "").split(os.pathsep)
               if d and os.path.normcase(os.path.abspath(d)) != bin_equipe]
    w = shutil.which("claude", path=os.pathsep.join(chemins))
    if _hors_equipe(w):
        return w
    home = Path.home()
    appdata = Path(os.environ.get("APPDATA") or (home / "AppData" / "Roaming"))
    for c in [home / ".local" / "bin" / ("claude.exe" if WINDOWS else "claude"), home / ".claude" / "local" / ("claude.cmd" if WINDOWS else "claude"),
              Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "claude" / "claude.exe", appdata / "npm" / "claude.cmd",
              Path("/opt/homebrew/bin/claude"), Path("/usr/local/bin/claude")]:
        if _hors_equipe(c):
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


# ------------------------------------------------------------------ réserve d'usage de Mustafa (abonnement Claude partagé)
# Un appel de fond au modèle puise dans la MÊME réserve que les conversations de Mustafa. Règles :
# 1. jamais pendant qu'il travaille : aucune activité depuis CALME minutes (message envoyé ou réponse reçue) ;
# 2. jamais quand sa réserve baisse : fenêtre de 5 h utilisée à SEUIL_5H ou plus, semaine à SEUIL_7J ou plus
#    (chiffres réels fournis par Claude à chaque appel, jamais estimés) ; reprise après la remise à zéro ;
# 3. un appel déjà parti s'arrête aussitôt si Mustafa écrit ou si la réserve passe sous le seuil.
ACTIVITE = RUN / "derniere-activite"
JAUGE = RUN / "reserve-usage.json"


def _reglage(cle, defaut):
    try:
        cb()
        from cb import config as K
        v = K.get(cle)
        return float(v) if v not in (None, "") else defaut
    except Exception:
        return defaut


def noter_activite():
    """posé par les hooks à chaque message et à chaque réponse"""
    try:
        RUN.mkdir(parents=True, exist_ok=True)
        ACTIVITE.write_text(stamp(), encoding="utf-8")
    except Exception:
        pass


def _sans_activite():
    """tests seulement : CEREBRO_CALME_MIN=0 → aucune activité de Mustafa simulée"""
    return os.environ.get("CEREBRO_CALME_MIN") == "0"


def mustafa_actif():
    if _sans_activite():
        return False
    calme = float(os.environ.get("CEREBRO_CALME_MIN") or _reglage("background.calme_minutes", 20)) * 60  # variable : tests
    try:
        return mustafa_ecrit() or (ACTIVITE.exists() and time.time() - ACTIVITE.stat().st_mtime < calme)
    except Exception:
        return False


def noter_jauge(info):
    """info = rate_limit_info d'un événement rate_limit_event de Claude Code"""
    try:
        f = (info or {}).get("unifiedWindows") or {}
        ecrire_json(JAUGE, {"le": stamp(), "statut": info.get("status"),
                            "cinq_heures": f.get("five_hour") or {}, "semaine": f.get("seven_day") or {}})
    except Exception:
        pass


def _au_dessus(j):
    """raison si la réserve est entamée au-delà des seuils (et pas encore remise à zéro), sinon None"""
    now = time.time()
    for cle, seuil, nom in (("cinq_heures", _reglage("background.seuil_5h", 0.5), "des 5 heures"),
                            ("semaine", _reglage("background.seuil_semaine", 0.75), "de la semaine")):
        w = (j or {}).get(cle) or {}
        u, reset = w.get("utilization"), w.get("resetsAt")
        if u is not None and u >= seuil and (not reset or reset > now):
            quand = dt.datetime.fromtimestamp(reset).strftime("%d.%m %H:%M") if reset else "plus tard"
            return f"réserve {nom} entamée à {int(u * 100)} % : appels de fond reportés après {quand}"
    if (j or {}).get("statut") == "rejected":
        return "limite d'usage atteinte : appels de fond reportés"
    return None


def modele_permis():
    """(bool, raison) : un appel de fond au modèle peut-il partir maintenant ?"""
    if mustafa_actif():
        return False, "Mustafa travaille : priorité à lui, appel de fond reporté"
    r = _au_dessus(lire_json(JAUGE, {}) or {})
    return (False, r) if r else (True, "ok")


def _tuer(p):
    try:
        if WINDOWS:  # un claude.cmd (installation npm) lance un enfant : tout l'arbre
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True, timeout=20)
        else:
            p.kill()
    except Exception:
        pass


def appeler_claude(cmd, entree, cwd, env, timeout):
    """lance claude -p en flux (stream-json) et le surveille : jauge relevée en direct, arrêt aussitôt si Mustafa écrit ou
    si la réserve passe sous le seuil. → (dernière ligne JSON du résultat, stderr, code, interruption ou None)"""
    import threading
    cmd = list(cmd)
    if "--output-format" in cmd:
        i = cmd.index("--output-format")
        cmd[i + 1] = "stream-json"
    else:
        cmd += ["--output-format", "stream-json"]
    if "--verbose" not in cmd:
        cmd.append("--verbose")
    donnees = entree.encode("utf-8") if isinstance(entree, str) else (entree or b"")
    p = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    etat = {"resultat": "", "arret": None}

    def lire():
        for brut in p.stdout:
            l = brut.decode("utf-8", "replace").strip()
            if not l.startswith("{"):
                continue
            try:
                e = json.loads(l)
            except Exception:
                continue
            if e.get("type") == "rate_limit_event":
                noter_jauge(e.get("rate_limit_info") or {})
                r = _au_dessus(lire_json(JAUGE, {}) or {})
                if r and not etat["arret"]:
                    etat["arret"] = r
            elif e.get("type") == "result":
                etat["resultat"] = l
    lecteur = threading.Thread(target=lire, daemon=True)
    lecteur.start()
    try:
        p.stdin.write(donnees)
        p.stdin.close()
    except Exception:
        pass
    debut = time.time()
    while p.poll() is None:
        if mustafa_ecrit() and not _sans_activite() and not etat["arret"]:
            etat["arret"] = "Mustafa écrit : appel de fond arrêté, repris plus tard"
        if time.time() - debut > timeout and not etat["arret"]:
            etat["arret"] = f"délai dépassé ({timeout // 60} min)"
        if etat["arret"]:
            _tuer(p)
            break
        time.sleep(0.5)
    try:
        p.wait(timeout=30)
    except Exception:
        pass
    lecteur.join(timeout=5)
    err = ""
    try:
        err = p.stderr.read().decode("utf-8", "replace")[-2000:]
    except Exception:
        pass
    if etat["arret"]:
        journal("reserve", evenement="appel de fond arrêté", raison=etat["arret"])
    return etat["resultat"], err, p.returncode if p.returncode is not None else -1, etat["arret"]
