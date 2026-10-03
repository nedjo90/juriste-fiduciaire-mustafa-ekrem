"""Délais et horloges (§14) : calculés depuis l'événement déclencheur, par règle sourcée ; chaque horloge a son document
préparé d'avance. Aucune durée n'est affirmée sans source : une règle non vérifiée contre le texte officiel porte ⚠."""
import datetime as dt, json
from .core import db, iso, today, new_id, stamp, audit
from .objets import create, link, get

# Règles candidates. `extrait_attendu` est vérifié par script contre le texte officiel ingéré (cerebro law verify).
# Tant que verifie_le est vide, toute horloge qui en dépend est marquée ⚠ « règle non vérifiée ».
REGLES = [
    # type, libellé, durée, unité, depuis, préavis, RS, article, extrait attendu, document à préparer
    ("reclamation_ifd", "Réclamation contre une décision de taxation IFD", 30, "jours", "notification", 10, "642.11", "art. 132", "30 jours", "reclamation"),
    ("recours_ifd", "Recours contre une décision sur réclamation IFD", 30, "jours", "notification", 10, "642.11", "art. 140", "30 jours", "recours"),
    ("impot_anticipe_dividende", "Déclaration et paiement de l'impôt anticipé sur dividende", 30, "jours", "echeance_dividende", 10, "642.21", "art. 16 al. 1 let. c", "trente jours après la naissance de la créance fiscale", "declaration_ia"),  # corrigé 2026-10-03 (texte LIA 2025-01-01 ; naissance : art. 12 al. 1)
    ("decompte_tva", "Décompte TVA de la période", 60, "jours", "fin_periode", 15, "641.20", "art. 71", "60 jours", "decompte_tva"),
    ("assemblee_generale", "Assemblée générale ordinaire", 6, "mois", "cloture_exercice", 45, "220", "art. 699", "six mois", "convocation_ag"),
    ("annonce_ayant_droit", "Annonce de l'ayant droit économique à la société", 1, "mois", "acquisition", 10, "955.3", "art. 13 al. 3", "un mois à compter de la création du contrôle", "annonce_adb"),  # corrigé 2026-10-03 : art. 697j CO abrogé au 1.10.2026 (LTPM)
    ("opposition_poursuite", "Opposition au commandement de payer", 10, "jours", "notification", 3, "281.1", "art. 74", "dix jours", "opposition"),
    ("recours_tf", "Recours au Tribunal fédéral", 30, "jours", "notification", 10, "173.110", "art. 100", "30 jours", "recours_tf"),
]
# règles internes (politique de la maison, pas du droit) : pas de vérification, étiquette [pratique maison]
REGLES_MAISON = [
    ("revue_lba", "Revue périodique du dossier LBA", 12, "mois", "derniere_revue", 30, "politique interne (OAR à préciser)"),
    ("resiliation_contrat", "Dernier jour pour résilier", 0, "jours", "resiliation_avant", 30, "contrat"),
    ("relance_pipeline", "Relance commerciale", 14, "jours", "dernier_contact", 0, "pratique maison"),
]

def _objet_regle(rid, lib, resume, source):
    from .objets import create
    create("regle_delai", lib, id=rid, resume=resume, source=source, domaine="délais", prochaine_action="vérifier contre le texte officiel")

def seed():
    con = db()
    for t, lib, n, u, dep, pre, rs, art, ext, doc in REGLES:
        r = con.execute("SELECT id FROM regles_delais WHERE type=?", (t,)).fetchone()
        if r:
            continue
        rid = new_id(con, "regle_delai")
        con.execute("INSERT INTO regles_delais(id,type,libelle,duree,unite,depuis,preavis_jours,source,article,extrait_attendu,document_type) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (rid, t, lib, n, u, dep, pre, f"RS {rs}", art, ext, doc))
        _objet_regle(rid, lib, f"{n} {u} dès {dep} — RS {rs} {art} ; extrait attendu « {ext} » ; non vérifiée tant que le texte officiel n'est pas ingéré", f"RS {rs} {art}")
    for t, lib, n, u, dep, pre, src in REGLES_MAISON:
        if con.execute("SELECT 1 FROM regles_delais WHERE type=?", (t,)).fetchone():
            continue
        rid = new_id(con, "regle_delai")
        con.execute("INSERT INTO regles_delais(id,type,libelle,duree,unite,depuis,preavis_jours,source,article,extrait_attendu,verifie_le,document_type,juridiction) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (rid, t, lib, n, u, dep, pre, src, "", "", "pratique maison", t, "maison"))
        _objet_regle(rid, lib, f"{n} {u} dès {dep} — {src} [pratique maison, pas une règle de droit]", src)
    con.commit()

def add_months(d, n):
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    import calendar
    return dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))

def report_jour_ouvrable(d):
    """samedi et dimanche reportés au lundi ; jours fériés cantonaux non connus → signalés"""
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d

def echeance(regle, declencheur):
    d = dt.date.fromisoformat(declencheur)
    if regle["unite"] == "mois":
        e = add_months(d, regle["duree"])
    else:
        e = d + dt.timedelta(days=regle["duree"])
    return report_jour_ouvrable(e)

