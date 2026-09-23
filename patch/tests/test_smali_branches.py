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


def skipped_creation(smali_name, smali_text):
    """Branchements qui sautent la CREATION du champ statique qu'ils testent.

    Motif fautif, mesure sur le telephone le 21/09 (PlayerKeepAlive.twouichWake
    et twouichSession) :

        sget-object v0, L...;->cache:...
        if-eqz v0, :cache_done      # saute quand le champ est NUL
        ... new-instance / sput-object v0, L...;->cache:...
      :cache_done                   # <- arrive ici avec v0 TOUJOURS nul

    « if-eqz » saute exactement dans le cas ou la creation est necessaire : le
    champ reste nul, et isHeld() ou tout autre appel sur l'objet rendu tombe sur
    un objet nul. Le pendant « if-nez » est correct : il saute quand le champ est
    deja rempli.
    """
    lines = smali_text.splitlines()
    out = []
    label_at = {}
    for n, line in enumerate(lines):
        s = line.strip()
        if s.startswith(":") and " " not in s and len(s) > 1:
            label_at.setdefault(s[1:], n)
    for n, line in enumerate(lines):
        s = line.strip()
        if not s.startswith("sget-object "):
            continue
        parts = s.replace(",", " ").split()
        register, field = parts[1], parts[2]
        for m in range(n + 1, len(lines)):
            nxt = lines[m].strip()
            if not nxt or nxt.startswith("#"):
                continue
            if not nxt.startswith("if-eqz %s," % register):
                break
            label = nxt.split(",")[-1].strip().lstrip(":")
            end = label_at.get(label)
            if end is None:
                break
            if end <= m:
                break
            for k in range(m + 1, end):
                body = lines[k].strip()
                if body.startswith("sput-object %s," % register) and field in body:
                    out.append(
                        "%s:%d %s saute la creation de %s"
                        % (smali_name, m + 1, nxt.split(",")[0].strip(), field)
                    )
                    break
            break
    return out


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


# --- Registres : aucune ecriture dans un registre de parametre -----------------
# Le 21/09/2026, PlayerKeepAlive.stop(Context) declarait `.locals 2` alors que son
# corps ecrivait dans v2 — qui, avec deux registres locaux, EST p0 (le Context).
# Le `const-class v2` a donc remplace le Context par un Class, et le verificateur
# d'ART a rejete TOUTE la classe au demarrage du lecteur :
#   VerifyError: [0xB] 'this' argument 'Reference: java.lang.Class' not instance
#   of 'Reference: android.content.Context'
# Le build, le patch et les autres tests passaient : seule la mesure sur appareil
# l'a vu. La regle est donc posee ici, hors appareil : avec `.locals N`, les
# registres v0..v(N-1) sont locaux et vN, v(N+1)… sont p0, p1… Ecrire dans l'un
# d'eux casse le contrat de type que le verificateur verifie.
# Instructions qui IMPOSENT un type a la valeur ecrite (constante, nouvel objet,
# champ lu, exception). Une reutilisation du parametre par move-result-object
# (PlaylistSanitizer.a le fait pour renvoyer sa chaine transformee) est licite :
# elle ne change pas le type. C'est une constante ou un objet neuf dans un
# registre de parametre qui casse le contrat verifie par ART.
TYPE_IMPOSING = (
    "const/4", "const/16", "const", "const/high16",
    "const-wide", "const-wide/16", "const-wide/32", "const-wide/high16",
    "const-string", "const-string/jumbo", "const-class",
    "new-instance", "new-array", "move-exception",
    "instance-of", "array-length",
    "sget", "sget-object", "sget-boolean", "sget-byte", "sget-char", "sget-short",
    "sget-wide",
    "iget", "iget-object", "iget-boolean", "iget-byte", "iget-char", "iget-short",
    "iget-wide",
)


def _param_width(signature: str) -> int:
    """Nombre de registres de parametre d'une methode (this compris)."""
    params = signature.split("(", 1)[1].split(")", 1)[0] if "(" in signature else ""
    count = 0 if " static " in signature else 1
    i = 0
    while i < len(params):
        ch = params[i]
        if ch == "[":
            i += 1
            continue
        if ch == "L":
            i = params.index(";", i) + 1
            count += 1
            continue
        count += 2 if ch in "JD" else 1
        i += 1
    return count


