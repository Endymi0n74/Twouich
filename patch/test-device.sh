#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# test-device.sh — procédure de test anti-pub sur Android TV / émulateur
# ═══════════════════════════════════════════════════════════════════════
# Usage :
#   bash patch/test-device.sh                       # installe puis capture
#   bash patch/test-device.sh --fresh               # désinstalle d'abord
#   bash patch/test-device.sh --list                # appareils disponibles
#   bash patch/test-device.sh --serial emulator-5554
#   bash patch/test-device.sh --connect 192.168.1.42:5555
#   bash patch/test-device.sh --duration 420        # capture auto de 7 min
#   bash patch/test-device.sh --no-install          # capture seule
#   bash patch/test-device.sh --install-only        # installe sans capturer
#   bash patch/test-device.sh --analyze work/device-test/logcat-xxx.txt
#
# La capture met en évidence la trace que l'app produit elle-même :
#   I Twouich : playlist nettoyee <taille avant> -> <après> octets,
#               segments pub retires : <n>
# Un « segments pub retires » > 0 pendant une coupure = le blocage a agi.
#
# Si ADB est capricieux (émulateur BlueStacks notamment), exporter son
# propre binaire avant de lancer :
#   ADB="/c/Users/<vous>/AppData/Local/ScrcpyGUI/scrcpy-bin/adb.exe" \
#       bash patch/test-device.sh
# ═══════════════════════════════════════════════════════════════════════
set -uo pipefail

# Git Bash (MSYS) réécrit les chemins absolus passés aux binaires natifs :
# `/data/local/tmp/x.apk` deviendrait `C:/Program Files/Git/data/local/tmp/x.apk`.
# Résultat : le push écrit ailleurs et l'installation échoue sans explication.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SELF_DIR="$(dirname "${BASH_SOURCE[0]}")"
cd "$ROOT"

PKG="com.s0und.s0undtv"
EXPECTED_VERSION="v1.5.10x-twouich1"
APK="dist/Twouich_beta144_ttv1.apk"
LOG_DIR="work/device-test"
FILTER="Twouich:V ExoPlayerImpl:W ExoPlayerImplInternal:W HlsMediaSource:W Loader:W MediaCodec:W MediaDrm:W AndroidRuntime:E *:S"

FRESH=0
NO_INSTALL=0
INSTALL_ONLY=0
DURATION=0
CONNECT=""
SERIAL=""
ANALYZE=""

while [ $# -gt 0 ]; do
    case "$1" in
        --fresh)        FRESH=1 ;;
        --no-install)   NO_INSTALL=1 ;;
        --install-only) INSTALL_ONLY=1 ;;
        --list)       SERIAL="__LIST__" ;;
        --duration)   DURATION="${2:-0}"; shift ;;
        --connect)    CONNECT="${2:-}"; shift ;;
        --serial|-s)  SERIAL="${2:-}"; shift ;;
        --analyze)    ANALYZE="${2:-}"; shift ;;
        --apk)        APK="${2:-$APK}"; shift ;;
        -h|--help)      sed -n '2,30p' "$0"; exit 0 ;;
        *) echo "option inconnue : $1"; exit 2 ;;
    esac
    shift
done

# ── Résolution d'adb ────────────────────────────────────────────────────
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
    echo "❌ adb introuvable."
    echo "   → Android SDK : installe 'platform-tools' (adb.exe)"
    echo "   → BlueStacks  : C:\\Program Files\\BlueStacks_nxt\\HD-Adb.exe"
    echo "   → ou : ADB=/chemin/vers/adb bash patch/test-device.sh"
    exit 1
}
echo "adb : $ADB  ($("$ADB" version 2>/dev/null | head -1))"

if [ -n "$CONNECT" ]; then
    echo "🔌 connexion à $CONNECT…"
    "$ADB" connect "$CONNECT" 2>&1 | tail -1
fi

# ── Analyse seule ───────────────────────────────────────────────────────
if [ -n "$ANALYZE" ]; then
    exec "$SELF_DIR/analyze_device_log.sh" "$ANALYZE"
fi

# ── Appel adb avec sélection explicite de l'appareil ─────────────────────
# `adb shell` peut échouer en « error: closed » quand deux binaires adb se
# disputent le port 5037 : le serveur redémarre en plein milieu de la
# commande. On redémarre donc le serveur une fois et on réessaie.
SERIAL_OPT=()

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

# ── Sélection de l'appareil ─────────────────────────────────────────────
# `adb devices` peut revenir vide au moment où le serveur redémarre : on
# relance une fois avant de conclure qu'aucun appareil n'est branché.
list_devices() {
    "$ADB" devices 2>/dev/null | tr -d '\r' | awk 'NR>1 && $2=="device" {print $1}'
}

DEV_LINES=()
for attempt in 1 2; do
    mapfile -t DEV_LINES < <(list_devices)
    [ "${#DEV_LINES[@]}" -gt 0 ] && break
    "$ADB" start-server >/dev/null 2>&1
    sleep 3
done

if [ "$SERIAL" = "__LIST__" ]; then
    echo "appareils utilisables : ${#DEV_LINES[@]}"
    for l in ${DEV_LINES[@]+"${DEV_LINES[@]}"}; do echo "   $l"; done
    "$ADB" devices -l 2>/dev/null | tr -d '\r' | tail -n +2 | grep . | sed 's/^/   (brut) /'
    exit 0
fi

