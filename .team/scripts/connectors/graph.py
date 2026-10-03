#!/usr/bin/env python3
"""Microsoft 365 (Outlook, agenda) par Microsoft Graph — LECTURE ET BROUILLONS SEULEMENT (§4 principe 4, §6.4, §12).
Permissions déléguées demandées : Mail.ReadWrite (lire, créer et compléter des brouillons), Calendars.Read, User.Read ;
offline_access/openid/profile sont ajoutés d'office par MSAL. JAMAIS Mail.Send.
Le connecteur est construit sans voie d'envoi : la couche HTTP n'émet que GET (lecture), POST …/createReply (brouillon)
et PATCH sur un message qui est un brouillon (corps du brouillon). Toute autre requête lève PermissionError avant
de partir (ce n'est pas un filtre de conversation : c'est la forme même du connecteur, §0.3 « connecteurs sans droit d'envoi »).
Jeton : MSAL, flux « device code », cache chiffré dans le profil utilisateur (hors dépôt) :
  Windows DPAPI · macOS Trousseau · Linux libsecret, sinon Fernet (clé à part, droits 600).
Variables de test : CEREBRO_GRAPH_URL (faux Graph), CEREBRO_GRAPH_TOKEN (jeton factice, MSAL contourné),
CEREBRO_M365_DIR (dossier du cache)."""
import os, sys, json, re, time, base64, html, urllib.request, urllib.parse, urllib.error
from pathlib import Path

ROOT = Path(os.environ.get("CEREBRO_ROOT") or Path(__file__).resolve().parents[3])
SCOPES = ["Mail.ReadWrite", "Calendars.Read", "User.Read"]  # + offline_access (ajouté par MSAL) ; jamais Mail.Send
INTERDIT_SCOPES = {"mail.send", "mail.send.shared"}
# identifiant public de l'application Microsoft « Microsoft Graph Command Line Tools » (client public, délégué,
# flux device code ; documentée par Microsoft comme application de première partie des outils Graph en ligne de commande)
CLIENT_ID_DEFAUT = "14d82eec-204b-4c2f-b7e8-296a70dab67e"
GRAPH = "https://graph.microsoft.com/v1.0"
CATEGORIE_BROUILLON = "Équipe — à relire"
SELECT_MAIL = ("id,subject,from,sender,toRecipients,ccRecipients,receivedDateTime,bodyPreview,conversationId,isRead,"
               "hasAttachments,internetMessageId,webLink,parentFolderId,inferenceClassification,importance,isDraft")
SELECT_RDV = "id,iCalUId,subject,start,end,location,attendees,organizer,bodyPreview,isCancelled,isOnlineMeeting,webLink,seriesMasterId"


def _journal(**rec):
    try:
        d = ROOT / ".team" / "brain" / "log"
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "m365.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"le": time.strftime("%Y-%m-%dT%H:%M:%S"), **rec}, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ------------------------------------------------------------------ configuration
def _config(cle, defaut=None):
    try:
        sys.path.insert(0, str(ROOT / ".team" / "cerebro"))
        os.environ.setdefault("CEREBRO_ROOT", str(ROOT))
        from cb import config as K
        v = K.get(cle)
        return defaut if v in (None, "", []) else v
    except Exception:
        return defaut


def client_id():
    return os.environ.get("CEREBRO_M365_CLIENT_ID") or _config("access.m365_client_id", CLIENT_ID_DEFAUT) or CLIENT_ID_DEFAUT


def autorite():
    return "https://login.microsoftonline.com/" + str(_config("access.m365_annuaire", "common") or "common")


def dossiers_suivis():
    v = _config("access.m365_dossiers_suivis", ["inbox"])
    if isinstance(v, str):
        v = [x.strip() for x in re.split(r"[,;]", v) if x.strip()]
    return v or ["inbox"]


def dossier_cache():
    if os.environ.get("CEREBRO_M365_DIR"):
        d = Path(os.environ["CEREBRO_M365_DIR"])
    elif os.name == "nt":
        d = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "MonEquipe" / "m365"
    elif sys.platform == "darwin":
        d = Path.home() / "Library" / "Application Support" / "MonEquipe" / "m365"
    else:
        d = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "mon-equipe" / "m365"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ------------------------------------------------------------------ cache chiffré
class _CacheFernet:
    """repli Linux sans trousseau : cache chiffré Fernet, clé dans un fichier séparé (droits 600), hors dépôt"""
    def __init__(self, chemin):
        from cryptography.fernet import Fernet
        self.p = Path(chemin)
        k = self.p.with_name("cle.bin")
        if not k.exists():
            k.write_bytes(Fernet.generate_key())
            try:
                os.chmod(k, 0o600)
            except Exception:
                pass
        self.f = Fernet(k.read_bytes())

    def load(self):
        return self.f.decrypt(self.p.read_bytes()).decode("utf-8") if self.p.exists() else None

    def save(self, txt):
        self.p.write_bytes(self.f.encrypt(txt.encode("utf-8")))
        try:
            os.chmod(self.p, 0o600)
        except Exception:
            pass


