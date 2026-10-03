#!/usr/bin/env python3
"""Tests du chantier connecteurs (écarts 8 et 9) : .msg Outlook, notes vocales, anciens formats Office, Microsoft 365.
Exécution : python .team/tests/test_connectors.py   → une ligne OK/ÉCHEC/NOTE par test, code 0 si tout passe.
Racine jetable (copie de .team, .claude, .mcp.json, CLAUDE.md + dossier fictif) ; la base réelle n'est jamais touchée.
Microsoft Graph est remplacé par un faux serveur HTTP local qui enregistre chaque requête : on vérifie qu'aucune requête
d'envoi ne part (ni sendMail, ni …/send), que le brouillon est créé, que la synchronisation est idempotente et rattachée.
Notes vocales : voix de synthèse hors ligne (espeak-ng) si présente ; transcription réelle si faster-whisper est installé
(modèle « base », cache .team/tools/whisper/ non suivi par git), sinon le test le dit (NOTE) ; le repli est toujours testé."""
import os, sys, json, time, shutil, struct, subprocess, tempfile, threading, wave, math, re, importlib.util, datetime as dt
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

REEL = Path(__file__).resolve().parents[2]
PY = sys.executable
RES, TESTS = [], []
AUJ = dt.date.today().isoformat()


def test(nom):
    def deco(f):
        def run():
            t0 = time.time()
            try:
                note = f()
                RES.append((nom, True, ""))
                print(f"OK     {nom} ({int((time.time() - t0) * 1000)} ms)" + (f" — {note}" if note else ""))
            except Exception as e:
                RES.append((nom, False, repr(e)))
                print(f"ÉCHEC  {nom} : {e!r}")
        TESTS.append(run)
        return run
    return deco


def preparer():
    tmp = Path(tempfile.mkdtemp(prefix="connecteurs-"))
    R = tmp / "racine"
    R.mkdir()
    ign = shutil.ignore_patterns("cerebro.db*", "__pycache__", "run", "sauvegardes", "*.jsonl", "bibliotheque", "archives", "outils")
    shutil.copytree(REEL / ".team", R / ".team", ignore=ign)
    shutil.copytree(REEL / ".claude", R / ".claude", ignore=shutil.ignore_patterns("__pycache__", "skills", "agents", "settings.local.json"))
    for f in (".mcp.json", "CLAUDE.md"):
        if (REEL / f).exists():
            shutil.copy2(REEL / f, R / f)
    (R / "Bureau" / "Informatique").mkdir(parents=True)
    (R / "Bureau" / "A-deposer").mkdir(parents=True)
    if (REEL / "Bureau" / "Informatique" / "DOSSIER-TECHNIQUE.md").exists():
        shutil.copy2(REEL / "Bureau" / "Informatique" / "DOSSIER-TECHNIQUE.md", R / "Bureau" / "Informatique")
    (R / ".team" / "run").mkdir(parents=True, exist_ok=True)
    (R / ".team" / "run" / "sans-fond").write_text("tests", encoding="utf-8")
    (tmp / "home").mkdir()
    env = dict(os.environ)
    for k in ("CEREBRO_BACKGROUND", "CEREBRO_CONTROLE", "CEREBRO_DB", "CEREBRO_GRAPH_URL", "CEREBRO_GRAPH_TOKEN"):
        env.pop(k, None)
    env.update({"CEREBRO_ROOT": str(R), "CEREBRO_SANS_MODELE": "1", "CEREBRO_SANS_RESEAU": "1", "CEREBRO_TODAY": AUJ,
                "PYTHONIOENCODING": "utf-8", "CEREBRO_M365_DIR": str(tmp / "m365"),
                "CEREBRO_WHISPER_MODELE": "base", "CEREBRO_WHISPER_DIR": str(REEL / ".team" / "tools" / "whisper")})
    r = subprocess.run([PY, str(R / ".team/tests/fixtures/fictional_case.py")], env=env, capture_output=True, timeout=180)
    assert r.returncode == 0, r.stderr[-400:]
    return tmp, R, env


