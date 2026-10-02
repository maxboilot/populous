"""Lit la structure d'un scrutin a partir de son libelle officiel.

Une loi se vote article par article : pour chaque article, l'Assemblee vote
d'abord les modifications proposees (sous-amendements, puis amendements),
puis l'article lui-meme ; a la fin, l'ensemble du texte. Chaque vote
enregistre nominativement est un « scrutin », dont le libelle dit de quoi il
s'agit : « le sous-amendement n° 1277 de Mme Garin a l'amendement n° 371 de
Mme Cathala a l'article 5 de la proposition de loi ... (premiere lecture) ».

Ce module ne devine rien : il decoupe le libelle, et renvoie None pour ce
qu'il n'y trouve pas. Aucun texte n'est invente ; l'app affiche les champs tels
quels. Utilise par ingest_scrutins.py (choix du scrutin vedette) et
construire_detail_jour.py (fenetre « Detail » de l'app).
"""
import re

# Rang de priorite pour le scrutin vedette : plus c'est haut, plus le vote
# dit ou en est le texte. Un amendement ou un sous-amendement n'est qu'une
# etape sur le chemin d'un article.
RANG = {
    'ensemble': 4,
    'article': 3,
    'motion': 2,
    'autre': 1,
    'amendement': 0,
    'sous-amendement': 0,
}

_TEXTES = (
    r"proposition de loi organique|projet de loi organique|proposition de loi constitutionnelle|"
    r"projet de loi constitutionnelle|proposition de loi|projet de loi|proposition de résolution"
)
_LECTURE = r"\((?:première|nouvelle|deuxième|seconde|troisième|lecture définitive|texte de la commission mixte|[^)]*lecture)[^)]*\)"
_ART = r"(liminaire|premier|1er|unique|\d+(?:\s?(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?(?:\s[A-Z])?)"


def _norm(t):
    return re.sub(r"\s+", " ", (t or "").replace("’", "'").replace("\xa0", " ")).strip()


def nature(titre):
    t = _norm(titre).lower()
    if t.startswith("le sous-amendement"):
        return "sous-amendement"
    if t.startswith("l'amendement"):
        return "amendement"
    if t.startswith("l'article"):
        return "article"
    if t.startswith("l'ensemble"):
        return "ensemble"
    if t.startswith("la motion"):
        return "motion"
    return "autre"


def rang(titre, solennel=False):
    """Vote solennel d'abord (cas historique), puis ensemble > article >
    motion > autre > amendements."""
    return 5 if solennel else RANG[nature(titre)]


def article_ref(titre):
    """Article concerne : celui que le scrutin vote (« l'article 5 ») ou
    auquel l'amendement se rattache (« a / apres l'article 5 »)."""
    t = _norm(titre)
    m = re.search(r"(?:^l'article|(?:à|après|avant|suppression de) l'article)\s+" + _ART, t, re.I)
    if m:
        return m.group(1)
    return "titre" if re.search(r"\bau titre de\b", t) else None


def numero_amendement(titre):
    m = re.search(r"n°\s*(\d+)", _norm(titre))
    return int(m.group(1)) if m else None


def amendement_parent(titre):
    m = re.search(r"à l'amendement n°\s*(\d+)", _norm(titre))
    return int(m.group(1)) if m else None


def auteur(titre):
    """« Mme Garin », « M. Coquerel », « du Gouvernement »... tel que ecrit."""
    t = _norm(titre)
    m = re.search(r"n°\s*\d+(?:\s*\(rect\.\))?(?:\s+rectifié)?\s+(?:de|du|des)\s+(.+?)(?=\s+(?:et\s+(?:l'|les\s)|à\s|après\s|avant\s)|,|$)", t)
    if not m:
        return None
    a = m.group(1).strip()
    return a if a.startswith(("M.", "Mme", "MM.", "Mmes")) else (f"du {a}" if a.lower().startswith("gouvernement") else a)


def texte_de_loi(titre):
    """(nature du texte, intitule, lecture) ; None si le libelle ne cite pas
    de texte (motion de censure, demande de suspension...)."""
    t = _norm(titre).rstrip(" .")
    m = re.search(r"(" + _TEXTES + r")(?:,\s*adoptée?\s+par\s+le\s+Sénat,?)?\s+(.+)$", t, re.I)
    if not m:
        return None
    nature_texte, reste = m.group(1).lower(), m.group(2)
    lecture = None
    ml = re.search(_LECTURE + r"(?:\s*" + _LECTURE + r")*\s*$", reste, re.I)
    if ml:
        lecture = ml.group(0).strip()
        reste = reste[:ml.start()].strip()
    return nature_texte, reste.rstrip(" ."), lecture


def cle_loi(titre):
    """Cle stable pour regrouper les scrutins d'un meme texte."""
    tl = texte_de_loi(titre)
    return _norm(f"{tl[0]} {tl[1]}").lower() if tl else None


def intitule_normalise(t):
    """Compare l'intitule d'une loi cite par un scrutin (« apportant une
    reponse... ») au titre de son dossier (« Apporter une reponse... ») :
    minuscules, sans ponctuation, sans le premier mot (le verbe change)."""
    mots = re.sub(r"\W+", " ", _norm(t).lower()).split()
    return " ".join(mots[1:])
