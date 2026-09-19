#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# test_analyzer.sh — vérifie les verdicts d'analyze_device_log.sh
# ═══════════════════════════════════════════════════════════════════════
# Rejoue des captures logcat synthétiques et contrôle la conclusion.
# Aucun appareil nécessaire :
#   bash patch/tests/test_analyzer.sh
# ═══════════════════════════════════════════════════════════════════════
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ANALYZE="$ROOT/patch/analyze_device_log.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PASS=0
FAIL=0

check() { # check <libellé> <fichier> <chaîne attendue>
    local label="$1" file="$2" expected="$3" out
    out="$(bash "$ANALYZE" "$file" 2>&1)"
    if printf '%s' "$out" | grep -qF "$expected"; then
        printf '  ✅ %s\n' "$label"
        PASS=$((PASS + 1))
    else
        printf '  ❌ %s\n     attendu : %s\n' "$label" "$expected"
        printf '%s\n' "$out" | sed 's/^/       /'
        FAIL=$((FAIL + 1))
    fi
}

CUT='09-15 09:40:12.345 I/Twouich ( 3120): playlist nettoyee 8412 -> 7103 octets, segments pub retires : 3'
ZERO='09-15 09:40:05.100 I/Twouich ( 3120): playlist nettoyee 8412 -> 8412 octets, segments pub retires : 0'

# 1. filtre actif, pubs retirées, lecture propre
{
    echo "$ZERO"
    echo "$CUT"
    echo '09-15 09:41:30.900 I/Twouich ( 3120): playlist nettoyee 8390 -> 7020 octets, segments pub retires : 4'
} > "$TMP/clean.txt"

# 2. filtre actif mais aucune coupure rencontrée
{
    echo "$ZERO"
    echo "$ZERO"
} > "$TMP/nocut.txt"

# 3. pubs retirées mais erreurs de lecture
{
    echo "$CUT"
    echo '09-15 09:40:12.400 E/ExoPlayerImplInternal ( 3120): BehindLiveWindowException'
} > "$TMP/errors.txt"

# 4. le filtre n'est pas dans le chemin du lecteur
echo '09-15 09:40:05.100 I/ExoPlayerImpl ( 3120): Release' > "$TMP/none.txt"

# 5. repli proxy
{
    echo "$CUT"
    echo '09-15 09:40:11.000 W/Twouich ( 3120): proxy indisponible : repli sur la requete directe'
} > "$TMP/proxy.txt"

# 6. sentinelle : marqueur pub inconnu → verdict 🚨 (prioritaire sur tous les autres)
{
    echo "$ZERO"
    echo '09-15 09:40:12.200 W/Twouich ( 3120): marqueur pub inconnu : #EXT-X-CUE-CONTINUE'
} > "$TMP/unknown.txt"

echo "== verdicts =="
check "pubs retirées + lecture propre → FONCTIONNEL" "$TMP/clean.txt" '✅ ANTI-PUB FONCTIONNEL : 7 segments publicitaires retirés'
check "comptage : playlists nettoyées = 3"          "$TMP/clean.txt" 'playlists nettoyées          : 3'
check "comptage : playlists avec pubs = 2"          "$TMP/clean.txt" 'playlists avec pubs retirées : 2'
check "comptage : max sur une playlist = 4"         "$TMP/clean.txt" 'max sur une playlist         : 4'
check "contenu sans pod, sentinelle muette → OK"    "$TMP/nocut.txt"    '✅ CONTENU TRAVERSÉ SANS POD'

# 2b. rien retiré MAIS erreurs de lecture → cas suspect (≠ cas bénin)
{
    echo "$ZERO"
    echo '09-15 09:40:12.400 E/ExoPlayerImplInternal ( 3120): ParserException'
} > "$TMP/nocut-errors.txt"
check "pubs retirées + erreur → avertissement"      "$TMP/errors.txt" 'MAIS 1 erreur(s) de lecture'
check "aucune playlist → filtré absent"             "$TMP/none.txt"         'AUCUNE playlist nettoyée'
check "repli proxy compté"                          "$TMP/proxy.txt"        'replis proxy → direct        : 1'
check "rien retiré + erreurs → cas suspect"         "$TMP/nocut-errors.txt" 'FILTRE ACTIF, RIEN RETIRÉ'
check "marqueur inconnu → verdict sentinelle"       "$TMP/unknown.txt"      '🚨 MARQUEUR(S) PUB NON RECONNU(S)'
check "marqueur inconnu compté = 1"                 "$TMP/unknown.txt"      'marqueurs pub inconnus       : 1'

echo
if [ "$FAIL" -eq 0 ]; then
    echo "✅ verdicts conformes ($PASS/$PASS)"
    exit 0
fi
echo "❌ $FAIL échec(s) sur $((PASS + FAIL))"
exit 1
