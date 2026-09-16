#!/usr/bin/env python3
"""
test_smali_branches.py — garde-fou sur les branchements de notre smali.

Pourquoi ce test existe
-----------------------
Le 2026-09-15, la lecture etait cassee sur appareil pour deux raisons qui ne
pouvaient PAS etre vues par test_sanitizer.py (qui teste un miroir Python) :

  1. `if-nez` avait ete ecrit la ou il fallait `if-eqz` (et inversement) dans
     PlaylistSanitizer.a : les vraies playlists repartaient intactes, pubs
     comprises.  2. `if-gez` / `if-gtz` avaient ete lus comme " < 0 " / " > 0 " alors que
     le bytecode Dalvik definit :
         if-ltz -> v <  0        if-gez -> v >= 0
         if-gtz -> v >  0        if-lez -> v <= 0
     Resultat : la boucle de lecture s'arretait des le premier octet recu et la
     playlist arrivee vide cassait le lecteur.

  3. Le 2026-09-15 au soir, le self-test embarque (SelfTest.smali, execute sur
     l'appareil) a montre un troisieme cas du meme genre, dans le COMPTEUR :
     le test `startsWith("#")` du chemin "ligne jetee" etait branche a l'envers,
     donc la trace logcat comptait les balises (#EXTINF, #EXT-X-DATERANGE) et
     ignorait les URI. Le nettoyage, lui, etait correct -- seule la preuve
     annoncee etait fausse (4 segments annonces pour 3). Ni le miroir Python ni
     ce fichier ne pouvaient le voir : il fallait executer le vrai bytecode.

Ce test verrouille ces deux points. Il ne remplace pas le test sur appareil
(patch/test-device.sh), il l'empeche de rejouer les memes degats.
"""

from pathlib import Path

HERE = Path(__file__).resolve().parent
SMALI = HERE.parent / "smali" / "com" / "twouich" / "adblock"
PATCHER = HERE.parent / "patch.py"

# Opcodes ambigus : leur nom se lit naturellement a l'envers de la semantique
# Dalvik. On impose l'emploi des formes non ambigues (eqz/nez/ltz/lez).
AMBIGUOUS = ("if-gez", "if-gtz")

checks = []


def load(name):
    path = SMALI / name
    if not path.is_file():
        raise SystemExit(f"smali introuvable : {path}")
    return path.read_text(encoding="utf-8")


def all_smali():
    """Tout le greffon : un nouveau fichier smali est surveille sans rien changer ici."""
    files = sorted(SMALI.glob("*.smali"))
    if not files:
        raise SystemExit(f"aucun smali dans {SMALI}")
    return {f.name: f.read_text(encoding="utf-8") for f in files}


def check(label, condition, detail=""):
    checks.append((label, bool(condition), detail))


def branch_lines(text):
    """Retourne [(numero, ligne)] pour toutes les instructions de branchement."""
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        for op in ("if-eq", "if-ne", "if-lt", "if-ge", "if-gt", "if-le"):
            if stripped.startswith(op):
                out.append((n, stripped))
                break
    return out


