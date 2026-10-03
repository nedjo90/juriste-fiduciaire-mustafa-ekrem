# Source de la skill `humanizer-de`

- Skill de la maison, dérivée de `humanizer` (https://github.com/blader/humanizer, commit 225a6f39ac85f76ee48dbad772ea4abe4ed6c9d8, v3.1.0, licence MIT, Copyright (c) 2025 Siqi Chen ; copie locale : `.claude/skills/humanizer/`).
- Source des motifs d'origine : Wikipédia « Signs of AI writing » (WikiProject AI Cleanup).
- Adaptation (2026-10-03) : tics propres à la langue, conventions typographiques suisses, interdits de la constitution §7.2 ; détection déterministe correspondante dans `.team/scripts/gates/p_tics.py` (dictionnaire `TICS["de"]`).
- Révision : par la fabrique quand la porte « tics » laisse passer un motif relevé par le relecteur (fixture ajoutée à `.team/tests/test_production.py`).
- Licence de la dérivée : MIT (notice d'origine reproduite ci-dessus).