def clock_start(type_, declencheur_date, client=None, dossier=None, canton=None, objet=None, acteur="agent"):
    """démarre une horloge : délai daté + document à préparer + prochaine action datée (préavis)"""
    seed()
    con = db()
    r = con.execute("SELECT * FROM regles_delais WHERE type=?", (type_,)).fetchone()
    if not r:
        return {"erreur": f"type de délai inconnu: {type_}", "types": [x[0] for x in con.execute("SELECT type FROM regles_delais")]}
    r = dict(r)
    ech = echeance(r, declencheur_date)
    verifie = bool(r["verifie_le"])
    reserve = "" if verifie else f"⚠ règle non vérifiée contre le texte officiel ({r['source']} {r['article']})"
    canton_note = "" if not canton else f" · jours fériés {canton} non pris en compte"
    nom = f"{r['libelle']}" + (f" — {objet}" if objet else "")
    pre = (ech - dt.timedelta(days=r["preavis_jours"] or 0)).isoformat()
    doc_id = create("document", f"Projet : {r['document_type'].replace('_', ' ')}" + (f" — {objet}" if objet else ""), client=client,
                    statut="à préparer", prochaine_action=f"rédiger avant {pre}", prochaine_date=pre,
                    resume=f"document préparé d'avance pour le délai {r['libelle']} (échéance {ech})", domaine="délais",
                    source=f"{r['source']} {r['article']}", liens=[dossier] if dossier else [],
                    body=f"# Projet : {r['document_type'].replace('_', ' ')}\n\n## Statut\nà préparer par la boucle d'initiative (gabarit {r['document_type']}).\n\n## Échéance\n{ech} ({r['libelle']}, {r['source']} {r['article']}) {reserve}\n")
    did = create("delai", nom, client=client, statut="ouvert", prochaine_action=f"préparer {doc_id}", prochaine_date=pre,
                 risque=(reserve or None), chiffre_cle=f"échéance {ech}", canton=canton, domaine="délais",
                 resume=f"{r['libelle']} : déclencheur {r['depuis']} le {declencheur_date} → échéance {ech} ; préavis {r['preavis_jours']} j{canton_note}. {reserve}",
                 source=f"{r['source']} {r['article']} ({r['id']})", liens=[(doc_id, "document"), (r["id"], "regle")] + ([dossier] if dossier else []),
                 typed=("delais", {"client": client, "dossier": dossier, "type": type_, "declencheur": r["depuis"], "declencheur_date": declencheur_date,
                                   "echeance": ech.isoformat(), "preavis_jours": r["preavis_jours"], "canton": canton, "regle": r["id"],
                                   "document": doc_id, "prolongeable": 0}))
    audit("horloge", did, f"{type_} {declencheur_date}→{ech}", acteur)
    return {"delai": did, "echeance": ech.isoformat(), "preavis": pre, "document": doc_id, "reserve": reserve or None}

def deadlines(days=30, canton=None, client=None):
    con = db()
    lim = (today() + dt.timedelta(days=days)).isoformat()
    q = "SELECT d.*, o.nom, o.risque FROM delais d JOIN objets o ON o.id=d.id WHERE d.statut='ouvert' AND d.echeance<=?"
    a = [lim]
    if canton:
        q += " AND d.canton=?"; a.append(canton)
    if client:
        q += " AND d.client=?"; a.append(client)
    rows = con.execute(q + " ORDER BY d.echeance", a).fetchall()
    out = []
    for r in rows:
        doc = get(r["document"]) if r["document"] else None
        out.append({"id": r["id"], "echeance": r["echeance"], "nom": r["nom"], "client": r["client"], "jours": (dt.date.fromisoformat(r["echeance"]) - today()).days,
                    "document": r["document"], "document_statut": doc["statut"] if doc else None, "reserve": r["risque"]})
    return out

def extensions_due(days=30):
    con = db()
    lim = (today() + dt.timedelta(days=days)).isoformat()
    return [dict(r) for r in con.execute("SELECT d.id,d.echeance,o.nom,d.client FROM delais d JOIN objets o ON o.id=d.id WHERE d.statut='ouvert' AND d.prolongeable=1 AND d.echeance<=? ORDER BY d.echeance", (lim,))]

def commitments_due(days=14):
    lim = (today() + dt.timedelta(days=days)).isoformat()
    return [dict(r) for r in db().execute("SELECT e.*, o.nom FROM engagements e JOIN objets o ON o.id=e.id WHERE e.statut='ouvert' AND e.du_le<=? ORDER BY e.du_le", (lim,))]

def lba_review_due(days=30):
    lim = (today() + dt.timedelta(days=days)).isoformat()
    return [dict(r) for r in db().execute("SELECT l.*, o.nom FROM dossiers_lba l JOIN objets o ON o.id=l.id WHERE COALESCE(l.prochaine_revue,'0000')<=? ORDER BY l.prochaine_revue", (lim,))]

def close(did, motif="fait"):
    db().execute("UPDATE delais SET statut=? WHERE id=?", (motif, did))
    db().commit()
    from .objets import update
    return update(did, statut=motif, prochaine_action="aucune", prochaine_date=iso())
