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

import re
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

    # --- 9. Le canal de mise à jour doit démarrer STABLE (flag beta désactivé) --
    # Le socle upstream est un build beta : b.a = true fait écrire
    # pref_update_channel = "1" au premier lancement de toute installation
    # neuve, et le canal Beta ne voit que des entrées ReleaseType: 1 — notre
    # publication stable y est muette, sans aucune erreur.
    check(
        "Canal : le patch force le flag beta à false (canal stable par défaut)",
        "BETA_FLAG_OLD" in patcher
        and "BETA_FLAG_NEW" in patcher
        and "force_stable_channel" in patcher
        and ".field public static final a:Z = false" in patcher,
        "le patch doit replacer b.a = true par b.a = false (voir BETA_FLAG_*)",
    )

    # --- 10. Le nettoyage doit bien etre atteignable (pas de return avant) -------
    body_ok = sanitizer.find(":body_ok")
    is_playlist = sanitizer.find(":is_playlist")
    check(
        "PlaylistSanitizer : le chemin de nettoyage existe",
        body_ok != -1 and is_playlist != -1 and is_playlist > body_ok,
        "labels :body_ok / :is_playlist introuvables ou dans le desordre",
    )

    # --- 11. Tap → clic Leanback : un appui suffit, mais jamais deux ouvertures --
    # Sur appareil (19/09), le premier appui sur une carte ne faisait que deplacer
    # la selection : la rangee relachait la cible pendant la transition de focus.
    # Le traducteur doit cliquer le tap franc, et RIEN faire quand la carte etait
    # deja selectionnee au moment de l'appui — sinon le clic natif s'y ajoute.
    tap = load("TapClick.smali")
    flat = "\n".join(line for line in tap.splitlines() if line.strip())
    check(
        "TapClick : le tap franc est traduit en clic",
        "    sget-boolean v1, Lcom/twouich/adblock/TapClick;->moved:Z\n"
        "    if-nez v1, :up_moved" in flat
        and "    invoke-virtual {v1}, Landroid/view/View;->performClick()Z" in flat,
        "attendu : 'if-nez v1, :up_moved' (= refuser des que moved est vrai). "
        "'if-eqz' refusait au contraire TOUS les taps francs : le premier appui "
        "n'ouvrait toujours rien.",
    )
    check(
        "TapClick : notre clic est le seul (relachement consomme)",
        "    if-eqz v1, :up_nothing\n"
        "    # Trace logcat" in flat
        and "    invoke-virtual {v1}, Landroid/view/View;->performClick()Z\n"
        "    const/4 v0, 0x1\n"
        "    return v0" in flat
        and "leanbackHandles" not in flat,
        "attendu : aucune exception basee sur l'etat de la carte (le focus ni la "
        "selection ne predisent le clic natif — mesure du 19/09), et un `return 1` "
        "apres performClick pour que la grille ne voie jamais le relachement.",
    )
    check(
        "TapClick : le geste est annule avant le clic",
        0 < flat.find("cancelGesture") < flat.rfind("performClick()Z"),
        "la carte resterait « appuyee » si le relachement n'etait pas annule",
    )
    check(
        "TapClick : seuil de glissement lu depuis ViewConfiguration",
        "getScaledTouchSlop()I" in flat,
        "un seuil en dur se tromperait selon la densite de l'ecran",
    )
    check(
        "TapClick : la television est hors de portee (600 dp)",
        "const/16 v1, 0x258" in flat
        and "smallestScreenWidthDp:I" in flat
        and "if-ge v0, v1, :tv" in flat,
        "attendu : clic tactile seulement si smallestScreenWidthDp < 600",
    )
    # Le 19/09, la descente dans l'arbre etait court-circuitee : `if-nez` sur le
    # resultat d'`instance-of` sautait au test « cette vue est cliquable » des que
    # la vue ETAIT un ViewGroup. La grille (cliquable) etait donc renvoyee comme
    # cible, et le tap ne faisait rien. Meme erreur pour `isClickable`.
    check(
        "TapClick : la descente dans les enfants n'est pas court-circuitee",
        "    instance-of v1, p0, Landroid/view/ViewGroup;\n"
        "    if-eqz v1, :clickable" in flat
        and "    invoke-virtual {p0}, Landroid/view/View;->isClickable()Z\n"
        "    move-result v1\n"
        "    if-eqz v1, :null" in flat,
        "attendu : 'if-eqz v1, :clickable' (instance-of vrai -> descendre) et "
        "'if-eqz v1, :null' (non cliquable -> rien). Avec 'if-nez', la grille se "
        "declarait elle-meme cible et le tap restait sans effet.",
    )
    check(
        "TapClick : la cible est cherchee recursivement sous le doigt",
        flat.count("clickableAt(Landroid/view/View;FF)Landroid/view/View;") >= 3
        and "getChildCount()I" in flat
        and "isClickable()Z" in flat,
        "il faut la plus profonde vue cliquable, sinon le tap sur la vignette "
        "n'atteint pas la carte",
    )

    # --- 12. Le branchement doit rester en tete de dispatchTouchEvent -----------
    check(
        "BaseGridView : tap traduit avant la logique d'origine de la grille",
        "TAP_HOOK_CALL" in patcher
        and "TAP_HOOK_LABEL" in patcher
        and "BASE_GRID_CLASS" in patcher
        and "find_base_grid" in patcher
        and "dispatchTouchEvent(Landroid/view/MotionEvent;)Z" in patcher
        and ".locals 3" in patcher,
        "le hook doit lire l'en-tete .locals 1 de la methode et passer a .locals 3",
    )

    # --- 13. Un override de callback doit rester public ------------------------
    # Le 2026-09-20, l'override d'onWindowFocusChanged injecte dans PlayerActivity
    # etait declare `.method protected`. Activity implemente Window.Callback, dont
    # onWindowFocusChanged(boolean) est public : le lieur ART rejette alors la
    # CLASSE ENTIERE ("implementing interface method ... is not public"). Sur
    # BlueStacks/API 25, PlayerActivity devenait introuvable et ouvrir un direct
    # plantait l'application -- alors que la meme APK se lancait sur l'appareil
    # de reference. Un test d'octets ne peut pas voir les drapeaux d'acces : il
    # faut les declarer ici, a la source.
    # On ne cherche que la DECLARATION (suivie de son corps), pas les mentions
    # citees dans les regles de reparation de patch.py, qui doivent pouvoir
    # nommer la forme fautive pour la corriger. Les callbacks du framework
    # surcharges par le patch sont tous dans cette liste : le 20/09, l'un d'eux
    # manquait et faisait rejeter la classe entiere par ART.
    callbacks = ("onWindowFocusChanged(Z)V",
                 "onPictureInPictureModeChanged(ZLandroid/content/res/Configuration;)V",
                 "onConfigurationChanged(Landroid/content/res/Configuration;)V")
    injected = dict(all_smali())
    injected["patch.py (smali embarque)"] = patcher
    found = {sig: {} for sig in callbacks}
    for sig in callbacks:
        decl = re.compile(rf"\.method\s+(public|protected|private)\s+{re.escape(sig)}\s*\n\s*\.locals")
        for name, text in injected.items():
            for m in decl.finditer(text):
                found[sig].setdefault(name, []).append(m.group(1))
    weak = [f"  {sig} : {name} = {', '.join(vis)}"
            for sig, by_file in found.items() for name, vis in by_file.items()
            if any(v != "public" for v in vis)]
    check(
        "greffon entier : aucun override de callback declare protected (ART rejette la classe)",
        not weak,
        "\n".join(weak) + "\n    Window.Callback declare ces callbacks publics : un override plus "
        "faible fait echouer le chargement de la classe (PlayerActivity introuvable, "
        "crash a l'ouverture d'un direct)",
    )
    # --- 14. Polarite des tests de place du lecteur telephonique ---------------
    # Meme famille de faute que §6 : les deux tests de place ont ete ecrits a
    # l'envers une fois (la video qui tenait etait plafonnee, et l'empilement se
    # faisait quand il n'y avait pas la place). Ils se relisent ici en une ligne
    # chacun, ce qui est la seule facon de les verrouiller avant l'appareil.
    for expected, detail in (
        ("    if-lt v10, v7, :twouich_phone_video_fits",
         "attendu : 'if-lt' pour SAUTER le plafond quand la video 16:9 tient "
         "deja dans la hauteur (v10 < v7). Avec 'if-ge', la video tient mais "
         "est plafonnee quand meme, et le chat tombe a zero."),
        ("    if-ge v7, v3, :twouich_phone_room",
         "attendu : 'if-ge' pour empiler quand il reste au moins un tiers de la "
         "hauteur pour le chat. Avec 'if-lt', l'empilement se fait en paysage, "
         "la ou il n'y a justement pas la place."),
    ):
        check(
            f"PlayerActivity : polarite du test de place ({expected.split(':')[-1]})",
            expected in patcher,
            detail,
        )

    check(
        "PlayerActivity : les trois callbacks surcharges sont declares public",
        all(found[sig].get("patch.py (smali embarque)") == ["public"] for sig in callbacks)
        and "twouichPhoneStackedLayout" in patcher,
        "l'application du lecteur empile se fait au retour du focus, la disposition "
        "est reappliquee au redimensionnement, et l'entree en incrustation doit "
        "rester traitee : les trois overrides doivent rester public",
    )

    # --- 15. Incrustation : la disposition telephonique ne doit plus repasser --
    # L'acceptation PiP du 20/09 sur le telephone a montre la barre « Envoyer un
    # message » tracee sur le bas de la FENETRE D'INCRUSTATION : l'entree en PiP
    # fait perdre le focus et changer la configuration, et chacun de ces rappels
    # reappliquait l'empilement APRES le masquage pose par le rappel PiP.
    # Seul le bloc INJECTE fait foi : les controles de patch.py doivent nommer la
    # forme fautive pour la corriger, et se denonceraient eux-memes (meme piege
    # que pour la visibilite des callbacks, §13).
    def constant(name):
        parts = patcher.split(f"{name} = (", 1)
        return parts[1].split("\n)\n", 1)[0] if len(parts) > 1 else ""

    guard = constant("PHONE_PIP_GUARD")
    state_write = constant("PHONE_PIP_STATE_WRITE")
    check(
        "PlayerActivity : la disposition empilee est refusee pendant l'incrustation",
        ".field private twouichPipActive:Z" in patcher
        and "iget-boolean v11, p0, Lcom/s0und/s0undtv/activities/"
            "PlayerActivity;->twouichPipActive:Z" in guard
        and "    if-eqz v11, :twouich_phone_layout_ok" in guard
        and "''' + PHONE_PIP_GUARD + r'''" in patcher,
        "attendu : sortir de twouichPhoneStackedLayout quand le champ "
        "twouichPipActive est vrai, sinon le chat et la saisie reviennent "
        "par-dessus la video en incrustation.",
    )
    check(
        "PlayerActivity : le garde d'incrustation n'est pas inverse",
        guard and "if-nez" not in guard,
        "'if-nez' reappliquerait l'empilement exactement pendant l'incrustation "
        "(meme famille de faute que §6 et §11).",
    )
    check(
        "PlayerActivity : l'etat d'incrustation est ecrit en tete du rappel PiP",
        "iput-boolean p1, p0, Lcom/s0und/s0undtv/activities/"
        "PlayerActivity;->twouichPipActive:Z" in state_write
        and "''' + PHONE_PIP_STATE_WRITE + r'''" in patcher,
        "l'ecriture de l'etat doit etre branchee juste apres l'appel au parent, "
        "avant tout retour : sinon le garde refuserait la disposition au moment "
        "meme ou il faut la remettre (sortie d'incrustation).",
    )

    # Le 20/09, twouichPhoneView sautait vers son retour nul des que
    # l'identifiant ETAIT trouve : la vue n'etait jamais rendue, le rappel PiP
    # sortait aussitot sur ses trois tests de nullite, et rien n'etait masque
    # (chat et saisie visibles par-dessus la video, mesures sur le telephone).
    # Seul le bloc injecte fait foi, le controle de patch.py devant nommer la
    # forme fautive pour la reparer.
    view_block = patcher.split(".method private twouichPhoneView", 1)
    view_block = view_block[1].split(".end method", 1)[0] if len(view_block) > 1 else ""
    check(
        "PlayerActivity : twouichPhoneView rend bien la vue trouvee",
        "    if-eqz v0, :no_phone_view" in view_block
        and "if-nez v0, :no_phone_view" not in view_block,
        "attendu : 'if-eqz v0, :no_phone_view' (= retour nul seulement quand "
        "l'identifiant vaut 0). Avec 'if-nez', la vue etait nulle des que "
        "l'identifiant existait : le rappel PiP ne masquait ni le chat ni la "
        "saisie.",
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
