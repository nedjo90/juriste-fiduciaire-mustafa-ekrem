#!/usr/bin/env python3
"""Exécution des routines posées par Mustafa (objets `routine`, cerebro routine add). Script d'abord (loi 3) :
une recette par besoin courant (délais, rendez-vous, engagements, revues LBA, brouillons, brief) ; sinon une mission de
fond sur le modèle intermédiaire (.equipe/scripts/entretien/taches/_mission.py). Chaque exécution produit un objet
`document` lié à la routine et une ligne au brief (état `routines_du_jour`).
Usage : recettes.py [--due] [--routine ROUT-001] [--simuler]"""
import os, sys, re, json, argparse, datetime as dt
from pathlib import Path

ROOT = Path(os.environ.get("CEREBRO_ROOT") or Path(__file__).resolve().parents[3])
EQ = ROOT / ".equipe"
sys.path.insert(0, str(EQ / "cerebro"))
sys.path.insert(0, str(EQ / "scripts" / "entretien"))
sys.path.insert(0, str(EQ / "scripts" / "entretien" / "taches"))
os.environ.setdefault("CEREBRO_ROOT", str(ROOT))
from cb import core, horloges as H, routines as RT  # noqa: E402
from cb.core import db, iso, today, cut, fold, journal  # noqa: E402
from cb.objets import create, get  # noqa: E402

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def date_fr(d):
    d = dt.date.fromisoformat(d) if isinstance(d, str) else d
    return f"{JOURS[d.weekday()]} {d.day}{'er' if d.day == 1 else ''} {MOIS[d.month - 1]} {d.year}"


def nom_client(cid):
    o = get(cid) if cid else None
    return o["nom"] if o else ""


def horizon(texte, defaut=7):
    f = fold(texte)
    m = re.search(r"(\d+)\s*(?:[a-z]+\s+)?(jours|j\b|days|tage|giorni)", f)
    if m:
        return min(120, int(m.group(1)))
    if re.search(r"deux semaines|quinzaine|2 semaines", f):
        return 14
    if re.search(r"\bmois\b|month|monat", f):
        return 30
    return defaut


# ------------------------------------------------------------------ recettes (script)
def r_delais(o, texte):
    j = horizon(texte)
    dls = H.deadlines(j, client=o.get("client"))
    fin = today() + dt.timedelta(days=j)
    titre = f"Délais du {date_fr(today())} au {date_fr(fin)}"
    L = [f"# {titre}", "", f"## Liste ({len(dls)})"]
    if dls:
        L += ["| Échéance | Dans | Délai | Client | Document prêt |", "|---|---|---|---|---|"]
        for d in dls:
            dans = "dépassé" if d["jours"] < 0 else ("aujourd'hui" if d["jours"] == 0 else f"{d['jours']} j")
            L.append(f"| {date_fr(d['echeance'])} | {dans} | {cut(d['nom'], 70)}{(' ' + d['reserve']) if d['reserve'] else ''} | "
                     f"{cut(nom_client(d['client']), 40)} | {d['document_statut'] or '—'} |")
    else:
        L.append("Aucun délai ouvert sur la période.")
    L += ["", "## Sources", "Délais enregistrés (cerebro deadlines) : " + (", ".join(d["id"] for d in dls) or "aucun") + "."]
    return titre, "\n".join(L) + "\n", [d["id"] for d in dls] + [d["document"] for d in dls if d.get("document")]


def r_rdv(o, texte):
    j = horizon(texte)
    lim = (today() + dt.timedelta(days=j)).isoformat()
    rows = [dict(r) for r in db().execute("SELECT * FROM objets WHERE type='rdv' AND statut!='archive' AND prochaine_date BETWEEN ? AND ? "
                                          "ORDER BY prochaine_date", (iso(), lim))]
    titre = f"Rendez-vous du {date_fr(today())} au {date_fr(lim)}"
    L = [f"# {titre}", "", f"## Liste ({len(rows)})"] + ([f"- {date_fr(r['prochaine_date'])} : {cut(r['nom'], 90)} (fiche : {r['statut']})" for r in rows]
                                                         or ["Aucun rendez-vous enregistré sur la période."])
    return titre, "\n".join(L) + "\n", [r["id"] for r in rows]