def main():
    source = load("AdBlockDataSource.smali")
    sanitizer = load("PlaylistSanitizer.smali")
    selftest = load("SelfTest.smali")

    # --- 1. Aucun opcode ambigu, dans TOUT le greffon ---------------------------
    offenders = []
    for name, text in all_smali().items():
        for n, line in branch_lines(text):
            if any(line.startswith(op) for op in AMBIGUOUS):
                offenders.append(f"  {name}:{n}: {line}")
    check(
        "greffon entier : pas d'opcode ambigu (if-gez/if-gtz)",
        not offenders,
        "\n".join(offenders) + "\n    utiliser if-ltz (v < 0) ou if-lez (v <= 0)",
    )

    # --- 2. Remplissage du cache : uniquement quand c == null -------------------
    check(
        "read() : :fill atteint seulement si le cache est nul (if-eqz)",
        "if-eqz v0, :fill" in source,
        "attendu : 'if-eqz v0, :fill' (= si c == null). "
        "'if-nez' enverrait le premier appel sur array-length(null).",
    )

    # --- 3. Boucle de lecture : arret sur fin de flux (v < 0) -------------------
    check(
        "boucle de lecture : arret sur -1 (if-ltz)",
        "if-ltz v3, :drained" in source,
        "attendu : 'if-ltz v3, :drained' (= si octets lus < 0). "
        "'if-gez' testait '>= 0' et sortait de la boucle avant d'ecrire.",
    )

    # --- 4. Fin de cache : -1 quand il ne reste rien ----------------------------
    check(
        "serve : fin de flux quand il ne reste rien (if-lez)",
        "if-lez v3, :eof" in source,
        "attendu : 'if-lez v3, :eof' (= si restant <= 0). "
        "'if-gtz' testait '> 0' et renvoyait 0 au lecteur "
        "(« Underlying input stream returned zero bytes »).",
    )

    # --- 5. Garde de PlaylistSanitizer : nettoyer SEULEMENT une playlist --------
    check(
        "PlaylistSanitizer : nettoyage reserve aux corps contenant #EXTM3U (if-nez)",
        "if-nez v1, :is_playlist" in sanitizer,
        "attendu : 'if-nez v1, :is_playlist' (= si contains(#EXTM3U)). "
        "'if-eqz' faisait l'inverse : playlists renvoyees intactes, "
        "corps non-playlist nettoyes pour rien.",
    )

    # --- 6. Compteur : seules les URI comptent (une par segment) ---------------
    check(
        "compteur pub : les balises ne sont pas comptees (if-nez)",
        "if-nez v5, :drop_nocount" in sanitizer,
        "attendu : 'if-nez v5, :drop_nocount' (= la ligne commence par #). "
        "'if-eqz' comptait les balises et ignorait les URI : la trace logcat "
        "annoncait 4 segments pub la ou il y en avait 3.",
    )

    # --- 7. Le self-test doit continuer d'exercer le VRAI chemin de lecture -----
    # Un self-test qui n'appelle plus AdBlockDataSource ne prouverait plus rien :
    # c'est cette traversee (c() puis read()) qui reproduisait la lecture cassee.
    check(
        "SelfTest : ouvre et lit via AdBlockDataSource",
        "AdBlockDataSource;->c(Lz3/p;)J" in selftest
        and "AdBlockDataSource;->read([BII)I" in selftest,
        "le self-test doit appeler c() puis read() sur AdBlockDataSource",
    )
    check(
        "SelfTest : source factice declarée (Lz3/l)",
        ".implements Lz3/l;" in load("SelfTest$Fake.smali"),
        "SelfTest$Fake.smali doit implementer l'interface DataSource de l'app",
    )

    # --- 8. L'updater doit lire la version installée, pas un plancher figé -----
    patcher = PATCHER.read_text(encoding="utf-8")
    check(
        "Updater : comparaison avec PackageManager",
        "PackageManager;->getPackageInfo" in patcher
        and "UPDATE_VERSION_CALL" in patcher
        and "UPDATE_VERSION_METHOD" in patcher,
        "le patch doit remplacer le plancher upstream par la version installée",
    )

    # --- 9. Le nettoyage doit bien etre atteignable (pas de return avant) -------
    body_ok = sanitizer.find(":body_ok")
    is_playlist = sanitizer.find(":is_playlist")
    check(
        "PlaylistSanitizer : le chemin de nettoyage existe",
        body_ok != -1 and is_playlist != -1 and is_playlist > body_ok,
        "labels :body_ok / :is_playlist introuvables ou dans le desordre",
    )

    # --- rapport ----------------------------------------------------------------
    width = max(len(label) for label, _, _ in checks)
    failed = 0
    for label, ok, detail in checks:
        print(f"[{'OK ' if ok else 'KO '}] {label.ljust(width)}")
        if not ok:
            failed += 1
            if detail:
                print(f"        -> {detail}")

    print(f"\n{len(checks) - failed}/{len(checks)} verifications passees")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
