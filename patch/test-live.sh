#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# test-live.sh — observation en direct longue (TEST-DEVICE.md § 2)
# ═══════════════════════════════════════════════════════════════════════
# Enchaîne les étapes mécaniques de la recette d'observation : état de
# l'appareil, capture logcat DÉTACHÉE (survit au script, append sur un
# fichier cumulé), lancement de l'app, surveillance de vie de la capture
# (relance automatique en append si elle meurt — leçon du 18/09), arrêt
# du client logcat sans toucher au serveur adb, verdict de
# analyze_device_log.sh. La NAVIGATION vers un direct (D-pad/télécommande)
# et l'observation de l'écran restent à la main.
#
# Usage :
#   bash patch/test-live.sh                       # 5 min d'observation
#   bash patch/test-live.sh --duration 600        # 10 min
#   bash patch/test-live.sh --serial emulator-5554
#   bash patch/test-live.sh --connect 127.0.0.1:5555
#   bash patch/test-live.sh --list                # appareils disponibles
#   bash patch/test-live.sh --no-launch           # app/direct déjà ouverts
#   bash patch/test-live.sh --no-quit             # ne pas fermer le direct à la fin
#   bash patch/test-live.sh --analyze <fichier>   # verdict d'une capture existante
#   ADB="/c/Program Files/BlueStacks_nxt/HD-Adb.exe" bash patch/test-live.sh
# ═══════════════════════════════════════════════════════════════════════
set -uo pipefail

# Git Bash (MSYS) réécrit les chemins absolus passés aux binaires natifs :
# même piège que test-device.sh (voir TEST-DEVICE.md § 1).
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SELF_DIR="$(dirname "${BASH_SOURCE[0]}")"
cd "$ROOT"

PKG="com.s0und.s0undtv"
LOG_DIR="work/device-test"
# Même filtre que test-device.sh — le verdict doit couvrir les mêmes lignes.
FILTER="Twouich:V ExoPlayerImpl:W ExoPlayerImplInternal:W HlsMediaSource:W Loader:W MediaCodec:W MediaDrm:W AndroidRuntime:E *:S"
SLICE=30               # fenêtre de contrôle de vie de la capture (s)
DEFAULT_DURATION=300

DURATION=0
CONNECT=""
SERIAL=""
ANALYZE=""
NO_LAUNCH=0
NO_QUIT=0

while [ $# -gt 0 ]; do
    case "$1" in
        --duration)   DURATION="${2:-0}"; shift ;;
        --connect)    CONNECT="${2:-}"; shift ;;
        --serial|-s)  SERIAL="${2:-}"; shift ;;
        --list)       SERIAL="__LIST__" ;;
        --no-launch)  NO_LAUNCH=1 ;;
        --no-quit)    NO_QUIT=1 ;;
        --analyze)    ANALYZE="${2:-}"; shift ;;
        -h|--help)    sed -n '2,32p' "$0"; exit 0 ;;
        *) echo "option inconnue : $1"; exit 2 ;;
    esac
    shift
done

# ── Résolution d'adb (identique à test-device.sh) ───────────────────────
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
    echo "   → BlueStacks  : C:\\Program Files\\BlueStacks_nxt\\HD-Adb.exe"
    echo "   → ou : ADB=/chemin/vers/adb bash patch/test-live.sh"
    exit 1
}

if [ -n "$ANALYZE" ]; then
    exec "$SELF_DIR/analyze_device_log.sh" "$ANALYZE"
fi

echo "adb : $ADB  ($("$ADB" version 2>/dev/null | head -1))"

# ── Appel adb avec reprise « error: closed » (cf. test-device.sh) ────────
SERIAL_OPT=()
adb_run() {
    local out rc
    out="$("$ADB" "${SERIAL_OPT[@]}" "$@" 2>&1)"
    rc=$?
    if printf '%s' "$out" | grep -q 'error: closed'; then
        echo "↻ adb a fermé la connexion — redémarrage du serveur adb…" >&2
        "$ADB" kill-server >/dev/null 2>&1
        sleep 2; "$ADB" start-server >/dev/null 2>&1; sleep 3
        out="$("$ADB" "${SERIAL_OPT[@]}" "$@" 2>&1)"
        rc=$?
    fi
    printf '%s\n' "$out"
    return $rc
}

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
    exit 0
