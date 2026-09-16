#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# test-selftest.sh — self-test anti-pub embarqué, verdict en une commande
# ═══════════════════════════════════════════════════════════════════════
# Le greffon contient un self-test (patch/smali/com/twouich/adblock/SelfTest.smali)
# qui rejoue des playlists publicitaires aux formats Twitch réels DANS le code
# compilé, et fait traverser la vraie source de données du lecteur
# (AdBlockDataSource : c() puis read()). Il ne dépend donc pas d'une coupure
# publicitaire réelle pour prouver que le filtre agit.
#
#   bash patch/test-selftest.sh                    # dex frais, sans installer
#   bash patch/test-selftest.sh --in-app           # depuis l'app installée
#   bash patch/test-selftest.sh --serial emulator-5554
#   bash patch/test-selftest.sh --apk dist/xxx.apk
#
# Mode par défaut (autonome) : l'APK de dist/ est poussé dans /data/local/tmp et
# exécuté avec app_process — il n'est PAS installé, rien n'est modifié sur
# l'appareil. On obtient le verdict en quelques secondes.
#
# Mode --in-app : lance l'application installée, dont MainApp.onCreate exécute le
# self-test au démarrage ; on lit la ligne dans logcat.
#
# Verdict attendu, une ligne (Log.i) :
#   I/Twouich : SELFTEST 18/18 verifications, flux filtre : 328 octets
# En cas d'échec : une ligne Log.e par vérification fautive, puis
#   E/Twouich : SELFTEST ECHEC <n>/<total> verifications, ...
#
# Code de sortie : 0 = self-test vert, 1 = échec ou verdict illisible.
# ═══════════════════════════════════════════════════════════════════════
set -uo pipefail

# Git Bash (MSYS) réécrit les chemins absolus passés aux binaires natifs :
# `/data/local/tmp/x.apk` deviendrait `C:/Program Files/Git/data/local/tmp/x.apk`.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

APK="dist/Twouich_v1.0.0.apk"
PKG="com.s0und.s0undtv"
ACTIVITY="$PKG/com.s0und.s0undtv.activities.FireTVMainActivity"
REMOTE="/data/local/tmp/twouich-selftest.apk"
SERIAL=""
IN_APP=0

while [ $# -gt 0 ]; do
    case "$1" in
        --apk)      APK="${2:-$APK}"; shift ;;
        --serial|-s) SERIAL="${2:-}"; shift ;;
        --in-app)   IN_APP=1 ;;
        -h|--help)  sed -n '2,30p' "$0"; exit 0 ;;
        *) echo "option inconnue : $1"; exit 2 ;;
    esac
    shift
done

# ── Résolution d'adb (un seul binaire, on s'y tient) ─────────────────────
find_adb() {
    if [ -n "${ADB:-}" ] && [ -x "$ADB" ]; then echo "$ADB"; return; fi
    if command -v adb >/dev/null 2>&1; then command -v adb; return; fi
    for c in \
        "$LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe" \
        "/c/Users/$USERNAME/AppData/Local/Android/Sdk/platform-tools/adb.exe" \
        "/c/Users/$USERNAME/AppData/Local/ScrcpyGUI/scrcpy-bin/adb.exe" \
        "/c/Program Files/BlueStacks_nxt/HD-Adb.exe" \
        "/c/Program Files (x86)/BlueStacks_nxt/HD-Adb.exe" \
        "/c/Program Files/BlueStacks/HD-Adb.exe" \
        "/c/Program Files/Nox/bin/adb.exe" \
        "/usr/bin/adb" "/usr/local/bin/adb"; do
        [ -x "$c" ] && { echo "$c"; return; }
    done
    return 1
}

ADB="$(find_adb)" || {
    echo "❌ adb introuvable (ADB=/chemin/vers/adb bash patch/test-selftest.sh)"
    exit 1
}
echo "adb : $ADB  ($("$ADB" version 2>/dev/null | head -1))"

SERIAL_OPT=()
[ -n "$SERIAL" ] && SERIAL_OPT=(-s "$SERIAL")

adb_run() {
    local out rc
    out="$("$ADB" "${SERIAL_OPT[@]}" "$@" 2>&1)"
    rc=$?
    if printf '%s' "$out" | grep -q 'error: closed'; then
        echo "↻ adb a fermé la connexion — redémarrage du serveur adb…" >&2
        "$ADB" kill-server >/dev/null 2>&1
        sleep 2
        "$ADB" start-server >/dev/null 2>&1
        sleep 3
        out="$("$ADB" "${SERIAL_OPT[@]}" "$@" 2>&1)"
        rc=$?
    fi
    printf '%s\n' "$out"
    return $rc
}

