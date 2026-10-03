"""Porte (d) tics de machine (§7.2), FR romand / DE alémanique / IT / EN.
Base : humanizer (blader/humanizer, MIT, d'après Wikipédia « Signs of AI writing »), adaptée aux usages suisses et
aux interdits de la constitution. Mesures : formules passe-partout, contrastes « non pas X mais Y », triades
systématiques, tirets longs en cascade, puces et gras dans une correspondance, émoticônes, mention de l'IA,
phrases de longueur uniforme (coefficient de variation). Renvoie des corrections suggérées ; ne réécrit rien."""
import re, statistics
from gates_common import resultat, ETAT_OK, ETAT_KO, phrases

A = r"['’]"
TICS = {
    "fr": [
        (r"il est (?:important|essentiel|crucial|primordial) de (?:noter|souligner|rappeler|préciser)", "formule de remplissage", "supprimer : énoncer directement le fait"),
        (r"il convient de (?:noter|souligner|relever)", "formule de remplissage", "supprimer"),
        (r"n" + A + r"h[ée]sitez pas", "clôture passe-partout", "supprimer ou remplacer par une proposition concrète (« je vous appelle jeudi »)"),
        (r"je reste (?:à votre (?:entière )?disposition|volontiers à disposition) pour (?:toute|tout|d" + A + r"éventuelles?) (?:question|information|renseignement)s?", "clôture passe-partout", "terminer sur la prochaine étape concrète"),
        (r"\ben conclusion\b", "formule de remplissage", "supprimer : la conclusion est en tête"),
        (r"\ben (?:résumé|somme|définitive)\b", "résumé redondant", "supprimer le résumé final"),
        (r"\bpour (?:résumer|conclure)\b", "résumé redondant", "supprimer"),
        (r"j" + A + r"esp[èe]re que (?:ce (?:message|courriel|mail)|la présente) vous trouve", "ouverture passe-partout", "entrer directement dans le sujet"),
        (r"\b(?:excellente|très bonne) question\b", "résidu de conversation", "supprimer"),
        (r"\bbien (?:sûr|entendu)\s*!", "résidu de conversation", "supprimer"),
        (r"\bje serais ravie? de\b", "résidu de conversation", "supprimer"),
        (r"\bnon (?:seulement|pas seulement)\b[^.;]{1,120}\bmais (?:aussi|également|encore)\b", "contraste mis en scène", "énoncer le point directement"),
        (r"\bce n" + A + r"est pas (?:seulement |juste |simplement )?[^.;]{1,60}, c" + A + r"est\b", "contraste mis en scène", "énoncer le point directement"),
        (r"\b(?:force est de constater|il va sans dire|dans un monde où|à l" + A + r"ère de)\b", "formule creuse", "supprimer"),
        (r"\b(?:au cœur (?:de|du)|véritable (?:levier|atout|enjeu)|incontournable|paysage (?:fiscal|juridique|réglementaire)|plonger dans|explorons|décortiquons)\b", "vocabulaire gonflé", "mot simple et précis"),
        (r"\b(?:crucial(?:e|es|aux)?|primordial(?:e|es|aux)?|essentiel(?:le|les|s)? de)\b", "insistance", "retirer l'adjectif ou chiffrer l'enjeu"),
        (r"\b(?:voici (?:ce qu" + A + r"il faut savoir|un aperçu)|passons (?:maintenant )?à)\b", "annonce avant le point", "supprimer l'annonce"),
        (r"\bil (?:pourrait|serait) (?:éventuellement|potentiellement) (?:possible|envisageable)\b", "précautions empilées", "une seule réserve, assumée"),
    ],
    "de": [
        (r"es ist (?:wichtig|entscheidend|wesentlich) (?:zu beachten|hervorzuheben|zu betonen)", "Füllformel", "streichen, Sachverhalt direkt nennen"),
        (r"zögern Sie nicht", "Standardschluss", "streichen oder konkreten nächsten Schritt nennen"),
        (r"(?:für (?:weitere )?(?:Fragen|Auskünfte) stehe(?:n)? (?:ich|wir) (?:Ihnen )?(?:gerne|jederzeit) zur Verfügung)", "Standardschluss", "mit dem nächsten Schritt enden"),
        (r"\b(?:abschliessend|zusammenfassend) (?:lässt sich sagen|kann man sagen|ist festzuhalten)\b", "Füllformel", "streichen: Fazit steht am Anfang"),
        (r"\bich hoffe, (?:diese Nachricht|es geht Ihnen gut)\b", "Standardeinstieg", "direkt zur Sache"),
        (r"\bnicht nur\b[^.;]{1,120}\bsondern auch\b", "inszenierter Kontrast", "Aussage direkt formulieren"),
        (r"\b(?:eintauchen|tauchen wir ein|vielschichtig|bahnbrechend|Landschaft der|im Herzen (?:von|des))\b", "aufgeblähtes Vokabular", "einfaches Wort"),
        (r"\b(?:entscheidend|unerlässlich|von zentraler Bedeutung)\b", "Nachdruck", "Adjektiv streichen oder beziffern"),
        (r"\bgute Frage\b|\bgerne helfe ich\b|\bselbstverständlich!\b", "Chat-Rest", "streichen"),
    ],
    "it": [
        (r"è (?:importante|fondamentale|essenziale|cruciale) (?:notare|sottolineare|ricordare)", "formula di riempimento", "eliminare, dire il fatto"),
        (r"non (?:esiti|esitate|esitare) a", "chiusura standard", "eliminare o indicare il passo successivo"),
        (r"(?:resto|restiamo) a (?:sua|vostra) (?:completa )?disposizione per (?:qualsiasi|ogni) (?:domanda|chiarimento)", "chiusura standard", "chiudere con il passo successivo"),
        (r"\bin (?:conclusione|sintesi|definitiva)\b|\bper concludere\b", "riassunto ridondante", "eliminare: la conclusione va in testa"),
        (r"\bspero che (?:questo messaggio|stia bene)\b", "apertura standard", "entrare nel merito"),
        (r"\bnon solo\b[^.;]{1,120}\bma anche\b", "contrasto messo in scena", "affermare direttamente"),
        (r"\b(?:immergersi|immergiamoci|panorama (?:fiscale|giuridico)|nel cuore di|imprescindibile)\b", "lessico gonfiato", "parola semplice"),
        (r"\b(?:cruciale|fondamentale)\b", "enfasi", "togliere l'aggettivo o quantificare"),
        (r"\bottima domanda\b|\bcertamente!\b", "residuo di chat", "eliminare"),
    ],
    "en": [
        (r"it is (?:important|worth|crucial) (?:to note|noting|to highlight|to remember)", "filler", "cut; state the fact"),
        (r"(?:don" + A + r"t|do not) hesitate to|feel free to", "stock closer", "cut or name the next step"),
        (r"\bin conclusion\b|\bin summary\b|\bto sum up\b", "redundant summary", "cut; the conclusion goes first"),
        (r"\bi hope this (?:helps|email finds you)\b|\blet me know if\b", "chatbot residue", "cut"),
        (r"\bgreat question\b|\bcertainly!\b|\bof course!\b|\byou" + A + r"re absolutely right\b", "chatbot residue", "cut"),
        (r"\bnot (?:just|only|merely)\b[^.;]{1,120}\bbut (?:also)?\b", "staged contrast", "state the point directly"),
        (r"\b(?:delve|tapestry|testament|pivotal|landscape|showcase|underscore|meticulous(?:ly)?|vibrant|intricate|garner|bolster(?:ed)?|interplay)\b", "stock AI word", "plain word"),
        (r"\b(?:let" + A + r"s dive in|here" + A + r"s what you need to know|without further ado)\b", "staged run-up", "cut the run-up"),
        (r"\b(?:stands as|serves as) a\b", "avoiding is/has", "use is / has"),
    ],
}
IA = {
    "fr": r"\b(?:intelligence artificielle|en tant qu" + A + r"(?:IA|assistant)|mod[èe]le de langage|ChatGPT|(?<!-)Claude(?!-)|GPT-\d|IA)\b",
    "de": r"\b(?:künstliche[rn]? Intelligenz|als KI|Sprachmodell|ChatGPT|(?<!-)Claude(?!-)|KI)\b",
    "it": r"\b(?:intelligenza artificiale|come IA|modello linguistico|ChatGPT|(?<!-)Claude(?!-)|IA)\b",
    "en": r"\b(?:artificial intelligence|as an AI|language model|ChatGPT|(?<!-)Claude(?!-)|AI)\b",
}
CONJ = {"fr": r"(?:et|ou)", "de": r"(?:und|oder)", "it": r"(?:e|o|ed)", "en": r"(?:and|or)"}
EMOJI = re.compile(r"[\U0001F300-\U0001FAFF\U0001F600-\U0001F64F✀-➿☀-⚟⚡-⛿]|(?<!\w)[:;]-?[)(DPp](?!\w)")
CORRESPONDANCE = {"mail", "lettre", "reponse", "courrier", "message"}


