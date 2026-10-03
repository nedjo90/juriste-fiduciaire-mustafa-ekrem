---
type: calcul
client: C-001
objet: impot anticipe dividende
titre: Impôt anticipé sur le dividende 2026
langue: fr
sources: [BIB-001]
hypotheses:
  - {nom: dividende_brut, libelle: Dividende brut voté, valeur: 200000, unite: CHF, source: PV AG 30.09.2026 (fictif)}
  - {nom: taux_ia, libelle: Taux de l'impôt anticipé, valeur: 0.35, unite: "%", source: "BIB-001 ⚠ à vérifier"}
  - {nom: variation, libelle: Pas de sensibilité, valeur: 0.01, unite: "%", source: hypothèse de travail}
calculs:
  - {libelle: Impôt retenu, formule: dividende_brut*taux_ia, unite: CHF}
  - {libelle: Net versé, formule: "dividende_brut-{C1}", unite: CHF}
sensibilites: {hypothese: taux_ia, pas: [-2, -1, 0, 1, 2], ecart: variation, etape: 1}
---
