# -*- coding: utf-8 -*-
"""Relie le glossaire à la bibliothèque : un article n'est inscrit que si la bibliothèque contient un article dont
l'alinéa 1 commence par « <notion> est/sont » suivi d'un déterminant
(définition textuelle), ou sous un intitulé « Définition ». Sinon « ⚠ à relier ». Idempotent ; rejouable après chaque ingestion (documentaliste)."""
import os, re, sqlite3, unicodedata
from pathlib import Path

ROOT = Path(os.environ.get("CEREBRO_ROOT") or Path(__file__).resolve().parents[3])
DB = os.environ.get("CEREBRO_DB") or ROOT / ".team/cerebro/cerebro.db"
G = ROOT / ".team/brain/firm/glossary.md"

def fold(s):
    s = unicodedata.normalize("NFKD", s.replace("’", "'").lower())
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c))).strip()

con = sqlite3.connect(DB)
LIB = {}
for bid, ab, ver, ch in con.execute("SELECT id, abreviation, version, chemin FROM bibliotheque WHERE langue='fr' AND abreviation!='' ORDER BY version"):
    LIB[ab] = (bid, ver, ROOT / ch)  # dernière version gagne

CACHE = {}
def articles(ab):
    if ab not in CACHE:
        bid, ver, p = LIB[ab]
        arts = []
        if p.exists():
            for bloc in re.split(r"\n(?=## Art\. )", p.read_text(encoding="utf-8")):
                m = re.match(r"## Art\. (\S+)\s*(.*)\n+(.*)", bloc)
                if m:
                    arts.append((m.group(1), re.sub(r"^[A-Za-z0-9IVX]{1,5}[a-z]?\.\s*", "", m.group(2)), m.group(3)))
        CACHE[ab] = arts
    return CACHE[ab]

def chercher(terme, lois):
    t = fold(terme)
    if len(t) < 5:
        return None
    for ab in lois:
        if ab not in LIB:
            continue
        for num, titre, al1 in articles(ab):
            a1 = fold(re.sub(r"^\d+\s+", "", al1))
            m = re.match(r"^(le |la |les |l')?" + re.escape(t) + r" (est|sont) (\S+)", a1)
            if m and (m.group(3) in ("un", "une", "celle", "celui", "ceux", "le", "la", "les", "des") or m.group(3).startswith("l'") or "definition" in fold(titre)):
                bid, ver, _ = LIB[ab]
                return f"art. {num} {ab} ({bid}, état {ver})"
    return None

lignes, n_ok, n_tot = [], 0, 0
for l in G.read_text(encoding="utf-8").splitlines():
    cells = [c.strip() for c in l.strip("|").split("|")] if l.startswith("|") else []
    if len(cells) == 6 and cells[5].startswith(("⚠", "art.")) and cells[4] not in ("loi", "---"):
        n_tot += 1
        lois = [x.strip() for x in re.split(r"[/+]", cells[4]) if x.strip() and x.strip() != "—"]
        termes = [x.strip() for x in re.split(r" / ", re.sub(r"\s*\(.*?\)", "", cells[0]))]
        trouve = next((r for r in (chercher(t, lois) for t in termes) if r), None)
        cells[5] = trouve or "⚠ à relier"
        n_ok += bool(trouve)
        l = "| " + " | ".join(cells) + " |"
    lignes.append(l)
txt = "\n".join(lignes) + "\n"
txt = re.sub(r"état de la bibliothèque au .*", f"état de la liaison : {n_ok}/{n_tot} notions reliées à un article vérifié (définition textuelle dans l'alinéa 1) ; le reste « ⚠ à relier » (relier : documentaliste).", txt)
G.write_text(txt, encoding="utf-8")
print(n_ok, "/", n_tot)
