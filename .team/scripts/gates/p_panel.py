"""Porte (j) panel (§6.2, §4.16, critère 5) : un livrable important (mémo, avis, calcul, présentation, PV, convention,
contrat) a eu son appel adverse groupé : un enregistrement dans la table `panels` (clé du livrable ou identifiant) ou une
note « Panel — … » liée au livrable. Les autres types : sans objet. KO → renvoi au producteur (panel à tenir)."""
from gates_common import resultat, ETAT_OK, ETAT_KO, ETAT_NA
import common as C

IMPORTANTS = {"memo", "avis", "calcul", "presentation", "pv", "convention", "contrat"}
DDL = """CREATE TABLE IF NOT EXISTS panels(n INTEGER PRIMARY KEY AUTOINCREMENT, le TEXT, cle TEXT, livrable TEXT, note TEXT,
 modele TEXT, tokens INTEGER, constats INTEGER, majeurs INTEGER, statut TEXT);
CREATE INDEX IF NOT EXISTS ix_panels_cle ON panels(cle);"""


def _con():
    core = C.cb()[0]
    con = core.db()
    con.executescript(DDL)
    return core, con


def enregistrer(cle, livrable, note, modele, tokens, constats, majeurs, statut="tenu"):
    core, con = _con()
    con.execute("INSERT INTO panels(le,cle,livrable,note,modele,tokens,constats,majeurs,statut) VALUES(?,?,?,?,?,?,?,?,?)",
                (core.stamp(), cle, livrable, note, modele, tokens, constats, majeurs, statut))
    con.commit()


def trouver(cle=None, livrable=None):
    core, con = _con()
    r = con.execute("SELECT * FROM panels WHERE statut='tenu' AND ((cle=? AND ?<>'') OR (livrable=? AND ?<>'')) ORDER BY n DESC LIMIT 1",
                    (cle or "", cle or "", livrable or "", livrable or "")).fetchone()
    if r:
        return dict(r)
    if livrable:  # repli : note « Panel — » liée au livrable (créée à la main par un rôle)
        r = con.execute("SELECT o.id FROM liens l JOIN objets o ON o.id IN (l.src, l.dst) AND o.id<>? "
                        "WHERE (l.src=? OR l.dst=?) AND o.type='note' AND o.nom LIKE 'Panel %'", (livrable, livrable, livrable)).fetchone()
        if r:
            return {"note": r[0], "livrable": livrable}
    return None


def verifier(doc, ctx=None):
    ctx = ctx or {}
    typ = (doc.get("type") or "").lower()
    if typ not in IMPORTANTS:
        return resultat(ETAT_NA, [f"type « {typ or '?'} » : pas d'appel adverse requis"])
    try:
        p = trouver(ctx.get("cle") or doc.get("meta", {}).get("cle"), ctx.get("livrable") or doc.get("meta", {}).get("livrable"))
    except Exception as e:
        return resultat(ETAT_NA, [f"registre des panels illisible ({e.__class__.__name__}) : réserve"], reserves=1)
    if not p:
        motif = ctx.get("panel_saute")
        return resultat(ETAT_KO, ["livrable important sans appel adverse groupé" + (f" ({motif})" if motif else "")],
                        [{"probleme": "panel non tenu", "correction": "produce.py sans --sans-panel (un appel groupé, modèle le plus capable)"}])
    return resultat(ETAT_OK, [f"panel tenu : note {p.get('note') or '?'}" + (f", {p['constats']} constat(s) dont {p['majeurs']} majeur(s)" if p.get("constats") is not None else "")])