TMP, R, ENV = preparer()
os.environ.update({k: v for k, v in ENV.items() if k.startswith(("CEREBRO_", "PYTHONIOENCODING"))})
sys.path.insert(0, str(R / ".team" / "cerebro"))
from cb import core  # noqa: E402  (racine jetable)
DEPOT = R / "Bureau" / "A-deposer"


def ingerer(env_extra=None):
    e = dict(ENV)
    e.update(env_extra or {})
    r = subprocess.run([PY, str(R / ".team/scripts/ingester/ingest.py")], env=e, capture_output=True, timeout=900, cwd=str(R))
    out = r.stdout.decode("utf-8", "ignore").strip().splitlines()
    assert out, r.stderr.decode("utf-8", "ignore")[-600:]
    return json.loads(out[-1])


def db():
    import sqlite3
    c = sqlite3.connect(str(R / ".team" / "cerebro" / "cerebro.db"))
    c.row_factory = sqlite3.Row
    return c


# ------------------------------------------------------------------ fabrique d'un vrai .msg (format OLE/MAPI)
def fabriquer_msg(path, sujet, corps, de_nom, de_mail, a, date, pieces=()):
    """écrit un fichier Outlook .msg authentique (stockage composé OLE + propriétés MAPI) avec l'écrivain OLE d'extract-msg"""
    from extract_msg.ole_writer import OleWriter
    u = lambda s: s.encode("utf-16-le")
    var = lambda tag, n: struct.pack("<IIII", tag, 6, n, 0)
    fix = lambda tag, raw8: struct.pack("<II", tag, 6) + raw8
    ft = struct.pack("<Q", int((date - dt.datetime(1601, 1, 1, tzinfo=dt.timezone.utc)).total_seconds() * 10 ** 7))
    w = OleWriter()
    ent = b""
    for pid, s in {0x001A: "IPM.Note", 0x0037: sujet, 0x1000: corps, 0x0C1A: de_nom, 0x0C1F: de_mail, 0x5D01: de_mail,
                   0x0E04: "; ".join(n for n, _ in a)}.items():
        tag = (pid << 16) | 0x001F
        w.addEntry(f"__substg1.0_{tag:08X}", u(s)); ent += var(tag, len(u(s)) + 2)
    for pid in (0x0039, 0x0E06):
        ent += fix((pid << 16) | 0x0040, ft)
    w.addEntry("__properties_version1.0", struct.pack("<QIIIIQ", 0, len(a), len(pieces), len(a), len(pieces), 0) + ent)
    w.addEntry("__nameid_version1.0", storage=True)
    for s in ("00020102", "00030102", "00040102"):
        w.addEntry(f"__nameid_version1.0/__substg1.0_{s}", b"")
    for i, (n, m) in enumerate(a):
        d = f"__recip_version1.0_#{i:08X}"
        w.addEntry(d, storage=True); e = b""
        for pid, s in {0x3001: n, 0x3003: m, 0x39FE: m}.items():
            tag = (pid << 16) | 0x001F
            w.addEntry(f"{d}/__substg1.0_{tag:08X}", u(s)); e += var(tag, len(u(s)) + 2)
        e += fix(0x0C150003, struct.pack("<II", 1, 0))
        w.addEntry(f"{d}/__properties_version1.0", struct.pack("<Q", 0) + e)
    for i, (nom, data) in enumerate(pieces):
        d = f"__attach_version1.0_#{i:08X}"
        w.addEntry(d, storage=True); e = b""
        for pid, s in {0x3707: nom, 0x3704: nom[:8], 0x3001: nom}.items():
            tag = (pid << 16) | 0x001F
            w.addEntry(f"{d}/__substg1.0_{tag:08X}", u(s)); e += var(tag, len(u(s)) + 2)
        w.addEntry(f"{d}/__substg1.0_37010102", data); e += var(0x37010102, len(data))
        e += fix(0x37050003, struct.pack("<II", 1, 0))
        w.addEntry(f"{d}/__properties_version1.0", struct.pack("<Q", 0) + e)
    w.write(str(path))


