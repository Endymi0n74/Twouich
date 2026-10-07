#!/usr/bin/env python
# ═══════════════════════════════════════════════════════════════════════
# fake-adb.py — double hors appareil de `adb`, pour test_device_ui.sh
# ═══════════════════════════════════════════════════════════════════════
# Répond aux commandes que patch/device-ui.sh émet, sur un petit scénario
# figé qui imite l'accueil TV de Twouich :
#
#   écran 0 : accueil — « Live Stream History » (focus de départ), la carte
#             « Niniste » (cliquable), « Recherche »
#   écran 1 : lecteur — « Revenir », « Chat »
#
# Deux propriétés sont **pilotées par l'environnement**, parce que c'est
# exactement ce que `device-ui.sh probe` doit savoir mesurer :
#
#   FAKE_TACTILE=1    `input tap` change d'écran (appareil où le tactile agit)
#   sinon             `input tap` ne fait rien   (appareil où il est absorbé :
#                     le cas Freebox / MIUI, cf. TEST-DEVICE.md § 8.1)
#   FAKE_ACTIVATE=1   `input keyevent 23` change d'écran
#   FAKE_NO_FOCUS=1   aucun nœud n'a le focus (écran de départ d'une grille Leanback)
#   FAKE_CAPTURE=empty|png   `screencap` écrit 0 octet (BlueStacks) ou des octets
#   FAKE_IME=sous|dessus|ferme|sans|invite|paysage|paysage-dehors|chevauche
#                     scénario du compositeur, du clavier et de la vidéo
#                     (verrou « saisie à sa place » de device-ui.sh) :
#                     `sous`   rejoue le défaut mesuré du § 8.11 (barre 913 px
#                              sous le bord du clavier), `dessus` l'état corrigé
#                      du § 8.26, `ferme` le clavier rentré, `sans` un clavier
#                      ouvert sans aucune saisie à l'écran, `invite` l'id du
#                      compositeur masqué (repli par le hint) ;
#                     `paysage`         l'état corrigé du § 8.26 en 2712×1220
#                                       (saisie dans sa colonne, à droite de la
#                                       vidéo) ;
#                     `paysage-dehors`  la RÉGRESSION de rotation du § 8.26 :
#                                       la branche portrait appliquée avec des
#                                       dimensions périmées, saisie pleine
#                                       largeur sous la vidéo ;
#                     `chevauche`       la vidéo qui déborde sur la saisie.
#
# Ce n'est pas un test de device-ui.sh *en soi* : c'est la preuve que sa
# logique de décision est juste — que `probe` distingue bien les deux canaux,
# et qu'il ne confond pas « le tap n'a rien fait » avec « la cible est inerte ».
# ═══════════════════════════════════════════════════════════════════════
import os
import re
import sys

STATE = os.environ.get("FAKE_STATE", ".")
SERIAL = "127.0.0.1:5555"


def node(text, cls, bounds, clickable="false", focused="false", rid="", hint=""):
    return (
        '<node index="0" text="%s" resource-id="%s" class="%s" '
        'package="com.s0und.s0undtv" content-desc="" checkable="false" '
        'checked="false" clickable="%s" enabled="true" focusable="true" '
        'focused="%s" scrollable="false" long-clickable="false" '
        'password="false" selected="false" bounds="%s" hint="%s" />'
        % (text, rid, cls, clickable, focused, bounds, hint)
    )