# ── Un appareil utilisable ? ─────────────────────────────────────────────
# BlueStacks expose souvent DEUX transports pour la même machine
# (`emulator-5554` et `127.0.0.1:5555`) : le second ne répond pas toujours à
# `app_process` et le verdict n'arrive jamais. On choisit donc explicitement.
if [ -n "$SERIAL" ]; then
    DEV="$SERIAL"
else
    DEVICES="$(adb_run devices | tr -d '\r' | awk 'NR>1 && $2=="device" {print $1}')"
    DEV="$(printf '%s\n' "$DEVICES" | grep -m1 '^emulator-' || true)"
    [ -z "$DEV" ] && DEV="$(printf '%s\n' "$DEVICES" | head -1)"
    [ "$(printf '%s\n' "$DEVICES" | wc -l)" -gt 1 ] &&
        echo "ℹ️  plusieurs transports disponibles, choix de $DEV : $(printf '%s' "$DEVICES" | tr '\n' ' ')"
fi
if [ -z "$DEV" ]; then
    echo "❌ aucun appareil en état « device »."
    echo "   BlueStacks : Paramètres → Avancé → Android Debug Bridge (activer),"
    echo "   puis : adb connect 127.0.0.1:5555"
    exit 1
fi
# Le transport choisi devient le seul utilisé pour la suite (messages et appels).
SERIAL_OPT=(-s "$DEV")
echo "📺 appareil : $DEV"

if [ "$IN_APP" = "1" ]; then
    # ── Verdict au démarrage de l'app installée ──────────────────────────
    # Le self-test vit dans MainApp.onCreate : il ne s'exécute que lorsqu'un
    # NOUVEAU processus démarre. Sans force-stop, `am start` se contente de
    # ramener la tâche existante au premier plan et rien n'est journalisé.
    echo "🚀 redémarrage de l'application (force-stop puis start)…"
    adb_run logcat -c >/dev/null
    adb_run shell am force-stop "$PKG"
    sleep 1
    adb_run shell am start -n "$ACTIVITY" | tail -2
    sleep 12
    CAPTURE="$(adb_run logcat -d -v time | grep -E 'SELFTEST|FATAL EXCEPTION')"
    echo "$CAPTURE" | grep -v '^$' | sed 's/^/   /'
    VERDICT="$(echo "$CAPTURE" | grep -E 'SELFTEST [0-9]+/[0-9]+' | tail -1)"
else
    # ── Verdict autonome : dex frais, sans installation ──────────────────
    [ -f "$APK" ] || { echo "❌ APK introuvable : $APK (lancer bash patch/build.sh)"; exit 1; }
    echo "📦 envoi de $APK → $REMOTE…"
    adb_run push "$APK" "$REMOTE" | tail -1
    adb_run logcat -c >/dev/null
    echo "▶ exécution du self-test (app_process)…"
    adb_run shell "CLASSPATH=$REMOTE app_process /system/bin com.twouich.adblock.SelfTest" >/dev/null
    sleep 3
    CAPTURE="$(adb_run logcat -d -v time | grep -E 'SELFTEST|VerifyError|FATAL EXCEPTION')"
    echo "$CAPTURE" | grep -v '^$' | sed 's/^/   /'
    VERDICT="$(echo "$CAPTURE" | grep -E 'SELFTEST [0-9]+/[0-9]+' | tail -1)"
fi

echo
if echo "$CAPTURE" | grep -qE 'SELFTEST KO|SELFTEST ECHEC|VerifyError|FATAL EXCEPTION'; then
    echo "❌ SELF-TEST EN ÉCHEC — le filtre anti-pub ou son instrumentation est cassé."
    exit 1
fi

if [ -z "$VERDICT" ]; then
    echo "❓ aucun verdict « SELFTEST n/n » dans la capture."
    echo "   causes probables : APK installé qui n'est pas le nôtre, self-test retiré,"
    echo "   ou application déjà en cours (le self-test ne tourne qu'au démarrage d'un processus)."
    exit 1
fi

echo "✅ SELF-TEST VERT"
echo "   $VERDICT"
echo "   → playlists publicitaires nettoyées par le vrai code compilé, sur l'appareil."
