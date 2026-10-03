#!/usr/bin/env python3
"""Connexion de la messagerie et de l'agenda Microsoft 365 (§2, §4.1, §16.5) — le seul geste de Mustafa : cliquer « autoriser ».
Flux « device code » (MSAL) : la page Microsoft s'ouvre dans le navigateur, le code est copié dans le presse-papiers,
une phrase simple est affichée ; un processus détaché attend l'autorisation (15 min au plus), puis :
  jeton dans le cache chiffré du profil (hors dépôt) → vérification (/me) → configuration (poste.messagerie_connectee,
  acces.connecteurs) → inscription du serveur MCP « m365 » dans .mcp.json → validation (valider_config.py --sans-session),
  retour à l'ancien .mcp.json si elle échoue → dossier de confiance (valider_config.py --confiance).
Permissions déléguées : Mail.ReadWrite, Calendars.Read, User.Read (+ offline_access) ; jamais Mail.Send.
Usage : connecter_messagerie.py              lance le flux (rend la main aussitôt ; l'attente continue en fond)
        connecter_messagerie.py --attendre   même chose, mais attend dans ce processus (technicien)
        connecter_messagerie.py --etat       état de la connexion (JSON)
        connecter_messagerie.py --inscrire   (ré)inscrit seulement le serveur MCP (après une connexion réussie)
        connecter_messagerie.py --deconnecter efface le jeton et retire le serveur MCP
Options : --sans-confiance (tests : ne touche pas ~/.claude.json) · --sans-navigateur"""
import sys, os, json, time, shutil, subprocess, argparse, webbrowser
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import graph as G

ROOT = G.ROOT
RUN = ROOT / ".equipe" / "run"
ETAT = RUN / "m365_connexion.json"
FLUX = RUN / "m365_flux.json"
MCP = ROOT / ".mcp.json"
NOM_SERVEUR = "m365"
ARGS_SERVEUR = [".equipe/scripts/connecteurs/m365_mcp.py"]


