#!/usr/bin/env python3
"""Ingesteur (§6.3, §4.2, §15) : tout ce que Mustafa glisse dans « Bureau/À déposer » est lu, classé, rattaché, archivé.
Par script : extraction du texte, empreinte (doublons), rattachement par alias, objet `document` avec en-tête et ligne de
sommaire, original déplacé dans « Bureau/Déposés/<date>/ » (nom d'origine conservé), texte intégral dans .equipe/archives
(non suivi par git). Le commentaire et l'exploitation (« document déposé relu sans demande ») sont mis en file pour le
modèle (tâche `ingestion_commentaire`). Ne bloque jamais : un fichier illisible devient une tâche « lire par le modèle »."""
import sys, os, json, hashlib, shutil, subprocess, zipfile, email, re
from email import policy
from pathlib import Path

ROOT = Path(os.environ.get("CEREBRO_ROOT") or Path(__file__).resolve().parents[3])
sys.path.insert(0, str(ROOT / ".equipe" / "cerebro"))
os.environ.setdefault("CEREBRO_ROOT", str(ROOT))
from cb import core
from cb.core import db, iso, cut, fold, journal
from cb.objets import create, get
from cb.recherche import find
from cb import files as F, brief as B

DEPOT = ROOT / "Bureau" / "À déposer"
DEPOSES = ROOT / "Bureau" / "Déposés"
ARCH = ROOT / ".equipe" / "archives" / "depots"
AUDIO = {".m4a", ".mp3", ".wav", ".ogg", ".aac", ".opus", ".amr"}
IMAGES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".heic", ".bmp", ".gif", ".webp"}

def _docx(p):
    import docx
    d = docx.Document(str(p))
    out = [para.text for para in d.paragraphs if para.text.strip()]
    for t in d.tables:
        for row in t.rows:
            out.append(" | ".join(c.text.strip() for c in row.cells))
    # suivi des modifications : signalé (le texte ci-dessus est la version courante)
    with zipfile.ZipFile(str(p)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    if "<w:ins " in xml or "<w:del " in xml:
        out.insert(0, "[document avec suivi des modifications]")
    return "\n".join(out)

def _xlsx(p):
    import openpyxl
    wb = openpyxl.load_workbook(str(p), data_only=True, read_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"## Feuille {ws.title}")
        for row in ws.iter_rows(values_only=True, max_row=500):
            if any(v is not None for v in row):
                out.append(" | ".join("" if v is None else str(v) for v in row))
    return "\n".join(out)

def _pptx(p):
    from pptx import Presentation
    out = []
    for i, s in enumerate(Presentation(str(p)).slides, 1):
        out.append(f"## Diapositive {i}")
        for sh in s.shapes:
            if sh.has_text_frame and sh.text_frame.text.strip():
                out.append(sh.text_frame.text)
    return "\n".join(out)

def _pdf(p):
    for cmd in (["pdftotext", "-layout", str(p), "-"],):
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=60)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.decode("utf-8", "ignore")
        except Exception:
            pass
    try:
        import pypdf
        return "\n".join((pg.extract_text() or "") for pg in pypdf.PdfReader(str(p)).pages)
    except Exception:
        return ""

def _eml(p):
    m = email.message_from_bytes(p.read_bytes(), policy=policy.default)
    body = m.get_body(preferencelist=("plain", "html"))
    txt = body.get_content() if body else ""
    if body and body.get_content_type() == "text/html":
        txt = re.sub(r"<[^>]+>", " ", txt)
    pj = [a.get_filename() for a in m.iter_attachments() if a.get_filename()]
    return f"De: {m['from']}\nÀ: {m['to']}\nDate: {m['date']}\nObjet: {m['subject']}\nPièces: {', '.join(pj) or '-'}\n\n{txt}"

def extraire(p):
    ext = p.suffix.lower()
    try:
        if ext == ".docx":
            return _docx(p), "texte"
        if ext in (".xlsx", ".xlsm"):
            return _xlsx(p), "texte"
        if ext == ".pptx":
            return _pptx(p), "texte"
        if ext == ".pdf":
            t = _pdf(p)
            return (t, "texte") if len(t.strip()) > 40 else ("", "pdf_scanne")
        if ext == ".eml":
            return _eml(p), "mail"
        if ext in (".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm"):
            return p.read_text(encoding="utf-8", errors="ignore"), "texte"
        if ext in AUDIO:
            return "", "audio"
        if ext in IMAGES:
            return "", "image"
        if ext in (".doc", ".xls", ".ppt", ".rtf", ".odt", ".msg"):
            # ancien format : conversion LibreOffice si disponible
            out = ARCH / "_conv"
            out.mkdir(parents=True, exist_ok=True)
            for soffice in ("soffice", "libreoffice"):
                try:
                    subprocess.run([soffice, "--headless", "--convert-to", "txt:Text", "--outdir", str(out), str(p)], capture_output=True, timeout=120)
                    q = out / (p.stem + ".txt")
                    if q.exists():
                        return q.read_text(encoding="utf-8", errors="ignore"), "texte"
                except Exception:
                    pass
            return "", "a_lire_par_modele"
    except Exception as e:
        journal("ingesteur", fichier=p.name, erreur=repr(e))
    return "", "a_lire_par_modele"

