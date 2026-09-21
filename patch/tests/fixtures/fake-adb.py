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


def node(text, cls, bounds, clickable="false", focused="false"):
    return (
        '<node index="0" text="%s" resource-id="" class="%s" '
        'package="com.s0und.s0undtv" content-desc="" checkable="false" '
        'checked="false" clickable="%s" enabled="true" focusable="true" '
        'focused="%s" scrollable="false" long-clickable="false" '
        'password="false" selected="false" bounds="%s" />'
        % (text, cls, clickable, focused, bounds)
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