def ecrire_etat(**d):
    RUN.mkdir(parents=True, exist_ok=True)
    d["le"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    ETAT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    G._journal(connexion=d.get("etat"), detail=d.get("detail"))
    return d


def lire_etat():
    try:
        return json.loads(ETAT.read_text(encoding="utf-8"))
    except Exception:
        return {"etat": "jamais connecté"}


def presse_papiers(txt):
    try:
        exe = "clip" if os.name == "nt" else ("pbcopy" if sys.platform == "darwin" else "xclip")
        if shutil.which(exe):
            args = [exe] if exe != "xclip" else [exe, "-selection", "clipboard"]
            subprocess.run(args, input=txt.encode("utf-16-le" if os.name == "nt" else "utf-8"), timeout=5)
            return True
    except Exception:
        pass
    return False


# ------------------------------------------------------------------ cerebro
def _cb():
    sys.path.insert(0, str(ROOT / ".equipe" / "cerebro"))
    os.environ.setdefault("CEREBRO_ROOT", str(ROOT))
    from cb import core, config as K, files as F
    return core, K, F


def apres_connexion(compte):
    """configuration, question close, état ; jamais bloquant"""
    try:
        core, K, F = _cb()
        K.set_("poste.messagerie_connectee", "oui", source=f"détecté le {core.iso()}")
        K.set_("poste.messagerie", "Outlook / Microsoft 365", source=f"détecté le {core.iso()}")
        con = core.db()
        for r in con.execute("SELECT id FROM questions_ouvertes WHERE statut='ouverte' AND (cle_config IN ('poste.messagerie_connectee','poste.messagerie') OR formulation LIKE '%brancher sur votre messagerie%')").fetchall():
            con.execute("UPDATE questions_ouvertes SET statut='repondue', reponse=? WHERE id=?", ("connectée", r[0]))
            con.execute("UPDATE objets SET statut='repondue' WHERE id=?", (r[0],))
        conn = K.get("acces.connecteurs") or []
        if "Microsoft 365 (lecture et brouillons)" not in conn:
            K.set_("acces.connecteurs", json.dumps(list(conn) + ["Microsoft 365 (lecture et brouillons)"], ensure_ascii=False), source=f"détecté le {core.iso()}")
        core.set_etat("m365", {"compte": compte, "connecte_le": core.stamp()})
        con.commit()
    except Exception as e:
        G._journal(apres_connexion=repr(e)[:300])


# ------------------------------------------------------------------ .mcp.json
def commande_python():
    try:
        m = json.loads(MCP.read_text(encoding="utf-8-sig"))
        c = ((m.get("mcpServers") or {}).get("cerebro") or {}).get("command")
        if c:
            return c
    except Exception:
        pass
    return os.environ.get("CEREBRO_PYTHON") or sys.executable or "python"


def inscrire_mcp(confiance=True):
    avant = MCP.read_text(encoding="utf-8-sig") if MCP.exists() else '{"mcpServers": {}}'
    m = json.loads(avant)
    m.setdefault("mcpServers", {})[NOM_SERVEUR] = {"type": "stdio", "command": commande_python(), "args": ARGS_SERVEUR, "env": {}}
    MCP.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    val = ROOT / ".equipe" / "scripts" / "valider_config.py"
    ok, detail = True, "validateur absent"
    if val.exists():
        r = subprocess.run([sys.executable, str(val), "--sans-session", "--json"], cwd=str(ROOT), capture_output=True,
                           timeout=300, encoding="utf-8", errors="ignore")
        try:
            d = json.loads((r.stdout or "").strip().splitlines()[-1])
            ok, detail = bool(d.get("ok")), d.get("erreurs") or "ok"
        except Exception:
            ok, detail = r.returncode == 0, (r.stdout or r.stderr or "")[-300:]
    if not ok:
        MCP.write_text(avant, encoding="utf-8")  # le lancement suivant ne peut jamais casser (§0.10)
        try:
            _cb()[2].incident_add("connecteurs", "inscription du serveur m365 refusée par la validation",
                                  "ancien .mcp.json remis ; la synchronisation de fond fonctionne sans le serveur")
        except Exception:
            pass
        return {"inscrit": False, "detail": detail}
    if confiance and val.exists():
        subprocess.run([sys.executable, str(val), "--confiance"], cwd=str(ROOT), capture_output=True, timeout=60)
    return {"inscrit": True, "detail": detail}


def retirer_mcp():
    try:
        m = json.loads(MCP.read_text(encoding="utf-8-sig"))
        if (m.get("mcpServers") or {}).pop(NOM_SERVEUR, None) is not None:
            MCP.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return True
    except Exception:
        pass
    return False


# ------------------------------------------------------------------ flux
def lancer(navigateur=True):
    app, mode = G.application()
    flux = app.initiate_device_flow(scopes=G.SCOPES)
    if "user_code" not in flux:
        d = ecrire_etat(etat="échec", detail=str(flux.get("error_description") or flux)[:300],
                        phrase="Je n'arrive pas à joindre Microsoft pour l'instant ; je réessaierai plus tard.")
        return d, None
    RUN.mkdir(parents=True, exist_ok=True)
    FLUX.write_text(json.dumps(flux), encoding="utf-8")
    copie = presse_papiers(flux["user_code"])
    url = flux.get("verification_uri") or "https://microsoft.com/devicelogin"
    if navigateur:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    phrase = (f"Une page Microsoft vient de s'ouvrir : collez-y le code {flux['user_code']}"
              + (" (il est déjà copié)" if copie else "") + ", puis cliquez sur « Autoriser ».")
    d = ecrire_etat(etat="en attente", phrase=phrase, url=url, code=flux["user_code"], cache=mode,
                    expire=time.strftime("%H:%M", time.localtime(flux.get("expires_at", time.time() + 900))))
    return d, flux


def attendre(flux=None, confiance=True):
    if flux is None:
        flux = json.loads(FLUX.read_text(encoding="utf-8"))
    app, mode = G.application()
    try:
        r = app.acquire_token_by_device_flow(flux)  # bloque jusqu'à l'autorisation ou l'expiration du code
    finally:
        FLUX.unlink(missing_ok=True)
    if "access_token" not in r and r.get("error") not in ("expired_token", "authorization_declined", "access_denied"):
        # flux par code d'appareil refusé par une stratégie de l'organisation : connexion par le navigateur (même application,
        # mêmes permissions déléguées) ; Mustafa clique « Autoriser » dans la page qui s'ouvre
        G._journal(repli_navigateur=str(r.get("error_description") or r.get("error"))[:200])
        try:
            r = app.acquire_token_interactive(G.SCOPES, timeout=600, prompt="select_account")
        except Exception as e:
            r = {"error": "interactive", "error_description": repr(e)[:300]}
    if "access_token" not in r:
        return ecrire_etat(etat="échec", detail=str(r.get("error_description") or r.get("error"))[:300],
                           phrase="La liaison avec votre messagerie n'a pas abouti ; je vous la reproposerai plus tard.")
    try:
        moi = G.Graph(tok=r["access_token"]).moi()
        compte = moi.get("mail") or moi.get("userPrincipalName")
    except Exception as e:
        compte = (r.get("id_token_claims") or {}).get("preferred_username")
        G._journal(verification=repr(e)[:200])
    apres_connexion(compte)
    ins = inscrire_mcp(confiance)
    return ecrire_etat(etat="connecté", compte=compte, cache=mode, mcp=ins,
                       phrase="C'est fait : je vois désormais vos mails et votre agenda, et je prépare les réponses en brouillon dans Outlook.")


def detacher():
    args = [sys.executable, str(Path(__file__).resolve()), "--attendre-flux"] + (["--sans-confiance"] if "--sans-confiance" in sys.argv else [])
    kw = {"cwd": str(ROOT), "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        kw["creationflags"] = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW
    else:
        kw["start_new_session"] = True
    subprocess.Popen(args, **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--attendre", action="store_true")
    ap.add_argument("--attendre-flux", action="store_true")
    ap.add_argument("--etat", action="store_true")
    ap.add_argument("--inscrire", action="store_true")
    ap.add_argument("--deconnecter", action="store_true")
    ap.add_argument("--sans-confiance", action="store_true")
    ap.add_argument("--sans-navigateur", action="store_true")
    a = ap.parse_args()
    if a.etat:
        d = lire_etat()
        d["connecte"] = G.connecte()
        return d
    if a.inscrire:
        return inscrire_mcp(not a.sans_confiance)
    if a.deconnecter:
        for f in G.dossier_cache().glob("*"):
            try:
                f.unlink()
            except Exception:
                pass
        return ecrire_etat(etat="déconnecté", mcp_retire=retirer_mcp(), phrase="La liaison avec votre messagerie est coupée.")
    if a.attendre_flux:
        return attendre(None, not a.sans_confiance)
    d, flux = lancer(not a.sans_navigateur)
    if not flux:
        return d
    if a.attendre:
        print(json.dumps(d, ensure_ascii=False), flush=True)
        return attendre(flux, not a.sans_confiance)
    detacher()
    return d


if __name__ == "__main__":
    try:
        r = main()
    except Exception as e:
        r = ecrire_etat(etat="échec", detail=repr(e)[:300], phrase="Je n'arrive pas à relier votre messagerie pour l'instant ; je continue sans.")
    print(json.dumps(r, ensure_ascii=False))
