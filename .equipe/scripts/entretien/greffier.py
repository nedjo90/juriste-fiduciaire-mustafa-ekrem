#!/usr/bin/env python3
"""Greffier groupé (§9.4, §11) : classe les captures non traitées de .equipe/inbox/ par UN appel claude -p (modèle léger).
Verrou (un seul greffier à la fois) ; état des lignes traitées dans .equipe/inbox/_etat-greffier.json ; mesure des tokens.
Usage : greffier.py [--max N] [--simuler] [--modele haiku]   (--simuler : prépare le lot sans appeler le modèle)
Rien à classer → aucun appel (loi 3). Échec → incident, captures laissées non classées (reprises au cycle suivant)."""
import sys, os, json, time, argparse, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fond
from fond import ROOT, EQ, INBOX, journal

ETAT = INBOX / "_etat-greffier.json"
ROLE = EQ / "roles" / "greffier.md"
MAX_CAR = 20000


def non_classees(maxi=40):
    """[(fichier, n_ligne, capture)] dans l'ordre chronologique, au plus `maxi`"""
    etat = fond.lire_json(ETAT, {}) or {}
    lot = []
    for p in sorted(INBOX.glob("*.jsonl")) if INBOX.exists() else []:
        deja = int(etat.get(p.name, 0))
        lignes = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        for i, l in enumerate(lignes[deja:], start=deja):
            try:
                lot.append((p.name, i + 1, json.loads(l)))
            except Exception:
                lot.append((p.name, i + 1, None))  # ligne illisible : marquée traitée, ignorée
            if len(lot) >= maxi:
                return lot
    return lot


def compter():
    return len(non_classees(10_000))


def formater(lot):
    """renvoie (lignes envoyées, nombre d'éléments du lot consommés, illisibles compris) sous budget de caractères"""
    out, total, n = [], 0, 0
    fond.cb()
    from cb.core import cut
    for k, (_, _, c) in enumerate(lot, 1):
        if c:
            s = f"[{k}] {str(c.get('le', ''))[:16].replace('T', ' ')} · M: {cut(c.get('prompt'), 1500)} · R: {cut(c.get('reponse'), 1200)}"
            if out and total + len(s) > MAX_CAR:
                break
            out.append(s)
            total += len(s)
        n = k
    return out, n


def marquer(lot, n):
    etat = fond.lire_json(ETAT, {}) or {}
    for f, ligne, _ in lot[:n]:
        etat[f] = max(int(etat.get(f, 0)), ligne)
    fond.ecrire_json(ETAT, etat)


def lancer(maxi=40, simuler=False, modele=None):
    t0 = time.time()
    lot = non_classees(maxi)
    if not lot:
        journal("greffier", statut="rien à classer")
        return {"captures": 0}
    lignes, n_lot = formater(lot)
    if not lignes:
        marquer(lot, n_lot)
        return {"captures": 0, "illisibles": n_lot}
    fond.cb()
    from cb import config as K, files as F, core
    modele = modele or K.get("modeles.leger") or "haiku"
    role = ROLE.read_text(encoding="utf-8") if ROLE.exists() else "Classe ces captures via cerebro."
    prompt = f"{role}\n\n## Date du jour\n{core.iso()} (Europe/Zurich)\n\n## Lot de captures ({len(lignes)})\n" + "\n".join(lignes)
    if simuler:
        journal("greffier", statut="simulé", captures=len(lignes))
        return {"captures": len(lignes), "simule": True, "prompt_car": len(prompt)}
    claude = fond.claude_exe()
    if not claude:
        fond.incident("greffier : programme claude introuvable, captures laissées en attente", "technique", "reprise au prochain cycle")
        return {"erreur": "claude introuvable"}
    cmd = [claude, "-p", "--model", modele, "--allowedTools", "Read,Bash(cerebro:*),Bash(python:*),Bash(python3:*)",
           "--permission-mode", "bypassPermissions", "--output-format", "json", "--strict-mcp-config", "--no-session-persistence"]
    journal("greffier", statut="début", captures=len(lignes), modele=modele)
    try:
        r = subprocess.run(cmd, input=prompt, capture_output=True,  # invite par l'entrée standard (limite de ligne de commande Windows)
                           cwd=str(ROOT), env=fond.env_fond(),
                           timeout=900, encoding="utf-8", errors="ignore")
        res = json.loads((r.stdout or "").strip().splitlines()[-1]) if (r.stdout or "").strip() else {}
    except Exception as e:
        res, r = {"is_error": True, "erreur": repr(e)}, None
    ms = int((time.time() - t0) * 1000)
    u = res.get("usage") or {}
    tokens = sum(int(u.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens"))
    ok = bool(res) and not res.get("is_error") and res.get("subtype") == "success"
    try:
        F.mesure("greffier", "classement", "leger", tokens, ms, 1 if ok else 0)
    except Exception:
        pass
    if ok:
        marquer(lot, n_lot)
        journal("greffier", statut="fin", ok=True, captures=len(lignes), ms=ms, tokens=tokens, cache_lu=u.get("cache_read_input_tokens"),
                cout_usd=res.get("total_cost_usd"), refus=len(res.get("permission_denials") or []), rapport=core.cut(res.get("result"), 600))
    else:
        err = res.get("erreur") or res.get("result") or (r.stderr[-300:] if r is not None and r.stderr else "sortie vide")
        journal("greffier", statut="fin", ok=False, ms=ms, erreur=core.cut(err, 400))
        fond.incident("greffier : classement groupé en échec", "technique", "captures laissées en attente, relance au prochain cycle")
    return {"captures": len(lignes), "ok": ok, "tokens": tokens, "ms": ms, "rapport": core.cut(res.get("result"), 300)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=40)
    ap.add_argument("--simuler", action="store_true")
    ap.add_argument("--modele")
    a = ap.parse_args()
    v = fond.Verrou("greffier", peremption=1800)
    if not v.prendre():
        journal("greffier", statut="déjà en cours")
        print(json.dumps({"deja_en_cours": True}))
        return
    try:
        fond.basse_priorite()
        print(json.dumps(lancer(a.max, a.simuler, a.modele), ensure_ascii=False, default=str))
    finally:
        v.rendre()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        journal("erreurs-fond", job="greffier", erreur=repr(e))
        print(json.dumps({"erreur": repr(e)}))
