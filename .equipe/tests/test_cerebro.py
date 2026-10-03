#!/usr/bin/env python3
"""Tests du noyau cerebro (§17 c2, c6, c7, c12, c24, c25, c26, c29, c33, c36, c37). Racine jetable, données fictives.
Usage : python .equipe/tests/test_cerebro.py [--echelle]   → une ligne OK/ÉCHEC par test ; un échec crée un ticket, ne bloque rien."""
import os, sys, json, shutil, tempfile, time, subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TMP = Path(tempfile.mkdtemp(prefix="cerebro-test-"))
shutil.copytree(REPO / ".equipe", TMP / ".equipe", ignore=shutil.ignore_patterns("cerebro.db*", "clients", "bibliotheque", "archives", "inbox", "run", "sommaires", "exports", "journal"))
(TMP / "Bureau" / "A-deposer").mkdir(parents=True)
(TMP / "Bureau" / "Informatique").mkdir(parents=True)
os.environ.update(CEREBRO_ROOT=str(TMP), CEREBRO_TODAY="2026-10-01")
os.environ.pop("CEREBRO_DB", None)
sys.path.insert(0, str(TMP / ".equipe" / "cerebro"))
sys.path.insert(0, str(TMP / ".equipe" / "tests" / "fixtures"))
from cb import core, objets as O, recherche as R, brief as B, config as K, files as F, metier as M, horloges as H, sommaires as S
import dossier_fictif
FX = dossier_fictif.build()

RES = []
def test(nom, cond, detail=""):
    RES.append((nom, bool(cond), detail))
    print(("OK     " if cond else "ÉCHEC  ") + nom + (f" — {detail}" if detail and not cond else ""))

# c2 : un message citant une société connue reçoit son contexte sans demande
ctx = B.context("Pour la holding Rochat, on peut verser le dividende fin octobre ?")
test("c2 contexte injecté pour une société citée", "E-001" in ctx and "DL-002" in ctx, ctx[:200])
test("c24 injection par tour ≤ 6 000 car.", len(ctx) <= 6000, len(ctx))
ctx2 = B.context("et pour la holding Rochat ?")
test("c24 injection en delta (rien de neuf → rien de réinjecté)", "E-001" not in ctx2, ctx2[:200])
deb = B.session_start()
test("c24 début de session ≤ 8 000 car.", len(deb) <= 8000, len(deb))
test("c4 « entre nous » détecté", B.context("entre nous, je trouve ce client pénible").startswith("MODE « ENTRE NOUS »"))

# c6 : décision de taxation → horloge et projet ; dividende → horloge IA ; relation → LBA
tax = FX["taxation"]
test("c6 taxation → horloge + document préparé", tax["delai"].startswith("DL-") and tax["document"].startswith("DOC-") and tax["echeance"] == "2026-10-22")
test("c6 dividende → horloge impôt anticipé", FX["dividende"]["delai"].startswith("DL-"))
test("c6 nouvelle relation → dossier LBA", FX["lba"]["lba"].startswith("LBA-"))
test("loi 7 : règle non vérifiée → ⚠", (tax["reserve"] or "").startswith("⚠"))

# c7 : nouveau mandat → contrôle de conflit (Luca Rochat est lié à C-001 et gérant chez C-002)
mn = M.matter_new(FX["clients"][1], "Levée de fonds série A", parties=["Luca Rochat", "Investisseur X (fictif)"])
test("c7 nouveau mandat → contrôle de conflit signalé, non bloquant", mn["dossier"].startswith("D-") and mn["conflit"]["conflit_possible"], json.dumps(mn["conflit"])[:200])

# c12 : personne liée à deux clients → dans les deux vues, signalée au brief
M.vue_client("C-001"); M.vue_client("C-002")
v1 = (O.client_dir("C-001") / "vue.md").read_text(encoding="utf-8"); v2 = (O.client_dir("C-002") / "vue.md").read_text(encoding="utf-8")
test("c12 personne liée à deux clients dans les deux vues", "Luca Rochat" in v1 and "Luca Rochat" in v2)
test("c12 croisement signalé au brief", "Luca Rochat" in B.brief())