def r_engagements(o, texte):
    j = horizon(texte, 14)
    rows = H.commitments_due(j)
    titre = f"Engagements dus d'ici au {date_fr(today() + dt.timedelta(days=j))}"
    L = [f"# {titre}", "", f"## Liste ({len(rows)})"] + ([f"- {date_fr(r['du_le'])} : {cut(r['nom'], 90)} (envers {r['envers']})" for r in rows]
                                                         or ["Aucun engagement dû sur la période."])
    return titre, "\n".join(L) + "\n", [r["id"] for r in rows]


def r_lba(o, texte):
    rows = H.lba_review_due(horizon(texte, 30))
    titre = f"Revues LBA à faire (état au {date_fr(today())})"
    L = [f"# {titre}", "", f"## Liste ({len(rows)})"] + ([f"- {r['prochaine_revue'] or 'non datée'} : {cut(r['nom'], 90)}" for r in rows]
                                                         or ["Aucune revue LBA due."])
    return titre, "\n".join(L) + "\n", [r["id"] for r in rows]


def r_brouillons(o, texte):
    rows = [dict(r) for r in db().execute("SELECT * FROM objets WHERE type IN ('mail','document') AND statut IN ('brouillon prêt','à relire','brouillon à relire') "
                                          "ORDER BY prochaine_date LIMIT 30")]
    titre = f"Brouillons prêts à relire ({date_fr(today())})"
    L = [f"# {titre}", "", f"## Liste ({len(rows)})"] + ([f"- {cut(r['nom'], 100)} ({cut(nom_client(r['client']), 40)})" for r in rows]
                                                         or ["Aucun brouillon en attente."])
    return titre, "\n".join(L) + "\n", [r["id"] for r in rows]


def r_brief(o, texte):
    from cb import brief as B
    titre = f"Point du {date_fr(today())}"
    return titre, f"# {titre}\n\n## Brief\n{B.brief()}\n", []


RECETTES = [  # (nom, motif sur la mission et l'énoncé, fonction) — premier qui correspond
    ("delais", r"\b(delais?|echeances?|fristen?|scadenze?|deadlines?)\b", r_delais),
    ("rdv", r"\b(rendez-vous|rdv|agenda|termine?|appuntament\w*|meetings?)\b", r_rdv),
    ("engagements", r"\bengagements?\b", r_engagements),
    ("lba", r"\b(lba|blanchiment|gwg|aml)\b", r_lba),
    ("brouillons", r"\bbrouillons?\b", r_brouillons),
    ("brief", r"\b(brief|point du jour|ou en est)\b", r_brief),
]


def recette(o):
    d = o["data"] or {}
    if d.get("script"):
        for nom, _, f in RECETTES:
            if nom == d["script"]:
                return nom, f
    texte = fold(f"{d.get('mission') or ''} {d.get('enonce') or o['nom']}")
    for nom, motif, f in RECETTES:
        if re.search(motif, texte):
            return nom, f
    return None, None


# ------------------------------------------------------------------ exécution
def _brief_ligne(o, doc_id, titre):
    e = core.get_etat("routines_du_jour", {}) or {}
    if e.get("le") != iso():
        e = {"le": iso(), "lignes": []}
    l = f"{cut(o['data'].get('enonce') or o['nom'], 70)} → {cut(titre, 70)} [{doc_id}]"
    if l not in e["lignes"]:
        e["lignes"].append(l)
    core.set_etat("routines_du_jour", e)


