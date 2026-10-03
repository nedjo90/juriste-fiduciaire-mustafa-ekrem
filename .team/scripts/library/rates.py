#!/usr/bin/env python3
"""Inscrit les barèmes de rates.yaml dans la table `bareme` (cerebro rates set), après avoir relu l'article officiel
ingéré et vérifié que l'extrait y figure. Idempotent : une valeur déjà inscrite pour (nom, année, clé) n'est pas dupliquée.
Échec de vérification → valeur non inscrite + incident (jamais d'arrêt).
Usage : python rates.py [--dry-run]"""
import argparse, datetime as dt, json, sys, unicodedata, re
from pathlib import Path
import yaml

sys.path.insert(0, str(Path(__file__).parent))
from fedlex import cerebro, utf8_console, aujourdhui  # noqa: E402


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower()).strip()


def annees(version, aujourd_hui):
    """année en cours + années entières antérieures couvertes par la version (en vigueur depuis un 1er janvier)"""
    v = dt.date.fromisoformat(version)
    a0 = v.year if (v.month, v.day) == (1, 1) else v.year + 1
    return sorted(set(range(a0, aujourd_hui.year + 1)) | {aujourd_hui.year})


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    utf8_console()
    conf = yaml.safe_load((Path(__file__).parent / "rates.yaml").read_text(encoding="utf-8"))
    auj = dt.date.fromisoformat(aujourdhui())
    out = []
    for b in conf["baremes"]:
        art = cerebro("law", "article", b["rs"], b["article"])
        if "texte" not in art or fold(b["extrait"]) not in fold(art["texte"]):
            msg = f"barème {b['nom']}.{b['cle']} non confirmé par RS {b['rs']} {b['article']} ({art.get('erreur') or 'extrait absent'})"
            if not a.dry_run:
                cerebro("incident", "add", msg, "--categorie", "bareme", "--repli", "valeur non inscrite ; calculs affichent ⚠")
            out.append({"bareme": f"{b['nom']}.{b['cle']}", "statut": "non confirmé", "detail": msg})
            continue
        src = f"RS {b['rs']} {b['article']}, version {art['version']} ({art['source']}) : « {b['extrait']} »" + (f" — {b['remarque']}" if b.get("remarque") else "")
        for an in annees(art["version"], auj):
            ex = cerebro("rates", "get", b["nom"], "--annee", an, "--cle", b["cle"])
            if isinstance(ex, list) and any(str(r["valeur"]) == str(b["valeur"]) and f"version {art['version']}" in (r["source"] or "") for r in ex):
                out.append({"bareme": f"{b['nom']}.{b['cle']}", "annee": an, "statut": "inchangé"})
                continue
            if a.dry_run:
                out.append({"bareme": f"{b['nom']}.{b['cle']}", "annee": an, "valeur": b["valeur"], "statut": "à inscrire", "source": src})
                continue
            r = cerebro("rates", "set", b["nom"], "--annee", an, "--cle", b["cle"], "--valeur", b["valeur"], "--source", src)
            out.append({"bareme": f"{b['nom']}.{b['cle']}", "annee": an, "valeur": b["valeur"], "id": r.get("id"), "statut": "inscrit"})
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