fi

if [ -n "$CONNECT" ]; then
    echo "🔌 connexion à $CONNECT…"
    "$ADB" connect "$CONNECT" 2>&1 | tail -1
    mapfile -t DEV_LINES < <(list_devices)
fi

if [ -z "$SERIAL" ]; then
    case "${#DEV_LINES[@]}" in
        0) echo "❌ aucun appareil utilisable (état 'device') — voir TEST-DEVICE.md § 1."; exit 1 ;;
        1) SERIAL="${DEV_LINES[0]}" ;;
        *) echo "❌ plusieurs appareils : précise lequel avec --serial."
           for l in "${DEV_LINES[@]}"; do echo "     $l"; done
           exit 1 ;;
    esac
fi
SERIAL_OPT=(-s "$SERIAL")
echo "📺 appareil : $SERIAL"

PROBE="$(adb_run shell echo twouich-probe || true)"
if ! printf '%s' "$PROBE" | grep -q 'twouich-probe'; then
    echo "❌ l'appareil ne répond pas aux commandes shell ($SERIAL)."
    exit 1
fi

# ── 1/5 État ────────────────────────────────────────────────────────────
echo ""
echo "── 1/5 État ──"
mkdir -p "$LOG_DIR"

INST="$(adb_run shell dumpsys package "$PKG" || true | tr -d '\r')"
if ! printf '%s' "$INST" | grep -q 'versionName'; then
    echo "❌ l'app n'est pas installée sur $SERIAL."
    echo "   → bash patch/test-device.sh --install-only"
    exit 1
fi
printf '%s\n' "$INST" | grep -E 'versionCode|versionName' | head -2 | sed 's/^/   /'

EXPECTED="$(sed -n 's/^VERSION_NAME="\(.*\)"$/\1/p' patch/build.sh | head -1)"
if [ -n "$EXPECTED" ] && ! printf '%s' "$INST" | grep -q "versionName=$EXPECTED"; then
    echo "   ⚠️  version installée ≠ VERSION_NAME de build.sh ($EXPECTED) — verdict à interpréter en conséquence."
fi

# ── Clients logcat résiduels : un seul appendeur par fichier ────────────
# Deux clients apposant le même fichier doubleraient les compteurs du
# verdict. On arrête les résidus AVANT de démarrer (leçon du 18/09).
logcat_clients() {
    if command -v powershell >/dev/null 2>&1; then
        # Exclure la sonde elle-même : sa ligne de commande contient « logcat ».
        powershell -NoProfile -Command \
            "Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -like '*logcat*' -and \$_.CommandLine -notlike '*Get-CimInstance*' } | Select-Object -ExpandProperty ProcessId" \
            2>/dev/null | grep -c .
    else
        pgrep -fc 'logcat' 2>/dev/null || echo 0
    fi
}
stop_logcat_clients() {
    if command -v powershell >/dev/null 2>&1; then
        # Sans l'exclusion, Stop-Process tue d'abord le process qui exécute la
        # requête elle-même et meurt avant d'avoir tué les clients logcat.
        powershell -NoProfile -Command \
            "Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -like '*logcat*' -and \$_.CommandLine -notlike '*Get-CimInstance*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }" \
            >/dev/null 2>&1 || true
    else
        pkill -f 'logcat' >/dev/null 2>&1 || true
    fi
}

STALE="$(logcat_clients)"
if [ "${STALE:-0}" -gt 0 ]; then
    echo "🧹 $STALE client(s) logcat résiduel(s) — arrêt (le serveur adb n'est pas touché)…"
    stop_logcat_clients
    sleep 2
fi

# ── 2/5 Capture détachée ────────────────────────────────────────────────
L="$LOG_DIR/logcat-live-$(date +%d-%m).txt"
[ -f "$L" ] && echo "   (append sur la capture existante : $L)"

