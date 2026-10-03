#!/usr/bin/env python3
"""Tests du chantier qualité (écarts 14 à 17 et 19 ; critères 5, 6, 15, 17, 23, 34).
Racine jetable (copie de la base, de la bibliothèque fédérale et de la configuration) + dossier fictif : la base réelle
n'est jamais touchée. Réseau facultatif : sans réseau, les tests réseau vérifient le repli propre.
Usage : python .team/tests/test_quality.py   → une ligne OK/ÉCHEC par vérification, puis le bilan."""
import os, sys, json, shutil, subprocess, tempfile, textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EQ = REPO / ".team"
FIX = EQ / "tests" / "fixtures"
RES = []


def check(nom, cond, detail=""):
    RES.append(bool(cond))
    print(("OK     " if cond else "ÉCHEC  ") + nom + (f" — {detail}" if detail and not cond else ""))


def racine_jetable():
    t = Path(tempfile.mkdtemp(prefix="test-qualite-"))
    e = t / ".team"
    e.mkdir()
    shutil.copytree(EQ / "cerebro", e / "cerebro", ignore=shutil.ignore_patterns("*.db", "*.db-*", "__pycache__", "exports", "sauvegardes"))
    import sqlite3  # copie cohérente de la base (sauvegarde SQLite), même si un autre processus l'écrit
    if (EQ / "cerebro" / "cerebro.db").exists():
        src = sqlite3.connect(f"file:{EQ / 'cerebro' / 'cerebro.db'}?mode=ro", uri=True, timeout=30)
        dst = sqlite3.connect(str(e / "cerebro" / "cerebro.db"))
        src.backup(dst); dst.close(); src.close()
    for d in ("config",):
        shutil.copytree(EQ / d, e / d)
    if (EQ / "library").exists():
        shutil.copytree(EQ / "library", e / "library", ignore=shutil.ignore_patterns("cache"))
    (e / "brain" / "firm" / "design").mkdir(parents=True)
    shutil.copy(EQ / "brain" / "firm" / "design" / "system.yaml", e / "brain" / "firm" / "design")
    shutil.copy(EQ / "constitution.md", e / "constitution.md")
    for d in ("Livrables", "Modeles", "Informatique", "A-deposer"):
        (t / "Bureau" / d).mkdir(parents=True)
    return t


def env_de(t, **kw):
    e = dict(os.environ, CEREBRO_ROOT=str(t), CEREBRO_TODAY="2026-10-03", PRODUCTEUR_SANS_OUVERTURE="1", PRODUCTEUR_SANS_MMDC="1",
             PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    e.pop("CEREBRO_DB", None)
    e.pop("CEREBRO_BACKGROUND", None)
    e.update({k: str(v) for k, v in kw.items()})
    return e


def py(t, code, timeout=600, **kw):
    """exécute un extrait Python dans la racine jetable ; renvoie le dernier JSON imprimé"""
    pre = textwrap.dedent(f"""
        import sys, json
        sys.path[:0] = [r"{EQ / 'cerebro'}", r"{EQ / 'scripts' / 'gates'}", r"{EQ / 'scripts' / 'producer'}",
                        r"{EQ / 'scripts' / 'research'}", r"{EQ / 'scripts' / 'library'}", r"{EQ / 'scripts' / 'maintenance'}"]
    """)
    r = subprocess.run([sys.executable, "-c", pre + textwrap.dedent(code)], capture_output=True, text=True, encoding="utf-8",
                       env=env_de(t, **kw), cwd=str(t), timeout=timeout)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1]), r
    except Exception:
        return None, r


def run(t, *args, timeout=900, **kw):
    r = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, encoding="utf-8", env=env_de(t, **kw), cwd=str(t), timeout=timeout)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1]), r
    except Exception:
        return None, r


