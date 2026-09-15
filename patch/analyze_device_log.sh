#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# analyze_device_log.sh — verdict d'une capture logcat de test anti-pub
# ═══════════════════════════════════════════════════════════════════════
# Usage : bash patch/analyze_device_log.sh work/device-test/logcat-xxx.txt
# ═══════════════════════════════════════════════════════════════════════
set -uo pipefail

LOG="${1:-}"
[ -n "$LOG" ] && [ -f "$LOG" ] || { echo "usage: $0 <fichier-logcat>"; exit 2; }

CLEANED="$(grep -c 'playlist nettoyee' "$LOG" || true)"
CUTS="$(grep -o 'segments pub retires : *[0-9]*' "$LOG" | sed 's/.*: *//' | awk '{s+=$1} END {printf "%d", s+0}')"
MAXCUT="$(grep -o 'segments pub retires : *[0-9]*' "$LOG" | sed 's/.*: *//' | sort -n | tail -1)"
CUTLINES="$(grep -c 'segments pub retires : *[1-9]' "$LOG" || true)"
PROXYFAIL="$(grep -c 'proxy indisponible' "$LOG" || true)"

echo "═══════════════════════════════════════════════════════════════════════"
echo "  VERDICT DE LA CAPTURE — $(basename "$LOG")"
echo "═══════════════════════════════════════════════════════════════════════"
printf '  playlists nettoyées          : %s\n' "$CLEANED"
printf '  playlists avec pubs retirées : %s\n' "$CUTLINES"
printf '  segments pub retirés (total) : %s\n' "$CUTS"
printf '  max sur une playlist         : %s\n' "${MAXCUT:-0}"
printf '  replis proxy → direct        : %s\n' "$PROXYFAIL"
echo ""

if [ "$CLEANED" -gt 0 ]; then
    echo "  🕒 premières coupures observées :"
    grep 'segments pub retires : *[1-9]' "$LOG" | head -5 | sed 's/^/     /'
    echo ""
fi

echo "  ── erreurs de lecture / discontinuités ──"
ERRORS=0
for pattern in 'BehindLiveWindow' 'ParserException' 'PlaybackException' 'Source error' 'Discontinuity' 'InvalidResponseCode' 'ANR in com.s0und.s0undtv' 'FATAL EXCEPTION'; do
    n="$(grep -c "$pattern" "$LOG" || true)"
    if [ "$n" -gt 0 ]; then
        printf '  ⚠️  %-24s %s occurrence(s)\n' "$pattern" "$n"
        grep "$pattern" "$LOG" | head -2 | sed 's/^/       /'
        ERRORS=$((ERRORS + n))
    fi
done
[ "$ERRORS" -eq 0 ] && echo "  ✅ aucune erreur de lecture"
echo ""

echo "═══════════════════════════════════════════════════════════════════════"
if [ "$CLEANED" -eq 0 ]; then
    echo "  ❓ AUCUNE playlist nettoyée : le lecteur n'est pas passé par le filtre."
    echo "     → vérifie que la version installée est bien celle du dépôt (patch/build.sh, VERSION_NAME)"
    echo "     → relance une capture : adb logcat -v time -s Twouich:V *:S"
elif [ "$CUTS" -eq 0 ]; then
    echo "  ⚠️  Le filtre tourne mais n'a rien retiré."
    echo "     → soit aucune coupure publicitaire n'a eu lieu pendant la capture,"
    echo "     → soit les marqueurs Twitch ont changé : voir AUDIT.md § 4.2 (constante \"stitched-ad\")."
elif [ "$ERRORS" -eq 0 ]; then
    echo "  ✅ ANTI-PUB FONCTIONNEL : $CUTS segments publicitaires retirés, lecture sans erreur."
else
    echo "  ⚠️  Pubs retirées ($CUTS) MAIS $ERRORS erreur(s) de lecture : vérifier les lignes ci-dessus."
fi
echo "═══════════════════════════════════════════════════════════════════════"