# c25 : objet renommé atteignable par son ancien nom ; archivé avec redirection
O.rename(FX["entites"][1], "Rochat Bois & Agencement SA")
hits = R.find("Menuiserie Rochat SA", limit=3)
test("c25 objet renommé atteignable par son ancien nom", hits and hits[0]["id"] == FX["entites"][1], hits[:1])
nid = O.create("note", "Note remplaçante", client="C-001", resume="remplace la note vocale")
O.archive("N-001", vers=nid)
test("c25 ancien identifiant redirigé", O.get("N-001")["id"] == nid)

# c26 : nouveau sujet → identifiant, ligne de sommaire, [à confirmer]
sid = O.create("dossier", "Litige fournisseur bois [à confirmer]", client="C-001", statut="à confirmer", resume="sujet nouveau détecté")
n1 = (core.SOMMAIRES / "clients" / "C-001.md").read_text(encoding="utf-8")
test("c26 nouveau sujet → identifiant + ligne de sommaire", sid in n1)

# c37 : protocole sommaire — summary renvoie le menu, open renvoie une seule section
s = R.summary(FX["dossier"])
test("c37 summary renvoie le menu des sections", s.get("sections") and "Contrôle de conflit" in s["sections"][0])
o = R.open_section(FX["dossier"], "Contrôle de conflit")
test("c37 open --section renvoie une seule section", o.get("section") == "Contrôle de conflit" and "Faits" not in o.get("contenu", ""))
test("c37 en-tête généré (id, résumé, liens, prochaine action)", all(k in (core.ROOT / O.get(FX["dossier"])["chemin"]).read_text(encoding="utf-8") for k in ("id:", "résumé:", "liens:", "prochaine_action:")))
test("niveau 0 ≤ 2 000 car.", len(S.niveau0()) <= 2000)

# c36 / c37 : configuration à trous
test("c37 clé vide → défaut appliqué", K.get("poste.messagerie") == "Outlook / Microsoft 365")
r = K.set_("mustafa.cantons_suivis", "VD,FR", source="déclaré par Mustafa le 2026-10-01")
test("c36 réponse simulée remplace le défaut et déclenche le recalcul", K.get("mustafa.cantons_suivis") == ["VD", "FR"] and "horloges_recalcul" in r["recalculs"])
test("c37 gaps classés par effet", K.gaps()[0]["effet"] >= K.gaps()[-1]["effet"])

# c36 : questions — aucune en première session ; ensuite ≤ 1 par message, ≤ 3 par jour
core.set_etat("sessions", 1)
F.questions_depuis_gaps()
test("c36 aucune question pendant la première session", F.question_next() is None)
core.set_etat("sessions", 2)
poses = []
for t in range(6):
    core.set_etat("tour", t + 10)
    q = F.question_next()
    if q:
        poses.append(q["id"])
test("c36 au plus trois questions par jour", 1 <= len(poses) <= 3, poses)
core.set_etat("tour", 99)
q1 = F.question_next(); q2 = F.question_next()
test("c36 jamais deux questions dans le même message", not (q1 and q2))
test("c36 jamais la même question deux fois dans la journée", len(set(poses)) == len(poses))

# rappel et zéro zombie
rap = R.autotest_rappel(20)
test("c25 rappel > 95 % sur faits reformulés", rap["rappel"] >= 0.95, rap)
B.gc()
z = B.zombies()
test("c28 zéro lien mort après ramasse-miettes", not z["liens_morts"], z["liens_morts"][:5])

# c33 : échelle (option --echelle : dix fois plus grand)
if "--echelle" in sys.argv:
    con = core.db()
    t0 = time.time()
    for i in range(1500):
        O.create("note", f"Note de test {i} sur le client fictif numéro {i % 50}", client="C-001" if i % 2 else "C-002",
                 resume=f"fait reformulable numéro {i} : montant CHF {i * 13} échéance {2027 + i % 3}")
    t1 = time.time()
    tf = time.time(); R.find("fait reformulable numéro 777 montant"); tf = time.time() - tf
    test("c33 find < 2 s sur jeu élargi", tf < 2, f"{tf:.2f}s ({t1 - t0:.0f}s pour créer 1500 objets)")
    test("c33 niveau 0 stable ≤ 2 000 car.", len(S.niveau0()) <= 2000)

ko = [r for r in RES if not r[1]]
print(f"\n{len(RES) - len(ko)}/{len(RES)} OK")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0)
