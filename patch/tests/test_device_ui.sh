#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# test_device_ui.sh — vérifie la logique de décision de patch/device-ui.sh
# ═══════════════════════════════════════════════════════════════════════
# Aucun appareil nécessaire : un double d'`adb` (fixtures/fake-adb.py) rejoue
# un scénario figé — l'accueil TV de Twouich, puis le lecteur — et permet de
# vérifier ce qui compte vraiment dans cet outil, à savoir ses **décisions** :
#
#   * `probe` distingue « le tactile agit » de « le tactile est absorbé alors
#     que les touches passent » (le cas Freebox / MIUI, § 8.1) ;
#   * `nav` déplace le focus jusqu'à la cible et **échoue proprement** si elle
#     est inatteignable, au lieu de boucler sans le dire ;
#   * les bornes `[x1,y1][x2,y2]` sont lues à la virgule près — l'erreur de
#     parsing qui donnait (60,120) au lieu de (205,90) est un piège payé (§ 8.4) ;
#   * une capture vide est **attribuée à l'appareil**, pas à la copie ;
#   * `help` et l'aiguillage ne dépendent d'aucun appareil.
#
# Usage :
#   bash patch/tests/test_device_ui.sh
# ═══════════════════════════════════════════════════════════════════════
set -uo pipefail
export MSYS_NO_PATHCONV=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
UI="$ROOT/patch/device-ui.sh"
STUB="$ROOT/patch/tests/fixtures/fake-adb.py"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PY="$(command -v python || command -v python3 || true)"
[ -n "$PY" ] || { echo "❌ python introuvable (patch/tests/fixtures/fake-adb.py en a besoin)"; exit 1; }

# Le double est exposé sous le nom `adb`, par un lanceur qui exec l'interpréteur
# courant : le shebang `#!/usr/bin/env python3` ne marche pas partout (sous Git
# Bash, `python3` peut être le raccourci Store de Windows, qui échoue).
#
# Le lanceur `cd` dans le dossier du double et lui passe un **nom simple** :
# device-ui.sh force `MSYS2_ARG_CONV_EXCL='*'`, donc un chemin MSYS
# (`/d/Codex/…`) arriverait tel quel à un python natif Windows, qui ne saurait
# pas le résoudre. Constaté ici même, et c'est exactement le piège de la § 8.4.
mkdir -p "$TMP/bin"
cat > "$TMP/bin/adb" <<EOF
#!/bin/bash
cd "\$(dirname "$STUB")" || exit 1
# MSYS ne convertit pas les variables d'environnement (et device-ui.sh force
# MSYS2_ARG_CONV_EXCL='*') : le chemin d'état doit être normalisé ici, sinon un
# python natif Windows le refuse et le double répond dans le vide.
if command -v cygpath >/dev/null 2>&1; then
    FAKE_STATE="\$(cygpath -w "\${FAKE_STATE:-}")"
fi
export FAKE_STATE
exec "$PY" "\$(basename "$STUB")" "\$@"
EOF
chmod +x "$TMP/bin/adb"
ADB_FAKE="$TMP/bin/adb"
STATE="$TMP/state"

PASS=0
FAIL=0
OUT=""
RC=0

pass() { printf '  ✅ %s\n' "$1"; PASS=$((PASS + 1)); }
fail() { printf '  ❌ %s\n' "$1"; printf '%s\n' "$OUT" | sed 's/^/       /'; FAIL=$((FAIL + 1)); }

reset_state() { rm -rf "$STATE"; mkdir -p "$STATE"; }

# run_ui <args…> — l'état du double est neuf à chaque appel, et les variables
# FAKE_* exportées par l'appelant pilotent le scénario (cf. fake-adb.py).
run_ui() {
    reset_state
    OUT="$(ADB="$ADB_FAKE" FAKE_STATE="$STATE" SERIAL= FAKE_NO_FOCUS="${FAKE_NO_FOCUS:-}" \
        FAKE_TACTILE="${FAKE_TACTILE:-}" FAKE_ACTIVATE="${FAKE_ACTIVATE:-}" \
        FAKE_CAPTURE="${FAKE_CAPTURE:-}" \
        bash "$UI" "$@" 2>&1)"
    RC=$?
}

# run_step — comme run_ui, mais **sans** remettre l'état à neuf : c'est ce qui
# permet de jouer une séquence (naviguer, activer, constater) au lieu d'un tir isolé.
run_step() {
    OUT="$(ADB="$ADB_FAKE" FAKE_STATE="$STATE" SERIAL= FAKE_NO_FOCUS="${FAKE_NO_FOCUS:-}" \
        FAKE_TACTILE="${FAKE_TACTILE:-}" FAKE_ACTIVATE="${FAKE_ACTIVATE:-}" \
        FAKE_CAPTURE="${FAKE_CAPTURE:-}" \
        bash "$UI" "$@" 2>&1)"
    RC=$?
}

