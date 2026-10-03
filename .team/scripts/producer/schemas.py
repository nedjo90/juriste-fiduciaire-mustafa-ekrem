"""Schémas (§7.1) : Mermaid → SVG/PNG par Mermaid CLI si disponible (npx -y @mermaid-js/mermaid-cli), sinon rendu
matplotlib d'un organigramme simple ; export draw.io (XML) toujours produit pour retouche par Mustafa.
Mermaid pris en charge par le repli : `graph TD|LR` / `flowchart`, nœuds A[txt] A(txt) A{txt} A((txt)), arêtes --> --- -.-> ==> avec |étiquette|."""
import os, re, json, shutil, subprocess, time, html
from pathlib import Path
import design as D
from common import EQ, journal

NOEUD = re.compile(r"([A-Za-z0-9_]+)\s*(\[\[?[^\]]*\]?\]|\(\([^)]*\)\)|\([^)]*\)|\{[^}]*\})?")
ARETE = re.compile(r"^\s*(.+?)\s*(-->|---|-\.->|==>|--)\s*(?:\|([^|]*)\|\s*)?(.+?)\s*;?\s*$")


def _noeud(tok, noeuds):
    m = NOEUD.match(tok.strip())
    if not m:
        return None
    nid, forme = m.group(1), m.group(2) or ""
    if forme:
        txt = forme.strip("[](){}").strip()
        kind = "decision" if forme.startswith("{") else ("rond" if forme.startswith("(") else "boite")
        noeuds[nid] = {"id": nid, "texte": txt.strip('"'), "forme": kind}
    else:
        noeuds.setdefault(nid, {"id": nid, "texte": nid, "forme": "boite"})
    return nid


def parse(src):
    lignes = [l.strip() for l in src.strip().splitlines() if l.strip() and not l.strip().startswith("%%")]
    sens = "TD"
    if lignes and re.match(r"^(graph|flowchart)\b", lignes[0]):
        m = re.match(r"^(?:graph|flowchart)\s+(\w+)", lignes[0])
        sens = (m.group(1) if m else "TD").upper()
        lignes = lignes[1:]
    noeuds, aretes = {}, []
    for l in lignes:
        for part in l.split(";"):
            part = part.strip()
            if not part:
                continue
            m = ARETE.match(part)
            if m:
                a = _noeud(m.group(1), noeuds); b = _noeud(m.group(4), noeuds)
                if a and b:
                    aretes.append({"de": a, "a": b, "texte": (m.group(3) or "").strip(), "style": m.group(2)})
            else:
                _noeud(part, noeuds)
    return {"sens": "LR" if sens in ("LR", "RL") else "TD", "noeuds": noeuds, "aretes": aretes}


def disposer(g):
    """couches par plus long chemin depuis les racines ; position (x, y) en unités de grille"""
    ent = {n: 0 for n in g["noeuds"]}
    for a in g["aretes"]:
        ent[a["a"]] += 1
    niveau = {n: 0 for n in g["noeuds"]}
    for _ in range(len(g["noeuds"])):
        for a in g["aretes"]:
            if niveau[a["a"]] < niveau[a["de"]] + 1 and niveau[a["de"]] + 1 < len(g["noeuds"]):
                niveau[a["a"]] = niveau[a["de"]] + 1
    couches = {}
    for n, k in niveau.items():
        couches.setdefault(k, []).append(n)
    pos = {}
    for k, ns in couches.items():
        for i, n in enumerate(ns):
            off = i - (len(ns) - 1) / 2
            pos[n] = (off, -k) if g["sens"] == "TD" else (k, -off)
    return pos


def drawio(g, dest, d):
    pos = disposer(g)
    fond = D.couleur(d, d["schemas"]["noeud"]["fond"]); bord = D.couleur(d, d["schemas"]["noeud"]["bordure"])
    dec_fond = D.couleur(d, d["schemas"]["noeud_decision"]["fond"]); dec_bord = D.couleur(d, d["schemas"]["noeud_decision"]["bordure"])
    fl = D.couleur(d, d["schemas"]["fleche"]); police = d["schemas"]["police"]
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    for n, (x, y) in pos.items():
        o = g["noeuds"][n]
        st = (f"rhombus;whiteSpace=wrap;html=1;fillColor={dec_fond};strokeColor={dec_bord};fontFamily={police};" if o["forme"] == "decision"
              else f"rounded=1;whiteSpace=wrap;html=1;fillColor={fond};strokeColor={bord};fontFamily={police};")
        cells.append(f'<mxCell id="n_{n}" value="{html.escape(o["texte"])}" style="{st}" vertex="1" parent="1">'
                     f'<mxGeometry x="{int(300 + x * 200)}" y="{int(40 - y * 120)}" width="160" height="60" as="geometry"/></mxCell>')
    for i, a in enumerate(g["aretes"]):
        dash = "dashed=1;" if a["style"] == "-.->" else ""
        cells.append(f'<mxCell id="e{i}" value="{html.escape(a["texte"])}" style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor={fl};{dash}fontFamily={police};" '
                     f'edge="1" parent="1" source="n_{a["de"]}" target="n_{a["a"]}"><mxGeometry relative="1" as="geometry"/></mxCell>')
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<mxfile host="producteur-maison"><diagram name="Schéma" id="s1"><mxGraphModel grid="1" gridSize="10">'
           f'<root>{"".join(cells)}</root></mxGraphModel></diagram></mxfile>\n')
    Path(dest).write_text(xml, encoding="utf-8")
    return dest


