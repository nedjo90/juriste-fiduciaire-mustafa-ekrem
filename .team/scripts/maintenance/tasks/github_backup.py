"""Extension du cycle : conseil facultatif « copie privée sur votre propre compte GitHub ».

Le travail de Mustafa reste sur son poste (commits locaux + sauvegarde chiffrée). Une copie en ligne sur SON compte est un
plus, jamais une obligation : on ne la propose pas tout de suite. Après trois semaines d'usage, s'il n'existe pas encore de
dépôt privé nommé « sauvegarde », un seul conseil entre dans la file du brief (au plus un conseil par jour, jamais pendant la
première session ni la construction ; ignoré deux fois → plus jamais présenté : voir cb/files.conseil_next).
S'il dit oui, l'associé suit la skill `github-backup` (pas à pas, l'équipe fait toutes les manipulations)."""
import datetime as dt
import subprocess

DELAI_JOURS = 21
CLE = "github-backup"
TEXTE = ("Une idée facultative, quand vous aurez cinq minutes : je peux garder une copie privée de votre travail sur votre "
         "propre compte GitHub, à l'abri si cet ordinateur tombe en panne. Je vous guide pas à pas et je fais le reste ; "
         "dites simplement « copie en ligne » le jour où cela vous arrange.")


def _a_un_depot_sauvegarde():
    import background as fond
    try:
        r = subprocess.run(["git", "-C", str(fond.ROOT), "remote"], capture_output=True, text=True, timeout=20,
                           stdin=subprocess.DEVNULL)
        return "sauvegarde" in r.stdout.split()
    except Exception:
        return False  # git absent : le conseil reste pertinent, l'installation de git est faite par l'équipe


def t_conseil_sauvegarde_github(arg, fin):
    import background as fond
    fond.cb()
    from cb import core, files as F
    if core.get_etat("conseil_sauvegarde_github_le"):
        return {"deja": True}
    debut = core.get_etat("premiere_session_le")
    if not debut or (core.today() - dt.date.fromisoformat(debut)).days < DELAI_JOURS:
        return {"trop_tot": True}
    if _a_un_depot_sauvegarde():
        core.set_etat("conseil_sauvegarde_github_le", core.iso())
        return {"deja_configure": True}
    cid = F.conseil_add(TEXTE, CLE, 2)
    core.set_etat("conseil_sauvegarde_github_le", core.iso())
    return {"conseil": cid}


TACHES = {"conseil_sauvegarde_github": t_conseil_sauvegarde_github}
CADENCES = {"conseil_sauvegarde_github": (7, 6)}