def rattacher(texte, nom_fichier):
    """client probable par alias / recherche ; renvoie (client, confiance, autres objets cités)"""
    tete = fold(f"{nom_fichier} {texte[:300]}")
    corps = fold(texte[:20000])
    clients, cites = {}, []
    # seuls les alias et identifiants rattachent (un mot commun du texte ne suffit pas) ; alias long et en tête = plus fort
    for r in db().execute("SELECT a.alias_fold, a.id, o.type, o.client FROM alias a JOIN objets o ON o.id=a.id WHERE o.statut!='archive'"):
        a = r["alias_fold"]
        if len(a) < 4 or not re.search(r"\b" + re.escape(a) + r"\b", corps + " " + tete):
            continue
        cid = r["id"] if r["type"] == "client" else r["client"]
        if not cid:
            continue
        poids = len(a) * (2 if re.search(r"\b" + re.escape(a) + r"\b", tete) else 1)
        clients[cid] = clients.get(cid, 0) + poids
        if r["type"] != "client" and r["id"] not in cites:
            cites.append(r["id"])
    for i in core.ID_RE.findall(texte):
        o = get(i)
        if o and (o["client"] or o["type"] == "client"):
            cid = o["client"] or o["id"]
            clients[cid] = clients.get(cid, 0) + 30
    if not clients:
        return None, 0.0, []
    best = max(clients.items(), key=lambda x: x[1])
    total = sum(clients.values())
    return best[0], round(best[1] / total, 2), cites[:8]

def ingerer_fichier(p):
    data = p.read_bytes()
    h = hashlib.sha256(data).hexdigest()[:16]
    con = db()
    dup = con.execute("SELECT id FROM objets WHERE type='document' AND data LIKE ?", (f'%"empreinte": "{h}"%',)).fetchone()
    jour = iso()
    dest = DEPOSES / jour
    dest.mkdir(parents=True, exist_ok=True)
    cible = dest / p.name
    i = 2
    while cible.exists():
        cible = dest / f"{p.stem} ({i}){p.suffix}"; i += 1
    if dup:
        shutil.move(str(p), str(cible))
        journal("ingesteur", fichier=p.name, doublon_de=dup[0])
        return {"fichier": p.name, "doublon_de": dup[0]}
    texte, nature = extraire(p)
    client, conf, cites = rattacher(texte, p.stem) if texte else (None, 0.0, [])
    a_confirmer = client is not None and conf < 0.7
    ARCH.mkdir(parents=True, exist_ok=True)
    arch_txt = ARCH / jour / f"{h}-{core.slug(p.stem, 40)}.txt"
    arch_txt.parent.mkdir(parents=True, exist_ok=True)
    arch_txt.write_text(texte or "", encoding="utf-8")
    shutil.move(str(p), str(cible))
    rel = str(cible.relative_to(ROOT)).replace("\\", "/")
    resume = cut(re.sub(r"\s+", " ", texte), 260) if texte else f"{nature} — à lire par le modèle"
    typ = "mail" if nature == "mail" else ("note" if nature == "audio" else "document")
    statut = "attente" if typ == "mail" else ("à confirmer" if a_confirmer or not client else "déposé")
    body = (f"# {p.name}\n\n## Origine\ndéposé le {jour} · original : {rel} · nature : {nature} · empreinte {h}\n\n"
            f"## Rattachement\n{client or 'non rattaché'} (confiance {conf}){' [à confirmer]' if a_confirmer else ''} · objets cités : {', '.join(cites) or '-'}\n\n"
            f"## Texte\nintégral archivé hors git : {str(arch_txt.relative_to(ROOT)).replace(chr(92), '/')} ({len(texte)} car.)\n\n## Commentaire\n(à rédiger par l'ingesteur : objet, parties, dates, montants, délais implicites, risques, ce que Mustafa n'a pas demandé)\n")
    oid = create(typ, p.stem[:80], client=client, statut=statut, resume=resume, source=rel, liens=cites, body=body,
                 prochaine_action="lire, commenter, exploiter" if texte else "lire par le modèle", prochaine_date=iso(),
                 empreinte=h, nature=nature, texte_archive=str(arch_txt.relative_to(ROOT)))
    if not client and texte:
        F.question_add(f"Le document « {p.name} » concerne quel client ?", f"rattachement de {oid}", "laissé non rattaché", "metier", 3, sujet=p.stem)
    B.queue_add("ingestion_commentaire", oid, 2 if typ == "mail" else 3)
    if nature in ("audio", "image", "pdf_scanne", "a_lire_par_modele"):
        B.queue_add("lecture_modele", oid, 3)
    F.task_seen(f"depot:{p.suffix.lower()}")
    return {"fichier": p.name, "id": oid, "client": client, "confiance": conf, "nature": nature}

def main():
    if not DEPOT.exists():
        print(json.dumps({"deposes": 0}))
        return
    res = []
    for p in sorted(DEPOT.rglob("*")):
        if p.is_file() and not p.name.startswith((".", "~$")) and p.name not in ("desktop.ini", "Thumbs.db"):
            try:
                res.append(ingerer_fichier(p))
            except Exception as e:
                journal("ingesteur", fichier=p.name, erreur=repr(e))
                F.incident_add("ingestion", f"fichier illisible : {p.name}", "laissé dans À déposer, nouvel essai au prochain cycle")
    for d in sorted([d for d in DEPOT.rglob("*") if d.is_dir()], reverse=True):
        try:
            d.rmdir()
        except OSError:
            pass
    print(json.dumps({"deposes": len(res), "resultats": res}, ensure_ascii=False))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        journal("ingesteur", erreur=repr(e))
        print(json.dumps({"erreur": repr(e)}))
