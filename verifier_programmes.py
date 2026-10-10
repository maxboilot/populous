#!/usr/bin/env python3
"""Vérifie que chaque passage de data/programmes/*.json est repris MOT POUR
MOT du document officiel cité.

Pour chaque fichier : télécharge le document, contrôle son empreinte SHA-256
(si le document a changé, il faut le relire : le script échoue), extrait le
texte de la page citée et vérifie que chaque paragraphe du passage s'y trouve.
La comparaison ignore seulement les espaces, les retours à la ligne, les
traits d'union de césure et le type d'apostrophe : aucun mot ne peut être
ajouté, retiré ou modifié sans faire échouer la vérification.

Usage : python verifier_programmes.py [cle ...] [id_document=chemin.pdf ...]
Dépendance : pypdf (pip install pypdf).
"""
import hashlib, io, json, pathlib, re, ssl, subprocess, sys, unicodedata, urllib.error, urllib.request

UA = "Populous/1.0 (+https://maxboilot.github.io/populous/)"


def telecharger(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()
    except (ssl.SSLError, urllib.error.URLError) as e:
        if "CERTIFICATE" not in str(e).upper():
            raise
        return subprocess.run(["curl", "-sSL", "-m", "120", "-A", UA, url], check=True, capture_output=True).stdout


def normaliser(t):
    t = unicodedata.normalize("NFKC", t).replace("’", "'").replace("‘", "'")
    return re.sub(r"[\s\-‐‑–]+", "", t)


def pages_pdf(octets):
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("pypdf manquant : pip install pypdf")
    return [(p.extract_text() or "") for p in PdfReader(io.BytesIO(octets)).pages]


def verifier(chemin, local):
    d = json.loads(pathlib.Path(chemin).read_text(encoding="utf-8"))
    cle = d["cle"]
    themes = {t["code"] for t in json.loads(pathlib.Path("data/themes.json").read_text(encoding="utf-8"))}
    erreurs, ignores, pages_par_doc = [], [], {}
    for doc in d["documents"]:
        did = doc["id"]
        if doc.get("format") != "pdf":
            erreurs.append("%s/%s : format %r non géré par ce script" % (cle, did, doc.get("format")))
            continue
        if did in local:
            octets = pathlib.Path(local[did]).read_bytes()
        elif doc.get("telechargement_protege"):
            ignores.append("%s/%s : téléchargement protégé par le site, vérifier avec --local %s=chemin.pdf" % (cle, did, did))
            continue
        else:
            octets = telecharger(doc["url"])
        if hashlib.sha256(octets).hexdigest() != doc["sha256"]:
            erreurs.append("%s/%s : le document a changé (SHA-256 différent) : relire le programme" % (cle, did))
            continue
        pages = pages_pdf(octets)
        if len(pages) != doc["pages"]:
            erreurs.append("%s/%s : %d pages au lieu de %d" % (cle, did, len(pages), doc["pages"]))
        pages_par_doc[did] = pages
    ids = {doc["id"] for doc in d["documents"]}
    for i, p in enumerate(d["passages"], 1):
        did = p["document"]
        if did not in ids:
            erreurs.append("%s passage %d : document inconnu %r" % (cle, i, did))
            continue
        if p["theme"] not in themes:
            erreurs.append("%s passage %d : thème inconnu %r" % (cle, i, p["theme"]))
        if not p["paragraphes"]:
            erreurs.append("%s passage %d : vide" % (cle, i))
        if did not in pages_par_doc:
            continue
        pages = pages_par_doc[did]
        if not 1 <= p["page_pdf"] <= len(pages):
            erreurs.append("%s passage %d : page %d hors document" % (cle, i, p["page_pdf"]))
            continue
        page = normaliser(pages[p["page_pdf"] - 1])
        for j, para in enumerate(p["paragraphes"], 1):
            if len(para.strip()) < 40 or normaliser(para) not in page:
                erreurs.append("%s passage %d, paragraphe %d (%s, page %d) : texte absent de la page citée : %.70r"
                               % (cle, i, j, did, p["page_pdf"], para))
    return erreurs, ignores


def main():
    args, local = [], {}
    for a in sys.argv[1:]:
        if "=" in a:
            k, v = a.split("=", 1)
            local[k] = v
        else:
            args.append(a)
    fichiers = sorted(pathlib.Path("data/programmes").glob("*.json"))
    if args:
        fichiers = [f for f in fichiers if f.stem in args]
    if not fichiers:
        sys.exit("Aucun programme à vérifier")
    total = 0
    for f in fichiers:
        err, ign = verifier(f, local)
        n = len(json.loads(f.read_text(encoding="utf-8"))["passages"])
        print("%-12s %s" % (f.stem, ("OK, %d passages mot pour mot" % n if not ign else "OK sauf documents ignorés") if not err else "ÉCHEC"))
        for e in err:
            print("   -", e)
        for e in ign:
            print("   ~ ignoré :", e)
        total += len(err)
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