expect_contains() { # expect_contains <libellé> <chaîne attendue>
    if printf '%s' "$OUT" | grep -qF -- "$2"; then pass "$1"; else
        printf '  ❌ %s\n     attendu : %s\n' "$1" "$2"
        printf '%s\n' "$OUT" | sed 's/^/       /'
        FAIL=$((FAIL + 1))
    fi
}

expect_absent() { # expect_absent <libellé> <chaîne qui ne doit plus être là>
    if printf '%s' "$OUT" | grep -qF -- "$2"; then
        printf '  ❌ %s\n     ne devait plus contenir : %s\n' "$1" "$2"
        printf '%s\n' "$OUT" | sed 's/^/       /'
        FAIL=$((FAIL + 1))
    else pass "$1"; fi
}

expect_rc() { # expect_rc <libellé> <code attendu>
    if [ "$RC" -eq "$2" ]; then pass "$1"; else
        printf '  ❌ %s\n     code attendu %s, obtenu %s\n' "$1" "$2" "$RC"
        printf '%s\n' "$OUT" | sed 's/^/       /'
        FAIL=$((FAIL + 1))
    fi
}

echo "═══ device-ui.sh — 1. aiguillage (aucun appareil requis)"
OUT="$(ADB=/nonexistent/adb bash "$UI" help 2>&1)"; RC=$?
expect_contains "help s'affiche sans appareil branché" "device-ui.sh — piloter l'interface"
expect_rc "help sort en 0" 0
run_ui bidule
expect_contains "commande inconnue nommée" "commande inconnue : bidule"
expect_rc "commande inconnue sort en 2" 2
run_ui nav
expect_contains "nav sans argument : usage" "usage: bash patch/device-ui.sh nav <texte>"
expect_rc "nav sans argument sort en 2" 2
run_ui --list
expect_contains "--list nomme l'appareil" "127.0.0.1:5555"

echo
echo "═══ 2. lecture de l'arbre (bornes, textes, focus)"
run_ui texts
expect_contains "texts relève les textes de l'écran" 'text="Niniste"'
run_ui find "Niniste"
expect_contains "find rend les bornes à la virgule près" "bounds   : [200,600][900,700]"
expect_contains "find dit si l'élément est cliquable" "clickable: true"
run_ui focus
expect_contains "focus nomme l'élément focalisé" "Live Stream History"
run_ui clickables
expect_contains "clickables liste les cibles tactiles" "[200,800][900,900]"

echo
echo "═══ 3. navigation au D-pad"
run_ui nav "Niniste"
expect_contains "nav atteint la cible et compte les déplacements" "✓ focus sur « Niniste » après 1 déplacement(s)"
expect_rc "nav atteint : code 0" 0
run_ui nav "Absent"
expect_contains "nav dit la cible inatteignable" "non atteint en 30 déplacements"
expect_contains "nav rend le focus courant en échec" "focus actuel"
expect_rc "nav inatteignable : code 1" 1
FAKE_ACTIVATE=1 run_ui press
expect_contains "press envoie DPAD_CENTER" "✓ DPAD_CENTER envoyé"
# Un écran où personne n'a le focus (le cas de l'accueil d'une vraie grille
# Leanback) : le diagnostic doit tomber en trois crans, pas après trente — sur
# un direct en cours, trente crans de D-pad coûtent 87 s et le silence.
FAKE_NO_FOCUS=1 run_ui nav "Niniste"
expect_contains "nav sans focus : le dit au bout de 3 crans" "aucun élément n'a pris le focus après 3 déplacements"
expect_contains "nav sans focus : oriente vers un autre axe" "UI_KEY=19|21|22"
expect_rc "nav sans focus : code 1" 1

echo
echo "═══ 4. les deux canaux — ce que « probe » doit mesurer"
run_ui probe
expect_contains "probe : tactile absorbé, touches actives" "tactile=non   touches=oui"
expect_contains "probe conclut au cas Freebox / MIUI" "cas Freebox / MIUI : piloter au D-pad uniquement"
expect_contains "probe oriente vers la commande de repli" "nav \"<texte du bouton>\" && bash patch/device-ui.sh press"
FAKE_TACTILE=1 run_ui probe
expect_contains "probe : appareil où le tactile agit" "tactile=oui"
expect_contains "probe y laisse le D-pad en secours" "le tactile suffit"

