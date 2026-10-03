#!/usr/bin/env python3
"""Producteur (§6.3, §7.1) : markdown structuré → livrable au format final, depuis les gabarits de la maison.
Usage : python produire.py <source.md> [--role redacteur] [--skill production-livrables] [--sans-ouvrir] [--sans-pdf] [--sans-inscrire]
                           [--sans-panel | --panel]
Front matter : type (memo|avis|note|lettre|pv|convention|contrat|calcul|presentation|rapport|mail), client (C-001 ou nom), dossier, objet, langue,
  titre, sous_titre, date_etat, confort, sources [BIB-…|référence datée], destinataire, lieu, salutation, formule, pieces…
Étapes : corrections automatiques sûres (⚠ sur le droit non sourcé, typographie) → rendu depuis le gabarit → PDF
(Word/PowerPoint/Excel du poste via office.py, sinon gabarit PDF reportlab) → portes → cerebro deliverable register → ouverture dans l'application par défaut.
Livrables importants (mémo, avis, calcul, présentation, PV, convention, contrat) : orchestration panel.py — un appel
adverse groupé (modèle le plus capable), corrections par le rédacteur (un appel au plus, intermédiaire), relecteur, portes
sommaires / contexte / panel. --sans-panel (ou PRODUCTEUR_SANS_PANEL, CEREBRO_SANS_MODELE) : production seule ; une
source tirée de .equipe/tests/fixtures/ est produite sans panel sauf --panel.
Sortie JSON. Jamais bloquant : une porte KO est renvoyée au rôle et le livrable sort avec ses réserves."""
import sys, re, json, argparse, shutil, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "portes"))
import commun as C
import design as D
import mdparse as MD

FORMATS = {"memo": ["docx", "pdf"], "avis": ["docx", "pdf"], "convention": ["docx", "pdf"], "contrat": ["docx", "pdf"], "note": ["docx", "pdf"], "lettre": ["docx", "pdf"], "pv": ["docx", "pdf"],
           "calcul": ["xlsx"], "presentation": ["pptx", "pdf"], "rapport": ["pdf"], "mail": ["eml", "txt"]}
PORTES_TEXTE = ["liens", "sources", "typographie", "tics", "regle_zero", "couverture", "budget"]
PORTES_SORTIE = ["presentation", "visuel"]
BIB_RE = re.compile(r"\bBIB-\d{3,5}\b")


def resoudre_client(meta):
    c = str(meta.get("client") or "").strip()
    if re.fullmatch(r"C-\d{3,5}", c):
        o = C.objet(c)
        nom = (o or {}).get("nom") or c
        return c, re.sub(r"^\[FICTIF\]\s*", "", nom)
    return None, c or "Divers"


def resoudre_source(ref):
    """BIB-… → {titre, etat, url} depuis la bibliothèque ; texte libre → tel quel"""
    if not BIB_RE.fullmatch(str(ref)):
        return {"titre": str(ref), "etat": "", "url": ""}
    try:
        core, objets, _, _ = C.cb()
        r = core.db().execute("SELECT * FROM bibliotheque WHERE id=?", (ref,)).fetchone()
        if r:
            t = " · ".join(x for x in [r["abreviation"], r["titre"], r["identifiant"] and f"RS {r['identifiant']}" if r["juridiction"] == "CH" else r["identifiant"]] if x)
            return {"titre": t, "etat": f"état au {r['date_etat']}" if r["date_etat"] else (r["version"] or ""), "url": r["url"] or "", "verifie_le": r["ingere_le"] or ""}
        o = objets.get(ref)
        if o:
            return {"titre": o["nom"], "etat": o.get("valide_du") or "", "url": o.get("source") or ""}
    except Exception:
        pass
    return {"titre": f"{ref} ⚠ introuvable dans la bibliothèque", "etat": "", "url": ""}


def numeroter_sources(raw, meta):
    """BIB-… cités → [n] ; annexe des sources construite dans l'ordre d'apparition, puis les sources du front matter"""
    ordre = []
    for m in BIB_RE.finditer(MD.front_matter(raw)[1]):
        if m.group(0) not in ordre:
            ordre.append(m.group(0))
    for s in meta.get("sources") or []:
        if str(s) not in ordre:
            ordre.append(str(s))
    table = []
    for n, ref in enumerate(ordre, 1):
        table.append({"n": n, "ref": ref, **resoudre_source(ref)})
    num = {s["ref"]: s["n"] for s in table}
    tete, corps = raw[: len(raw) - len(MD.front_matter(raw)[1])], MD.front_matter(raw)[1]
    corps = BIB_RE.sub(lambda m: f"[{num[m.group(0)]}]", corps)
    return tete + corps, table


