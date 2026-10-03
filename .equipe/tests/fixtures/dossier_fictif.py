"""Données de répétition (§3) : dossier client fictif complet. Toutes les personnes et sociétés sont inventées.
Usage : CEREBRO_DB=<base de test> python dossier_fictif.py   (ne jamais lancer sur la base réelle de Mustafa)"""
import os, sys, json
from pathlib import Path
HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[2] / "cerebro"))
from cb import core
from cb.objets import create, link, add_alias, get
from cb import metier as M, horloges as H, files as F

FICTIF = "[FICTIF] "

BASE = "2026-10-01"  # dates du scénario écrites pour ce jour ; recalées si le jour simulé ou réel est autre

def _decaler(today):
    import datetime as dt, re as _re
    delta = dt.date.fromisoformat(today) - dt.date.fromisoformat(BASE)
    def D(s):
        return (dt.date.fromisoformat(s) + delta).isoformat()
    return D

def CH(iso_):
    y, m, d = iso_.split("-")
    return f"{d}.{m}.{y}"

def build(today=None):
    today = today or os.environ.get("CEREBRO_TODAY") or BASE
    os.environ["CEREBRO_TODAY"] = today
    global D
    D = _decaler(today)
    H.seed()
    # --- client 1 : groupe familial vaudois
    c1 = M.client_new("Famille Rochat-Vuilleumier", forme="groupe familial", canton="VD", alias=["Rochat", "groupe Rochat"],
                      resume=FICTIF + "Groupe familial vaudois : holding, société d'exploitation (menuiserie), immobilier ; succession à préparer.")
    pA = M.person_new("Jean-Marc Rochat", client=c1, canton="VD", domicile="Échallens", alias=["JMR", "M. Rochat"], resume=FICTIF + "Fondateur, 64 ans, administrateur président des deux sociétés.")
    pB = M.person_new("Sandrine Vuilleumier", client=c1, canton="VD", domicile="Échallens", alias=["Mme Vuilleumier"], resume=FICTIF + "Épouse de J.-M. Rochat, régime de la participation aux acquêts.")
    pC = M.person_new("Luca Rochat", client=c1, canton="GE", domicile="Carouge", resume=FICTIF + "Fils, ingénieur, repreneur pressenti de la menuiserie.")
    h1 = M.entity_new("Rochat Holding SA", c1, "SA", "CHE-000.000.001", "Échallens", "VD", "12-31", alias=["Rochat Holding", "la holding"],
                      organes=[{"personne": pA, "fonction": "président du CA", "signature": "individuelle"}, {"personne": pB, "fonction": "administratrice", "signature": "collective à deux"}],
                      resume=FICTIF + "Holding de participations, capital CHF 100'000, détient 100 % de la menuiserie et un immeuble à Yverdon.")
    e1 = M.entity_new("Menuiserie Rochat SA", c1, "SA", "CHE-000.000.002", "Échallens", "VD", "12-31", alias=["la menuiserie", "Menuiserie Rochat"],
                      organes=[{"personne": pA, "fonction": "administrateur unique", "signature": "individuelle"}],
                      resume=FICTIF + "Société d'exploitation, 18 collaborateurs, chiffre d'affaires ~ CHF 3,2 mio.")
    M.participation(pA, h1, 60, True, "registre des actions (fictif)")
    M.participation(pB, h1, 40, True, "registre des actions (fictif)")
    M.participation(h1, e1, 100, False, "registre des actions (fictif)")
    d1 = M.matter_new(c1, "Transmission de la menuiserie à Luca Rochat", parties=["Luca Rochat", "Banque Cantonale (fictive)"], canton="VD", domaine="successions")["dossier"]
    tax = M.event_taxation(c1, h1, "Administration cantonale des impôts VD", "VD", "2025", D("2026-09-22"), 48250.0)
    div = M.event_dividende(c1, h1, D("2026-09-30"), 200000)
    lba1 = M.event_relation(c1, "Rochat Holding SA", "normal")
    ct = create("contrat", "Bail commercial — dépôt de Cheseaux", client=c1, liens=[e1], prochaine_action="résiliation à décider", prochaine_date=D("2026-11-15"),
                resume=FICTIF + f"Bail commercial de la menuiserie, échéance {CH(D('2027-03-31'))}, préavis 6 mois → résilier avant le {CH(D('2026-09-30'))} ? À vérifier.",
                typed=("contrats", {"client": c1, "parties": "Menuiserie Rochat SA / SI Les Pins (fictive)", "objet": "bail dépôt", "debut": D("2022-04-01"), "fin": D("2027-03-31"), "preavis": "6 mois", "resiliation_avant": D("2026-09-30")}))
    m1 = create("mail", "Re: dividende 2026 et impôt anticipé", client=c1, statut="attente", liens=[pA, h1], prochaine_action="répondre (brouillon)", prochaine_date=D("2026-10-02"),
                resume=FICTIF + "J.-M. Rochat demande si le dividende de CHF 200'000 voté le 30.09 peut être versé avant la fin octobre et ce qu'il faut annoncer.",
                body="# Re: dividende 2026 et impôt anticipé\n\n## Message\nBonjour Monsieur Ekrem,\nL'assemblée a voté hier un dividende de 200'000 francs. Pouvons-nous le verser avant fin octobre ? Faut-il annoncer quelque chose ?\nMeilleures salutations\nJean-Marc Rochat\n\n## Métadonnées\nde: jm.rochat@exemple.ch · reçu le {D('2026-10-01')} · langue fr\n")
    doc1 = create("document", "PV assemblée générale 2026 Rochat Holding", client=c1, liens=[h1], prochaine_action="classer", prochaine_date=D("2026-10-15"),
                  resume=FICTIF + f"PV de l'AG ordinaire du {CH(D('2026-09-30'))} : approbation des comptes 2025, dividende CHF 200'000, décharge.", source="Bureau/A-deposer (fictif)")
    nv = create("note", "Note vocale — appel J.-M. Rochat sur la succession", client=c1, liens=[d1, pA, pC], prochaine_action="compte rendu", prochaine_date=D("2026-10-03"),
                resume=FICTIF + "Transcription : souhaite transmettre la menuiserie à Luca d'ici 2028, se demande si une donation des actions de la holding est possible sans impôt.")
    rdv = create("rdv", "Rendez-vous Rochat — planification successorale", client=c1, liens=[d1, pA, pB], prochaine_action="fiche la veille", prochaine_date=D("2026-10-02"), statut="fiche à préparer",
                 resume=FICTIF + f"RDV au cabinet le {CH(D('2026-10-02'))} à 14h00 avec J.-M. Rochat et S. Vuilleumier.")
    # --- client 2 : PME genevoise, lien croisé (Luca Rochat y est administrateur)
    c2 = M.client_new("Lémantech Sàrl", forme="Sàrl", canton="GE", alias=["Lemantech", "Lémantech"], resume=FICTIF + "Start-up genevoise de capteurs, levée de fonds en cours, TVA trimestrielle.")
    e2 = M.entity_new("Lémantech Sàrl", c2, "Sàrl", "CHE-000.000.003", "Carouge", "GE", "12-31", organes=[{"personne": pC, "fonction": "gérant", "signature": "individuelle"}],
                      resume=FICTIF + "Sàrl, capital CHF 20'000 ; gérant Luca Rochat.")
    link(e2, pC, "gérant")
    H.clock_start("decompte_tva", D("2026-09-30"), client=c2, canton="GE", objet="T3 2026")
    M.pipeline_add(c2, "Accompagnement levée de fonds (convention d'actionnaires)", 15000)
    M.engagement_add(c2, "Luca Rochat", "envoyer projet de convention d'actionnaires", D("2026-10-09"))
    core.db().commit()
    return {"clients": [c1, c2], "personnes": [pA, pB, pC], "entites": [h1, e1, e2], "dossier": d1, "taxation": tax, "dividende": div, "lba": lba1, "mail": m1}

if __name__ == "__main__":
    if not os.environ.get("CEREBRO_DB") and not os.environ.get("CEREBRO_ROOT"):
        import tempfile
        os.environ["CEREBRO_DB"] = str(Path(tempfile.mkdtemp(prefix="fictif-")) / "fictif.db")
        core.DB_PATH = None
        print(f"(base fictive isolée : {os.environ['CEREBRO_DB']} — la base réelle n'est pas touchée)", file=sys.stderr)
    print(json.dumps(build(), ensure_ascii=False))
