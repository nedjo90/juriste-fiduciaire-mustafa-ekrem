#!/usr/bin/env python3
"""cerebro — seule voie structurée vers la mémoire de l'équipe (§9.1). Sortie JSON compacte pour les agents.
Exemples : cerebro find "Alpina dividende" · cerebro summary C-001 · cerebro open DOC-0003 --section Analyse
           cerebro deadlines --days 30 · cerebro config set mustafa.cantons_suivis VD,FR · cerebro brief"""
import sys, os, json, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cb import core
from cb.core import out
core.utf8_io()

def J(s):
    try:
        return json.loads(s)
    except Exception:
        return s

def build():
    p = argparse.ArgumentParser(prog="cerebro", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd")
    a = s.add_parser("init"); a.add_argument("--import-provisoire", action="store_true"); a.add_argument("--importer-si-vide", action="store_true", help="recharge la mémoire livrée (exports) si la base est vide")
    a = s.add_parser("find"); a.add_argument("q", nargs="+"); a.add_argument("--limit", type=int, default=10); a.add_argument("--deep", action="store_true"); a.add_argument("--asof"); a.add_argument("--type", action="append")
    a = s.add_parser("summary"); a.add_argument("id")
    a = s.add_parser("asof", help="état d'un objet à une date (bitemporalité)"); a.add_argument("id"); a.add_argument("date")
    a = s.add_parser("open"); a.add_argument("id"); a.add_argument("--section")
    a = s.add_parser("trace"); a.add_argument("id"); a.add_argument("-n", type=int, default=30)
    a = s.add_parser("regen"); a.add_argument("ids", nargs="*"); a.add_argument("--tout", action="store_true"); a.add_argument("--sales", action="store_true")
    a = s.add_parser("new", help="créer un objet générique"); a.add_argument("type"); a.add_argument("nom"); a.add_argument("--client"); a.add_argument("--resume", default="")
    a.add_argument("--prochaine-action"); a.add_argument("--date"); a.add_argument("--lien", action="append", default=[]); a.add_argument("--alias", action="append", default=[])
    a.add_argument("--source", default=""); a.add_argument("--corps-fichier"); a.add_argument("--statut", default="actif"); a.add_argument("--canton"); a.add_argument("--domaine"); a.add_argument("--risque"); a.add_argument("--chiffre"); a.add_argument("--mots-cles", default="")
    a = s.add_parser("update"); a.add_argument("id"); a.add_argument("champs", nargs="*", help="clé=valeur"); a.add_argument("--corps-fichier")
    a = s.add_parser("archive"); a.add_argument("id"); a.add_argument("--vers")
    a = s.add_parser("rename"); a.add_argument("id"); a.add_argument("nom")
    a = s.add_parser("link"); a.add_argument("src"); a.add_argument("dst"); a.add_argument("--type", default="lie")
    a = s.add_parser("links"); a.add_argument("id")
    a = s.add_parser("alias"); a.add_argument("id"); a.add_argument("alias"); a.add_argument("--langue")
    a = s.add_parser("client"); a.add_argument("action", choices=["show", "new", "vue"]); a.add_argument("arg"); a.add_argument("--forme", default=""); a.add_argument("--canton"); a.add_argument("--langue", default="fr"); a.add_argument("--alias", action="append", default=[]); a.add_argument("--resume", default="")
    a = s.add_parser("entity"); a.add_argument("action", choices=["show", "organs", "chain", "new"]); a.add_argument("arg"); a.add_argument("--client"); a.add_argument("--forme", default="SA"); a.add_argument("--ide", default=""); a.add_argument("--siege", default=""); a.add_argument("--canton"); a.add_argument("--organes", default="[]")
    a = s.add_parser("person"); a.add_argument("action", choices=["new"]); a.add_argument("nom"); a.add_argument("--client"); a.add_argument("--canton"); a.add_argument("--domicile")
    a = s.add_parser("participation"); a.add_argument("detenteur"); a.add_argument("detenue"); a.add_argument("pct", type=float); a.add_argument("--ayant-droit", action="store_true"); a.add_argument("--source", default="")
    a = s.add_parser("deadlines"); a.add_argument("--days", type=int, default=30); a.add_argument("--canton"); a.add_argument("--client")
    a = s.add_parser("extensions"); a.add_argument("due", nargs="?"); a.add_argument("--days", type=int, default=30)
    a = s.add_parser("commitments"); a.add_argument("due", nargs="?"); a.add_argument("--days", type=int, default=14)
    a = s.add_parser("matter"); a.add_argument("action", choices=["new"]); a.add_argument("client"); a.add_argument("objet"); a.add_argument("--partie", action="append", default=[]); a.add_argument("--canton"); a.add_argument("--domaine")
    a = s.add_parser("conflict-check"); a.add_argument("noms", nargs="+"); a.add_argument("--client")
    a = s.add_parser("clock"); a.add_argument("action", choices=["start", "close", "types"]); a.add_argument("arg", nargs="?"); a.add_argument("--date"); a.add_argument("--client"); a.add_argument("--dossier"); a.add_argument("--canton"); a.add_argument("--objet")
    a = s.add_parser("event"); a.add_argument("type", choices=["taxation", "dividende", "relation"]); a.add_argument("--client", required=True); a.add_argument("--contribuable"); a.add_argument("--autorite", default=""); a.add_argument("--canton"); a.add_argument("--periode", default=""); a.add_argument("--date"); a.add_argument("--montant", type=float); a.add_argument("--societe"); a.add_argument("--nom"); a.add_argument("--risque", default="normal")
    a = s.add_parser("lba"); a.add_argument("action", choices=["review"]); a.add_argument("due", nargs="?"); a.add_argument("--days", type=int, default=30)
    a = s.add_parser("question"); a.add_argument("action", choices=["add", "list", "next", "answer", "from-gaps"]); a.add_argument("arg", nargs="?"); a.add_argument("--besoin", default=""); a.add_argument("--defaut", default=""); a.add_argument("--type", default="metier"); a.add_argument("--priorite", type=int, default=3); a.add_argument("--cle"); a.add_argument("--sujet"); a.add_argument("--reponse")
    a = s.add_parser("conseil"); a.add_argument("action", choices=["add", "next", "suivi"]); a.add_argument("arg", nargs="?"); a.add_argument("--cle"); a.add_argument("--gain", type=int, default=3)
    a = s.add_parser("time"); a.add_argument("action", choices=["add"]); a.add_argument("client"); a.add_argument("minutes", type=int); a.add_argument("libelle"); a.add_argument("--dossier")
    a = s.add_parser("pipeline"); a.add_argument("action", nargs="?", choices=["list", "add"], default="list"); a.add_argument("client", nargs="?"); a.add_argument("opportunite", nargs="?"); a.add_argument("--valeur", type=float)
    a = s.add_parser("engagement"); a.add_argument("client"); a.add_argument("envers"); a.add_argument("objet"); a.add_argument("du_le")
    a = s.add_parser("law"); a.add_argument("action", choices=["ingest", "search", "asof", "article", "verify", "reindex"]); a.add_argument("arg", nargs="*"); a.add_argument("--fichier"); a.add_argument("--juridiction", default="CH"); a.add_argument("--type", default="loi"); a.add_argument("--titre", default=""); a.add_argument("--langue", default="fr"); a.add_argument("--version"); a.add_argument("--date-etat"); a.add_argument("--url", default=""); a.add_argument("--abrev", default=""); a.add_argument("--date")
    a = s.add_parser("rates"); a.add_argument("action", choices=["get", "set"]); a.add_argument("nom"); a.add_argument("--juridiction", default="CH"); a.add_argument("--annee"); a.add_argument("--cle"); a.add_argument("--valeur"); a.add_argument("--source", default="")
    a = s.add_parser("capability"); a.add_argument("action", choices=["list", "propose", "register"]); a.add_argument("arg", nargs="?"); a.add_argument("--categorie", default="outil"); a.add_argument("--localisation", default="LOCAL"); a.add_argument("--sort", default="rien"); a.add_argument("--vers", default="-"); a.add_argument("--licence", default=""); a.add_argument("--version", default=""); a.add_argument("--statut", default="actif"); a.add_argument("--source", default="")
    a = s.add_parser("incident"); a.add_argument("action", choices=["add", "resolve", "list"]); a.add_argument("arg", nargs="?"); a.add_argument("--categorie", default="technique"); a.add_argument("--repli", default=""); a.add_argument("--phrase", default="")
    a = s.add_parser("deliverable"); a.add_argument("action", choices=["register"]); a.add_argument("chemin"); a.add_argument("--client"); a.add_argument("--dossier"); a.add_argument("--type", default="memo"); a.add_argument("--portes", default="{}"); a.add_argument("--reserves", default="")
    a = s.add_parser("config"); a.add_argument("action", choices=["get", "set", "gaps"]); a.add_argument("cle", nargs="?"); a.add_argument("valeur", nargs="?"); a.add_argument("--source")
    s.add_parser("brief"); s.add_parser("health"); s.add_parser("coverage"); s.add_parser("export"); s.add_parser("import-exports"); s.add_parser("croisements"); s.add_parser("rappel")
    a = s.add_parser("gc"); a.add_argument("--simuler", action="store_true")
    a = s.add_parser("context"); a.add_argument("prompt", nargs="*"); a.add_argument("--debut", action="store_true")
    a = s.add_parser("reprocess"); a.add_argument("--since", required=True)
    a = s.add_parser("sommaires"); a.add_argument("--niveau0", action="store_true")
    a = s.add_parser("cardinal"); a.add_argument("action", choices=["show", "inject", "check"])
    a = s.add_parser("queue"); a.add_argument("action", choices=["add", "next", "done", "list"]); a.add_argument("arg", nargs="*"); a.add_argument("--priorite", type=int, default=4)
    a = s.add_parser("task-seen"); a.add_argument("type")
    a = s.add_parser("mesure"); a.add_argument("role"); a.add_argument("tache"); a.add_argument("palier"); a.add_argument("--tokens", type=int, default=0); a.add_argument("--ms", type=int, default=0)
    from cb import routines as RT; RT.parseurs(s)  # routine, regle, reconcile (chantier autonomie)
    return p

def main(argv=None):
    args = build().parse_args(argv)
    c = args.cmd
    if not c:
        build().print_help(); return
    from cb import objets as O, recherche as R, sommaires as S, config as K, files as F, horloges as H, metier as M, brief as B, juridique as L, cardinal as X
    from cb import routines as RT
    if c in RT.COMMANDES:
        out(RT.executer(args)); return
    if c == "init":
        for d in ("A-deposer", "Deposes", "Livrables", "Modeles", "Informatique"):
            (core.BUREAU / d).mkdir(parents=True, exist_ok=True)
        H.seed()
        r = {"db": str(core.DB_PATH), "fts": core.has_fts()}
        if args.import_provisoire:
            r["importes"] = S.importer_provisoire(core.ROOT / "SOMMAIRE.md")
        if args.importer_si_vide and core.db().execute("SELECT COUNT(*) FROM objets WHERE type IN ('role','skill','methode')").fetchone()[0] == 0:
            r["import"] = B.importer_exports()
        r["niveau0"] = len(S.tout())
        out(r)
    elif c == "find":
        out(R.find(" ".join(args.q), args.limit, args.deep, args.asof, args.type))
    elif c == "asof":
        o = O.etat_au(args.id, args.date); out({k: o[k] for k in ("id", "type", "nom", "statut", "client", "resume", "etat_au")} if o else {"erreur": "inconnu"})
    elif c == "summary":
        out(R.summary(args.id))
    elif c == "open":
        if args.id.endswith("-VUE"):
            cid = args.id[:-4]; M.vue_client(cid)
            p = O.client_dir(cid) / "vue.md"; out(p.read_text(encoding="utf-8") if p.exists() else {"erreur": "inconnu"})
        else:
            out(R.open_section(args.id, args.section))
    elif c == "trace":
        out(R.trace(args.id, args.n))
    elif c == "regen":
        con = core.db()
        ids = args.ids
        if args.tout:
            ids = [r[0] for r in con.execute("SELECT id FROM objets")]
        elif args.sales or not ids:
            ids = [r[0] for r in con.execute("SELECT id FROM objets WHERE a_regenerer=1")]
        lignes, erreurs = [], []
        for i in ids:
            try:
                lignes.append(O.regen(i))
            except Exception as e:  # un objet en défaut n'arrête jamais la régénération des autres
                erreurs.append(f"{i}: {repr(e)[:120]}")
                con.rollback()
        S.niveau0()
        out({"regeneres": len(lignes), "lignes": [l for l in lignes if l][:20], "erreurs": erreurs[:10]})
    elif c == "new":
        body = core.lire(args.corps_fichier) if args.corps_fichier else None
        chemin = None
        if args.type in O.EXTERNES and args.source and (core.ROOT / args.source).is_file():
            chemin = args.source.replace("\\", "/")
        oid = O.create(args.type, args.nom, body=body, client=args.client, chemin=chemin, resume=args.resume, prochaine_action=args.prochaine_action, prochaine_date=args.date,
                       liens=args.lien, alias=args.alias, source=args.source, statut=args.statut, canton=args.canton, domaine=args.domaine, risque=args.risque,
                       chiffre_cle=args.chiffre, mots_cles=args.mots_cles)
        out({"id": oid, "ligne": S.ligne(O.get(oid)), "chemin": O.get(oid)["chemin"]})
    elif c == "update":
        mal = [x for x in args.champs if "=" not in x]
        if mal:
            out({"erreur": f"attendu clé=valeur : {', '.join(mal)}"}); return
        if not O.get(args.id):
            out({"erreur": f"objet inconnu : {args.id}"}); return
        kw = dict(x.split("=", 1) for x in args.champs)
        body = open(args.corps_fichier, encoding="utf-8").read() if args.corps_fichier else None
        out({"ligne": O.update(args.id, body=body, **kw)})
    elif c == "archive":
        out({"ligne": O.archive(args.id, args.vers)})
    elif c == "rename":
        out({"ligne": O.rename(args.id, args.nom)} if O.get(args.id) else {"erreur": f"objet inconnu : {args.id}"})
    elif c == "link":
        O.link(args.src, args.dst, args.type); core.db().commit(); O.regen(args.src); O.regen(args.dst); out({"ok": True})
    elif c == "links":
        o, i = O.links_of(O.resolve(args.id)); out({"sortants": o, "entrants": i})
    elif c == "alias":
        if not O.get(args.id):
            out({"erreur": f"objet inconnu : {args.id}"}); return
        O.add_alias(O.resolve(args.id), args.alias, args.langue); core.db().commit(); O.regen(args.id); out({"ok": True})
    elif c == "client":
        if args.action == "show": out(M.client_show(args.arg))
        elif args.action == "vue": out({"vue": M.vue_client(args.arg)})
        else: out({"id": M.client_new(args.arg, args.forme, args.canton, args.langue, args.alias, args.resume)})
    elif c == "entity":
        if args.action == "show": out(M.entity_show(args.arg))
        elif args.action == "organs": out(M.entity_organs(args.arg))
        elif args.action == "chain": out(M.entity_chain(args.arg))
        else: out({"id": M.entity_new(args.arg, args.client, args.forme, args.ide, args.siege, args.canton, organes=J(args.organes))})
    elif c == "person":
        out({"id": M.person_new(args.nom, args.client, canton=args.canton, domicile=args.domicile)})
    elif c == "participation":
        M.participation(args.detenteur, args.detenue, args.pct, args.ayant_droit, args.source); out({"ok": True})
    elif c == "deadlines":
        out(H.deadlines(args.days, args.canton, args.client))
    elif c == "extensions":
        out(H.extensions_due(args.days))
    elif c == "commitments":
        out(H.commitments_due(args.days))
    elif c == "matter":
        out(M.matter_new(args.client, args.objet, args.partie, args.canton, args.domaine))
    elif c == "conflict-check":
        out(M.conflict_check(args.noms, args.client))
    elif c == "clock":
        if args.action == "types":
            H.seed(); out([dict(r) for r in core.db().execute("SELECT type,libelle,duree,unite,source,article,verifie_le FROM regles_delais")])
        elif args.action == "close":
            out({"ligne": H.close(args.arg)})
        else:
            out(H.clock_start(args.arg, args.date or core.iso(), args.client, args.dossier, args.canton, args.objet))
    elif c == "event":
        d = args.date or core.iso()
        if args.type == "taxation":
            out(M.event_taxation(args.client, args.contribuable, args.autorite, args.canton, args.periode, d, args.montant))
        elif args.type == "dividende":
            out(M.event_dividende(args.client, args.societe, d, args.montant))
        else:
            out(M.event_relation(args.client, args.nom or "relation", args.risque))
    elif c == "lba":
        out(H.lba_review_due(args.days))
    elif c == "question":
        if args.action == "add": out({"id": F.question_add(args.arg, args.besoin, args.defaut, args.type, args.priorite, args.cle, args.sujet)})
        elif args.action == "list": out(F.question_list(args.arg or "ouverte"))
        elif args.action == "next": out(F.question_next(args.sujet))
        elif args.action == "answer": out(F.question_answer(args.arg, args.reponse))
        else: out({"ajoutees": F.questions_depuis_gaps()})
    elif c == "conseil":
        if args.action == "add": out({"id": F.conseil_add(args.arg, args.cle or core.slug(args.arg), args.gain)})
        elif args.action == "next": out(F.conseil_next())
        else: F.conseil_suivi(args.arg); out({"ok": True})
    elif c == "time":
        out({"id": M.time_add(args.client, args.minutes, args.libelle, args.dossier)})
    elif c == "pipeline":
        out(M.pipeline_list() if args.action == "list" else {"id": M.pipeline_add(args.client, args.opportunite, args.valeur)})
    elif c == "engagement":
        out({"id": M.engagement_add(args.client, args.envers, args.objet, args.du_le)})
    elif c == "law":
        if args.action == "ingest":
            txt = open(args.fichier, encoding="utf-8").read()
            out(L.ingest(txt, args.juridiction, args.type, args.arg[0], args.titre or args.arg[0], args.langue, args.version, args.date_etat, args.url, args.abrev))
        elif args.action == "search": out(L.search(" ".join(args.arg), args.juridiction if args.juridiction != "CH" else None, langue=args.langue))
        elif args.action == "asof": out(L.asof(args.arg[0], args.date, args.langue))
        elif args.action == "article": out(L.article(args.arg[0], " ".join(args.arg[1:]), args.date, args.langue))
        elif args.action == "reindex": out(L.reindex_articles())
        else: out(L.verify_rules())
    elif c == "rates":
        out(L.rates_get(args.nom, args.juridiction, args.annee, args.cle) if args.action == "get" else {"id": L.rates_set(args.nom, args.juridiction, args.annee, args.cle, args.valeur, args.source)})
    elif c == "capability":
        if args.action == "list": out(F.capability_list())
        elif args.action == "propose": out(F.capability_propose(args.arg))
        else: out({"id": F.capability_register(args.arg, args.categorie, args.localisation, args.sort, args.vers, args.licence, args.version, args.statut, args.source)})
    elif c == "incident":
        if args.action == "add": out({"id": F.incident_add(args.categorie, args.arg, args.repli, args.phrase)})
        elif args.action == "resolve": out({"id": F.incident_resolve(args.arg, args.repli)})
        else: out(F.incident_list(args.arg or "ouvert"))
    elif c == "deliverable":
        out({"id": F.deliverable_register(args.chemin, args.client, args.dossier, args.type, J(args.portes), args.reserves)})
    elif c == "config":
        if args.action in ("get", "set") and not args.cle: out({"erreur": "clé manquante (ex. poste.messagerie)"})
        elif args.action == "get": out({"cle": args.cle, "valeur": K.get(args.cle), "detail": K.get_full(args.cle)})
        elif args.action == "set": out(K.set_(args.cle, args.valeur, args.source))
        else: out(K.gaps())
    elif c == "brief":
        out(B.brief())
    elif c == "health":
        out(B.health())
    elif c == "coverage":
        out(B.coverage())
    elif c == "gc":
        out(B.gc(not args.simuler))
    elif c == "export":
        out(B.export())
    elif c == "import-exports":
        out(B.importer_exports())
    elif c == "croisements":
        out(M.croisements())
    elif c == "rappel":
        r = R.autotest_rappel(); core.set_etat("rappel", r); out(r)
    elif c == "context":
        out(B.session_start() if args.debut else B.context(" ".join(args.prompt)))
    elif c == "reprocess":
        out(B.reprocess(args.since))
    elif c == "sommaires":
        out(S.niveau0() if args.niveau0 else S.tout())
    elif c == "cardinal":
        out(X.bloc() if args.action == "show" else (X.injecter() if args.action == "inject" else {"perimes": X.verifier()}))
    elif c == "queue":
        if args.action == "add": B.queue_add(args.arg[0], " ".join(args.arg[1:]), args.priorite); out({"ok": True})
        elif args.action == "next": out(B.queue_next())
        elif args.action == "done": B.queue_done(int(args.arg[0]), args.arg[1] if len(args.arg) > 1 else "fait"); out({"ok": True})
        else: out([dict(r) for r in core.db().execute("SELECT * FROM file_entretien WHERE statut='attente' ORDER BY priorite, n")])
    elif c == "task-seen":
        F.task_seen(args.type); out({"ok": True})
    elif c == "mesure":
        F.mesure(args.role, args.tache, args.palier, args.tokens, args.ms); out({"ok": True})

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:  # jamais de trace brute : une erreur est un incident journalisé
        core.journal("erreurs-cli", argv=[a[:200] for a in sys.argv[1:]], erreur=repr(e)[:300])
        try:
            core.db().rollback()
        except Exception:
            pass
        out({"erreur": repr(e)[:300]})
        sys.exit(1)
