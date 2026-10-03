"""Tableau de bord des principes (§7.5) : chaque passage aux portes est enregistré (table `portes_passages`
de la base cerebro + `mesures` via cerebro mesure) ; taux de passage du premier coup par rôle, skill et porte.
python tableau.py [--jours 30]  → JSON {par_role, par_skill, par_porte, ecarts}"""
import sys, json, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "producteur"))
import commun as C

DDL = """CREATE TABLE IF NOT EXISTS portes_passages(n INTEGER PRIMARY KEY AUTOINCREMENT, le TEXT, livrable TEXT, cle TEXT,
 role TEXT, skill TEXT, porte TEXT, etat TEXT, premier_coup INTEGER, nb_corrections INTEGER, details TEXT);
CREATE INDEX IF NOT EXISTS ix_pp_cle ON portes_passages(cle, porte);"""
SEUIL_ECART = 0.8  # en dessous : écart signalé à la fabrique


def _db():
    core, _, _, _ = C.cb()
    con = core.db()
    con.executescript(DDL)
    return core, con


def enregistrer(livrable, cle, role, skill, res):
    """res = sortie de portes.py ; premier_coup = premier passage de cette clé (livrable sans version) à cette porte"""
    try:
        core, con = _db()
        le = core.stamp()
        for porte, r in res.get("portes", {}).items():
            if r["etat"] == "na":
                continue
            deja = con.execute("SELECT 1 FROM portes_passages WHERE cle=? AND porte=?", (cle, porte)).fetchone()
            con.execute("INSERT INTO portes_passages(le,livrable,cle,role,skill,porte,etat,premier_coup,nb_corrections,details) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (le, str(livrable), cle, role or "?", skill or "?", porte, r["etat"], 0 if deja else 1, len(r.get("corrections", [])),
                         json.dumps(r.get("details", [])[:3], ensure_ascii=False)[:500]))
        con.commit()
        from cb import files as F
        ok = int(all(r["etat"] != "ko" for r in res.get("portes", {}).values()))
        F.mesure(role or "?", f"portes:{skill or '?'}", "script", 0, int(res.get("duree_ms", 0)), ok)
        return True
    except Exception as e:
        C.journal("erreurs-portes", op="enregistrer", erreur=repr(e))
        return False


def tableau(jours=30):
    core, con = _db()
    import datetime as dt
    depuis = (C.today() - dt.timedelta(days=jours)).isoformat()
    def agr(col):
        out = {}
        for r in con.execute(f"SELECT {col} k, COUNT(*) n, SUM(etat='ok') ok FROM portes_passages WHERE premier_coup=1 AND le>=? GROUP BY {col}", (depuis,)):
            out[r["k"]] = {"passages": r["n"], "premier_coup_ok": r["ok"], "taux": round(r["ok"] / r["n"], 3) if r["n"] else None}
        return out
    res = {"periode_jours": jours, "par_role": agr("role"), "par_skill": agr("skill"), "par_porte": agr("porte")}
    res["ecarts"] = [{"axe": axe, "nom": k, "taux": v["taux"]} for axe in ("par_role", "par_skill") for k, v in res[axe].items()
                     if v["taux"] is not None and v["taux"] < SEUIL_ECART and v["passages"] >= 3]
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--jours", type=int, default=30)
    print(json.dumps(tableau(ap.parse_args().jours), ensure_ascii=False))
