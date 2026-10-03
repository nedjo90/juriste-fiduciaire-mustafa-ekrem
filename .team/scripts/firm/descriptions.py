#!/usr/bin/env python3
"""Descriptions courtes des sous-agents et skills (chargées à CHAQUE message : coût fixe en tokens, loi 3).
Règle : ≤ 160 caractères, verbe d'usage + déclencheur. Idempotent. Usage : python descriptions.py [--verifier]
La fabrique applique la même règle à tout nouveau rôle ou skill (voir .team/roles/builder.md)."""
import re, sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MAX = 160

AGENTS = {
    "archivist": "Entretien de la mémoire : index, alias, doublons, condensation, vues client, croisements, santé. Tâche de fond.",
    "litigator": "Argumente comme devant un tribunal : réclamations, recours, mises en demeure, réponses à l'administration.",
    "calculator": "Calculs fiscaux et successoraux par script sur barèmes sourcés (IA, TVA, timbre, charges, parts) ; feuille d'hypothèses, Excel.",
    "chief-of-staff": "Brief du jour et suivi : délais, rendez-vous, brouillons prêts, file des questions et conseils.",
    "researcher": "Recherche juridique sourcée, jamais de mémoire : table des autorités, jurisprudence, pratique de l'administration, note de recherche.",
    "business-developer": "Plan de compte, opportunités, forfaits, relances et propositions commerciales.",
    "communicator": "Messages délicats (mauvaise nouvelle, conflit, crise) : SCQA, ton juste, variantes.",
    "foresight-advisor": "Revue d'anticipation d'un client ou d'un document : risques non vus, délais implicites, opportunités.",
    "art-director": "Mise en forme des livrables selon la charte : gabarits, mise en page, contrôle visuel.",
    "source-checker": "Vérifie chaque citation contre la bibliothèque et les sources officielles ; rapport de sources, ⚠ sinon.",
    "human-editor": "Relit un texte pour qu'il sonne humain, dans la voix de la maison, sans tic de machine (FR/DE/IT/EN).",
    "builder": "Fabrique de nouvelles skills et de nouveaux rôles quand un besoin revient ou qu'une règle est posée.",
    "ingester": "Traite les documents déposés : lecture, classement, rattachement, commentaire, délais nés.",
    "marketer": "Alertes clients, posts et newsletters FR/DE à partir des changements de droit.",
    "negotiator": "Prépare une négociation : intérêts, options, BATNA, concessions, script.",
    "compliance-officer": "LBA, ayants droit, EAR/FATCA, protection des données, conflits : signale et prépare, ne communique jamais.",
    "adversarial-panel": "Un seul appel critique groupé sur un livrable important : contradicteur, juge, administration, client difficile, réviseur.",
    "producer": "Produit le livrable au format final (Word, Excel, PowerPoint, PDF, mail, schéma) depuis les gabarits.",
    "drafter": "Rédige mémos, avis, lettres et contrats au niveau grande étude, FR/DE/IT/EN, conclusion d'abord.",
    "experience-lead": "Veille à ce que Mustafa vive l'équipe simplement : réponses claires, sans jargon ni identifiant, une question à la fois ; propose les corrections.",
    "proofreader": "Dernière relecture : termes définis, renvois, chiffres, dates, canton, langue, gabarit, aucune note interne.",
    "corporate-secretary": "Assemblées, PV, décisions circulaires, registres, réquisitions RC, statuts, conventions d'actionnaires.",
    "contracts-specialist": "Contrats suisses (CO) : rédaction, revue, clauses, risques, variantes commentées.",
    "foreign-law-specialist": "Droit étranger (FR, DE, IT, UK, US, UE) : texte vérifié, limites, renvoi à un conseil local.",
    "corporate-tax-specialist": "Fiscalité fédérale et cantonale des sociétés : bénéfice, capital, IA, restructurations, décisions de taxation.",
    "international-tax-specialist": "Fiscalité internationale : CDI, établissements stables, prix de transfert, retenues à la source.",
    "real-estate-specialist": "Immobilier : acquisitions, Lex Koller, gains immobiliers, droits de mutation, baux.",
    "aml-specialist": "LBA et OAR : identification, ayants droit, profil de risque, revues périodiques.",
    "individual-tax-specialist": "Impôts des personnes physiques et arrivants : revenu, fortune, forfait, impôt à la source.",
    "debt-enforcement-specialist": "LP : poursuites, opposition, mainlevée, faillite, concordat ; délais.",
    "company-law-specialist": "Droit des sociétés et registre du commerce : fondation, organes, capital, fusion (LFus), réquisitions.",
    "estates-specialist": "Successions et régimes matrimoniaux : réserves, partage, pactes, donations, transmission d'entreprise.",
    "employment-specialist": "Droit du travail et assurances sociales (AVS, LPP, LAA) : contrats, fins de rapports, cotisations.",
    "vat-specialist": "TVA : assujettissement, taux, décomptes, méthodes, corrections, contrôles AFC.",
    "strategist": "Stratégie d'un dossier : parties prenantes, pre-mortem, options, timing.",
    "coach": "Note hebdomadaire de progression et ajustements du style et des règles de l'équipe.",
    "legal-watch": "Veille juridique : nouvelles lois, consolidations, circulaires, jurisprudence ; impacts par client.",
    "visualizer": "Graphiques et schémas avec message, unité et source (organigrammes, chronologies, arbres).",
}