def blocs_speciaux(bl, dossier, base, d, langue):
    """```mermaid → schéma (png/svg/drawio) ; ```graphique → graphique matplotlib ; renvoie (blocs, fichiers annexes)"""
    import yaml
    out, annexes, n_s, n_g = [], [], 0, 0
    fmt = d["legendes"]["format_figure"].get(langue, d["legendes"]["format_figure"]["fr"])
    for b in bl:
        if b["t"] == "code" and b["lang"] == "mermaid":
            n_s += 1
            import schemas
            try:
                r = schemas.rendre(b["texte"], dossier / f"{base}-schema-{n_s}", d)
                annexes += [r["png"], r["svg"], r["drawio"]]
                out.append({"t": "image", "chemin": r["png"], "legende": fmt.format(n=n_s + n_g, titre="Schéma", source="dossier")})
            except Exception as e:
                C.journal("erreurs-producteur", op="schema", erreur=repr(e))
        elif b["t"] == "code" and b["lang"] in ("graphique", "chart", "diagramme"):
            n_g += 1
            import graphiques
            try:
                spec = yaml.safe_load(b["texte"]) or {}
                r = graphiques.rendre(spec, dossier / f"{base}-graphique-{n_g}", d)
                annexes += [r["png"], r["svg"]]
                out.append({"t": "image", "chemin": r["png"], "legende": fmt.format(n=n_s + n_g, titre=r["message"], source=r["source"])})
            except Exception as e:
                C.journal("erreurs-producteur", op="graphique", erreur=repr(e))
        else:
            out.append(b)
    return out, annexes


def version_suivante(dossier, base):
    n = 0
    if dossier.exists():
        for f in dossier.iterdir():
            m = re.fullmatch(re.escape(base) + r"-v(\d+)(?:\..+)?", f.name.split(".")[0] if "." in f.name else f.name)
            m = m or re.match(re.escape(base) + r"-v(\d+)\b", f.name)
            if m:
                n = max(n, int(m.group(1)))
    return n + 1


def pages_des_titres(pdf, titres, debut=2):
    """page de chaque titre dans le PDF (recherche séquentielle à partir de la page `debut`, 1 = page de titre)"""
    from commun_portes import pdf_texte
    pages = pdf_texte(pdf, par_page=True)
    norm = [re.sub(r"\s+", " ", x) for x in pages]
    res, k = {}, max(0, debut - 1)
    for (_, num, t, _) in titres:
        cle = re.sub(r"\s+", " ", t)[:40]
        for i in range(k, len(norm)):
            if cle and cle in norm[i]:
                res[(num, t)] = i + 1; k = i
                break
    return res, len([p for p in pages if p.strip()])