def executer(o, simuler=False):
    """exécute une routine maintenant ; renvoie {routine, document, voie} ou {_partiel: True} si l'appel attend le budget"""
    d = o["data"] or {}
    texte = f"{d.get('mission') or ''} {d.get('enonce') or o['nom']}"
    nom, f = recette(o)
    if f:
        titre, corps, ids = f(o, texte)
        if simuler:
            return {"routine": o["id"], "voie": f"script:{nom}", "titre": titre, "simule": True}
        doc = create("document", titre, body=corps, client=o.get("client"), statut="prêt", prochaine_action="présenter à Mustafa",
                     prochaine_date=iso(), resume=cut(f"Routine {o['id']} ({d.get('cadence')}) : {titre}", 280),
                     source=f"routine {o['id']} (script {nom}) · cerebro", liens=[(o["id"], "routine")] + [i for i in ids if i and get(i)][:30],
                     mots_cles="routine " + nom, acteur="routine")
        voie = f"script:{nom}"
    else:
        import _mission as MI
        cli = "python .equipe/cerebro/cerebro.py" if os.name == "nt" else ".equipe/bin/cerebro"
        mission = (f"Routine {o['id']} posée par Mustafa : « {d.get('enonce') or o['nom']} ».\nÀ produire aujourd'hui : {d.get('mission')}.\n"
                   + (f"Client : {o['client']}.\n" if o.get("client") else "")
                   + "Données : uniquement par la CLI (find → summary → open --section, deadlines, brief) ; aucune affirmation de droit sans source "
                   "datée (sinon ⚠). Rédige en français soigné, ton de collègue, sans mot de mécanique ni identifiant (destiné à Mustafa). "
                   f"Enregistre : {cli} new document \"<titre>\" --corps-fichier <fichier.md> --lien {o['id']}"
                   + (f" --client {o['client']}" if o.get("client") else "")
                   + f" --statut prêt --prochaine-action \"présenter à Mustafa\" --date {iso()} . Dernière ligne : {{\"document\": \"DOC-…\"}}")
        if simuler:
            return {"routine": o["id"], "voie": "modèle:intermediaire", "simule": True}
        r = MI.lancer(mission, role=None, palier="intermediaire", priorite=2, nom="routine", tache=o["id"])
        if not r.get("ok"):
            journal("routines", id=o["id"], statut="différée", raison=r.get("saute") or r.get("erreur"))
            return {"routine": o["id"], "_partiel": True, "attente": r.get("saute") or r.get("erreur")}
        doc = (r.get("json") or {}).get("document")
        titre = get(doc)["nom"] if doc and get(doc) else f"{cut(d.get('mission') or o['nom'], 60)} — {iso()}"
        if not doc or not get(doc):
            doc = create("document", titre, body=f"# {titre}\n\n## Contenu\n{r.get('resultat') or ''}\n", client=o.get("client"), statut="prêt",
                         prochaine_action="présenter à Mustafa", prochaine_date=iso(), source=f"routine {o['id']} (modèle {r.get('modele')})",
                         liens=[(o["id"], "routine")], acteur="routine")
        voie = f"modèle:{r.get('modele')}"
    RT.routine_marquer(o["id"], doc)
    _brief_ligne(o, doc, titre)
    journal("routines", id=o["id"], statut="faite", document=doc, voie=voie)
    return {"routine": o["id"], "document": doc, "voie": voie, "titre": titre}


def executer_dues(simuler=False):
    out = []
    for r in RT.routine_due():
        o = get(r["id"])
        try:
            out.append(executer(o, simuler))
        except Exception as e:
            journal("erreurs-fond", job="routines", id=r["id"], erreur=repr(e)[:300])
            out.append({"routine": r["id"], "echec": repr(e)[:200]})
    return out


def main():
    core.utf8_io()
    ap = argparse.ArgumentParser()
    ap.add_argument("--routine")
    ap.add_argument("--due", action="store_true")
    ap.add_argument("--simuler", action="store_true")
    a = ap.parse_args()
    if a.routine:
        o = get(a.routine)
        print(json.dumps(executer(o, a.simuler) if o else {"erreur": "inconnue"}, ensure_ascii=False))
    else:
        print(json.dumps(executer_dues(a.simuler), ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        journal("erreurs-fond", job="recettes", erreur=repr(e)[:300])
        print(json.dumps({"erreur": repr(e)[:300]}))