SKILLS = {
    "law-change-alert": "Changement de droit → alertes clients rédigées (clients touchés, effet, actions datées), brouillons seulement.",
    "spreadsheet-audit": "Auditer un classeur Excel : formules, valeurs en dur, totaux, barèmes sourcés.",
    "daily-brief": "Brief du jour ou « où en est-on ? » : urgences, délais, rendez-vous, brouillons prêts, une question au plus.",
    "fact-chronology": "Chronologie sourcée d'un dossier à partir des documents (litige, réclamation, contrôle, succession).",
    "meeting-report": "Compte rendu d'un rendez-vous ou d'un appel : décisions, actions, délais nés, version client.",
    "conflict-check": "Contrôle de conflit avant un nouveau mandat, client ou partie ; signale sans bloquer.",
    "shareholders-agreement": "Rédiger ou revoir une convention d'actionnaires ou d'associés suisse.",
    "circular-resolutions": "Décision d'un organe par voie de circulation : texte, bulletins, constatation.",
    "aml-file": "Ouvrir ou revoir un dossier LBA : identification, ayants droit, risque, pièces ; jamais de communication.",
    "meeting-prep": "Fiche de rendez-vous la veille : participants, historique, délais, documents, questions.",
    "amendment-history": "État actuel d'un contrat à travers ses avenants, clause par clause.",
    "humanizer": "Retirer les tics de machine d'un texte anglais sans en changer le sens.",
    "humanizer-de": "Deutschen Text (Schweiz) ohne Maschinenspuren überarbeiten, Inhalt unverändert.",
    "humanizer-fr": "Retirer les tics de machine d'un texte français (Suisse romande) sans en changer le sens.",
    "humanizer-it": "Togliere le tracce di macchina da un testo italiano (Svizzera), contenuto invariato.",
    "inbox-ingestion": "Document déposé dans « À déposer » : lecture, rattachement, commentaire, délais nés.",
    "client-onboarding": "Nouveau client ou mandat : sociétés, personnes, conflits, LBA, échéances, sans questionnaire.",
    "deliverable-production": "Sortir un livrable fini (Word, Excel, PowerPoint, PDF, mail, schéma) depuis les gabarits, contrôlé.",
    "general-meeting-minutes": "Convocation et PV d'assemblée ou de séance d'organe (SA, Sàrl), avec les suites.",
    "sourced-legal-research": "Question de droit suisse ou étranger : recherche sourcée, table des autorités, note réutilisable.",
    "tax-objection": "Décision de taxation reçue : délai, analyse, projet de réclamation complet, jamais déposé.",
    "email-drafting": "Brouillon de mail professionnel dans la langue du destinataire ; jamais envoyé.",
    "legal-memo": "Mémo ou avis de droit suisse au niveau grande étude : résumé, droit sourcé, options, confort.",
    "foresight-review": "Revue d'anticipation d'un client ou d'un document : risques, délais implicites, opportunités.",
    "tabular-review": "Extraire les mêmes points d'un lot de documents dans un tableau cité (due diligence, baux).",
    "skill-creator": "Créer ou améliorer une skill (méthode Anthropic) ; utilisé par la fabrique.",
}
# rarement utiles à un juriste : en sommeil hors de .claude/skills (coût nul), réveillées par la fabrique au besoin
DORMANTES = ["canvas-design", "theme-factory", "frontend-design", "internal-comms", "doc-coauthoring", "brand-guidelines"]

def _set_desc(p, desc):
    t = p.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---", t, re.S)
    if not m:
        return False
    head = m.group(1)
    lines, out, skip = head.split("\n"), [], False
    for l in lines:
        if re.match(r"^description\s*:", l):
            out.append("description: " + json.dumps(desc, ensure_ascii=False))  # citée : les « : » ne cassent pas le YAML
            skip = True
            continue
        if skip and (l.startswith(" ") or l.startswith("\t")):
            continue  # suite d'une description multiligne
        skip = False
        out.append(l)
    nt = "---\n" + "\n".join(out) + "\n---" + t[m.end():]
    if nt != t:
        p.write_text(nt, encoding="utf-8")
        return True
    return False

def main():
    verifier = "--verifier" in sys.argv
    trop, faits = [], 0
    for nom, d in {**{f".claude/agents/{k}.md": v for k, v in AGENTS.items()}, **{f".claude/skills/{k}/SKILL.md": v for k, v in SKILLS.items()}}.items():
        assert len(d) <= MAX, (nom, len(d))
        p = ROOT / nom
        if p.exists() and not verifier:
            faits += _set_desc(p, d)
    dorm = ROOT / ".team" / "dormant-skills"
    for s in DORMANTES:
        src = ROOT / ".claude" / "skills" / s
        if src.exists() and not verifier:
            dorm.mkdir(parents=True, exist_ok=True)
            if (dorm / s).exists():
                import shutil; shutil.rmtree(dorm / s)
            src.rename(dorm / s)
    for p in list((ROOT / ".claude" / "agents").glob("*.md")) + list((ROOT / ".claude" / "skills").glob("*/SKILL.md")):
        m = re.search(r"^description:\s*(.*)$", p.read_text(encoding="utf-8"), re.M)
        if m and len(m.group(1)) > MAX + 20:
            trop.append(f"{p.relative_to(ROOT)} ({len(m.group(1))})")
    print({"modifies": faits, "dormantes": DORMANTES, "trop_longues": trop})

if __name__ == "__main__":
    main()