echo
echo "═══ 5. tap et capture — ne pas attribuer au mauvais coupable"
run_ui tap 550 650
expect_contains "tap sans effet : le dit" "sans effet visible — le tactile paraît absorbé"
expect_contains "tap sans effet : propose le repli D-pad" "bash patch/device-ui.sh nav"
expect_rc "tap sans effet : code 1" 1
FAKE_TACTILE=1 run_ui tap 550 650
expect_contains "tap efficace : confirme le changement d'écran" "a changé l'écran"
expect_rc "tap efficace : code 0" 0
FAKE_CAPTURE=empty run_ui shot "$TMP/vide.png"
expect_contains "capture vide : le dit" "✗ capture vide"
expect_contains "capture vide : accuse l'appareil, pas la copie" "screencap a écrit 0 octet SUR l'appareil"
expect_rc "capture vide : code 1" 1
FAKE_CAPTURE=png run_ui shot "$TMP/plein.png"
expect_contains "capture pleine : confirme la taille" "octets)"
expect_rc "capture pleine : code 0" 0

echo
echo "═══ 6. le scénario d'usage : atteindre un direct au D-pad"
# La séquence réelle du § 2 étape 3 : amener le focus sur la carte, l'activer,
# constater qu'on est bien sur le lecteur. Chaque étape partage l'état du double.
FAKE_ACTIVATE=1 run_ui nav "Niniste"
expect_contains "étape 1 : amener le focus sur la carte de la chaîne" "✓ focus sur « Niniste »"
FAKE_ACTIVATE=1 run_step press
expect_contains "étape 2 : activer (DPAD_CENTER) l'entrée focalisée" "DPAD_CENTER envoyé"
FAKE_ACTIVATE=1 run_step texts
expect_contains "étape 3 : le lecteur est à l'écran" 'text="Chat"'
expect_absent "étape 3 : l'accueil a bien été quitté" 'text="Niniste"'

echo
echo "═══ 7. step — une vérification complète en une ligne"
# « avant » présent, action, « après » présent → conforme.
FAKE_ACTIVATE=1 run_ui step "Live Stream History" "nav:Niniste+press" "Chat"
expect_contains "step conforme : verdict" "✓ ÉTAPE CONFORME"
expect_rc "step conforme : code 0" 0
expect_contains "step conforme : l'écran de départ est vérifié" "« Live Stream History » présent"
expect_contains "step conforme : delta gagné (la preuve du changement)" "+[Chat, Revenir]"
expect_contains "step conforme : delta perdu (l'accueil a été quitté)" "−[Live Stream History, Niniste, Recherche]"
# La même ligne sans activation : l'écran obtenu diffère de l'attendu → échec, et c'est le but.
run_ui step "Live Stream History" "nav:Niniste+press" "Chat"
expect_contains "step non conforme : dit l'écran obtenu" "✗ « Chat » ABSENT"
expect_contains "step non conforme : verdict" "✗ ÉCHEC — écran obtenu différent de l'écran attendu"
expect_rc "step non conforme : code 1" 1
expect_contains "step non conforme : delta vide, il le dit" "+[aucun] −[aucun]"
# L'écran de départ n'est pas le bon : on le dit avant de toucher à l'appareil (aucune action jouée).
run_ui step "Écran Qui N'Existe Pas" "nav:Niniste+press" "Chat"
expect_contains "step : écran de départ absent" "l'écran de départ n'est pas celui attendu"
expect_rc "step : écran de départ absent → code 1" 1
# Un verbe inconnu est signalé, il ne part pas activer un élément au hasard.
run_ui step "Live Stream History" "bidule" "Chat"
expect_contains "step : verbe inconnu nommé" "verbe inconnu : « bidule »"
expect_rc "step : verbe inconnu → code 1" 1
# Une action qui échoue interrompt l'étape.
run_ui step "Live Stream History" "nav:Absent+press" "Chat"
expect_contains "step : une action en échec arrête l'étape" "ÉCHEC — une action n'a pas abouti"
expect_rc "step : action en échec → code 1" 1
# Le piège du test qui passe sans rien prouver : la sortie attendue était déjà là.
run_ui step "Live Stream History" "wait:0.1" "Live Stream History"
expect_contains "step : signale une vérification vide" "DÉJÀ présente avant l'action"
expect_rc "step : sortie déjà présente → conforme malgré le doute" 0
# Le script de recette : deux étapes enchaînées, l'état de départ de la 2ᵉ étant
# celui laissé par la 1ʳᵉ — c'est ce qui fait une recette de bout en bout.
reset_state
FAKE_ACTIVATE=1 run_step step "Live Stream History" "nav:Niniste+press" "Chat"
expect_contains "recette 1/2 : accueil → lecteur" "✓ ÉTAPE CONFORME"
FAKE_ACTIVATE=1 run_step step "Revenir" "key:4" "Live Stream History"
expect_contains "recette 2/2 : lecteur → accueil (BACK)" "✓ ÉTAPE CONFORME"
expect_contains "recette 2/2 : la carte est revenue à l'écran" "Live Stream History, Niniste"
expect_rc "recette : chaque étape sort en 0" 0


echo
echo "══════════════════════════════════════════════════════════"
printf 'verdict : %d vérification(s) passée(s), %d échec(s)\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
