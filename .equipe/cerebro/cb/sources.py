"""Sources vivantes (§9.5, §10) : une source s'ajoute, change, déménage ou disparaît. Rien n'est figé.

- officielle(url) : la liste officielle est le fichier modifiable `scripts/recherche/liste_blanche.yaml` (domaines et
  sous-domaines, ajouts datés) ; aucune autre liste en dur.
- verifier(ref) : avant de RÉUTILISER une source (objet `source` ou adresse), on vérifie qu'elle tient encore :
  page joignable et inchangée (empreinte du texte), ou loi fédérale toujours dans sa version en vigueur (Fedlex).
  Vérifiée depuis moins de FRAIS jours → réponse immédiate, sans réseau (coût nul). Adresse inconnue de la mémoire →
  enregistrée comme objet `source` (fiabilité officielle ou secondaire) : une source fiable apparue en conversation
  n'est jamais perdue, et elle sera revérifiée avant chaque réutilisation.
Statuts : actif · modifiée (texte changé : nouvelle lecture en file) · introuvable (incident ; la veille cherche la
nouvelle adresse) · nouvelle version (loi) · hors ligne (réseau absent : réserve, rien n'est conclu)."""
import hashlib, json, os, re, subprocess, sys, urllib.parse, urllib.request, urllib.error
import datetime as dt
from .core import db, iso, today, cut, EQ, journal
from .objets import get, create, update

FRAIS = 7
LISTE = EQ / "scripts" / "recherche" / "liste_blanche.yaml"
FEDLEX = EQ / "scripts" / "bibliotheque" / "fedlex.py"


