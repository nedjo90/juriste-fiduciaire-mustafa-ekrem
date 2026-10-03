#!/usr/bin/env python3
"""Portes déterministes (§7.5) — scripts, jamais des avis d'agent, jamais bloquantes.
Usage : python portes.py <fichier> [--type memo] [--langue fr] [--role redacteur] [--skill production-livrables]
                         [--corriger] [--pdf rendu.pdf] [--portes liens,sources,...] [--sans-enregistrer]
                         [--livrable LIV-…] [--tour N]
Sortie JSON : {fichier, ok, portes: {porte: {etat: ok|ko|na, details, corrections}}, reserves, a_renvoyer}
--corriger (markdown) : écrit <fichier>.corrige.md avec ⚠ insérés et typographie corrigée.
Code de sortie toujours 0 : une porte KO renvoie la correction au rôle ; à défaut le livrable sort avec réserves."""
import sys, json, time, argparse
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "producteur"))
import commun as C
from commun_portes import charger
import p_liens, p_sources, p_typo, p_tics, p_jargon, p_presentation, p_couverture, p_visuel, p_budget, p_sommaires, p_contexte, p_panel

PORTES = {"liens": p_liens, "sources": p_sources, "typographie": p_typo, "tics": p_tics, "regle_zero": p_jargon,
          "presentation": p_presentation, "couverture": p_couverture, "visuel": p_visuel, "budget": p_budget,
          "sommaires": p_sommaires, "contexte": p_contexte, "panel": p_panel}
RESPONSABLE = {"liens": "archiviste", "sources": "documentaliste", "typographie": "relecteur", "tics": "editeur-humain",
               "regle_zero": "associe", "presentation": "directeur-artistique", "couverture": "chef-de-cabinet",
               "visuel": "directeur-artistique", "budget": "redacteur",
               "sommaires": "archiviste", "contexte": "chef-de-cabinet", "panel": "producteur"}
TEXTE_SEUL = {"md", "txt", "eml"}


def executer(chemin, type_=None, langue=None, role=None, skill=None, pdf=None, portes=None, enregistrer=True, meta=None, cle=None, contexte=None):
    t0 = time.time()
    doc = charger(chemin, dict(meta or {}, type=type_, langue=langue))
    if type_:
        doc["type"] = type_
    if langue:
        doc["langue"] = langue
    ctx = {"pdf": pdf, **(contexte or {})}
    doc["ctx"] = ctx
    noms = portes or list(PORTES)
    if doc["format"] in TEXTE_SEUL:
        noms = [n for n in noms if n != "visuel"]
    # le visuel d'abord : il fournit le nombre de pages à la porte présentation
    ordre = sorted(noms, key=lambda n: 0 if n == "visuel" else 1)
    res = {}
    for n in ordre:
        try:
            res[n] = PORTES[n].verifier(doc, ctx)
        except Exception as e:
            C.journal("erreurs-portes", porte=n, fichier=str(chemin), erreur=repr(e))
            res[n] = {"etat": "na", "details": [f"porte non exécutée ({e.__class__.__name__}) : réserve"], "corrections": [], "reserves": 1}
    res = {n: res[n] for n in noms if n in res}
    ko = [n for n, r in res.items() if r["etat"] == "ko"]
    reserves = []
    for n, r in res.items():
        if r["etat"] == "ko":
            reserves.append(f"{n} : " + "; ".join(r["details"][:2]))
        elif r.get("reserves"):
            reserves.append(f"{n} : " + "; ".join(r["details"][:1]))
    out = {"fichier": str(chemin), "type": doc.get("type"), "langue": doc.get("langue"), "ok": not ko,
           "portes": res, "a_renvoyer": {n: RESPONSABLE[n] for n in ko}, "reserves": reserves,
           "pages": ctx.get("pages"), "duree_ms": int((time.time() - t0) * 1000)}
    if enregistrer:
        cle = cle or C.slug(Path(chemin).stem.split("-v")[0] if "-v" in Path(chemin).stem else Path(chemin).stem, 80)
        out["enregistre"] = __import__("tableau").enregistrer(chemin, cle, role, skill, out)
    C.journal("portes", fichier=str(chemin), ok=out["ok"], ko=ko, duree_ms=out["duree_ms"])
    return out


def corriger_markdown(raw, langue="fr"):
    """corrections automatiques sûres : ⚠ sur le droit non sourcé, puis typographie de la langue"""
    t1, n_src = p_sources.corriger_md(raw)
    t2, typo = p_typo.corriger_md(t1, langue)
    return t2, {"sources_marquees": n_src, "typographie": len(typo)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("fichier")
    ap.add_argument("--type"); ap.add_argument("--langue"); ap.add_argument("--role"); ap.add_argument("--skill")
    ap.add_argument("--pdf"); ap.add_argument("--portes"); ap.add_argument("--corriger", action="store_true")
    ap.add_argument("--sans-enregistrer", action="store_true")
    ap.add_argument("--livrable"); ap.add_argument("--tour")
    a = ap.parse_args(argv)
    try:
        ctxe = {k: v for k, v in (("livrable", a.livrable), ("tour", a.tour)) if v}
        out = executer(a.fichier, a.type, a.langue, a.role, a.skill, a.pdf, a.portes.split(",") if a.portes else None, not a.sans_enregistrer, contexte=ctxe)
        if a.corriger and Path(a.fichier).suffix.lower() in (".md", ".markdown"):
            raw = Path(a.fichier).read_text(encoding="utf-8")
            nv, stats = corriger_markdown(raw, out.get("langue") or "fr")
            dest = Path(a.fichier).with_suffix(".corrige.md")
            dest.write_text(nv, encoding="utf-8")
            out["corrige"] = {"fichier": str(dest), **stats}
    except Exception as e:  # jamais bloquant
        C.journal("erreurs-portes", fichier=a.fichier, erreur=repr(e))
        out = {"fichier": a.fichier, "ok": False, "portes": {}, "reserves": [f"portes non exécutées : {e!r}"], "a_renvoyer": {}}
    print(json.dumps(out, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
