#!/usr/bin/env python3
"""Dispatcher unique des hooks Claude Code (constitution §5, §11 ; jamais bloquant).
Usage (settings.json, forme exec) : python .claude/hooks/hook.py <SessionStart|UserPromptSubmit|Stop|PreCompact|SessionEnd|PostToolUse>
Garanties : sortie immédiate si CEREBRO_BACKGROUND ; try global ; toute erreur → journal + succès vide ;
garde-fou de durée (1,7 s) ; aucune sortie de blocage, de refus ni de décision de permission."""
import os, sys

if os.environ.get("CEREBRO_BACKGROUND"):  # anti-récursion : rôles et tâches de fond
    sys.exit(0)

import json, re, time, threading, unicodedata
from pathlib import Path

T0 = time.time()
# délai interne par événement (Claude Code accorde 10 s) : le brief de démarrage vaut d'attendre un peu sur un poste lent
LIMITE = float(os.environ.get("CEREBRO_HOOK_LIMITE") or {"SessionStart": 8.0, "UserPromptSubmit": 4.0}.get(sys.argv[1] if len(sys.argv) > 1 else "", 1.7))
os.environ.setdefault("CEREBRO_BUSY_MS", "1500")  # un hook n'attend jamais longtemps un verrou tenu par l'entretien
ICI = Path(__file__).resolve().parent              # <racine>/.claude/hooks
RACINE = ICI.parents[1]
ENTRETIEN = RACINE / ".equipe" / "scripts" / "entretien"
try:
    sys.path.insert(0, str(ENTRETIEN))
    import fond  # noqa: E402
    from fond import RUN, INBOX, SESSION, journal  # noqa: E402
except BaseException as _e:  # socle illisible : on journalise à la main et on sort en succès plus bas
    fond = None
    RUN = INBOX = SESSION = ICI

    def journal(nom, **rec):
        try:
            d = RACINE / ".equipe" / "cerveau" / "journal"
            d.mkdir(parents=True, exist_ok=True)
            with open(d / f"{nom}.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"le": time.strftime("%Y-%m-%dT%H:%M:%S"), **rec}, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass
    journal("hooks-erreurs", evenement=(sys.argv[1:] or [""])[0], erreur="socle fond.py illisible: " + repr(_e)[:300])

DEBUT_MAX, TOUR_MAX = 8000, 6000
CACHE_DEBUT = Path(__file__).resolve().parents[2] / ".equipe" / "run" / "contexte-debut.txt"
GREFFIER_TOUS_LES = 15
CONTROLE = bool(os.environ.get("CEREBRO_CONTROLE"))  # session de contrôle : rien d'écrit dans inbox, aucun job de fond


def _garde_fou():
    """délai dépassé : au démarrage, on sert le dernier brief calculé (jamais une session sans contexte) ; sinon sortie vide"""
    journal("hooks", evenement=EVT, statut="délai dépassé", ms=int((time.time() - T0) * 1000))
    try:
        if EVT == "SessionStart" and CACHE_DEBUT.exists():
            ctx = CACHE_DEBUT.read_text(encoding="utf-8")
            sys.stdout.buffer.write(json.dumps(sortie_contexte("SessionStart", ctx, DEBUT_MAX), ensure_ascii=False).encode("utf-8"))
        sys.stdout.flush()
    except Exception:
        pass
    os._exit(0)


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower())


def sid(data):
    return re.sub(r"[^A-Za-z0-9_-]", "", str(data.get("session_id") or "session"))[:64] or "session"


def tour_path(data):
    return RUN / f"tour-{sid(data)}.json"


def sortie_contexte(evenement, texte, maxi):
    texte = (texte or "").strip()
    if not texte:
        return None
    return {"hookSpecificOutput": {"hookEventName": evenement, "additionalContext": texte[:maxi]}}