start_capture() {
    # read -ra découpe sans globbing (le filtre contient *:S).
    read -r -a FILTER_ARGS <<< "$FILTER"
    # -T <heure appareil> : ne re-émettre QUE les lignes à venir — sans -T,
    # logcat rejoue son tampon au démarrage et les compteurs du verdict
    # doublent les événements d'avant la relance.
    # Appel DIRECT (jamais adb_run) : la reprise « error: closed » d'adb_run
    # fait kill-server, qui déconnecterait les clients logcat en cours —
    # la relance se saborderait elle-même en boucle.
    local since
    # Le format est quoté CÔTÉ DISTANT : en args séparés, le `date` toolbox
    # d'Android ne voit que le premier fragment (« +%m-%d » → « 09-19 ») et
    # logcat -T refuse ce format tronqué (capture morte à chaque relance).
    since="$("$ADB" -s "$SERIAL" shell "date '+%m-%d %H:%M:%S.000'" 2>/dev/null | tr -d '\r' | tail -1)"
    if [ -n "$since" ]; then
        nohup "$ADB" -s "$SERIAL" logcat -v time -T "$since" "${FILTER_ARGS[@]}" >> "$L" 2>&1 &
    else
        nohup "$ADB" -s "$SERIAL" logcat -v time "${FILTER_ARGS[@]}" >> "$L" 2>&1 &
    fi
    sleep 3
}

echo "── 2/5 Capture détachée : $L"
start_capture
# Avec -T (aucune re-émission du tampon), un appareil au repos ne produit
# RIEN au démarrage : un fichier vide n'est pas une erreur. On n'échoue que
# sur une erreur explicite dans la capture (stderr y est redirigé) ; sinon,
# la présence d'un client logcat fait foi et la surveillance prend le relais.
if [ -s "$L" ] && tail -n 5 "$L" | grep -qiE 'not in time format|error: closed|error: no devices|error: device'; then
    echo "❌ la capture ne démarre pas — stderr est dans le fichier :"
    tail -3 "$L" 2>/dev/null | sed 's/^/   /'
    stop_logcat_clients
    exit 1
fi
CLIENTS="$(logcat_clients)"
if [ "${CLIENTS:-0}" -eq 0 ]; then
    echo "   ⚠️  aucun client logcat visible — la surveillance relancera si besoin."
else
    echo "   capture vivante ($CLIENTS client(s) logcat, $(wc -l < "$L" 2>/dev/null | tr -d ' ' || echo 0) lignes)."
fi

# ── 3/5 Lancement de l'app (la navigation reste à la main) ──────────────
if [ "$NO_LAUNCH" -eq 0 ]; then
    echo "── 3/5 Lancement de l'app"
    adb_run shell monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1 || true
    sleep 6
    UI_XML="$LOG_DIR/ui-live.xml"
    adb_run shell uiautomator dump /sdcard/ui.xml >/dev/null 2>&1 || true
    adb_run pull /sdcard/ui.xml "$UI_XML" >/dev/null 2>&1 || true
    if [ -f "$UI_XML" ]; then
        echo "   élément focusé (boussole D-pad) :"
        grep -o '<node[^>]*focused="true"[^>]*>' "$UI_XML" | head -2 \
            | cut -c1-220 | sed 's/^/     /' || echo "     (aucun)"
        grep -q 'Live Stream History' "$UI_XML" \
            && echo "   « Live Stream History » visible à l'écran." \
            || echo "   « Live Stream History » non visible (écran d'accueil différent ?)."
    else
        echo "   ⚠️  dump uiautomator indisponible — navigation à l'aveugle."
    fi
else
    echo "── 3/5 Lancement de l'app : sauté (--no-launch)"
fi

echo ""
echo "   ▶ À TOI : ouvre un direct (télécommande ou D-pad ADB — 19/20/21/22 flèches,"
echo "     23 valider ; dump de contrôle : adb shell uiautomator dump). Le script"
echo "     surveille la capture et rend le verdict à la fin."
echo ""