if [ -z "$SERIAL" ]; then
    case "${#DEV_LINES[@]}" in
        0)
            echo "❌ aucun appareil utilisable (état 'device')."
            echo "   Android TV : Paramètres > À propos > Réseau > Débogage ADB (activer), puis :"
            echo "     $ADB connect <ip-de-la-tv>:5555"
            echo "   BlueStacks : Paramètres > Avancé > Android Debug Bridge (activer), puis"
            echo "     $ADB connect 127.0.0.1:5555"
            echo "   Ligne listée mais état 'offline'/'unauthorized' ? → accepter le message sur l'écran"
            echo "   de la TV, ou '$ADB kill-server' puis relancer."
            exit 1 ;;
        1)
            SERIAL="${DEV_LINES[0]}" ;;
        *)
            echo "❌ plusieurs appareils : précise lequel avec --serial."
            for l in "${DEV_LINES[@]}"; do echo "     $l"; done
            exit 1 ;;
    esac
fi
SERIAL_OPT=(-s "$SERIAL")
echo "📺 appareil : $SERIAL"

# Sonde : l'appareil répond-il vraiment ?
PROBE="$(adb_run shell echo twouich-probe || true)"
if ! printf '%s' "$PROBE" | grep -q 'twouich-probe'; then
    echo "❌ l'appareil ne répond pas aux commandes shell ($SERIAL)."
    printf '   réponse adb : %s\n' "$(printf '%s' "$PROBE" | head -1)"
    case "$SERIAL" in
        *:*)
            echo "   → relance la connexion : $ADB disconnect ${SERIAL%%:*} ; $ADB connect $SERIAL" ;;
        *)
            echo "   → émulateur/instance bloqué : redémarre-la (BlueStacks : Paramètres > Avancé >"
            echo "     ADB, puis Arrêter/Redémarrer l'instance) ou redémarre l'appareil." ;;
    esac
    exit 1
fi

mkdir -p "$LOG_DIR"

# ── Installation ────────────────────────────────────────────────────────
if [ "$NO_INSTALL" -eq 0 ]; then
    [ -f "$APK" ] || { echo "❌ APK introuvable : $APK (lancer d'abord bash patch/build.sh)"; exit 1; }

    if [ "$FRESH" -eq 1 ]; then
        echo "🗑️  désinstallation de l'app (signature différente : obligatoire une fois)…"
        adb_run uninstall "$PKG" | tail -2
    fi

    echo "📦 installation de $APK…"
    INSTALL_OUT="$(adb_run install -r "$APK")"
    printf '%s\n' "$INSTALL_OUT" | tail -3
    if ! printf '%s' "$INSTALL_OUT" | grep -q 'Success'; then
        echo "↻ flux direct refusé — repli push + pm install…"
        if adb_run push "$APK" /data/local/tmp/twouich.apk >/dev/null 2>&1; then
            INSTALL_OUT="$(adb_run shell pm install -r /data/local/tmp/twouich.apk)"
            printf '%s\n' "$INSTALL_OUT" | tail -3
            adb_run shell rm -f /data/local/tmp/twouich.apk >/dev/null 2>&1
        fi
    fi

    case "$INSTALL_OUT" in
        *Success*) : ;;
        *UPDATE_INCOMPATIBLE*|*signatures*)
            echo "❌ signature différente de l'app déjà installée → relance avec --fresh"
            exit 1 ;;
        *VERSION_DOWNGRADE*)
            echo "❌ version installée plus récente → relance avec --fresh (ou installe un versionCode supérieur)"
            exit 1 ;;
        *)
            echo "❌ installation échouée :"
            printf '%s\n' "$INSTALL_OUT" | tail -6
            echo "   → '$ADB' uninstall $PKG  puis relancer avec --fresh"
            exit 1 ;;
    esac

    VERSION="$(adb_run shell dumpsys package "$PKG" | grep -m1 versionName | tr -d '\r')"
    echo "✅ installée — $VERSION"
    case "$VERSION" in
        *"$EXPECTED_VERSION"*) : ;;
        "") echo "⚠️  version illisible : l'APK installé n'est peut-être pas le nôtre." ;;
        *)  echo "⚠️  attendu : $EXPECTED_VERSION → ce n'est PAS notre build." ;;
    esac
fi

if [ "$INSTALL_ONLY" -eq 1 ]; then
    echo ""
    echo "✅ installation terminée. Lance un stream puis :"
    echo "   bash patch/test-device.sh --no-install --serial $SERIAL"
    exit 0
fi

# ── Capture ─────────────────────────────────────────────────────────────
STAMP="$(date +%Y%m%d-%H%M%S)"
LOG="$LOG_DIR/logcat-$STAMP.txt"
adb_run logcat -c >/dev/null 2>&1 || true

cat <<EOF

═══════════════════════════════════════════════════════════════════════
  CAPTURE EN COURS → $LOG
═══════════════════════════════════════════════════════════════════════
1. lance un stream sur la TV (chaîne programmant des midrolls si possible) ;
2. laisse tourner AU MOINS une coupure publicitaire complète ;
3. note l'heure de la coupure (précieuse pour l'analyse) ;
4. reviens ici et appuie sur Ctrl+C.
EOF

if [ "$DURATION" -gt 0 ]; then
    echo "⏱️  capture automatique de ${DURATION}s…"
    timeout "$DURATION" "$ADB" "${SERIAL_OPT[@]}" logcat -v time -s $FILTER | tee "$LOG" || true
else
    "$ADB" "${SERIAL_OPT[@]}" logcat -v time -s $FILTER | tee "$LOG" || true
fi

echo ""
echo "🧾 capture terminée : $LOG"
"$SELF_DIR/analyze_device_log.sh" "$LOG"