def param_writes(name: str, text: str) -> list[str]:
    """Ecritures dans un registre de parametre : « fichier:methode v2 (= p0) »."""
    body_re = re.compile("(?ms)^[.]method ([^\n]*)\n(.*?)^[.]end method")
    locals_re = re.compile("^[ 	]*[.](locals|registers) ([0-9]+)", re.M)
    register_re = re.compile("([vp])([0-9]+)")
    out = []
    for block in body_re.finditer(text):
        signature, body = block.group(1), block.group(2)
        locals_line = locals_re.search(body)
        if locals_line is None:
            continue
        declared, count = locals_line.group(1), int(locals_line.group(2))
        if declared == "locals":
            first_param = count
        else:
            first_param = count - _param_width(signature)
        method_name = signature.split("(")[0].split()[-1]
        for raw in body.splitlines():
            line = raw.split("#", 1)[0].strip()
            if not line or line.startswith(".") or line.startswith(":"):
                continue
            words = line.split()
            if words[0] not in TYPE_IMPOSING or len(words) < 2:
                continue
            match = register_re.fullmatch(words[1].rstrip(","))
            if match is None:
                continue
            index = int(match.group(2))
            if match.group(1) == "p":
                index += first_param
            if index >= first_param:
                alias = "p%d" % (index - first_param)
                out.append(f"{name}:{method_name} ecrit dans {words[1].rstrip(chr(44))} (= {alias})")
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



    # --- 16. Registres : ecrire dans un parametre, jamais ----------------------
    # Le 21/09, le build et tous les tests hors appareil passaient pendant que le
    # lecteur plantait : PlayerKeepAlive.stop() avait `.locals 2` et ecrivait dans
    # v2, c'est-a-dire dans p0 (le Context). Seul le verificateur d'ART l'a vu.
    offenders = []
    for smali_name, smali_text in all_smali().items():
        offenders += param_writes(smali_name, smali_text)
    check(
        "greffon entier : aucune ecriture dans un registre de parametre",
        not offenders,
        "; ".join(offenders[:4]) + " -- un .locals trop court fait de vN l'alias de "
        "pN : la classe est rejetee et l'application plante au premier onResume",
    )

    # --- 17. Polarite des branchements sur les champs mis en cache ---------------
    # Le 21/09, deux fautes de polarite ont survecu au build ET a tous les tests
    # hors appareil : le verrou de veille sautait sa creation (NullPointerException
    # sur isHeld, lecteur plante a l'ouverture) et la session media n'etait jamais
    # creee (methode qui renvoyait nul, sans erreur visible).
    offenders = []
    for smali_name, smali_text in all_smali().items():
        offenders += skipped_creation(smali_name, smali_text)
    check(
        "greffon entier : aucun branchement ne saute la creation du champ teste",
        not offenders,
        "; ".join(offenders[:4]) + " -- « if-eqz » saute quand le champ est nul : "
        "la creation est evitee exactement quand elle est necessaire (voir §6).",
    )
    keepalive = all_smali().get("PlayerKeepAlive.smali", "")
    check(
        "PlayerKeepAlive : le verrou et la session sont crees quand le champ est nul",
        "if-nez v0, :twouich_wake_ready" in keepalive
        and "if-nez v0, :twouich_sess_done" in keepalive,
        "« if-eqz » a ces deux endroits laisse le verrou nul (NullPointerException "
        "sur isHeld) et rend une session nulle.",
    )
    check(
        "PlayerKeepAlive : le canal de notification est cree a partir de l'API 26",
        "if-ge v0, v1, :twouich_chan_go" in keepalive
        and "if-lt v0, v1, :twouich_chan_go" not in keepalive,
        "« if-lt » saute la creation du canal des l'API 26 : plus aucune "
        "notification de lecture, et un startForeground sans canal.",
    )

    # --- 18. Interface TV : une seule source de verite -------------------------
    # Le 21/09, la TV a ete cassee par un seuil de dp : un televiseur 1080p en
    # 320 dpi declare 540 dp, donc la disposition telephone s'appliquait a un vrai
    # televiseur — et l'amont ne livre qu'une seule configuration de layout
    # lecteur, donc c'est bien `layout/` que la TV gonfle.
    check("lecteur : toute ecriture passe par la source unique TV",
          patcher.count("player_smali.write_text(") == 1
          and "def write_player(final: str) -> None:" in patcher,
          "une ecriture hors de write_player laisserait un seuil de dp decider de "
          "l'interface : c'est exactement la regression TV du 21/09.")
    # `if-eq` et non `if-ne` : mesure du 22/09 sur la Freebox — avec `if-ne`,
    # tout appareil NON television sautait vers la branche TV (un telephone
    # passait pour une TV) et la Freebox n'etait TV que par accident, par le
    # seul seuil de dp : le service de premier plan se lancait sur le televiseur.
    check("lecteur : twouichTvInterface lit le mode TV du systeme",
          "uiMode:I" in patcher
          and "and-int/lit8 v2, v2, 0xf" in patcher
          and "if-eq v2, v3, :twouich_tv_by_mode" in patcher
          and "if-ge v2, v3, :twouich_tv_by_mode" in patcher,
          "sans le mode TV, un televiseur 540 dp retombe dans la branche telephone.")
    # Meme inversion que ci-dessus : `if-eq` saute vers le panneau deploye quand
    # le mode EST la television, le seuil de dp saute vers le meme endroit au-dela
    # de 600 dp, et le repli est le telephone.
    check("panneau Leanback : etat TV lu dans le mode systeme",
          "if-eq v1, v2, :cond_twouich_tv_headers" in patcher
          and "if-ge v1, v2, :cond_twouich_tv_headers" in patcher,
          "l'etat du panneau etait calcule sur les seuls dp : la TV perdait sa "
          "colonne de navigation (HEADERS_HIDDEN).")
    # Borne au bloc du garde : « move-result v0 » est legitime ailleurs.
    tv_rows = patcher[patcher.index('TV_INTERFACE_ROWS = ('):patcher.index('TV_INTERFACE_METHOD =')]
    check("lecteur : le garde TV n'ecrit pas dans le registre du Resources",
          "    move-result v2" in tv_rows and "    move-result v0" not in tv_rows,
          "un move-result v0 ecrase le Resources que twouichPhoneStackedLayout lit "
          "plus loin : le verificateur d'ART rejette la classe entiere (VerifyError "
          "mesure sur le telephone le 21/09, lecteur plante a l'ouverture).")
    tv_source = HERE.parent / "res-tv" / "activity_player.xml"
    tv_text = tv_source.read_text(encoding="utf-8") if tv_source.is_file() else ""
    check("layout TV versionne, et vierge de toute greffe",
          bool(tv_text) and "twouich" not in tv_text
          and "@id/ChatRecycleView" in tv_text,
          "patch/res-tv/activity_player.xml doit etre la capture de l'amont : "
          "c'est la seule source du layout TV, jamais le layout telephone.")
    # --- 19. Veille : garde sur TOUT le demontage d'onStop() --------------------
    # Mesure du 21/09 sur le telephone, service de premier plan `mediaPlayback`
    # actif : le demontage d'onStop() est large — `w2()`/`R1()` (instance
    # principale) puis `x2()`/`R1()` (multiview) puis `o3()` — et c'est lui qui
    # coupe le decodeur (`disconnectFromSurface`) et l'AudioTrack
    # (`setStreamEndDone`) a la seconde de l'extinction. Proteger le seul `o3()`
    # ne suffisait donc pas, et la premiere version branchait a l'envers
    # (`if-eqz` sur `:twouich_screen_off_stop`) : elle liberait quand l'ecran
    # etait ETEINT.
    anchor_src = patcher[patcher.index("PHONE_SCREEN_OFF_ANCHOR = "):
                         patcher.index("PHONE_SCREEN_OFF_O3 = ")]
    veille_fn = patcher[patcher.index("def _patch_screen_off_stop("):
                        patcher.index("# --- Interface TV")]
    check("veille : le garde enveloppe tout le demontage, pas le seul o3()",
          "->w2()LG6/i;" in anchor_src
          and "body[:anchor]" in veille_fn
          and "body[anchor:super_call]" in veille_fn,
          "un garde pose devant o3() seul laisse w2/R1 et x2/R1 demonter les "
          "lecteurs : la lecture s'arrete des que l'ecran s'eteint (mesure du "
          "21/09), service de premier plan ou non.")
    # Borne au bloc du garde : la forme precedente, gardee pour la reparation
    # des arbres deja patches, porte encore l'etiquette `..._stop`.
    guard_src = patcher[patcher.index("PHONE_SCREEN_OFF_GUARD = "):
                        patcher.index("PHONE_SCREEN_OFF_KEPT = ")]
    check("veille : ecran eteint => demontage saute (polarite du branchement)",
          "if-eqz v1, :twouich_screen_off_kept" in guard_src
          and ":twouich_screen_off_stop" not in guard_src,
          "la forme inversee libere quand l'ecran est eteint, soit exactement "
          "l'inverse de l'intention.")
    check("veille : la forme inversee des arbres deja patches est retiree",
          "PHONE_SCREEN_OFF_LEGACY = " in patcher
          and "if PHONE_SCREEN_OFF_LEGACY in body:" in veille_fn,
          "sans cette reparation, un arbre deja patche garde l'ancien garde : "
          "deux gardes cohabitent et le build ne change jamais de SHA.")
    check("veille : invoke-super reste appele hors du garde",
          "PHONE_SCREEN_OFF_SUPER" in veille_fn
          and "body[:anchor]" in veille_fn,
          "sauter invoke-super casserait le cycle de vie de l'Activity.")

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
