"""Markdown structuré du producteur : front matter YAML + blocs (titres, paragraphes, listes, tableaux, citations,
blocs de code `mermaid` / `graphique` / `notes`, saut de page). Volontairement petit et sans dépendance."""
import re
import yaml

FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)


def front_matter(text):
    m = FM_RE.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except Exception:
        meta = {}
    return meta, text[m.end():]


def _table_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def blocs(body):
    lines = body.replace("\r\n", "\n").split("\n")
    out, i, para = [], 0, []

    def flush():
        if para:
            out.append({"t": "p", "texte": " ".join(x.strip() for x in para).strip()})
            para.clear()

    while i < len(lines):
        l = lines[i]
        s = l.strip()
        if not s:
            flush(); i += 1; continue
        if s.startswith("```"):
            flush()
            lang = s[3:].strip().lower()
            j = i + 1
            buf = []
            while j < len(lines) and not lines[j].strip().startswith("```"):
                buf.append(lines[j]); j += 1
            out.append({"t": "code", "lang": lang, "texte": "\n".join(buf)})
            i = j + 1; continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*$", s)
        if m:
            flush()
            out.append({"t": "h", "niveau": len(m.group(1)), "texte": m.group(2).strip()})
            i += 1; continue
        if s in ("\\newpage", "<!-- saut -->", "<!-- pagebreak -->"):
            flush(); out.append({"t": "saut"}); i += 1; continue
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", s):
            flush(); out.append({"t": "hr"}); i += 1; continue
        if s.startswith("|") and i + 1 < len(lines) and re.fullmatch(r"\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?", lines[i + 1].strip()):
            flush()
            ent = _table_row(s)
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                rows.append(_table_row(lines[j])); j += 1
            out.append({"t": "table", "entete": ent, "lignes": rows})
            i = j; continue
        if re.match(r"^([-*•])\s+", s):
            flush()
            items = []
            while i < len(lines) and re.match(r"^\s*([-*•])\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*•]\s+", "", lines[i]).strip()); i += 1
                while i < len(lines) and lines[i].startswith("  ") and lines[i].strip() and not re.match(r"^\s*([-*•]|\d+[.)])\s+", lines[i]):
                    items[-1] += " " + lines[i].strip(); i += 1
            out.append({"t": "ul", "items": items}); continue
        if re.match(r"^\d+[.)]\s+", s):
            flush()
            items = []
            while i < len(lines) and re.match(r"^\s*\d+[.)]\s+", lines[i]):
                items.append(re.sub(r"^\s*\d+[.)]\s+", "", lines[i]).strip()); i += 1
            out.append({"t": "ol", "items": items}); continue
        if s.startswith(">"):
            flush()
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip()); i += 1
            out.append({"t": "quote", "texte": " ".join(buf)}); continue
        para.append(l)
        i += 1
    flush()
    return out


def normaliser_niveaux(bl):
    """le niveau de titre le plus haut du corps devient 1 (« ## Résumé » → titre 1) ; un « # » unique en tête = titre du document"""
    hs = [b for b in bl if b["t"] == "h"]
    titre = None
    if hs and hs[0]["niveau"] == 1 and sum(1 for b in hs if b["niveau"] == 1) == 1 and bl and bl[0] is hs[0]:
        titre = hs[0]["texte"]; bl = bl[1:]; hs = hs[1:]
    if hs:
        m = min(b["niveau"] for b in hs)
        for b in hs:
            b["niveau"] = b["niveau"] - m + 1
    return titre, bl


def parse(text):
    meta, body = front_matter(text)
    titre, bl = normaliser_niveaux(blocs(body))
    if titre and not meta.get("titre"):
        meta["titre"] = titre
    return meta, bl


INLINE_RE = re.compile(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`)")


def runs(texte):
    """texte → [(morceau, gras, italique, code)]"""
    out = []
    for part in INLINE_RE.split(texte or ""):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            out.append((part[2:-2], True, False, False))
        elif part.startswith("`") and part.endswith("`"):
            out.append((part[1:-1], False, False, True))
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            out.append((part[1:-1], False, True, False))
        else:
            out.append((part, False, False, False))
    return out


def texte_brut(texte):
    return "".join(r[0] for r in runs(texte))


def sections(bl, niveau=2):
    """découpe par titres d'un niveau donné → [(titre, [blocs])] ; le contenu avant le premier titre a titre=None"""
    res, cur = [], (None, [])
    for b in bl:
        if b["t"] == "h" and b["niveau"] <= niveau:
            if cur[0] is not None or cur[1]:
                res.append(cur)
            cur = (b["texte"], [])
        else:
            cur[1].append(b)
    if cur[0] is not None or cur[1]:
        res.append(cur)
    return res


def vers_texte(bl):
    """blocs → texte simple (pour les portes)"""
    out = []
    for b in bl:
        if b["t"] in ("p", "quote"):
            out.append(texte_brut(b["texte"]))
        elif b["t"] == "h":
            out.append(texte_brut(b["texte"]))
        elif b["t"] in ("ul", "ol"):
            out += ["- " + texte_brut(x) for x in b["items"]]
        elif b["t"] == "table":
            out.append(" | ".join(b["entete"]))
            out += [" | ".join(r) for r in b["lignes"]]
    return "\n\n".join(out)
