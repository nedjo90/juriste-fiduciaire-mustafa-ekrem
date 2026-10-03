"""Graphiques matplotlib au thème de la maison : le titre porte le message, l'axe l'unité, le pied la source.
Spécification (bloc ```graphique en YAML) :
  type: barres | lignes | barres_h | empile
  message: "La charge fiscale baisse de 12 % après la réorganisation"
  unite: CHF
  source: "BIB-002 ; calcul de l'équipe"
  x: [2024, 2025, 2026]
  series: {Avant: [10, 12, 13], Après: [9, 10, 11]}"""
from pathlib import Path
import design as D


def rendre(spec, base, d):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter
    g = d["graphiques"]
    police = D.police_mpl(d)
    plt.rcParams.update({"font.family": police, "font.size": g["taille_texte"], "axes.edgecolor": D.couleur(d, g["couleur_axes"]),
                         "axes.labelcolor": D.couleur(d, g["couleur_texte"]), "xtick.color": D.couleur(d, g["couleur_axes"]),
                         "ytick.color": D.couleur(d, g["couleur_axes"]), "text.color": D.couleur(d, g["couleur_texte"])})
    fig, ax = plt.subplots(figsize=(g["largeur_cm"] / 2.54, g["hauteur_cm"] / 2.54))
    x = [str(v) for v in spec.get("x", [])]
    series = spec.get("series") or {}
    pal = d["palette"]["graphiques"]
    typ = spec.get("type", "barres")
    n = max(1, len(series))
    import numpy as np
    idx = np.arange(len(x))
    bas = np.zeros(len(x))
    for k, (nom, vals) in enumerate(series.items()):
        vals = [float(v) for v in vals]
        c = pal[k % len(pal)]
        if typ == "lignes":
            ax.plot(x, vals, color=c, lw=2, marker="o", ms=4, label=nom)
        elif typ == "barres_h":
            ax.barh(idx + k * 0.8 / n, vals, height=0.8 / n, color=c, label=nom)
        elif typ == "empile":
            ax.bar(x, vals, bottom=bas, color=c, label=nom, width=0.6); bas += np.array(vals)
        else:
            ax.bar(idx + (k - (n - 1) / 2) * 0.8 / n, vals, width=0.8 / n, color=c, label=nom)
    if typ in ("barres",):
        ax.set_xticks(idx); ax.set_xticklabels(x)
    if typ == "barres_h":
        ax.set_yticks(idx + 0.4 - 0.4 / n); ax.set_yticklabels(x)
    sep = d["typo"]["fr"]["separateur_milliers"]
    fmt = FuncFormatter(lambda v, _: f"{v:,.0f}".replace(",", sep))
    (ax.xaxis if typ == "barres_h" else ax.yaxis).set_major_formatter(fmt)
    for s in g["epines_masquees"]:
        ax.spines[s].set_visible(False)
    ax.grid(axis="x" if typ == "barres_h" else g["grille"]["axe"], color=D.couleur(d, g["grille"]["couleur"]), lw=g["grille"]["epaisseur"])
    ax.set_axisbelow(True)
    if spec.get("unite"):
        (ax.set_xlabel if typ == "barres_h" else ax.set_ylabel)(spec["unite"])
    ax.set_title(spec.get("message", ""), loc="left", fontsize=g["taille_titre"], color=D.couleur(d, "primaire"), fontweight="bold")
    if len(series) > 1:
        ax.legend(frameon=False, ncol=min(4, len(series)), loc="upper left", bbox_to_anchor=(0, -0.12))
    src = spec.get("source") or "⚠ source à indiquer"
    fig.text(0.01, 0.005, f"Source : {src}", fontsize=8, color=D.couleur(d, "discret"), ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    base = Path(base)
    png, svg = base.with_suffix(".png"), base.with_suffix(".svg")
    fig.savefig(png, dpi=g["dpi"], facecolor="white")
    fig.savefig(svg, facecolor="white")
    plt.close(fig)
    return {"png": str(png), "svg": str(svg), "message": spec.get("message", ""), "unite": spec.get("unite", ""), "source": src}