def _triades(texte, langue):
    c = CONJ.get(langue, CONJ["fr"])
    mot = r"[\w’'\-]+(?:\s[\w’'\-]+){0,2}"
    return re.findall(rf"\b{mot},\s{mot},?\s{c}\s{mot}", texte)


def analyser(texte, langue="fr", type_livrable="", lignes=None):
    """texte → liste de constats {motif, extrait, suggestion}"""
    constats = []
    for pat, motif, sugg in TICS.get(langue, []):
        for m in re.finditer(pat, texte, re.I):
            constats.append({"motif": motif, "extrait": m.group(0)[:120], "suggestion": sugg})
    for m in re.finditer(IA.get(langue, IA["fr"]), texte):
        constats.append({"motif": "mention de l'IA", "extrait": m.group(0), "suggestion": "supprimer toute mention de l'outil"})
    for m in EMOJI.finditer(texte):
        constats.append({"motif": "émoticône", "extrait": m.group(0), "suggestion": "supprimer"})
    pars = [p for p in re.split(r"\n\s*\n", texte) if p.strip()]
    # tirets longs en cascade
    tirets = len(re.findall(r"—|\s–\s|\s--\s", texte))
    cascade = [p for p in pars if len(re.findall(r"—|\s–\s|\s--\s", p)) >= 2]
    if tirets >= 3 or cascade:
        constats.append({"motif": "tirets longs en cascade", "extrait": f"{tirets} tirets", "suggestion": "remplacer par virgule, deux-points, parenthèses ou point"})
    # triades systématiques
    tri = _triades(texte, langue)
    if len(tri) >= 3 and len(tri) >= 0.25 * max(1, len(pars)):
        constats.append({"motif": "énumérations par trois systématiques", "extrait": " | ".join(t[:50] for t in tri[:3]), "suggestion": "varier : deux éléments, ou développer le plus fort"})
    # correspondance : ni puces ni gras
    if type_livrable in CORRESPONDANCE:
        src = lignes if lignes is not None else texte.split("\n")
        puces = [l for l in src if re.match(r"^\s*(?:[-*•]|\d+[.)])\s+", l)]
        if puces:
            constats.append({"motif": "puces dans une correspondance", "extrait": puces[0][:80], "suggestion": "rédiger en phrases liées"})
        if "**" in texte:
            constats.append({"motif": "gras dans une correspondance", "extrait": "**", "suggestion": "retirer le gras"})
    # longueur uniforme des phrases
    ph = [p for p in phrases(re.sub(r"\n\s*[-*•]\s+", "\n", texte)) if len(p.split()) >= 3]
    if len(ph) >= 6:
        lg = [len(p.split()) for p in ph]
        cv = statistics.pstdev(lg) / statistics.mean(lg)
        if cv < 0.30:
            constats.append({"motif": "phrases de longueur uniforme", "extrait": f"coefficient de variation {cv:.2f} sur {len(ph)} phrases", "suggestion": "mêler phrases courtes et longues"})
    return constats


def verifier(doc, ctx=None):
    langue = doc.get("langue", "fr")
    texte = "\n\n".join(p["texte"] for p in doc.get("paragraphes", []) if p["style"] not in ("tableau", "cellule"))
    lignes = None
    if doc.get("brut"):
        from mdparse import front_matter
        lignes = front_matter(doc["brut"])[1].split("\n")
    elif doc.get("type") in CORRESPONDANCE:
        lignes = [("- " if p["style"] in ("puce", "List Bullet", "List Number") else "") + p["texte"] for p in doc.get("paragraphes", [])]
    c = analyser(texte, langue, doc.get("type", ""), lignes)
    if not c:
        return resultat(ETAT_OK, [f"aucun tic détecté ({langue})"])
    motifs = sorted({x["motif"] for x in c})
    return resultat(ETAT_KO, [f"{len(c)} tic(s) : " + ", ".join(motifs)], c[:40])