# Scénario IME : bornes du compositeur + cadre du clavier, tels que mesurés
# sur le Xiaomi — le défaut du § 8.11 (barre `y 2600→2712` sous un clavier
# ouvert à `y=1687`, soit 913 px sous la première touche) et son correctif du
# § 8.26 (barre `0,1479-1220,1687`, collée au bord du clavier).
IME_SCENARIOS = {
    #    compositeur              cadre IME                  visible  vidéo              fenêtre             chat
    "sous":   ("[0,2600][1220,2712]", "[0,1687][1220,2712]", "true",  "[0,130][1220,816]",  "[0,0][1220,2712]", "[0,816][1220,2452]"),
    "dessus": ("[0,1479][1220,1687]", "[0,1687][1220,2712]", "true",  "[0,130][1220,816]",  "[0,0][1220,2712]", "[0,816][1220,1479]"),
    "ferme":  ("[0,2452][1220,2660]", "[0,2712][1220,2712]", "false", "[0,130][1220,816]",  "[0,0][1220,2712]", "[0,816][1220,2452]"),
    "sans":   (None,                   "[0,1687][1220,2712]", "true",  "[0,130][1220,816]",  "[0,0][1220,2712]", "[0,816][1220,2452]"),
    # `invite` : l'id du compositeur est masqué — c'est alors son **hint** qui
    # le désigne, jamais son `text` (qui vaut « , » sur le vrai appareil).
    "invite": ("[0,1479][1220,1687]", "[0,1687][1220,2712]", "true",  "[0,130][1220,816]",  "[0,0][1220,2712]", "[0,816][1220,1479]"),
    # Paysage 2712×1220, tel que mesuré au § 8.26 : vidéo 16:9 à gauche
    # (1845×1038), chat en haut de la colonne de droite, saisie au bas.
    "paysage": ("[1845,960][2712,1168]", "[0,1220][2712,1220]", "false",
                "[0,130][1845,1168]", "[0,0][2712,1220]", "[1845,130][2712,960]"),
    # La régression de rotation du § 8.26 : la branche portrait tournant avec
    # des dimensions périmées — vidéo, chat et saisie pleine largeur. Aucun
    # chevauchement, mais les colonnes sont quittées.
    "paysage-dehors": ("[0,960][2712,1168]", "[0,1220][2712,1220]", "false",
                       "[0,130][2712,816]", "[0,0][2712,1220]", "[0,816][2712,960]"),
    # La vidéo qui déborde sur la saisie (l'ancien défaut « la fenêtre vidéo
    # n'empiète plus sur le chat », § 8.18) : recouvrement 1220×48 px. Pas de
    # chat ici : le scénario isole le chevauchement saisie×vidéo.
    "chevauche": ("[0,2452][1220,2660]", "[0,2712][1220,2712]", "false",
                  "[0,130][1220,2500]", "[0,0][1220,2712]", None),
    # Le chat qui déborde sur la vidéo : 145×830 px de recouvrement.
    "chat-video": ("[1845,960][2712,1168]", "[0,1220][2712,1220]", "false",
                   "[0,130][1845,1168]", "[0,0][2712,1220]", "[1700,130][2712,960]"),
    # Le chat qui déborde sur la saisie : 867×208 px de recouvrement.
    "chat-saisie": ("[1845,960][2712,1168]", "[0,1220][2712,1220]", "false",
                    "[0,130][1845,1168]", "[0,0][2712,1220]", "[1845,900][2712,1168]"),
}


def ime_scenario():
    return IME_SCENARIOS.get(os.environ.get("FAKE_IME", ""))


def ime_window_dump():
    sc = ime_scenario()
    if sc is None:
        return ""
    _composer, frame, visible, _video, _geo, _chat = sc
    return (
        "WINDOW MANAGER WINDOWS (dumpsys window -a)\n"
        "  InsetsState:\n"
        "    InsetsSource id=3 type=ime frame=%s visible=%s\n" % (frame, visible)
    )


SCREENS = [
    '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hierarchy rotation="0">'
    + node("Live Stream History", "android.widget.TextView", "[200,300][900,380]", focused="true")
    + node("Niniste", "android.widget.Button", "[200,600][900,700]", clickable="true")
    + node("Recherche", "android.widget.Button", "[200,800][900,900]", clickable="true")
    + "</hierarchy>",
    '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?><hierarchy rotation="0">'
    + node("Revenir", "android.widget.Button", "[60,60][300,140]", clickable="true", focused="true")
    + node("Chat", "android.widget.EditText", "[100,1600][1180,1800]")
    + "</hierarchy>",
]

NODES = [re.findall(r"<node[^>]*>", s) for s in SCREENS]


def state_path(*parts):
    return os.path.join(STATE, *parts)


def read_int(name, default):
    try:
        with open(state_path(name)) as fh:
            return int(fh.read().strip())
    except (IOError, OSError, ValueError):
        return default


def write_int(name, value):
    with open(state_path(name), "w") as fh:
        fh.write(str(value))


def initial_focus(idx):
    for i, n in enumerate(NODES[idx]):
        if 'focused="true"' in n:
            return i
    return 0


def current_screen():
    return min(max(read_int("screen", 0), 0), len(SCREENS) - 1)