FAUX_CLAUDE = r'''
import sys, json, re
p = sys.stdin.read()
if "----- CONSTATS DU PANEL -----" in p:          # rédacteur : écrit la source corrigée
    dest = re.search(r"corrigé dans\s+(\S+)", p).group(1)
    src = p.split("----- SOURCE -----", 1)[1].lstrip("\n")
    open(dest, "w", encoding="utf-8").write(src.replace("## Analyse\n", "## Analyse\nAnalyse revue après le panel.\n", 1))
    res = 'Corrections appliquées.\n{"ecrit": true, "corrections": 1}'
else:                                             # panel adverse
    res = ('{"voix":"testeur","gravite":"important","lieu":"Résumé","constat":"montant net à justifier","correction":"renvoyer au tableau","source":"-"}\n'
           'Synthèse : 1 important.\n{"constats": 1, "majeurs": 0, "importants": 1, "confort": "should", "presentable": "avec réserves"}')
print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": res,
                  "usage": {"input_tokens": 1000, "output_tokens": 200}}))
'''


def faux_claude(t):
    f = t / "faux_claude.py"
    f.write_text(FAUX_CLAUDE, encoding="utf-8")
    if os.name == "nt":
        w = t / "faux_claude.cmd"
        w.write_text(f'@"{sys.executable}" "{f}" %*\r\n', encoding="utf-8")
    else:
        w = t / "faux_claude.sh"
        w.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{f}" "$@"\n', encoding="utf-8")
        w.chmod(0o755)
    return w