# ------------------------------------------------------------------ événements
def session_start(data):
    from cb import brief as B
    src = data.get("source") or "startup"
    try:
        (RUN / "mustafa-ecrit").unlink()
    except Exception:
        pass
    ctx = B.session_start(src)
    try:
        CACHE_DEBUT.write_text(ctx, encoding="utf-8")
    except Exception:
        pass
    if src != "compact":
        fond.lancer_detache(ENTRETIEN / "cycle.py", "--rattrapage", nom="cycle-rattrapage")
    return sortie_contexte("SessionStart", ctx, DEBUT_MAX)


def user_prompt_submit(data):
    from cb import brief as B
    prompt = data.get("prompt") or ""
    ctx = B.context(prompt) or ""
    entre_nous = ctx.startswith("MODE « ENTRE NOUS »")
    if not CONTROLE:
        RUN.mkdir(parents=True, exist_ok=True)
        fond.ecrire_json(tour_path(data), {"entre_nous": entre_nous, "prompt": "" if entre_nous else prompt, "le": fond.stamp()})
        (RUN / "mustafa-ecrit").write_text(fond.stamp(), encoding="utf-8")  # pause du cycle d'entretien
    return sortie_contexte("UserPromptSubmit", ctx, TOUR_MAX)


def _dernier_message_transcript(chemin):
    """repli si last_assistant_message est absent : texte du dernier message assistant du transcript (lecture de la fin)"""
    try:
        p = Path(chemin)
        with open(p, "rb") as fh:
            fh.seek(0, 2)
            n = fh.tell()
            fh.seek(max(0, n - 400_000))
            lignes = fh.read().decode("utf-8", "ignore").splitlines()
        for l in reversed(lignes):
            try:
                d = json.loads(l)
            except Exception:
                continue
            if d.get("type") == "assistant":
                c = (d.get("message") or {}).get("content")
                if isinstance(c, str):
                    return c
                txt = [b.get("text", "") for b in (c or []) if isinstance(b, dict) and b.get("type") == "text"]
                if any(txt):
                    return "\n".join(txt)
    except Exception:
        pass
    return ""


_VOC = None


def vocabulaire():
    global _VOC
    if _VOC is None:
        mots, rx = [], []
        try:
            for l in (ICI / "vocabulaire-technique.txt").read_text(encoding="utf-8").splitlines():
                l = l.strip()
                if not l or l.startswith("#"):
                    continue
                if l.startswith("re:"):
                    rx.append(re.compile(l[3:].strip(), re.I | re.M))
                else:
                    mots.append(fold(l))
        except Exception:
            pass
        _VOC = (re.compile(r"(?<![\w-])(" + "|".join(re.escape(m) for m in sorted(mots, key=len, reverse=True)) + r")(?![\w-])") if mots else None, rx)
    return _VOC


def termes_techniques(texte):
    mots, rx = vocabulaire()
    f = fold(texte)
    trouves = set(m.group(1) for m in mots.finditer(f)) if mots else set()
    for r in rx:
        m = r.search(texte)
        if m:
            trouves.add(m.group(0).strip()[:40])
    return sorted(trouves)


TECHNICIEN = re.compile(r"\b(je suis (informaticien|technicien|developpeur|admin\w*)|en tant que (technicien|informaticien|developpeur)|"
                        r"stack ?trace|traceback|stderr|stdout|regex|localhost|sudo|pip install|npm|git (push|pull|commit|status|log)|"
                        r"settings\.json|claude\.md|\.equipe)\b")


def interlocuteur_technicien(prompt):
    """heuristique : présentation explicite, code, commandes, ou au moins trois termes de mécanique dans le message"""
    f = fold(prompt)
    if TECHNICIEN.search(f) or "```" in prompt or re.search(r"(^|\s)--[a-z]", prompt):
        return True
    return len(termes_techniques(prompt)) >= 3