def render(idx, focus):
    # FAKE_NO_FOCUS=1 fige un écran où **personne** n'a le focus : mesuré sur
    # l'accueil d'une vraie app (grille Leanback), où `nav` n'a alors aucune
    # prise. Le double doit savoir le reproduire pour que le diagnostic soit
    # verrouillé par un test et non seulement documenté.
    aveugle = os.environ.get("FAKE_NO_FOCUS") == "1"
    nodes = []
    for i, n in enumerate(NODES[idx]):
        nodes.append(
            re.sub(
                r'focused="[^"]*"',
                'focused="%s"' % ("true" if i == focus and not aveugle else "false"),
                n,
            )
        )
    # Le compositeur du lecteur (« Envoyer un message », id SendMessageWindow)
    # n'apparaît que dans le scénario IME, sur l'écran 1 : les autres tests
    # voient leurs écrans inchangés, deltas de `step` compris.
    sc = ime_scenario()
    if idx == 1 and sc is not None:
        if sc[0] is not None:
            if os.environ.get("FAKE_IME") == "invite":
                # Fidèle au vrai arbre : `text=","`, l'invite dans `hint`, aucun
                # id exploitable — le repli de composer_node passe par le hint.
                nodes.append(
                    node(",", "android.widget.EditText", sc[0], hint="Envoyer un message")
                )
            else:
                nodes.append(
                    node(
                        "Envoyer un message",
                        "android.widget.EditText",
                        sc[0],
                        rid="com.s0und.s0undtv:id/SendMessageWindow",
                    )
                )
        # Le cadre vidéo (`ExoPlayer`, mesuré `[0,130][1220,816]` en portrait
        # sur le Xiaomi) et la fenêtre (`container`, plein écran) : les bornes
        # réelles du § 8.26, pas une reconstruction.
        nodes.append(
            node("", "android.widget.FrameLayout", sc[3], rid="com.s0und.s0undtv:id/ExoPlayer")
        )
        nodes.append(
            node("", "android.widget.RelativeLayout", sc[4], rid="com.s0und.s0undtv:id/container")
        )
        if sc[5] is not None:
            # La zone de chat : classe `com.s0und.s0undtv.chat.ChatRecyclerView`,
            # id `ChatRecycleView` (relus dans le greffon et les layouts).
            nodes.append(
                node(
                    "",
                    "com.s0und.s0undtv.chat.ChatRecyclerView",
                    sc[5],
                    rid="com.s0und.s0undtv:id/ChatRecycleView",
                )
            )
    head = SCREENS[idx][: SCREENS[idx].index("<node")]
    return head + "".join(nodes) + "</hierarchy>"


def dump_xml():
    idx = current_screen()
    return render(idx, read_int("focus", initial_focus(idx)))


def advance_screen():
    idx = min(current_screen() + 1, len(SCREENS) - 1)
    write_int("screen", idx)
    write_int("focus", initial_focus(idx))


def move_focus(delta):
    idx = current_screen()
    focus = read_int("focus", initial_focus(idx)) + delta
    write_int("focus", min(max(focus, 0), len(NODES[idx]) - 1))


def store_remote(path, data):
    with open(state_path("remote-" + os.path.basename(path)), "wb") as fh:
        fh.write(data)


def read_remote(path):
    try:
        with open(state_path("remote-" + os.path.basename(path)), "rb") as fh:
            return fh.read()
    except (IOError, OSError):
        return b""


def main(argv):
    if argv and argv[0] == "-s":
        argv = argv[2:]
    if not argv:
        return 1

    if argv[0] in ("devices",):
        out = "List of devices attached\n%s\tdevice\n" % SERIAL
        if len(argv) > 1 and argv[1] == "-l":
            out += "%s device product:fake model:Twouich_Fake\n" % SERIAL
        sys.stdout.write(out)
        return 0
    if argv[0] in ("connect", "kill-server", "start-server"):
        return 0
    if argv[0] == "exec-out":
        sys.stdout.buffer.write(read_remote(argv[-1]))
        return 0
    if argv[0] != "shell":
        return 1

    cmd = argv[1:]
    if not cmd:
        return 1

    if cmd[0] == "uiautomator" and cmd[1:2] == ["dump"]:
        store_remote(cmd[2], dump_xml().encode())
        sys.stdout.write("UI hierchary dumped to: %s\n" % cmd[2])
        return 0

    if cmd[0] == "dumpsys" and cmd[1:2] == ["window"]:
        # L'état des insets, dont la ligne `type=ime` d'où device-ui.sh lit le
        # cadre du clavier (la fenêtre `InputMethod` ne dit rien d'exploitable).
        sys.stdout.write(ime_window_dump())
        return 0

    if cmd[0] == "cat":
        sys.stdout.buffer.write(read_remote(cmd[1]))
        return 0

    if cmd[0] == "stat":                        # stat -c %s <chemin>
        sys.stdout.write("%d\n" % len(read_remote(cmd[-1])))
        return 0

    if cmd[0] == "rm":
        path = state_path("remote-" + os.path.basename(cmd[-1]))
        if os.path.exists(path):
            os.remove(path)
        return 0

    if cmd[0] == "screencap":
        data = b"" if os.environ.get("FAKE_CAPTURE") == "empty" else b"\x89PNG\r\n\x1a\n" + b"x" * 128
        store_remote(cmd[-1], data)
        return 0

    if cmd[0] == "monkey":
        sys.stdout.write("Events injected: 1\n")
        return 0

    if cmd[0] == "input":
        if cmd[1] == "tap":
            if os.environ.get("FAKE_TACTILE") == "1":
                advance_screen()
            return 0
        if cmd[1] == "keyevent":
            code = cmd[2]
            if code == "20":
                move_focus(+1)
            elif code == "19":
                move_focus(-1)
            elif code == "23" and os.environ.get("FAKE_ACTIVATE") == "1":
                advance_screen()
            elif code == "4":                   # BACK
                write_int("screen", 0)
                write_int("focus", initial_focus(0))
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