def main():
    t = racine_jetable()
    try:
        _, r = run(t, FIX / "fictional_case.py")
        check("dossier fictif chargé dans la racine jetable", r.returncode == 0, r.stderr[-300:])

        # ---------------------------------------------------------- p_sommaires
        doc = t / "note-test.md"
        doc.write_text("---\ntype: note\nclient: C-001\n---\n## Résumé\nPoint sur le client C-001.\n", encoding="utf-8")
        o, r = py(t, f"""
            import gates_common as CP, p_summaries as PS, common as C
            core, objets, _, _ = C.cb()
            cid = [r[0] for r in core.db().execute("SELECT id FROM objets WHERE type='client' ORDER BY id")][0]
            open(r"{doc}", "w", encoding="utf-8").write(f"---\\ntype: note\\nclient: {{cid}}\\n---\\n## Résumé\\nPoint sur {{cid}}.\\n")
            PS.reparer([cid])
            ok1 = PS.verifier(CP.charger(r"{doc}"))["etat"]
            core.db().execute("UPDATE objets SET a_regenerer=1 WHERE id=?", (cid,)); core.db().commit()
            r2 = PS.verifier(CP.charger(r"{doc}"))
            PS.reparer(r2.get("a_regenerer", []))
            ok3 = PS.verifier(CP.charger(r"{doc}"))["etat"]
            print(json.dumps({{"a": ok1, "b": r2["etat"], "corr": r2["corrections"][:1], "c": ok3}}))
        """)
        check("p_sommaires : objet cité régénéré et au sommaire → ok", o and o["a"] == "ok", (r.stderr or r.stdout)[-400:])
        check("p_sommaires : objet à régénérer → ko avec correction « cerebro regen »", o and o["b"] == "ko" and "regen" in json.dumps(o["corr"]))
        check("p_sommaires : réparation déterministe puis ok", o and o["c"] == "ok")

        # ---------------------------------------------------------- p_contexte
        o, r = py(t, f"""
            import gates_common as CP, p_context as PX, common as C
            core = C.cb()[0]
            d = CP.charger(r"{doc}")
            a = PX.verifier(d, {{"injection": 7200, "tour": "T-test-1"}})["etat"]
            b = PX.verifier(d, {{"injection": "x" * 2000, "tour": "T-test-2"}})["etat"]
            for i in range(6):
                core.db().execute("INSERT INTO ouvertures(le,tour,id,section,acteur) VALUES(datetime('now'),'T-test-3',?,?,?)", (f"X-{{i}}", "s", "agent"))
            core.db().commit()
            c = PX.verifier(d, {{"injection": 1000, "tour": "T-test-3"}})
            print(json.dumps({{"a": a, "b": b, "c": c["etat"], "det": c["details"]}}))
        """)
        check("p_contexte : injection > 6 000 caractères → ko", o and o["a"] == "ko", (r.stderr or r.stdout)[-400:])
        check("p_contexte : injection sous budget et ouvertures ≤ 5 → ok", o and o["b"] == "ok")
        check("p_contexte : six ouvertures pour une question → ko", o and o["c"] == "ko", json.dumps(o)[:300] if o else "")

        # ---------------------------------------------------------- p_panel + orchestration (faux modèle)
        o, r = py(t, f"""
            import gates_common as CP, p_panel as PP
            d = CP.charger(r"{FIX / 'memo_demo.md'}")
            a = PP.verifier(d, {{"cle": "cle-test-panel"}})["etat"]
            PP.enregistrer("cle-test-panel", None, "N-000", "faux", 0, 1, 0)
            b = PP.verifier(d, {{"cle": "cle-test-panel"}})["etat"]
            l = CP.charger(r"{FIX / 'lettre_demo.md'}")
            c = PP.verifier(l, {{}})["etat"]
            print(json.dumps({{"a": a, "b": b, "c": c}}))
        """)
        check("p_panel : mémo sans appel adverse → ko", o and o["a"] == "ko", (r.stderr or r.stdout)[-400:])
        check("p_panel : panel enregistré → ok ; lettre → sans objet", o and o["b"] == "ok" and o["c"] == "na")

        prod = EQ / "scripts" / "producer" / "produce.py"
        o1, r1 = run(t, prod, FIX / "memo_demo.md", "--role", "drafter", "--sans-panel", "--sans-ouvrir")
        check("produire --sans-panel : mémo produit, porte panel ko, livrable présenté avec réserves",
              o1 and o1.get("principal") and o1["portes"].get("panel") == "ko" and any("panel" in x for x in o1.get("reserves", [])),
              (r1.stderr or r1.stdout)[-400:])
        check("produire : relecteur, sommaires et contexte exécutés", o1 and {"proofreader", "sommaires", "contexte"} <= set(o1.get("portes", {})),
              json.dumps(o1.get("portes") if o1 else {}))
        fc = faux_claude(t)
        o2, r2 = run(t, prod, FIX / "memo_demo.md", "--role", "drafter", "--panel", "--sans-ouvrir", CEREBRO_CLAUDE=fc)
        pn = (o2 or {}).get("panel", {})
        check("produire --panel : un appel adverse groupé tenu, note « Panel — » liée au livrable",
              pn.get("tenu") and str(pn.get("note", "")).startswith("N") and o2["portes"].get("panel") == "ok", (r2.stderr or json.dumps(o2))[-500:])
        check("panel : corrections appliquées par le rédacteur (second appel au plus), même version",
              pn.get("corrections", {}).get("appliquees") is True and (o2 or {}).get("source_apres_panel"),
              json.dumps(pn)[:300])
        o, r = py(t, f"""
            import common as C
            core = C.cb()[0]
            n = core.db().execute("SELECT COUNT(*) FROM liens WHERE (src=? AND dst=?) OR (src=? AND dst=?)", ("{pn.get('note')}", "{(o2 or {}).get('livrable')}", "{(o2 or {}).get('livrable')}", "{pn.get('note')}")).fetchone()[0]
            m = core.db().execute("SELECT COUNT(*) FROM mesures WHERE role='adversarial-panel'").fetchone()[0]
            print(json.dumps({{"lien": n, "mesures": m}}))
        """)
        check("panel : lien note ↔ livrable et appel mesuré (tokens)", o and o["lien"] >= 1 and o["mesures"] >= 1, json.dumps(o))

        # ---------------------------------------------------------- horloges cantonales
        cant = EQ / "scripts" / "library" / "cantons.py"
        o, r = run(t, cant, "ingerer", "--canton", "VD", timeout=600)
        ing = (o or {}).get("ingestion", [{}])[0] if o else {}
        if ing.get("id"):
            v, rv = run(t, EQ / "cerebro" / "cerebro.py", "law", "verify")
            vd = next((x for x in (v or []) if x.get("regle") == "reclamation_icc_vd"), {})
            check("règle cantonale vérifiée : réclamation ICC VD (LI art. 186) confirmée par law verify",
                  vd.get("verifie") is True and "LI-VD art. 186" in vd.get("article", "") and "trente jours" in vd.get("detail", ""), json.dumps(vd)[:300])
            a, ra = run(t, EQ / "cerebro" / "cerebro.py", "law", "article", "LI-VD", "art. 186")
            check("law article LI-VD art. 186 : texte, version, URL officielle (BLV)", a and "prestations.vd.ch" in a.get("url", "") and a.get("version"), json.dumps(a)[:200] if a else ra.stderr[-200:])
        else:
            check("recueil vaudois injoignable : incident noté, règle cantonale laissée ⚠ (repli propre)", o is not None and ing.get("erreur"), (r.stderr or r.stdout)[-300:])
        o, r = py(t, """
            from cb import business as M, objects as O, core
            cid = [r[0] for r in core.db().execute("SELECT id FROM objets WHERE type='client' ORDER BY id")][0]
            a = M.event_taxation(cid, None, "Administration cantonale des impôts VD", "VD", "2025", "2026-09-22", 1000.0)
            b = M.event_taxation(cid, None, "Kantonales Steueramt Zürich", "ZH", "2025", "2026-09-22", 1000.0)
            c = M.event_taxation(cid, None, "Administration cantonale des impôts", "VD", "2025", "2026-09-22", 1000.0, impot="ICC")
            print(json.dumps({"a": [h["regle"] for h in a["horloges"]], "ech": a["echeance"], "b": [h["regle"] for h in b["horloges"]],
                              "c": [h["regle"] for h in c["horloges"]]}))
        """)
        check("event_taxation VD (IFD/ICC) → règle cantonale VD + IFD en parallèle", o and o["a"] == ["reclamation_icc_vd", "reclamation_ifd"] and o["ech"] == "2026-10-22",
              (r.stderr or json.dumps(o))[-300:])
        check("event_taxation canton non suivi → cadre LHID + IFD ; ICC seul → une horloge cantonale",
              o and o["b"] == ["reclamation_icc", "reclamation_ifd"] and o["c"] == ["reclamation_icc_vd"], json.dumps(o))

        # ---------------------------------------------------------- tableau de bord des principes (tâche du cycle)
        o, r = py(t, """
            import importlib.util, common as C
            core = C.cb()[0]
            import dashboard as tableau
            con = core.db(); con.executescript(tableau.DDL)
            for i in range(4):
                con.execute("INSERT INTO portes_passages(le,livrable,cle,role,skill,porte,etat,premier_coup,nb_corrections,details) VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (core.stamp(), "x", f"k{i}", "role-test-ecart", "skill-x", "sources", "ko", 1, 1, "[]"))
            con.commit()
            spec = importlib.util.spec_from_file_location("q", r"%s")
            q = importlib.util.module_from_spec(spec); spec.loader.exec_module(q)
            r1 = q.t_principes("", 0); r2 = q.t_principes("", 0)
            et = core.get_etat("principes", {})
            f = [r[0] for r in con.execute("SELECT arg FROM file_entretien WHERE tache='fabrique' AND statut='attente'")]
            print(json.dumps({"r1": r1, "r2": r2, "ligne": et.get("ligne"), "fabrique": f}))
        """ % (EQ / "scripts" / "maintenance" / "tasks" / "quality.py"))
        check("tâche principes : résumé écrit dans l'état lu par la santé", o and "écart" in (o.get("ligne") or ""), (r.stderr or r.stdout)[-400:])
        check("rôle en écart deux cycles de suite → fabrique « réviser <nom> »", o and "réviser role-test-ecart" in o["fabrique"] and not o["r1"]["revisions"], json.dumps(o)[:300] if o else "")

        # ---------------------------------------------------------- recherche académique (réseau ou repli)
        o, r = run(t, EQ / "scripts" / "research" / "academic.py", "Swiss withholding tax dividends", "--n", "3", timeout=180)
        check("recherche académique : au moins un résultat daté, ou repli propre sans erreur",
              o and ((o["resultats"] and o["resultats"][0].get("consulte_le")) or o.get("repli")), (r.stderr or r.stdout)[-300:])
        o, r = run(t, EQ / "scripts" / "research" / "official_web.py", "verifier", "https://www.vd.ch/x")
        o2_, _ = run(t, EQ / "scripts" / "research" / "official_web.py", "recuperer", "https://exemple.invalid/page")
        check("web officiel : liste blanche appliquée (vd.ch admis, domaine inconnu jamais ingéré)",
              o and o.get("liste_blanche") and o.get("juridiction") == "VD" and o2_ and o2_.get("etat") == "hors liste blanche")

        # ---------------------------------------------------------- données de répétition réelles
        dep = t / "inbox-docs"
        o, r = run(t, FIX / "inbox-docs" / "generate.py", "--dest", dep)
        noms = set((o or {}).get("fichiers", []))
        attendus = {".eml", ".msg", ".docx", ".xlsx", ".pdf"}
        check("fixtures de dépôt : eml, msg, pdf texte, pdf image, docx suivi, xlsx générés",
              attendus <= {Path(n).suffix for n in noms} and len([n for n in noms if n.endswith(".pdf")]) == 2, (r.stderr or str(noms))[-300:])
        try:
            import extract_msg
            m = extract_msg.openMsg(str(dep / "mail-lemantech-convention.msg"))
            check(".msg Outlook relu par extract-msg (objet, expéditeur, pièce jointe)", "Lémantech" in (m.subject or "") and m.attachments)
        except ImportError:
            check(".msg présent (extract-msg absent : lecture non testée)", (dep / "mail-lemantech-convention.msg").exists())
        from docx import Document
        x = Document(str(dep / "convention-lemantech-suivi-modifications.docx")).element.xml
        check(".docx : suivi des modifications réel (w:ins et w:del avec auteur)", "<w:ins " in x and "<w:del " in x and "w:author" in x)
        o, r = run(t, EQ / "scripts" / "research" / "ocr.py", dep / "pv-ag-2026-rochat-holding-scan.pdf", timeout=300)
        if o and o.get("moteur"):
            check("OCR local du PDF scanné : texte reconnu (dividende)", "dividende" in (o.get("extrait") or "").lower(), json.dumps(o)[:200])
        else:
            check("OCR indisponible : repli documenté (None, aucune erreur)", o is not None and o.get("caracteres") == 0)
        o, r = py(t, f"""
            import office
            print(json.dumps({{"pdf": str(office.vers_pdf(r"{dep / 'convention-lemantech-suivi-modifications.docx'}") or ""), "methode": office.disponible()}}))
        """)
        check("office.vers_pdf : conversion par Office ou None sans erreur (repli)", o is not None and (o["pdf"].endswith(".pdf") or (not o["pdf"] and not o["methode"])), (r.stderr or "")[-200:])
    finally:
        if not os.environ.get("GARDER_RACINE"):
            shutil.rmtree(t, ignore_errors=True)
        else:
            print("racine gardée :", t)
    ok = all(RES)
    print(f"{'OK' if ok else 'ÉCHEC'} — {sum(RES)}/{len(RES)} vérifications")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