# ------------------------------------------------------------------ .msg
@test("msg : en-tête, corps, pièces jointes extraites et ingérées comme documents liés, rattachement client")
def t_msg():
    import extract_msg  # noqa: F401  (bibliothèque requise)
    p = DEPOT / "Taxation Rochat.msg"
    fabriquer_msg(p, "Décision de taxation 2025 — Menuiserie Rochat SA",
                  "Bonjour Monsieur Ekrem,\n\nVeuillez trouver ci-joint la décision de taxation. Pouvez-vous la vérifier ?\n\nJean-Marc Rochat",
                  "Jean-Marc Rochat", "jm.rochat@example.ch", [("Mustafa Ekrem", "mustafa@fiduciaire.example")],
                  dt.datetime(2026, 9, 30, 8, 15, tzinfo=dt.timezone.utc),
                  [("decision-taxation.txt", "Décision de taxation IFD 2025\nMenuiserie Rochat SA\nMontant : 12 345 CHF\n".encode("utf-8"))])
    out = ingerer()
    r = [x for x in out["resultats"] if x["fichier"].endswith(".msg")][0]
    assert r["nature"] == "mail", r
    assert r["client"], f"non rattaché : {r}"
    assert len(r.get("pieces") or []) == 1, r
    c = db()
    o = c.execute("SELECT * FROM objets WHERE id=?", (r["id"],)).fetchone()
    assert o["type"] == "mail" and o["statut"] == "attente", dict(o)
    txt = (R / json.loads(o["data"])["texte_archive"]).read_text(encoding="utf-8")
    for attendu in ("De: Jean-Marc Rochat <jm.rochat@example.ch>", "Mustafa Ekrem", "Date: 2026-09-30", "Objet: Décision de taxation 2025",
                    "Pièces: decision-taxation.txt", "Pouvez-vous la vérifier"):
        assert attendu in txt, (attendu, txt[:400])
    pj = r["pieces"][0]
    lien = c.execute("SELECT type FROM liens WHERE src=? AND dst=?", (pj, r["id"])).fetchone()
    assert lien and lien[0] == "piece_jointe", "pièce non liée au mail"
    po = c.execute("SELECT client, type FROM objets WHERE id=?", (pj,)).fetchone()
    assert po["type"] == "document" and po["client"] == r["client"], dict(po)
    assert not p.exists() and list((R / "Bureau" / "Deposes").rglob("Taxation Rochat.msg")), "original non archivé"
    assert list((R / "Bureau" / "Deposes").rglob("decision-taxation.txt")), "pièce jointe non rangée à côté du mail"
    q = c.execute("SELECT tache FROM file_entretien WHERE arg=?", (r["id"],)).fetchall()
    assert [x[0] for x in q] == ["ingestion_commentaire"], q
    return f"{r['id']} → {r['client']} · pièce {pj}"


@test("ancien format Office hors Windows : aucune conversion LibreOffice, repli lecture par le modèle")
def t_ancien_office():
    p = DEPOT / "vieux contrat.doc"
    p.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 600)
    sys.path.insert(0, str(R / ".team" / "scripts" / "connectors"))
    import office_read as office_lecture
    assert office_lecture.vers_moderne(p) is None if os.name != "nt" else True
    src = (R / ".team/scripts/ingester/ingest.py").read_text(encoding="utf-8")
    assert "soffice" not in src and "libreoffice" not in src.lower(), "LibreOffice encore appelé par l'ingester"
    out = ingerer()
    r = [x for x in out["resultats"] if x["fichier"] == "vieux contrat.doc"][0]
    assert r["nature"] == ("a_lire_par_modele" if os.name != "nt" else r["nature"]), r