def stop(data):
    try:
        (RUN / "mustafa-ecrit").unlink()
    except Exception:
        pass
    tp = tour_path(data)
    tour = fond.lire_json(tp, {}) or {}
    try:
        tp.unlink()
    except Exception:
        pass
    if tour.get("entre_nous") or CONTROLE:
        return None  # « entre nous » : aucune trace
    prompt = tour.get("prompt") or ""
    reponse = data.get("last_assistant_message") or ""
    if not reponse and data.get("transcript_path"):
        reponse = _dernier_message_transcript(data["transcript_path"])
    if not prompt and not reponse:
        return None
    from cb import core
    INBOX.mkdir(parents=True, exist_ok=True)
    rec = {"le": core.stamp(), "session": sid(data), "prompt": prompt, "reponse": reponse}
    with open(INBOX / f"{core.iso()}.jsonl", "a", encoding="utf-8") as fh:  # ajout seul
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    # filtre de vocabulaire technique : journalise seulement, ne bloque ni ne réécrit (§4.1 (4))
    if reponse and not interlocuteur_technicien(prompt):
        t = termes_techniques(reponse)
        if t:
            journal("vocabulaire", session=sid(data), termes=t, nb=len(t))
    # greffier groupé tous les 15 échanges (verrou dans le greffier)
    cp = RUN / "compteur-echanges.json"
    c = (fond.lire_json(cp, {}) or {}).get("n", 0) + 1
    if c >= GREFFIER_TOUS_LES:
        fond.lancer_detache(ENTRETIEN / "greffier.py", nom="greffier")
        c = 0
    fond.ecrire_json(cp, {"n": c})
    fond.lancer_detache(ENTRETIEN / "cycle.py", "--increment", nom="cycle-increment")  # temps mort : un incrément (sort si file vide)
    return None


def pre_compact(data):
    """snapshot compact de l'état de session (≤ 1 200 car. relus au démarrage suivant)"""
    from cb import core
    L = [f"# État de session (snapshot avant compaction) · {core.stamp()}", f"session: {sid(data)} · déclencheur: {data.get('trigger') or '-'}"]
    try:
        inj = core.get_etat("injectes", {}) or {}
        if inj:
            L.append("objets en cours: " + ", ".join(list(inj)[-12:]))
        L.append(f"tour: {core.get_etat('tour', 0)}")
    except Exception:
        pass
    p = INBOX / f"{core.iso()}.jsonl"
    if p.exists():
        rec = []
        for l in p.read_text(encoding="utf-8").splitlines()[-40:]:
            try:
                d = json.loads(l)
            except Exception:
                continue
            if d.get("session") == sid(data):
                rec.append(d)
        if rec:
            L.append("derniers échanges:")
            for d in rec[-5:]:
                L.append(f"- M: {core.cut(d.get('prompt'), 140)} → R: {core.cut(d.get('reponse'), 100)}")
    ci = (data.get("custom_instructions") or "").strip()
    if ci:
        L.append(f"consigne de compaction: {core.cut(ci, 200)}")
    SESSION.mkdir(parents=True, exist_ok=True)
    if not CONTROLE:
        (SESSION / "etat.md").write_text("\n".join(L)[:1200] + "\n", encoding="utf-8")
    return None


def session_end(data):
    fond.lancer_detache(ENTRETIEN / "fin_session.py", nom="fin-de-session")
    return None


ID_LIGNE = re.compile(r"^id:\s*([A-Z]+-\d{3,5})\s*$", re.M)


LECTURE_LARGE = re.compile(r"(^|[;&|]\s*)(cat|head|tail|sed|less|more|type)\b[^|;&]*(\.equipe|\.claude)[/\\]", re.I)

