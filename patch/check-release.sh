#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# check-release.sh — la release publiée est-elle celle que l'app ira chercher ?
# ═══════════════════════════════════════════════════════════════════════
# L'updater ne lit qu'une chose : `update.json` sur `master`. Il en tire un tag
# (`releases/download/<VersionName>/<APK>`) et télécharge l'asset correspondant.
# Rien dans ce chemin ne vérifie quoi que ce soit : si le tag, le nom d'asset ou
# le versionCode divergent de ce qui a été construit, l'app annonce une mise à
# jour et échoue en silence — ou pire, installe autre chose.
#
# Ce script confronte les trois étages, dans l'ordre où l'app les traverse :
#
#   1. le livrable local          dist/<APK_NAME> (et son SHA-256)
#   2. ce que l'app va lire       raw.githubusercontent.com/<repo>/master/update.json
#   3. ce que l'app va télécharger releases/download/<VersionName>/<APK_NAME>
#
# Usage :  bash patch/check-release.sh
# Sortie : 0 si la chaîne est cohérente, 1 sinon.
# ═══════════════════════════════════════════════════════════════════════
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

REPO="$(git remote get-url origin 2>/dev/null | sed -E 's#(git@github.com:|https://github.com/)##; s#\.git$##')"
REPO="${REPO:-Endymi0n74/Twouich}"

VERSION_CODE="$(sed -n 's/^VERSION_CODE=\(.*\)$/\1/p' patch/build.sh | head -1)"
VERSION_NAME="$(sed -n 's/^VERSION_NAME="\(.*\)"$/\1/p' patch/build.sh | head -1)"
APK_NAME="$(sed -n 's/^APK_NAME="\(.*\)"$/\1/p' patch/build.sh | head -1)"
[ -n "$VERSION_CODE" ] && [ -n "$VERSION_NAME" ] && [ -n "$APK_NAME" ] || {
    echo "❌ VERSION_CODE / VERSION_NAME / APK_NAME illisibles dans patch/build.sh"
    exit 1
}

FAIL=0
ok()   { echo "  ✅ $1"; }
ko()   { echo "  ❌ $1"; FAIL=1; }
info() { echo "     $1"; }

echo "═══════════════════════════════════════════════════════════════════════"
echo "  Release publique : $VERSION_NAME (versionCode $VERSION_CODE)"
echo "  Dépôt : $REPO"
echo "═══════════════════════════════════════════════════════════════════════"

# ── 1. Le livrable local ────────────────────────────────────────────────
echo
echo "1. Livrable local"
APK="dist/$APK_NAME"
if [ ! -f "$APK" ]; then
    ko "$APK absent (lancer : bash patch/build.sh)"
    exit 1
fi
LOCAL_SHA="$(sha256sum "$APK" | cut -d' ' -f1)"
ok "$APK ($(stat -c%s "$APK" 2>/dev/null || echo '?') octets)"
info "SHA-256 $LOCAL_SHA"

# Le versionCode du livrable, lu dans le manifeste binaire — et non dans l'arbre
# de travail, qui peut être en avance ou en retard sur ce qui a été publié.
if python patch/tests/test_apk.py >/dev/null 2>&1; then
    ok "le livrable porte le versionCode/versionName de update.json"
else
    ko "test_apk.py échoue — le livrable ne décrit pas ce que update.json annonce"
    python patch/tests/test_apk.py 2>&1 | grep '❌' | sed 's/^/     /'
fi

# ── 2. Ce que l'app lit ─────────────────────────────────────────────────
echo
echo "2. update.json publié sur master (ce que l'app interroge)"
REMOTE_JSON="$(curl -sSL --max-time 60 "https://raw.githubusercontent.com/$REPO/master/update.json")"
if [ -z "$REMOTE_JSON" ]; then
    ko "raw.githubusercontent.com/$REPO/master/update.json injoignable"
    REMOTE_JSON='[]'
fi
read -r R_CODE R_NAME R_APK <<<"$(printf '%s' "$REMOTE_JSON" | python -c '
import json, sys
try:
    entries = json.load(sys.stdin)
except Exception:
    print("- - -"); raise SystemExit
stable = [e for e in entries if e.get("ReleaseType") == 0]
e = stable[0] if stable else {}
print(e.get("VersionCode", "-"), e.get("VersionName", "-"), e.get("APK", "-"))
')"
[ "$R_CODE" = "$VERSION_CODE" ] && ok "versionCode publié : $R_CODE" \
    || ko "versionCode publié = $R_CODE, attendu $VERSION_CODE"
[ "$R_NAME" = "$VERSION_NAME" ] && ok "versionName publié : $R_NAME" \
    || ko "versionName publié = $R_NAME, attendu $VERSION_NAME"
[ "$R_APK" = "$APK_NAME" ] && ok "asset annoncé : $R_APK" \
    || ko "asset annoncé = $R_APK, attendu $APK_NAME"

# ── 3. Ce que l'app télécharge ──────────────────────────────────────────
echo
echo "3. Release et assets au tag $VERSION_NAME"
if command -v gh >/dev/null 2>&1; then
    ASSETS="$(gh release view "$VERSION_NAME" -R "$REPO" --json assets --jq '.assets[].name' 2>/dev/null)"
    if [ -z "$ASSETS" ]; then
        ko "aucune release au tag $VERSION_NAME (le tag doit être exactement le VersionName)"
    else
        echo "$ASSETS" | grep -qx "$APK_NAME" && ok "asset $APK_NAME présent" \
            || ko "asset $APK_NAME absent de la release"
        echo "$ASSETS" | grep -qx "changelog.html" && ok "asset changelog.html présent" \
            || ko "asset changelog.html absent — la page « Nouveautés » restera vide"
    fi
    LATEST="$(gh release list -R "$REPO" --limit 1 --json tagName --jq '.[0].tagName' 2>/dev/null)"
    [ "$LATEST" = "$VERSION_NAME" ] && ok "c'est la release « latest »" \
        || ko "la release « latest » est $LATEST — or AutoUpdateService tape releases/latest/download/"
else
    info "(gh absent : contrôle de la release ignoré)"
fi

for url in "https://github.com/$REPO/releases/download/$VERSION_NAME/$APK_NAME" \
           "https://github.com/$REPO/releases/download/$VERSION_NAME/changelog.html"; do
    CODE="$(curl -sL -o /dev/null -w '%{http_code}' --max-time 300 "$url")"
    [ "$CODE" = "200" ] && ok "$CODE  ${url##*/}" || ko "$CODE  $url"
done

# Les octets réellement servis : c'est la seule preuve que l'app installera
# exactement ce qui a été testé, et pas un fichier remplacé après coup.
echo
echo "4. Octets servis"
SERVED="$(curl -sL --max-time 300 "https://github.com/$REPO/releases/latest/download/$APK_NAME" | sha256sum | cut -d' ' -f1)"
[ "$SERVED" = "$LOCAL_SHA" ] && ok "SHA-256 servi = SHA-256 local" \
    || { ko "SHA-256 servi = $SERVED"; info "            local = $LOCAL_SHA"; }

echo
if [ "$FAIL" -eq 0 ]; then
    echo "✅ CHAÎNE COHÉRENTE : update.json → tag → asset → octets du livrable"
    echo "   Un appareil en $VERSION_CODE-1 doit se mettre à jour vers $VERSION_CODE."
else
    echo "❌ CHAÎNE INCOHÉRENTE — ne pas annoncer cette version : les appareils"
    echo "   verraient « mise à jour disponible » et n'installeraient rien."
fi
exit "$FAIL"