def cache():
    """renvoie (msal.TokenCache, mode) ; le cache n'est jamais écrit en clair"""
    import msal
    chemin = dossier_cache() / "jeton.bin"
    try:
        import msal_extensions as X
        if os.name == "nt":
            pers = X.FilePersistenceWithDataProtection(str(chemin))
            mode = "DPAPI"
        elif sys.platform == "darwin":
            pers = X.KeychainPersistence(str(chemin), "MonEquipe", "m365")
            mode = "Trousseau"
        else:
            pers = X.LibsecretPersistence(str(chemin), schema_name="mon_equipe", attributes={"app": "mon-equipe-m365"})
            mode = "libsecret"
        return X.PersistedTokenCache(pers), mode
    except Exception:
        pass
    store = _CacheFernet(chemin)

    class C(msal.SerializableTokenCache):
        def __init__(self):
            super().__init__()
            try:
                t = store.load()
                if t:
                    self.deserialize(t)
            except Exception:
                pass

        def modify(self, *a, **k):
            super().modify(*a, **k)
            store.save(self.serialize())
    return C(), "Fernet"


def application():
    import msal
    c, mode = cache()
    return msal.PublicClientApplication(client_id(), authority=autorite(), token_cache=c), mode


def connecte():
    """sans réseau : un compte figure-t-il dans le cache ?"""
    if os.environ.get("CEREBRO_GRAPH_TOKEN"):
        return True
    if not (dossier_cache() / "jeton.bin").exists():
        return False
    try:
        app, _ = application()
        return bool(app.get_accounts())
    except Exception:
        return False


def _scp(jeton):
    try:
        p = jeton.split(".")[1]
        return set(json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4))).get("scp", "").split())
    except Exception:
        return set()


def jeton():
    if os.environ.get("CEREBRO_GRAPH_TOKEN"):
        return os.environ["CEREBRO_GRAPH_TOKEN"]
    app, _ = application()
    comptes = app.get_accounts()
    if not comptes:
        raise RuntimeError("messagerie non connectée")
    r = app.acquire_token_silent(SCOPES, account=comptes[0])
    if not r or "access_token" not in r:
        raise RuntimeError("autorisation expirée : reconnecter la messagerie")
    en_trop = {s for s in _scp(r["access_token"]) if s.lower() in INTERDIT_SCOPES}
    if en_trop:  # consentement partagé hérité d'un autre usage de l'application : jamais utilisé ici, signalé
        _journal(avertissement="le jeton porte un droit d'envoi non demandé", scopes=sorted(en_trop))
    return r["access_token"]


# ------------------------------------------------------------------ couche HTTP (lecture et brouillons seulement)
RE_CREATE_REPLY = re.compile(r"^/me/messages/[^/]+/createReply$")
RE_MESSAGE = re.compile(r"^/me/messages/[^/]+$")


def autorise(methode, chemin):
    """forme du connecteur : lecture, création de brouillon de réponse, mise à jour d'un brouillon ; rien d'autre"""
    c = urllib.parse.urlsplit(chemin).path
    c = re.sub(r"^/v1\.0", "", c)
    if re.search(r"/(send|sendMail|forward|reply|replyAll)$", c, re.I):
        return False
    if methode == "GET":
        return c == "/me" or c.startswith("/me/")
    if methode == "POST":
        return bool(RE_CREATE_REPLY.match(c))
    if methode == "PATCH":
        return bool(RE_MESSAGE.match(c))
    return False


