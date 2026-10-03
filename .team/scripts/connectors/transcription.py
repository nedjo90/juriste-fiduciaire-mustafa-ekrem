#!/usr/bin/env python3
"""Transcription locale des notes vocales (§6.4 « transcription vocale locale si installable ») : faster-whisper sur CPU
(int8), modèle téléchargé au premier usage dans .team/tools/whisper/ (non suivi par git). Rien ne sort du poste
après ce téléchargement. Langue détectée, ramenée à fr/de/it/en si la détection hésite. Budget de temps : au-delà,
la transcription est rendue partielle (jamais un ingesteur bloqué). Indisponible → TranscriptionImpossible (repli de
l'appelant : note « à transcrire » + question simple à Mustafa ; le modèle de langage ne lit pas l'audio).
Variables : CEREBRO_WHISPER_MODELE (défaut small ; tests : base), CEREBRO_WHISPER_DIR, CEREBRO_SANS_TRANSCRIPTION=1."""
import os, sys, time
from pathlib import Path

ROOT = Path(os.environ.get("CEREBRO_ROOT") or Path(__file__).resolve().parents[3])
DOSSIER = Path(os.environ.get("CEREBRO_WHISPER_DIR") or ROOT / ".team" / "tools" / "whisper")
LANGUES = ("fr", "de", "it", "en")
BUDGET_S = 420


class TranscriptionImpossible(Exception):
    pass


def modele_nom():
    return os.environ.get("CEREBRO_WHISPER_MODELE") or "small"


def disponible():
    if os.environ.get("CEREBRO_SANS_TRANSCRIPTION"):
        return False
    import importlib.util
    return importlib.util.find_spec("faster_whisper") is not None


_MODELE = {}


def _modele():
    nom = modele_nom()
    if nom not in _MODELE:
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")  # Windows sans droit de lien symbolique : copies
        os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
        from faster_whisper import WhisperModel
        DOSSIER.mkdir(parents=True, exist_ok=True)
        _MODELE[nom] = WhisperModel(nom, device="cpu", compute_type="int8", download_root=str(DOSSIER),
                                    cpu_threads=max(1, min(4, os.cpu_count() or 2)))
    return _MODELE[nom]


def _passe(m, chemin, langue, debut, budget):
    try:
        segs, info = m.transcribe(str(chemin), language=langue, vad_filter=True, beam_size=5)
    except Exception:  # filtre de silence (onnxruntime) absent : sans filtre
        segs, info = m.transcribe(str(chemin), language=langue, vad_filter=False, beam_size=5)
    morceaux, partiel = [], False
    for s in segs:
        morceaux.append(s.text.strip())
        if time.time() - debut > budget:
            partiel = True
            break
    return " ".join(x for x in morceaux if x), info, partiel


def transcrire(chemin, budget=BUDGET_S):
    """→ {texte, langue, probabilite, duree_s, modele, partiel}"""
    if not disponible():
        raise TranscriptionImpossible("faster-whisper absent")
    t0 = time.time()
    try:
        m = _modele()
        texte, info, partiel = _passe(m, chemin, None, t0, budget)
        langue = info.language
        if langue not in LANGUES:
            probs = dict(getattr(info, "all_language_probs", None) or [])
            langue = max(LANGUES, key=lambda l: probs.get(l, 0.0))
            texte, info, partiel = _passe(m, chemin, langue, t0, budget)
    except TranscriptionImpossible:
        raise
    except Exception as e:
        raise TranscriptionImpossible(repr(e)[:300])
    if not texte.strip():
        raise TranscriptionImpossible("aucune parole reconnue")
    return {"texte": texte, "langue": langue, "probabilite": round(float(info.language_probability or 0), 2),
            "duree_s": round(float(getattr(info, "duration", 0) or 0), 1), "modele": modele_nom(), "partiel": partiel,
            "secondes_calcul": round(time.time() - t0, 1)}


if __name__ == "__main__":
    import json
    try:
        print(json.dumps(transcrire(sys.argv[1]), ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"erreur": repr(e)}, ensure_ascii=False))
