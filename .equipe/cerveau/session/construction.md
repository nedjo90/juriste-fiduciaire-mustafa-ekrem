# construction — tableau de bord (machine)
# format: [ticket] etape · chantier · statut(todo|wip|done|debt) · cycle(T=tests,R=relu,A=adverse) · écarts · prochaine action
maj: 2026-10-03
environnement: machine distante (conteneur cloud Linux) → construire le portable, livrer par git (section 2)
branche_livraison: ccr-e8f5838b-808ukj
dernier_point: étapes 0-3 noyau faits ; agents en cours : plomberie (T-012..016), bibliothèque (T-040), production (T-051/T-060), équipe (T-050/T-052/T-070/T-100)

[T-000] 0 · persistance (constitution, construction, backlog, CLAUDE.md reprise) · done · T · - · -
[T-001] 0 · config à trous + défauts + profil + environnement · done · T · - · -
[T-002] 0 · fiche substrat testée (DOSSIER-TECHNIQUE) · done · T · - · -
[T-003] 0 · dossier client fictif · done · T · - · -
[T-004] 0 · socle outils (python libs, LibreOffice, MCP) · todo · - · - · inventorier
[T-010] 1 · CLI cerebro + base SQLite + ids + en-têtes + sommaires · done · T(30/30) · relecture et adverse à faire · -
[T-011] 1 · serveur MCP local cerebro · done · T · - · -
[T-012] 1 · hooks non bloquants (début, message, fin, compaction, après outil, fin de session) · todo
[T-013] 1 · filtre vocabulaire journalisant · todo
[T-014] 1 · settings.json permissif sans deny + config-valide · todo
[T-015] 1 · intendant + greffier (fond, claude -p) · todo
[T-016] 1 · lanceurs (.bat .ps1 .command) + installateurs (ps1, sh) · todo
[T-020] 2 · ingesteur (À déposer) + onboarding par initiative · done · T · - · -
[T-021] 2 · vues client 360 + croisements · done · T · - · -
[T-030] 3 · brief + délais + horloges + documents préparés · done · T · règles à vérifier (bibliothèque) · -
[T-031] 3 · boucle d'initiative + cycle d'entretien (file, verrou) · wip · T(initiative réelle OK) · cycle : agent plomberie · -
[T-040] 4 · bibliothèque juridique (Fedlex SPARQL, ingest, asof) · todo
[T-050] 5 · fiches méthodes · todo
[T-051] 5 · producteur + système de design + gabarits docx/xlsx/pptx/pdf · todo
[T-052] 5 · rôles juridiques + skills de rédaction/société · todo
[T-053] 5 · calculateur (scripts, barèmes versionnés) · todo
[T-060] 6 · portes déterministes + appel adverse groupé + relecteur · todo
[T-070] 7 · stratège, commercial, négociateur, marketeur, communicant · todo
[T-080] 8 · plugins officiels, recherche académique, veilleur, connecteurs · todo
[T-090] 9 · correspondants, temps, onboarding client, LBA · todo
[T-100] 10 · fabrique · todo
[T-110] 11 · tests complets, protections non bloquantes, démo, retrait reprise · todo