class Graph:
    def __init__(self, base=None, tok=None):
        self.base = (base or os.environ.get("CEREBRO_GRAPH_URL") or GRAPH).rstrip("/")
        self._tok = tok
        self.requetes = []

    def _req(self, methode, chemin, corps=None, entetes=None, _essai=0):
        if chemin.startswith("http"):  # @odata.nextLink : URL complète
            u = urllib.parse.urlsplit(chemin)
            chemin = chemin[len(self.base):] if chemin.startswith(self.base) else re.sub(r"^/v1\.0", "", u.path) + ("?" + u.query if u.query else "")
        if not autorise(methode, chemin):
            _journal(refuse=f"{methode} {chemin[:120]}")
            raise PermissionError(f"opération hors du connecteur lecture-brouillons : {methode} {chemin[:80]}")
        self._tok = self._tok or jeton()
        h = {"Authorization": f"Bearer {self._tok}", "Accept": "application/json"}
        h.update(entetes or {})
        data = None
        if corps is not None:
            data = json.dumps(corps).encode("utf-8")
            h["Content-Type"] = "application/json"
        r = urllib.request.Request(self.base + chemin, data=data, method=methode, headers=h)
        self.requetes.append((methode, chemin))
        try:
            with urllib.request.urlopen(r, timeout=60) as resp:
                txt = resp.read().decode("utf-8")
                _journal(req=f"{methode} {chemin.split('?')[0][:100]}", code=resp.status)
                return json.loads(txt) if txt.strip() else {}
        except urllib.error.HTTPError as e:
            if e.code in (429, 503, 504) and _essai < 3:
                time.sleep(min(int(e.headers.get("Retry-After") or 2), 30))
                return self._req(methode, chemin, corps, entetes, _essai + 1)
            _journal(req=f"{methode} {chemin.split('?')[0][:100]}", code=e.code)
            raise

    def get(self, chemin, entetes=None):
        return self._req("GET", chemin, None, entetes)

    def pages(self, chemin, entetes=None, maxi=500):
        out, url = [], chemin
        while url and len(out) < maxi:
            d = self.get(url, entetes)
            out += d.get("value", [])
            url = d.get("@odata.nextLink")
        return out

    # -------------------------------------------------------------- outils
    def moi(self):
        return self.get("/me?$select=displayName,mail,userPrincipalName")

    def messages_recents(self, jours=2, dossiers=None, corps=False):
        import datetime as dt
        depuis = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=float(jours))).strftime("%Y-%m-%dT%H:%M:%SZ")
        sel = SELECT_MAIL + (",body" if corps else "")
        out = []
        for d in dossiers or dossiers_suivis():
            q = urllib.parse.urlencode({"$filter": f"receivedDateTime ge {depuis}", "$orderby": "receivedDateTime desc",
                                        "$top": "50", "$select": sel}, safe="$,:/'", quote_via=urllib.parse.quote)
            for m in self.pages(f"/me/mailFolders/{urllib.parse.quote(d)}/messages?{q}",
                                {"Prefer": 'outlook.body-content-type="text"'}):
                m["_dossier"] = d
                out.append(m)
        return out

    def message(self, mid):
        return self.get(f"/me/messages/{urllib.parse.quote(mid)}?$select={SELECT_MAIL},body,uniqueBody",
                        {"Prefer": 'outlook.body-content-type="text"'})

    def chercher_par_internet_id(self, iid):
        q = urllib.parse.quote(f"internetMessageId eq '{iid}'")
        v = self.get(f"/me/messages?$filter={q}&$select=id,isDraft").get("value", [])
        return v[0]["id"] if v else None

    def brouillon_reponse(self, mid, texte, categorie=CATEGORIE_BROUILLON):
        """crée dans Outlook un BROUILLON de réponse (jamais envoyé) : createReply puis corps du brouillon"""
        d = self._req("POST", f"/me/messages/{urllib.parse.quote(mid)}/createReply", {})
        bid = d["id"]
        actuel = self.get(f"/me/messages/{urllib.parse.quote(bid)}?$select=id,isDraft,body")
        if not actuel.get("isDraft", False):
            raise PermissionError("le message créé n'est pas un brouillon : rien n'est modifié")
        cite = (actuel.get("body") or {}).get("content") or ""
        if (actuel.get("body") or {}).get("contentType", "html").lower() == "text":
            cite = "<pre>" + html.escape(cite) + "</pre>"
        contenu = texte_vers_html(texte) + "<br>" + cite
        maj = {"body": {"contentType": "HTML", "content": contenu}}
        if categorie:
            maj["categories"] = [categorie]
        self._req("PATCH", f"/me/messages/{urllib.parse.quote(bid)}", maj)
        _journal(brouillon=bid, reponse_a=mid[:40])
        return {"id": bid, "webLink": d.get("webLink"), "brouillon": True, "envoye": False}

    def agenda(self, jours=7):
        import datetime as dt
        n = dt.datetime.now(dt.timezone.utc)
        q = urllib.parse.urlencode({"startDateTime": n.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                    "endDateTime": (n + dt.timedelta(days=float(jours))).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                    "$orderby": "start/dateTime", "$top": "100", "$select": SELECT_RDV}, safe="$,:/", quote_via=urllib.parse.quote)
        return self.pages(f"/me/calendarView?{q}", {"Prefer": 'outlook.timezone="Europe/Zurich"'})


def texte_vers_html(t):
    paras = [p.strip() for p in re.split(r"\n\s*\n", (t or "").strip()) if p.strip()]
    return "".join(f"<p>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in paras)
