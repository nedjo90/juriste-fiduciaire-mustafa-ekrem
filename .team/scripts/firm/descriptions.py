#!/usr/bin/env python3
"""Short descriptions of subagents and skills (loaded on EVERY message: fixed token cost, law 3).
Rule: ≤ 160 characters, English, usage verb + trigger; Swiss legal terms kept in their language. Idempotent.
Usage: python descriptions.py [--verifier]. The builder applies the same rule to any new role or skill (.team/roles/builder.md)."""
import re, sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MAX = 160

AGENTS = {
    "archivist": "Memory upkeep: index, aliases, duplicates, condensation, client views, cross-links, health. Background task.",
    "litigator": "Argues as before a court: réclamations, recours, mises en demeure, replies to authorities.",
    "calculator": "Tax and estate calculations by script on sourced barèmes (IA, TVA, timbre, social charges, shares); assumptions sheet, Excel.",
    "chief-of-staff": "Daily brief and follow-up: deadlines, meetings, drafts ready, question and advice queues.",
    "researcher": "Sourced legal research, never from memory: table of authorities, case law, administrative practice, research note.",
    "business-developer": "Account plans, opportunities, flat fees, follow-ups and commercial proposals.",
    "communicator": "Delicate messages (bad news, conflict, crisis): SCQA, right tone, variants.",
    "foresight-advisor": "Foresight review of a client or document: unseen risks, implicit deadlines, opportunities.",
    "art-director": "Formats deliverables to the house style: templates, layout, visual check.",
    "source-checker": "Checks every citation against the library and official sources; source report, ⚠ otherwise.",
    "human-editor": "Edits a text so it reads human, in the house voice, without machine tics (FR/DE/IT/EN).",
    "builder": "Builds new skills and roles when a need recurs or a rule is set.",
    "ingester": "Processes dropped documents: reading, filing, linking, comment, deadlines triggered.",
    "marketer": "Client alerts, posts and FR/DE newsletters from law changes.",
    "negotiator": "Prepares a negotiation: interests, options, BATNA, concessions, script.",
    "compliance-officer": "LBA, beneficial owners, EAR/FATCA, data protection, conflicts: flags and prepares, never reports.",
    "adversarial-panel": "One grouped critical call on an important deliverable: opponent, judge, authority, difficult client, auditor.",
    "producer": "Produces the deliverable in final format (Word, Excel, PowerPoint, PDF, email, diagram) from templates.",
    "drafter": "Drafts memos, avis, letters and contracts at top-firm level, FR/DE/IT/EN, conclusion first.",
    "experience-lead": "Keeps Mustafa's experience simple: clear answers, no jargon or IDs, one question at a time; proposes fixes.",
    "proofreader": "Final review: defined terms, cross-references, figures, dates, canton, language, template, no internal notes.",
    "corporate-secretary": "General meetings, PV, circular resolutions, registers, RC filings, articles, shareholders' agreements.",
    "contracts-specialist": "Swiss contracts (CO): drafting, review, clauses, risks, annotated variants.",
    "foreign-law-specialist": "Foreign law (FR, DE, IT, UK, US, EU): verified text, limits, referral to local counsel.",
    "corporate-tax-specialist": "Federal and cantonal corporate tax: profit, capital, IA, restructurings, décisions de taxation.",
    "international-tax-specialist": "International tax: double tax treaties (CDI), permanent establishments, transfer pricing, withholding taxes.",
    "real-estate-specialist": "Real estate: acquisitions, Lex Koller, gains immobiliers, droits de mutation, leases.",
    "aml-specialist": "LBA and OAR: identification, beneficial owners, risk profile, periodic reviews.",
    "individual-tax-specialist": "Individual taxation and newcomers: income, wealth, forfait fiscal, impôt à la source.",
    "debt-enforcement-specialist": "LP: poursuites, opposition, mainlevée, faillite, concordat; deadlines.",
    "company-law-specialist": "Company law and commercial register: incorporation, bodies, capital, mergers (LFus), RC filings.",
    "estates-specialist": "Successions and matrimonial regimes: réserves, partage, pactes, gifts, business succession.",
    "employment-specialist": "Employment law and social insurance (AVS, LPP, LAA): contracts, terminations, contributions.",
    "vat-specialist": "TVA: liability, rates, returns, methods, corrections, AFC audits.",
    "strategist": "Case strategy: stakeholders, pre-mortem, options, timing.",
    "coach": "Weekly progress note and adjustments of the team's style and rules.",
    "legal-watch": "Legal watch: new laws, consolidations, circulars, case law; impact per client.",
    "visualizer": "Charts and diagrams with a message, unit and source (org charts, timelines, trees).",
}

SKILLS = {
    "law-change-alert": "Law change → drafted client alerts (clients affected, effect, dated actions), drafts only.",
    "spreadsheet-audit": "Audit an Excel workbook: formulas, hard-coded values, totals, sourced barèmes.",
    "daily-brief": "Daily brief or « où en est-on ? »: urgent items, deadlines, meetings, drafts ready, one question at most.",
    "fact-chronology": "Sourced chronology of a matter from its documents (litige, réclamation, audit, succession).",
    "meeting-report": "Report of a meeting or call: decisions, actions, deadlines triggered, client version.",
    "conflict-check": "Conflict check before a new mandate, client or party; flags without blocking.",
    "shareholders-agreement": "Draft or review a Swiss shareholders' or partners' agreement (convention d'actionnaires).",
    "circular-resolutions": "Circular resolution of a corporate body (décision circulaire): text, ballots, record.",
    "aml-file": "Open or review an LBA file: identification, beneficial owners, risk, documents; never reports.",
    "meeting-prep": "Meeting sheet the day before: participants, history, deadlines, documents, questions.",
    "amendment-history": "Current state of a contract across its amendments (avenants), clause by clause.",
    "humanizer": "Remove machine tics from an English text without changing its meaning.",
    "humanizer-de": "Deutschen Text (Schweiz) ohne Maschinenspuren überarbeiten, Inhalt unverändert.",
    "humanizer-fr": "Remove machine tics from a French (Suisse romande) text without changing its meaning.",
    "humanizer-it": "Togliere le tracce di macchina da un testo italiano (Svizzera), contenuto invariato.",
    "inbox-ingestion": "Document dropped in « À déposer »: reading, linking, comment, deadlines triggered.",
    "client-onboarding": "New client or mandate: companies, persons, conflicts, LBA, deadlines, no questionnaire.",
    "deliverable-production": "Produce a finished deliverable (Word, Excel, PowerPoint, PDF, email, diagram) from templates, checked.",
    "general-meeting-minutes": "Notice and PV of a general meeting or board meeting (SA, Sàrl), with follow-ups.",
    "sourced-legal-research": "Swiss or foreign law question: sourced research, table of authorities, reusable note.",
    "tax-objection": "Décision de taxation received: deadline, analysis, complete draft réclamation, never filed.",
    "email-drafting": "Draft a professional email in the recipient's language; never sent.",
    "legal-memo": "Swiss-law memo or avis de droit at top-firm level: summary, sourced law, options, comfort level.",
    "foresight-review": "Foresight review of a client or document: risks, implicit deadlines, opportunities.",
    "tabular-review": "Extract the same points from a batch of documents into a cited table (due diligence, leases).",
    "skill-creator": "Create or improve a skill (Anthropic method); used by the builder.",
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