def produire(source, role=None, skill=None, ouvrir=True, pdf=True, inscrire=True, version=None):
    t0 = time.time()
    import portes as P
    raw0 = Path(source).read_text(encoding="utf-8")
    meta0, _ = MD.parse(raw0)
    langue = str(meta0.get("langue") or "fr")[:2]
    typ = str(meta0.get("type") or "memo").lower()
    d = D.charger()
    # 1. corrections automatiques sûres
    raw1, stats_corr = P.corriger_markdown(raw0, langue)
    meta, _ = MD.parse(raw1)
    client_id, client_nom = resoudre_client(meta)
    today = C.today()
    date = str(meta.get("date") or today.isoformat())
    objet = meta.get("objet") or meta.get("titre") or Path(source).stem
    dossier = C.LIVRABLES / C.nom_dossier(client_nom) / f"{date}-{C.slug(objet, 40)}"
    dossier.mkdir(parents=True, exist_ok=True)
    base = f"{C.slug(client_nom, 30)}-{C.slug(objet, 40)}-{date}"
    v = int(version) if version else int(meta.get("version")) if str(meta.get("version", "")).isdigit() else version_suivante(dossier, base)
    stem = f"{base}-v{v}"
    # 2. source corrigée gardée côté machine (pour les portes texte et la traçabilité)
    run_dir = C.EQ / "run" / "producteur"; run_dir.mkdir(parents=True, exist_ok=True)
    md_corr = run_dir / f"{stem}.md"; md_corr.write_text(raw1, encoding="utf-8")
    # 3. sources numérotées, blocs spéciaux
    raw2, sources = numeroter_sources(raw1, meta)
    meta2, blocs = MD.parse(raw2)
    blocs, annexes = blocs_speciaux(blocs, dossier, stem, d, langue)
    m = dict(meta2, langue=langue, type=typ, client_id=client_id, client_nom=client_nom, date=date, version=v, objet=str(objet),
             date_etat=meta2.get("date_etat") or date, liens=[x for x in [meta2.get("dossier")] if x])
    fichiers, principal, pdf_path, reserves = [], None, None, []
    formats = meta2.get("formats") or FORMATS.get(typ, ["docx", "pdf"])
    # 4. rendu
    try:
        if typ in ("memo", "avis", "note", "lettre", "pv", "convention", "contrat"):
            import rendu_docx as R
            principal = dossier / f"{stem}.docx"
            fn = {"memo": R.memo, "avis": R.memo, "note": R.memo, "convention": R.memo, "contrat": R.memo, "lettre": R.lettre, "pv": R.pv}[typ]
            titres = fn(m, blocs, principal, d, sources)
            if pdf and "pdf" in formats:
                pdf_path = C.vers_pdf(principal, dossier)
                lim = (d["livrables"].get(typ) or {}).get("table_des_matieres_au_dela_pages")
                if pdf_path and lim and typ in ("memo", "avis", "note"):
                    tp, npages = pages_des_titres(pdf_path, titres)
                    if npages > lim:  # table des matières au-delà de dix pages : deux passes pour des numéros exacts
                        n_toc = 1 + len(titres) // 32
                        tp = {k: v + n_toc for k, v in tp.items()}
                        R.memo(m, blocs, principal, d, sources, titres_pages=tp)
                        pdf_path = C.vers_pdf(principal, dossier)
                        tp2, _ = pages_des_titres(pdf_path, titres, debut=2 + n_toc)
                        if tp2 and tp2 != tp:
                            R.memo(m, blocs, principal, d, sources, titres_pages=tp2)
                            pdf_path = C.vers_pdf(principal, dossier)
        elif typ == "calcul":
            import rendu_tableur as RT
            principal = dossier / f"{stem}.xlsx"
            RT.rendre(m, principal, sources)
            if pdf and "pdf" in formats:
                pdf_path = C.vers_pdf(principal, dossier)
        elif typ == "presentation":
            import rendu_pptx as RP
            principal = dossier / f"{stem}.pptx"
            RP.rendre(m, blocs, principal, d)
            if pdf and "pdf" in formats:
                pdf_path = C.vers_pdf(principal, dossier)
        elif typ == "mail":
            import mail as ML
            pieces = [Path(p) if Path(p).is_absolute() else C.ROOT / p for p in (m.get("pieces") or [])]
            eml, txt = ML.rendre(m, blocs, dossier / stem, d, pieces)
            principal = eml; fichiers.append(txt)
        else:  # rapport : gabarit PDF de la maison
            pdf = True
    except Exception as e:
        C.journal("erreurs-producteur", op="rendu", source=str(source), erreur=repr(e))
        reserves.append(f"rendu {typ} incomplet ({e.__class__.__name__}) : repli PDF de la maison")
        principal = None
    if (typ == "rapport" or principal is None or (pdf and "pdf" in formats and typ not in ("calcul", "mail") and not pdf_path)):
        try:  # repli reportlab : Office absent (Linux, poste sans Word) ou rendu impossible
            import rendu_pdf
            pdf_path = dossier / f"{stem}.pdf"
            m["_pied"] = re.sub(r"\s+", " ", __import__("rendu_docx").marqueurs(d, m)["pied"])
            m["date_affichee"] = C.date_longue(date, langue); m["date_etat_affichee"] = C.date_longue(m["date_etat"], langue)
            bl_pdf = blocs + ([{"t": "h", "niveau": 1, "texte": "Annexe — Sources", "sans_numero": True},
                               {"t": "table", "entete": ["Réf.", "Source", "Version / état", "Lien"], "lignes": [[f"[{s['n']}]", s["titre"], s["etat"], s["url"]] for s in sources]}] if sources else [])
            rendu_pdf.rendre(pdf_path, d, m, bl_pdf)
            if principal is None:
                principal = pdf_path
            if typ != "rapport" and office_absent(principal):
                reserves.append("PDF produit par le gabarit PDF de la maison (Word/PowerPoint indisponibles ici) ; contrôle visuel limité à l'analyse du fichier")
        except Exception as e:
            C.journal("erreurs-producteur", op="pdf", erreur=repr(e))
            reserves.append("PDF non produit")
    fichiers = [principal] + ([pdf_path] if pdf_path and pdf_path != principal else []) + fichiers + [Path(a) for a in annexes]
    # 5. portes : texte sur la source corrigée (le mail : sur le brouillon), présentation et visuel sur le fichier final
    portes = {}
    cle = C.slug(base, 80)
    texte_src = principal if typ == "mail" else md_corr
    r1 = P.executer(texte_src, typ, langue, role, skill, portes=PORTES_TEXTE, enregistrer=False, meta={"client": client_id, "dossier": meta2.get("dossier")})
    r2 = P.executer(principal, typ, langue, role, skill, pdf=str(pdf_path) if pdf_path else None, portes=PORTES_SORTIE, enregistrer=False) if principal else {"portes": {}, "reserves": []}
    portes.update(r1["portes"]); portes.update(r2["portes"])
    res_portes = {"portes": portes, "duree_ms": r1.get("duree_ms", 0) + r2.get("duree_ms", 0)}
    import tableau
    tableau.enregistrer(principal, cle, role, skill, res_portes)
    ko = {n: P.RESPONSABLE[n] for n, r in portes.items() if r["etat"] == "ko"}
    reserves += r1.get("reserves", []) + r2.get("reserves", [])
    # 6. inscription cerebro
    lid = None
    if inscrire and principal:
        try:
            _, objets, _, files = C.cb()
            lid = files.deliverable_register(objets.relpath(principal), client_id, meta2.get("dossier"), typ,
                                             {n: r["etat"] for n, r in portes.items()}, " | ".join(reserves)[:900])
        except Exception as e:
            C.journal("erreurs-producteur", op="deliverable_register", erreur=repr(e))
            reserves.append("livrable non inscrit (cerebro indisponible)")
    ouvert = C.ouvrir(principal) if (ouvrir and principal) else False
    out = {"livrable": lid, "principal": str(principal) if principal else None, "pdf": str(pdf_path) if pdf_path else None,
           "fichiers": [str(f) for f in fichiers if f], "version": v, "corrections_automatiques": stats_corr,
           "portes": {n: r["etat"] for n, r in portes.items()}, "a_renvoyer": ko,
           "corrections": {n: portes[n]["corrections"][:8] for n in ko}, "reserves": reserves, "ouvert": ouvert,
           "source_corrigee": str(md_corr), "type": typ, "langue": langue, "client_id": client_id, "dossier": meta2.get("dossier"),
           "objet": str(objet), "cle": cle, "duree_ms": int((time.time() - t0) * 1000)}
    C.journal("producteur", op="produire", source=str(source), livrable=lid, ko=list(ko), duree_ms=out["duree_ms"])
    return out


def office_absent(principal=None):
    return C.office_disponible(str(principal or "x.docx")) is None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source"); ap.add_argument("--role"); ap.add_argument("--skill", default="production-livrables")
    ap.add_argument("--sans-ouvrir", action="store_true"); ap.add_argument("--sans-pdf", action="store_true"); ap.add_argument("--sans-inscrire", action="store_true")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--sans-panel", action="store_true", help="production seule, sans appel adverse (tests)")
    g.add_argument("--panel", action="store_true", help="force le panel (même pour une source de test)")
    a = ap.parse_args(argv)
    try:
        import panel as PN
        if PN.panel_voulu(a.source, a.sans_panel, a.panel):
            out = PN.livrer(a.source, a.role, a.skill, not a.sans_ouvrir, not a.sans_pdf, not a.sans_inscrire)
        else:
            out = PN.livrer(a.source, a.role, a.skill, not a.sans_ouvrir, not a.sans_pdf, not a.sans_inscrire, panel=False)
    except Exception as e:
        C.journal("erreurs-producteur", op="main", source=a.source, erreur=repr(e))
        out = {"erreur": repr(e), "reserves": ["production interrompue : l'intendant reprend"]}
    print(json.dumps(out, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