def _liste():
    try:
        import yaml
        d = yaml.safe_load(LISTE.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    doms = dict(d.get("domaines") or {})
    for a in d.get("ajouts") or []:
        if isinstance(a, dict) and a.get("domaine"):
            doms[a["domaine"]] = a
    return doms


def officielle(url):
    """entrée de la liste officielle (dict) si l'hôte ou un domaine parent y figure, sinon None"""
    hote = (urllib.parse.urlparse(url or "").hostname or "").lower()
    parts, doms = hote.split("."), _liste()
    for i in range(len(parts) - 1):
        if ".".join(parts[i:]) in doms:
            return doms[".".join(parts[i:])]
    return None


def noms_officiels(limite=40):
    """liste lisible des sources officielles (pour la veille) : lue dans le fichier, jamais écrite en dur"""
    return [f"{d} ({(v or {}).get('nom') or (v or {}).get('motif') or ''})".replace(" ()", "") for d, v in list(_liste().items())[:limite]]


def _texte(data):
    t = data.decode("utf-8", "ignore")
    t = re.sub(r"(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


IDENTITES = ("cerebro-sources/1.0 (+usage interne fiduciaire)", "curl/8.5.0",
             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def _get(url, timeout=12):
    """chaque site a sa règle (certains refusent les programmes, d'autres les faux navigateurs) : plusieurs identités
    honnêtes essayées, la première acceptée l'emporte ; 404/410 = introuvable, sans autre essai"""
    dernier = None
    for ua in IDENTITES:
        req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Language": "fr-CH,fr;q=0.9,de;q=0.8"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(4_000_000)
        except urllib.error.HTTPError as e:
            dernier = e
            if e.code in (404, 410):
                raise
        except Exception as e:
            dernier = e
    raise dernier


def _fedlex_en_vigueur(rs, timeout=20):
    """date de la consolidation en vigueur aujourd'hui (Fedlex), ou None si injoignable"""
    r = subprocess.run([sys.executable, str(FEDLEX), "versions", rs], capture_output=True, text=True, encoding="utf-8",
                       timeout=timeout, env={**os.environ, "PYTHONIOENCODING": "utf-8"}, stdin=subprocess.DEVNULL)
    d = json.loads(r.stdout)
    auj = os.environ.get("CEREBRO_TODAY") or today().isoformat()
    for c in (d[0].get("consolidations") if d else []) or []:
        if c["du"] <= auj and (not c.get("au") or c["au"] >= auj):
            return c["du"]
    return None


def _trouver(ref):
    o = get(ref) if re.match(r"^[A-Z]+-\d+$", ref or "") else None
    if o:
        return o, (o.get("data") or {}).get("url") or o.get("source") or ""
    r = db().execute("SELECT id FROM objets WHERE type='source' AND (source=? OR json_extract(data,'$.url')=?) ORDER BY id DESC LIMIT 1",
                     (ref, ref)).fetchone()
    return (get(r[0]) if r else None), ref


def verifier(ref, force=False):
    o, url = _trouver(ref)
    data = (o or {}).get("data") or {}
    if o and not force and data.get("verifie_le") and (today() - dt.date.fromisoformat(data["verifie_le"][:10])).days < FRAIS:
        return {"id": o["id"], "statut": data.get("statut_source") or "actif", "verifie_le": data["verifie_le"][:10], "reseau": False}
    if os.environ.get("CEREBRO_SANS_RESEAU"):
        return {"id": o and o["id"], "statut": "hors ligne", "reserve": "⚠ non revérifiée (réseau absent) : citer avec réserve"}
    biblio = db().execute("SELECT identifiant, version, juridiction FROM bibliotheque WHERE id=?", (o["id"],)).fetchone() if o else None
    if biblio and biblio["juridiction"] == "CH" and re.match(r"^0?\.?\d", biblio["identifiant"] or ""):
        try:
            en_vigueur = _fedlex_en_vigueur(biblio["identifiant"])
        except Exception as e:
            return {"id": o["id"], "statut": "hors ligne", "reserve": f"⚠ Fedlex injoignable ({cut(repr(e), 60)}) : citer avec réserve"}
        statut = "nouvelle version" if en_vigueur and en_vigueur > biblio["version"] else "actif"
        update(o["id"], verifie_le=iso(), statut_source=statut, acteur="sources")
        if statut != "actif":
            from .brief import queue_add
            queue_add("bibliotheque_ingest", biblio["identifiant"], 1)
        return {"id": o["id"], "statut": statut, "version": biblio["version"], "en_vigueur": en_vigueur, "reseau": True}
    if not url.startswith("http"):
        return {"id": o and o["id"], "statut": "inconnue", "reserve": "⚠ ni adresse ni texte officiel à vérifier"}
    off = officielle(url)
    try:
        texte = _texte(_get(url))
        statut = "actif"
    except urllib.error.HTTPError as e:
        texte, statut = "", "introuvable" if e.code in (404, 410) else "hors ligne"
    except Exception:
        texte, statut = "", "hors ligne"
    emp = hashlib.sha256(texte.encode("utf-8")).hexdigest()[:16] if texte else None
    if not o:  # source apparue en conversation : enregistrée, jamais perdue
        if statut != "actif":
            return {"statut": statut, "reserve": "⚠ adresse injoignable : rien n'est enregistré ni conclu"}
        hote = urllib.parse.urlparse(url).hostname or url
        oid = create("source", cut(f"{(off or {}).get('nom') or hote} — {url.split('/', 3)[-1] if url.count('/') >= 3 else hote}", 80),
                     source=url, statut="actif", domaine="sources", mots_cles=f"source web {hote}",
                     resume=cut(f"Source {'officielle' if off else 'secondaire'} relevée le {iso()} ; revérifiée avant chaque réutilisation", 280),
                     prochaine_action="revérifier avant réutilisation" if off else "vérifier contre une source primaire",
                     url=url, fiabilite="officielle" if off else "secondaire", empreinte_web=emp, verifie_le=iso(),
                     statut_source="actif", acteur="sources")
        if off:
            from .brief import queue_add
            queue_add("source_officielle_lire", url, 3)
        journal("sources", op="ajout", id=oid, url=url, officielle=bool(off))
        return {"id": oid, "statut": "ajoutée", "fiabilite": "officielle" if off else "secondaire", "reseau": True}
    if statut == "actif" and data.get("empreinte_web") and emp != data.get("empreinte_web"):
        statut = "modifiée"
    champs = {"verifie_le": iso(), "statut_source": statut}
    if emp:
        champs["empreinte_web"] = emp
    if statut == "introuvable":
        champs["prochaine_action"] = "retrouver la nouvelle adresse (veille)"
        champs["prochaine_date"] = (today() + dt.timedelta(days=7)).isoformat()
        from .files import incident_add
        incident_add("source", f"source {o['id']} introuvable ({cut(url, 80)})", "réserve sur les réutilisations ; la veille cherche la nouvelle adresse")
    if statut != "hors ligne":
        update(o["id"], acteur="sources", **champs)
    if statut == "modifiée" and (off or data.get("fiabilite") == "officielle"):
        from .brief import queue_add
        queue_add("source_officielle_lire", url, 3)
    out = {"id": o["id"], "statut": statut, "fiabilite": data.get("fiabilite"), "reseau": True}
    if statut in ("introuvable", "hors ligne", "modifiée"):
        out["reserve"] = {"introuvable": "⚠ source disparue : ne pas la citer sans la retrouver",
                          "hors ligne": "⚠ non revérifiée (réseau) : citer avec réserve",
                          "modifiée": "⚠ texte modifié depuis la dernière lecture : relire avant de citer"}[statut]
    return out