def _lecture_hors_cli(data):
    """protocole sommaire (§0 ter) : une lecture entière ou un listing de la mémoire hors cerebro est journalisé (jamais bloqué) ;
    l'archiviste en tire la conformité par rôle et la fabrique révise le rôle en écart"""
    outil, ti = data.get("tool_name"), data.get("tool_input") or {}
    quoi = None
    if outil == "Read":
        f = str(ti.get("file_path") or "")
        if re.search(r"[/\\]\.(equipe|claude)[/\\]", f) and not (ti.get("offset") or ti.get("limit")) and not re.search(r"(SKILL\.md|SOMMAIRE\.md|sommaires[/\\])", f):
            quoi = f
    elif outil == "Bash":
        c = str(ti.get("command") or "")
        if "cerebro" not in c and LECTURE_LARGE.search(c):
            quoi = c[:200]
    if quoi:
        journal("lectures-hors-cli", outil=outil, quoi=quoi[-200:], session=sid(data))
        try:
            from cb import core
            con = core.db()
            con.execute("INSERT INTO ouvertures(le,tour,id,section,acteur) VALUES(datetime('now'),?,?,?,?)", (str(core.get_etat("tour", "0")), "hors-cli", quoi[-120:], "hors-cli"))
            con.commit()
        except Exception:
            pass

def post_tool_use(data):
    if data.get("tool_name") in ("Read", "Bash"):
        _lecture_hors_cli(data)
        return None
    ti = data.get("tool_input") or {}
    chemin = ti.get("file_path") or ti.get("notebook_path") or ti.get("path")
    if not chemin:
        return None
    p = Path(chemin)
    if not p.is_absolute():
        p = Path(data.get("cwd") or fond.ROOT) / p
    if p.suffix.lower() not in (".md", ".markdown", ".txt") or not p.exists():
        return None
    with open(p, "r", encoding="utf-8", errors="ignore") as fh:
        tete = fh.read(4000)
    if not tete.startswith("---"):
        return None
    fin = tete.find("\n---", 3)
    m = ID_LIGNE.search(tete[: fin if fin > 0 else len(tete)])
    if not m:
        return None
    from cb import core
    con = core.db()
    con.execute("UPDATE objets SET a_regenerer=1 WHERE id=?", (m.group(1),))
    con.commit()
    return None


def observer(data):
    """version « journalise seulement » d'un mécanisme retiré par l'intendant (ex-PreToolUse/PermissionRequest) : jamais de décision"""
    journal("observation", evenement=data.get("hook_event_name"), outil=data.get("tool_name"))
    return None


EVENEMENTS = {"Observer": observer, "SessionStart": session_start, "UserPromptSubmit": user_prompt_submit, "Stop": stop,
              "PreCompact": pre_compact, "SessionEnd": session_end, "PostToolUse": post_tool_use}
EVT = sys.argv[1] if len(sys.argv) > 1 else ""


def main():
    minuteur = threading.Timer(LIMITE, _garde_fou)
    minuteur.daemon = True
    minuteur.start()
    raw = "" if sys.stdin is None or sys.stdin.isatty() else sys.stdin.buffer.read().decode("utf-8", "ignore")
    data = json.loads(raw) if raw.strip() else {}
    if os.environ.get("CEREBRO_HOOK_TEST_ERREUR"):  # test : erreur interne simulée (critère 39)
        raise RuntimeError("erreur interne simulée")
    f = EVENEMENTS.get(EVT or data.get("hook_event_name", ""))
    if not f or fond is None:
        journal("hooks-erreurs", evenement=EVT, erreur="événement inconnu" if not f else "socle absent")
        return None
    if CONTROLE:  # session de contrôle (valider_config) : preuve que le hook a tourné
        journal("controle", jeton=os.environ.get("CEREBRO_CONTROLE"), evenement=EVT)
    fond.cb()
    return f(data)


if __name__ == "__main__":
    res = None
    try:
        res = main()
    except BaseException as e:  # try global : erreur journalisée, succès vide
        if not isinstance(e, SystemExit):
            import traceback
            journal("hooks-erreurs", evenement=EVT, erreur=repr(e)[:500], trace=traceback.format_exc()[-1500:])
        res = None
    try:
        if res:
            out = json.dumps(res, ensure_ascii=False)
            sys.stdout.buffer.write(out.encode("utf-8"))
            sys.stdout.flush()
        journal("hooks", evenement=EVT, ms=int((time.time() - T0) * 1000)) if os.environ.get("CEREBRO_HOOK_TRACE") else None
    except BaseException:
        pass
    os._exit(0)