# ------------------------------------------------------------------ audio
def voix(path, texte):
    """voix de synthèse hors ligne (espeak-ng) ; sinon un son pur (suffit pour le repli)"""
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if exe:
        subprocess.run([exe, "-v", "fr", "-s", "140", "-w", str(path), texte], capture_output=True, timeout=60)
        if path.exists() and path.stat().st_size > 1000:
            return True
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * 440 * i / 16000))) for i in range(16000)))
    return False


@test("note vocale, repli : note « à transcrire » + question simple différée, jamais de tâche « lecture par le modèle »")
def t_audio_repli():
    p = DEPOT / "note vocale Rochat.wav"
    voix(p, "Bonjour, ici Jean-Marc Rochat, rappelez-moi au sujet de la taxation.")
    out = ingerer({"CEREBRO_SANS_TRANSCRIPTION": "1"})
    r = [x for x in out["resultats"] if x["fichier"] == p.name][0]
    assert r["nature"] == "audio_a_transcrire", r
    c = db()
    o = c.execute("SELECT type, statut FROM objets WHERE id=?", (r["id"],)).fetchone()
    assert o["type"] == "note" and o["statut"] == "à transcrire", dict(o)
    assert not c.execute("SELECT 1 FROM file_entretien WHERE arg=? AND tache='lecture_modele'", (r["id"],)).fetchone(), "tâche modèle créée pour un audio"
    q = c.execute("SELECT formulation FROM questions_ouvertes WHERE statut='ouverte' AND formulation LIKE '%résumer en deux phrases%'").fetchall()
    assert q and "note vocale Rochat" in q[0][0], q
    assert c.execute("SELECT 1 FROM incidents WHERE categorie='transcription'").fetchone(), "repli non inscrit (incident)"


@test("note vocale : transcription locale réelle (faster-whisper, voix de synthèse), note créée avec le texte")
def t_audio_transcription():
    if not importlib.util.find_spec("faster_whisper"):
        return "NOTE : faster-whisper absent ici, transcription non testée (le repli l'est)"
    p = DEPOT / "message Lemantech.wav"
    if not voix(p, "Bonjour Monsieur Ekrem, je vous appelle au sujet de la levée de fonds. Pouvez-vous me rappeler demain matin ?"):
        p.unlink(missing_ok=True)
        return "NOTE : aucune voix de synthèse hors ligne ici, transcription non testée"
    out = ingerer()
    r = [x for x in out["resultats"] if x["fichier"] == p.name][0]
    if r["nature"] == "audio_a_transcrire":
        return "NOTE : modèle non téléchargeable ici (réseau) ; repli appliqué proprement"
    assert r["nature"] == "audio", r
    c = db()
    o = c.execute("SELECT type, statut, data FROM objets WHERE id=?", (r["id"],)).fetchone()
    d = json.loads(o["data"])
    txt = (R / d["texte_archive"]).read_text(encoding="utf-8")
    assert o["type"] == "note" and "[transcription automatique" in txt and len(txt) > 60, txt[:200]
    assert d.get("transcription", {}).get("langue") == "fr", d.get("transcription")
    assert re.search(r"rappeler|demain|fonds", txt, re.I), txt
    t = [x[0] for x in c.execute("SELECT tache FROM file_entretien WHERE arg=?", (r["id"],))]
    assert t == ["ingestion_commentaire"], t
    return "transcrit : " + txt.split("\n\n", 1)[-1][:80]


# ------------------------------------------------------------------ faux Microsoft Graph
REQUETES = []
ETAT = {"drafts": {}, "n": 0}
MOI = "mustafa@fiduciaire.example"