# ── 4/5 Observation surveillée ──────────────────────────────────────────
[ "$DURATION" -le 0 ] && DURATION=$DEFAULT_DURATION
echo "── 4/5 Observation : $DURATION s"
SECONDS=0
END=$((SECONDS + DURATION))
RESTARTS=0
PREV_LINES="$(wc -l < "$L" 2>/dev/null | tr -d ' ' || echo 0)"
PREV_CUTS=0
while [ "$SECONDS" -lt "$END" ]; do
    REMAIN=$((END - SECONDS))
    [ "$REMAIN" -gt "$SLICE" ] && REMAIN=$SLICE
    sleep "$REMAIN"

    CUR="$(wc -l < "$L" 2>/dev/null | tr -d ' ' || echo 0)"
    CLEAN="$(grep -c 'playlist nettoyee' "$L" 2>/dev/null || true)"
    CUTS="$(grep -c 'segments pub retires : *[1-9]' "$L" 2>/dev/null || true)"
    UNKNOWN="$(grep -c 'marqueur pub inconnu' "$L" 2>/dev/null || true)"

    if [ "${CUTS:-0}" -gt "$PREV_CUTS" ]; then
        grep 'segments pub retires : *[1-9]' "$L" | tail -1 | sed 's/^/   🛑 retrait : /'
        PREV_CUTS="$CUTS"
    fi
    if [ "${UNKNOWN:-0}" -gt 0 ]; then
        echo "   🚨 SENTINELLE : marqueur pub inconnu détecté — voir le verdict final !"
        grep 'marqueur pub inconnu' "$L" | tail -1 | cut -c1-220 | sed 's/^/      /'
    fi
    echo "   t+${SECONDS}s : $CUR lignes, $CLEAN nettoyages, $CUTS retraits"

    # Capture morte ou app au repos ? Un client logcat VIVANT sur un
    # appareil silencieux ne produit aucune ligne : ce n'est pas une mort.
    # On ne relance que si AUCUN client n'existe (la leçon du 18/09 : un
    # client peut mourir sans prévenir) — sinon les relances à l'aveugle
    # empilent les appenders et dupliquent les lignes.
    if [ "$CUR" = "$PREV_LINES" ]; then
        # Une sonde CIM peut crever à zéro un instant : ne déclarer la mort
        # que si DEUX sondes consécutives ne voient aucun client.
        DEAD=0
        if [ "$(logcat_clients)" -eq 0 ]; then
            sleep 2
            [ "$(logcat_clients)" -eq 0 ] && DEAD=1
        fi
        if [ "$DEAD" -eq 1 ] && [ "$RESTARTS" -lt 3 ]; then
            RESTARTS=$((RESTARTS + 1))
            echo "   ⚠️  capture morte (plus aucun client logcat, 2 sondes) — relance en append ($RESTARTS/3)…"
            start_capture
            CUR="$(wc -l < "$L" 2>/dev/null | tr -d ' ' || echo 0)"
            if [ "$(logcat_clients)" -eq 0 ]; then
                echo "   ⚠️  la relance n'a pas produit de client visible — la capture peut rester inactive."
            fi
        else
            echo "   (aucune nouvelle ligne — client logcat vivant, app au repos ?)"
        fi
    fi
    PREV_LINES="$CUR"
done

# ── 5/5 Arrêt + verdict ─────────────────────────────────────────────────
echo ""
echo "── 5/5 Arrêt + verdict"
if [ "$NO_QUIT" -eq 0 ]; then
    adb_run shell input keyevent 4 >/dev/null 2>&1 || true   # BACK : sortir du direct
    sleep 2
    if adb_run shell dumpsys activity activities 2>/dev/null | grep -q 'PlayerActivity'; then
        adb_run shell input keyevent 4 >/dev/null 2>&1 || true
        sleep 1
    fi
fi

stop_logcat_clients
sleep 1

bash "$SELF_DIR/analyze_device_log.sh" "$L"
rc=$?
echo ""
echo "capture archivée : $L"
exit $rc