def _mmdc(src_file, out_file):
    """Mermaid CLI via npx ; indisponibilité mémorisée 7 jours pour ne pas retenter à chaque schéma"""
    if os.environ.get("PRODUCTEUR_SANS_MMDC"):
        return False
    marque = EQ / "run" / "mmdc-indisponible"
    if marque.exists() and time.time() - marque.stat().st_mtime < 7 * 86400:
        return False
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        return False
    try:
        r = subprocess.run([npx, "-y", "@mermaid-js/mermaid-cli", "-i", str(src_file), "-o", str(out_file), "-b", "white"],
                           capture_output=True, timeout=180)
        ok = r.returncode == 0 and Path(out_file).exists()
    except Exception as e:
        journal("erreurs-producteur", op="mmdc", erreur=repr(e)); ok = False
    if not ok:
        marque.parent.mkdir(parents=True, exist_ok=True); marque.write_text("échec mmdc", encoding="utf-8")
    return ok


def _matplotlib(g, png, svg, d, titre=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    pos = disposer(g)
    xs = [p[0] for p in pos.values()] or [0]; ys = [p[1] for p in pos.values()] or [0]
    fig_w = max(6, (max(xs) - min(xs) + 1) * 2.4); fig_h = max(3, (max(ys) - min(ys) + 1) * 1.4)
    fig, ax = plt.subplots(figsize=(min(fig_w, 16) / 2.54 * 2.54, min(fig_h, 12)))
    police = D.police_mpl(d)
    plt.rcParams["font.family"] = police
    bord = D.couleur(d, d["schemas"]["noeud"]["bordure"]); dec = D.couleur(d, d["schemas"]["noeud_decision"]["bordure"])
    for a in g["aretes"]:
        (x1, y1), (x2, y2) = pos[a["de"]], pos[a["a"]]
        ax.annotate("", xy=(x2, y2 + 0.22 if g["sens"] == "TD" else y2), xytext=(x1, y1 - 0.22 if g["sens"] == "TD" else y1),
                    arrowprops=dict(arrowstyle="-|>", color=D.couleur(d, d["schemas"]["fleche"]), lw=1.1, linestyle="--" if a["style"] == "-.->" else "-"))
        if a["texte"]:
            ax.text((x1 + x2) / 2, (y1 + y2) / 2, a["texte"], fontsize=8, color=D.couleur(d, "secondaire"), ha="center", va="center",
                    bbox=dict(fc="white", ec="none", pad=1))
    for n, (x, y) in pos.items():
        o = g["noeuds"][n]
        fc = D.couleur(d, "fond_clair") if o["forme"] == "decision" else "white"
        ax.add_patch(FancyBboxPatch((x - 0.42, y - 0.2), 0.84, 0.4, boxstyle="round,pad=0.02,rounding_size=0.06", fc=fc,
                                    ec=dec if o["forme"] == "decision" else bord, lw=1.2))
        ax.text(x, y, o["texte"], ha="center", va="center", fontsize=9, color=D.couleur(d, "encre"), wrap=True)
    ax.set_xlim(min(xs) - 0.7, max(xs) + 0.7); ax.set_ylim(min(ys) - 0.6, max(ys) + 0.6)
    ax.axis("off")
    if titre:
        ax.set_title(titre, loc="left", fontsize=d["graphiques"]["taille_titre"], color=D.couleur(d, "primaire"))
    fig.savefig(png, dpi=d["graphiques"]["dpi"], bbox_inches="tight", facecolor="white")
    fig.savefig(svg, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def rendre(src, base, d, titre=""):
    """src mermaid → {png, svg, drawio, moteur}"""
    base = Path(base)
    g = parse(src)
    res = {"drawio": str(drawio(g, base.with_suffix(".drawio"), d))}
    mmd = EQ / "run" / f"{base.stem}.mmd"
    mmd.parent.mkdir(parents=True, exist_ok=True)
    mmd.write_text(src, encoding="utf-8")
    png, svg = base.with_suffix(".png"), base.with_suffix(".svg")
    if _mmdc(mmd, svg) and _mmdc(mmd, png):
        res.update(png=str(png), svg=str(svg), moteur="mermaid-cli")
    else:
        _matplotlib(g, png, svg, d, titre)
        res.update(png=str(png), svg=str(svg), moteur="matplotlib")
    try:
        mmd.unlink()
    except Exception:
        pass
    return res