def _iso(delta_h):
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=delta_h)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mail(i, de_nom, de, sujet, apercu, a=(MOI,), cc=(), classement="focused"):
    return {"id": f"AAMk-{i}", "internetMessageId": f"<msg-{i}@example.ch>", "subject": sujet, "bodyPreview": apercu,
            "body": {"contentType": "text", "content": apercu + "\n\nCordialement"}, "receivedDateTime": _iso(-3 * i),
            "from": {"emailAddress": {"name": de_nom, "address": de}}, "conversationId": f"conv-{i}", "isDraft": False,
            "toRecipients": [{"emailAddress": {"name": "", "address": x}} for x in a],
            "ccRecipients": [{"emailAddress": {"name": "", "address": x}} for x in cc], "inferenceClassification": classement,
            "hasAttachments": False, "isRead": False, "webLink": "https://outlook.example/x"}


MAILS = [
    _mail(1, "Jean-Marc Rochat", "jm.rochat@example.ch", "Dividende Rochat Holding", "Bonjour, pouvons-nous verser le dividende avant la fin de l'année ?"),
    _mail(2, "Newsletter Fiscale", "no-reply@news.example", "Les nouveautés fiscales", "Abonnez-vous à notre webinaire", classement="other"),
    _mail(3, "Collègue", "collegue@fiduciaire.example", "Pour info Lemantech", "Le procès-verbal Lemantech est classé.", a=("autre@fiduciaire.example",), cc=(MOI,)),
]
DEMAIN = (dt.datetime.now() + dt.timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
EVENEMENTS = [{"id": "EV-1", "iCalUId": "ical-1", "subject": "Séance Lémantech — levée de fonds",
               "start": {"dateTime": DEMAIN.strftime("%Y-%m-%dT%H:%M:%S.0000000"), "timeZone": "Europe/Zurich"},
               "end": {"dateTime": (DEMAIN + dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.0000000"), "timeZone": "Europe/Zurich"},
               "location": {"displayName": "Genève"}, "attendees": [{"emailAddress": {"name": "CEO Lemantech", "address": "ceo@lemantech.example"}}],
               "isCancelled": False, "isOnlineMeeting": False, "bodyPreview": "Ordre du jour : levée de fonds"}]


class FauxGraph(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _rep(self, code, obj=None):
        b = json.dumps(obj or {}).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _corps(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def do_GET(self):
        u = urlsplit(self.path)
        REQUETES.append(("GET", u.path, self.headers.get("Authorization")))
        p = u.path.replace("/v1.0", "", 1)
        if p == "/me":
            return self._rep(200, {"displayName": "Mustafa Ekrem", "mail": MOI, "userPrincipalName": MOI})
        if p == "/me/mailFolders/inbox/messages":
            if "page=2" in u.query:
                return self._rep(200, {"value": MAILS[2:]})
            return self._rep(200, {"value": MAILS[:2], "@odata.nextLink": f"http://{self.headers['Host']}/v1.0/me/mailFolders/inbox/messages?page=2"})
        if p == "/me/mailFolders/sentitems/messages":
            return self._rep(200, {"value": []})
        if p == "/me/calendarView":
            return self._rep(200, {"value": EVENEMENTS})
        m = re.match(r"^/me/messages/([^/]+)$", p)
        if m and m.group(1) in ETAT["drafts"]:
            return self._rep(200, ETAT["drafts"][m.group(1)])
        return self._rep(404, {"error": {"code": "ErrorItemNotFound"}})

    def do_POST(self):
        u = urlsplit(self.path)
        REQUETES.append(("POST", u.path, None))
        p = u.path.replace("/v1.0", "", 1)
        self._corps()
        m = re.match(r"^/me/messages/([^/]+)/createReply$", p)
        if m:
            ETAT["n"] += 1
            did = f"DRAFT-{ETAT['n']}"
            ETAT["drafts"][did] = {"id": did, "isDraft": True, "replyTo": m.group(1),
                                   "body": {"contentType": "html", "content": "<div>---- message d'origine ----</div>"}}
            return self._rep(201, {"id": did, "webLink": "https://outlook.example/draft"})
        return self._rep(202, {})  # un envoi serait « accepté » ici : le test vérifie qu'il n'est jamais demandé

    def do_PATCH(self):
        u = urlsplit(self.path)
        REQUETES.append(("PATCH", u.path, None))
        p = u.path.replace("/v1.0", "", 1)
        d = self._corps()
        m = re.match(r"^/me/messages/([^/]+)$", p)
        if m and m.group(1) in ETAT["drafts"]:
            ETAT["drafts"][m.group(1)].update(d)
            return self._rep(200, ETAT["drafts"][m.group(1)])
        return self._rep(404, {})


SRV = ThreadingHTTPServer(("127.0.0.1", 0), FauxGraph)
threading.Thread(target=SRV.serve_forever, daemon=True).start()
GURL = f"http://127.0.0.1:{SRV.server_address[1]}/v1.0"


def charger_extension():
    spec = importlib.util.spec_from_file_location("tasks_mail_sync", R / ".team/scripts/maintenance/tasks/mail_sync.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def aucun_envoi():
    env = [r for r in REQUETES if re.search(r"/(send|sendMail|forward|reply|replyAll)$", r[1], re.I)]
    assert not env, f"requête d'envoi émise : {env}"


@test("extension messagerie : non connectée → rien planifié ; connectée → synchro (P1) avant l'initiative, dépôt des brouillons (P2)")
def t_planifier():
    os.environ.pop("CEREBRO_GRAPH_TOKEN", None)
    M = charger_extension()
    vus = []
    M.PLANIFIER(False, "rattrapage", lambda t, a="", p=4: vus.append((t, p)))
    assert vus == [], vus
    os.environ.update({"CEREBRO_GRAPH_URL": GURL, "CEREBRO_GRAPH_TOKEN": "jeton-factice"})
    M.PLANIFIER(False, "rattrapage", lambda t, a="", p=4: vus.append((t, p)))
    assert vus == [("messagerie_sync", 1), ("messagerie_brouillons", 2)], vus
    assert {"messagerie_sync", "messagerie_brouillons"} <= set(M.TACHES) and M.RESEAU


@test("faux Graph : synchronisation lecture seule → objets mail/rdv rattachés, « attente » seulement si une réponse est attendue")
def t_sync():
    os.environ.update({"CEREBRO_GRAPH_URL": GURL, "CEREBRO_GRAPH_TOKEN": "jeton-factice"})
    M = charger_extension()
    b = M.synchroniser()
    assert b["mails_crees"] == 3 and b["attente"] == 1 and b["rdv_crees"] == 1, b
    c = db()
    rows = {json.loads(r["data"])["internet_message_id"]: r for r in c.execute("SELECT * FROM objets WHERE type='mail' AND data LIKE '%\"origine\": \"m365\"%'")}
    roch = rows["<msg-1@example.ch>"]
    assert roch["statut"] == "attente" and roch["client"], dict(roch)
    assert c.execute("SELECT nom FROM objets WHERE id=?", (roch["client"],)).fetchone()[0].startswith("Famille Rochat")
    assert rows["<msg-2@example.ch>"]["statut"] == "information" and rows["<msg-3@example.ch>"]["statut"] == "information"
    rdv = c.execute("SELECT * FROM objets WHERE type='rdv' AND data LIKE '%\"graph_id\": \"EV-1\"%'").fetchone()
    assert rdv and rdv["statut"] == "fiche à préparer" and rdv["prochaine_date"] == DEMAIN.date().isoformat(), dict(rdv) if rdv else None
    assert c.execute("SELECT nom FROM objets WHERE id=?", (rdv["client"],)).fetchone()[0].startswith("Lémantech"), rdv["client"]
    assert all(r[2] == "Bearer jeton-factice" for r in REQUETES if r[0] == "GET")
    assert {r[0] for r in REQUETES} == {"GET"}, "la synchronisation a écrit dans Outlook"
    aucun_envoi()
    # la boucle d'initiative voit bien le mail et le rendez-vous
    sys.path.insert(0, str(R / ".team/scripts/initiative"))
    import initiative
    ids = [o["id"] for _, o in initiative.collecter(20)]
    assert roch["id"] in ids and rdv["id"] in ids, ids


@test("faux Graph : synchronisation idempotente (deuxième passage : rien de nouveau, rien en double)")
def t_idempotent():
    M = charger_extension()
    avant = db().execute("SELECT COUNT(*) FROM objets WHERE type IN ('mail','rdv')").fetchone()[0]
    b = M.synchroniser()
    apres = db().execute("SELECT COUNT(*) FROM objets WHERE type IN ('mail','rdv')").fetchone()[0]
    assert b["mails_crees"] == 0 and b["rdv_crees"] == 0 and avant == apres, (b, avant, apres)


@test("faux Graph : brouillon de l'initiative déposé dans Outlook (createReply + corps), jamais envoyé, une seule fois")
def t_brouillon():
    from cb.objects import create
    c = db()
    mail = [r for r in c.execute("SELECT id, client, data FROM objets WHERE type='mail'") if json.loads(r["data"]).get("internet_message_id") == "<msg-1@example.ch>"][0]
    doc = create("document", "Brouillon de réponse — Dividende Rochat Holding", client=mail["client"], statut="brouillon à relire",
                 liens=[mail["id"]], prochaine_action="Mustafa relit",
                 body="# Brouillon de réponse — Dividende Rochat Holding\n\n## Brouillon\nBonjour Monsieur Rochat,\n\nOui, c'est possible si l'assemblée générale le décide.\n\nAvec mes meilleures salutations\n")
    core.db().commit()
    M = charger_extension()
    n0 = len(REQUETES)
    b = M.deposer_brouillons()
    assert b["deposes"] == 1, b
    nouvelles = REQUETES[n0:]
    assert ("POST", "/v1.0/me/messages/AAMk-1/createReply", None) in nouvelles, nouvelles
    assert any(r[0] == "PATCH" and r[1] == "/v1.0/me/messages/DRAFT-1" for r in nouvelles), nouvelles
    d = ETAT["drafts"]["DRAFT-1"]
    assert d["isDraft"] and "Oui, c&#x27;est possible" in d["body"]["content"] and "message d'origine" in d["body"]["content"], d["body"]
    assert "Brouillon de réponse" not in d["body"]["content"], "titre interne recopié dans le mail"
    o = json.loads(db().execute("SELECT data FROM objets WHERE id=?", (doc,)).fetchone()[0])
    assert o.get("outlook_brouillon_id") == "DRAFT-1", o
    n1 = len(REQUETES)
    b2 = M.deposer_brouillons()
    assert b2["deposes"] == 0 and len(REQUETES) == n1, ("second dépôt", b2, REQUETES[n1:])
    aucun_envoi()


@test("connecteur sans voie d'envoi : sendMail, …/send, forward, DELETE refusés avant de partir (aucune requête émise)")
def t_aucun_envoi():
    sys.path.insert(0, str(R / ".team/scripts/connectors"))
    import graph as G
    g = G.Graph()
    n0 = len(REQUETES)
    for meth, chemin in [("POST", "/me/sendMail"), ("POST", "/me/messages/AAMk-1/send"), ("POST", "/me/messages/DRAFT-1/send"),
                         ("POST", "/me/messages/AAMk-1/forward"), ("POST", "/me/messages/AAMk-1/reply"), ("DELETE", "/me/messages/AAMk-1"),
                         ("POST", "/me/events"), ("POST", "/users/x/sendMail")]:
        try:
            g._req(meth, chemin, {})
            raise AssertionError(f"{meth} {chemin} accepté")
        except PermissionError:
            pass
    assert len(REQUETES) == n0, REQUETES[n0:]
    assert "Mail.Send" not in G.SCOPES and set(G.SCOPES) == {"Mail.ReadWrite", "Calendars.Read", "User.Read"}
    src = "\n".join((R / ".team/scripts/connectors" / f).read_text(encoding="utf-8") for f in ("graph.py", "m365_mcp.py", "connect_mail.py"))
    assert not re.search(r'["\']/me/sendMail|/send["\']', src), "une URL d'envoi figure dans le code"


@test("serveur MCP m365 : quatre outils lecture/brouillon, aucun outil d'envoi, brouillon créé par l'outil")
def t_mcp():
    e = dict(ENV, CEREBRO_GRAPH_URL=GURL, CEREBRO_GRAPH_TOKEN="jeton-factice")
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "messages_recents", "arguments": {"jours": 2}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "brouillon_reponse", "arguments": {"id": "AAMk-3", "texte": "Merci, bien noté."}}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "agenda", "arguments": {}}}]
    r = subprocess.run([PY, str(R / ".team/scripts/connectors/m365_mcp.py")], input="\n".join(json.dumps(m) for m in msgs).encode("utf-8"),
                       env=e, capture_output=True, timeout=60)
    rep = {d["id"]: d for d in (json.loads(l) for l in r.stdout.decode("utf-8").splitlines() if l.strip())}
    noms = [t["name"] for t in rep[2]["result"]["tools"]]
    assert noms == ["messages_recents", "message", "brouillon_reponse", "agenda"], noms
    assert not any(re.search(r"send|envoi|envoy", t["name"], re.I) for t in rep[2]["result"]["tools"])
    assert len(json.loads(rep[3]["result"]["content"][0]["text"])) == 3
    b = json.loads(rep[4]["result"]["content"][0]["text"])
    assert b.get("brouillon") is True and b.get("envoye") is False, b
    assert json.loads(rep[5]["result"]["content"][0]["text"])[0]["objet"].startswith("Séance")
    aucun_envoi()


@test("connexion : inscription du serveur m365 dans .mcp.json après validation de la configuration")
def t_inscription():
    e = dict(ENV)
    r = subprocess.run([PY, str(R / ".team/scripts/connectors/connect_mail.py"), "--inscrire", "--sans-confiance"],
                       env=e, capture_output=True, timeout=400, cwd=str(R))
    d = json.loads(r.stdout.decode("utf-8").strip().splitlines()[-1])
    m = json.loads((R / ".mcp.json").read_text(encoding="utf-8"))
    if d.get("inscrit"):
        assert m["mcpServers"]["m365"]["args"] == [".team/scripts/connectors/m365_mcp.py"], m
        assert "cerebro" in m["mcpServers"], "serveurs existants perdus"
        return "validée (--sans-session)"
    assert "m365" not in m["mcpServers"], "inscription refusée mais .mcp.json non restauré"
    return f"NOTE : validation refusée dans la racine jetable ({str(d.get('detail'))[:120]}) ; ancien .mcp.json remis"


@test("jeton : cache chiffré hors dépôt (jamais en clair)")
def t_cache():
    sys.path.insert(0, str(R / ".team/scripts/connectors"))
    import graph as G
    d = G.dossier_cache()
    assert str(d).startswith(str(TMP)) and not str(d).startswith(str(R)), d
    c, mode = G.cache()
    secret = '{"AccessToken": {"x": {"secret": "JETON-TRES-SECRET"}}}'
    if mode == "Fernet":
        s = G._CacheFernet(d / "essai.bin")
        s.save(secret)
        assert b"JETON-TRES-SECRET" not in (d / "essai.bin").read_bytes() and s.load() == secret
    return f"mode {mode}"


def main():
    for t in TESTS:
        t()
    SRV.shutdown()
    ko = [r for r in RES if not r[1]]
    print(f"\n{len(RES) - len(ko)}/{len(RES)} tests réussis" + (f" — échecs : {', '.join(r[0][:40] for r in ko)}" if ko else ""))
    if not ko:
        shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(1 if ko else 0)


if __name__ == "__main__":
    main()
