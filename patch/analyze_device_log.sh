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
# Sentinelle « marqueur pub inconnu » (PlaylistSanitizer.b()) : balises qui
# ressemblent a un marqueur pub sans etre couvertes par une regle connue.
# Voir AUDIT.md § 4.3 et le miroir patch/tests/test_sanitizer.py.
UNKNOWN="$(grep 'marqueur pub inconnu' "$LOG" | grep -v 'marqueur pub inconnu : SENTINEL' || true)"
UNKNOWN_N="$(printf '%s\n' "$UNKNOWN" | grep -c . || true)"

echo "═══════════════════════════════════════════════════════════════════════"
echo "  VERDICT DE LA CAPTURE — $(basename "$LOG")"
echo "═══════════════════════════════════════════════════════════════════════"
printf '  playlists nettoyées          : %s\n' "$CLEANED"
printf '  playlists avec pubs retirées : %s\n' "$CUTLINES"
printf '  segments pub retirés (total) : %s\n' "$CUTS"
printf '  max sur une playlist         : %s\n' "${MAXCUT:-0}"
printf '  replis proxy → direct        : %s\n' "$PROXYFAIL"
printf '  marqueurs pub inconnus       : %s\n' "$UNKNOWN_N"
echo ""

if [ "$UNKNOWN_N" -gt 0 ]; then
    echo "  🚨 balises suspectées publicitaires NON couvertes par les règles :"
    printf '%s\n' "$UNKNOWN" | head -3 | sed 's/^/     /'
    echo ""
fi

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
elif [ "$UNKNOWN_N" -gt 0 ]; then
    echo "  🚨 MARQUEUR(S) PUB NON RECONNU(S) : Twitch a changé de format —"
    echo "     les balises ci-dessus ressemblent à des pubs (X-TV-TWITCH-AD-* / CUE)"
    echo "     qu'aucune règle de PlaylistSanitizer ne couvre. Capturer la playlist"
    echo "     brute (méthode AUDIT.md § 4.4), ajouter la règle dans le smali + un cas"
    echo "     figé dans patch/tests/test_sanitizer.py, puis rebuild."
elif [ "$CUTS" -eq 0 ] && [ "$ERRORS" -eq 0 ]; then
    echo "  ✅ CONTENU TRAVERSÉ SANS POD : $CLEANED playlist(s) nettoyée(s), 0 marqueur inconnu —"
    echo "     la sentinelle confirme que le format servi est celui des règles. Cas bénin : aucune"
    echo "     pub n'a été servie pendant la capture (pour voir des retraits, cibler une chaîne à"
    echo "     forte charge — radar multi-chaînes, AUDIT.md § 4.4)."
elif [ "$CUTS" -eq 0 ]; then
    echo "  ⚠️  FILTRE ACTIF, RIEN RETIRÉ, $ERRORS erreur(s) de lecture : à qualifier."
    echo "     → commencer par les erreurs ci-dessus (TEST-DEVICE.md § 7) ; si elles indiquent un"
    echo "       format de marqueur non reconnu, suivre AUDIT.md § 4.2 (constante \"stitched-ad\")."
elif [ "$ERRORS" -eq 0 ]; then
    echo "  ✅ ANTI-PUB FONCTIONNEL : $CUTS segments publicitaires retirés, lecture sans erreur."
else
    echo "  ⚠️  Pubs retirées ($CUTS) MAIS $ERRORS erreur(s) de lecture : vérifier les lignes ci-dessus."
fi
echo "═══════════════════════════════════════════════════════════════════════"
