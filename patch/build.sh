#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# build.sh — Twouich : APK Android TV Twitch + anti-pub
# ═══════════════════════════════════════════════════════════════════════
# Usage :  cd /d/Codex/Twouich && bash patch/build.sh
#
# Chaîne : APK upstream → apktool d → patch.py → apktool b → signature
#          v1+v2+v3 → vérification → dist/Twouich_beta144_ttv1.apk
# Tout est rejouable : les patchs sont dans patch/, l'APK upstream est
# retéléchargé si besoin, la clé vit dans keys/ (jamais versionnée).
# ═══════════════════════════════════════════════════════════════════════
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

UPSTREAM_URL="https://github.com/S0und/S0undTV/releases/download/beta/beta_144.apk"
UPSTREAM_APK="work/upstream/beta_144.apk"
UPSTREAM_SHA256="578da49bcab05b1bf0448bbf638f88af71ad7188052cd65c3319093ee5b151b0"
DECODED="work/decoded"
BUILD_DIR="work/build"
APKTOOL="tools/apktool-3.0.3.jar"
SIGNER="tools/uber-apk-signer.jar"

KEYSTORE="keys/twouich.keystore"
KEY_ALIAS="twouich-dev"
# Le mot de passe du keystore n'est PAS écrit ici : ce dépôt est public, et une
# clé de signature dont le mot de passe est public permet à n'importe qui de
# signer un APK qu'Android acceptera comme une mise à jour de Twouich. Il vient de
# l'environnement (`KEY_PASS=…`) ou de `keys/keystore.properties` (ignoré par git).
KEY_PASS=""
KEY_PROPS="keys/keystore.properties"
if [ -z "$KEY_PASS" ] && [ -f "$KEY_PROPS" ]; then
    _alias="$(sed -n 's/^keyAlias=//p' "$KEY_PROPS" | head -1)"
    [ -n "$_alias" ] && KEY_ALIAS="$_alias"
    KEY_PASS="$(sed -n 's/^storePassword=//p' "$KEY_PROPS" | head -1)"
fi
if [ -z "$KEY_PASS" ]; then
    echo "❌ mot de passe du keystore introuvable."
    echo "   Ce script n'en contient aucun (dépôt public). Créer $KEY_PROPS :"
    echo "     keyAlias=$KEY_ALIAS"
    echo "     storePassword=<le mot de passe de la clé>"
    echo "   ou lancer : KEY_PASS=… bash patch/build.sh"
    exit 1
fi

VERSION_CODE=146
VERSION_NAME="v1.5.10x-twouich2"
APK_NAME="Twouich_beta144_ttv1.apk"

echo "═══════════════════════════════════════════════"
echo "  Twouich — build $VERSION_NAME ($VERSION_CODE)"
echo "═══════════════════════════════════════════════"

# ── 0. Outils ──
for tool in "$APKTOOL" "$SIGNER"; do
    [ -f "$tool" ] || { echo "❌ outil manquant : $tool"; exit 1; }
done
command -v python >/dev/null 2>&1 || { echo "❌ python introuvable"; exit 1; }

# ── 1. APK upstream (vérification d'intégrité) ──
mkdir -p work/upstream work/build dist
if [ ! -f "$UPSTREAM_APK" ]; then
    echo "⬇️  Téléchargement de l'APK upstream…"
    curl -sSL --max-time 300 -o "$UPSTREAM_APK" "$UPSTREAM_URL"
fi
echo "$UPSTREAM_SHA256  $UPSTREAM_APK" | sha256sum -c - >/dev/null \
    || { echo "❌ SHA-256 de l'APK upstream inattendu — abandon"; exit 1; }
echo "✅ APK upstream conforme (SHA-256)"

# ── 2. Désassemblage ──
# L'arbre est réutilisé d'un build à l'autre (le désassemblage coûte cher), mais un
# bump de version le rend incohérent : les artefacts qu'il contient déjà portent la
# version précédente — le journal embarqué en tête, que patch.py refuse alors de
# réécrire (et il a raison : mieux vaut échouer que livrer un APK dont la page
# « Nouveautés » cite une autre version). On redésassemble dès que la version du
# script n'est plus celle de l'arbre, pour que « bump puis rebuild » marche seul.
DECODED_VERSION="$(sed -n 's/^ *versionName: //p' "$DECODED/apktool.yml" 2>/dev/null | head -1)"
if [ -f "$DECODED/apktool.yml" ] && [ "$DECODED_VERSION" != "$VERSION_NAME" ]; then
    echo "♻️  Arbre en $DECODED_VERSION ≠ $VERSION_NAME → désassemblage neuf"
    rm -rf "$DECODED"
fi
if [ ! -f "$DECODED/apktool.yml" ]; then
    echo "📦 apktool d…"
    java -jar "$APKTOOL" d -f -o "$DECODED" "$UPSTREAM_APK" >/dev/null
fi
echo "✅ Arbre apktool : $DECODED"

# ── 2b. Identité visuelle (assets de marque) ──
# Les assets sont versionnés : si la régénération échoue (Pillow ou polices
# absentes), le build continue sur la dernière version connue plutôt que de
# produire un APK avec l'identité d'avant.
if python patch/branding/make_brand.py emit >/dev/null 2>&1; then
    echo "🎨 Identité visuelle régénérée depuis patch/branding/make_brand.py"
else
    [ -d patch/branding/assets/res ] || {
        echo "❌ assets de marque absents et régénération impossible"
        echo "   (installer Pillow + numpy, puis : python patch/branding/make_brand.py emit)"
        exit 1
    }
    echo "⚠️  Régénération impossible — assets versionnés utilisés tels quels"
fi

# ── 3. Patchs ──
python patch/patch.py --decoded "$DECODED" \
    --version-code "$VERSION_CODE" --version-name "$VERSION_NAME" --apk-name "$APK_NAME"

# ── 4. Recompilation ──
echo "🔨 apktool b…"
rm -f "$BUILD_DIR/twouich_unsigned.apk"
java -jar "$APKTOOL" b -f -o "$BUILD_DIR/twouich_unsigned.apk" "$DECODED" 2>&1 | tail -5

# ── 5. Clé de signature ──
mkdir -p keys
if [ ! -f "$KEYSTORE" ]; then
    echo "🔑 Création de la clé Twouich (à sauvegarder !)…"
    keytool -genkeypair -v -keystore "$KEYSTORE" -alias "$KEY_ALIAS" \
        -keyalg RSA -keysize 2048 -validity 10000 \
        -storepass "$KEY_PASS" -keypass "$KEY_PASS" \
        -dname "CN=Twouich, OU=Twouich, O=Twouich, L=Paris, C=FR" >/dev/null
fi

# ── 6. Signature v1+v2+v3 (+ zipalign intégré) ──
echo "🔐 Alignement + signature…"
rm -f dist/*.apk dist/*.idsig
java -jar "$SIGNER" \
    --apks "$BUILD_DIR/twouich_unsigned.apk" \
    --ks "$KEYSTORE" --ksAlias "$KEY_ALIAS" \
    --ksPass "$KEY_PASS" --ksKeyPass "$KEY_PASS" \
    --out dist >/dev/null

# ── 7. Nommage + vérification ──
SIGNED="dist/twouich_unsigned-aligned-signed.apk"
[ -f "$SIGNED" ] || { echo "❌ APK signé introuvable ($SIGNED)"; exit 1; }
mv -f "$SIGNED" "dist/$APK_NAME"
rm -f dist/*.idsig

echo "🔎 Vérification de la signature…"
java -jar "$SIGNER" -y --verbose -a "dist/$APK_NAME" 2>&1 \
    | grep -Ei 'true|verified|does not verify|zip' | head -5 || true

echo "🧾 Empreinte du livrable :"
sha256sum "dist/$APK_NAME"
ls -l "dist/$APK_NAME"

cat <<EOF

═══════════════════════════════════════════════
  BUILD TERMINÉ → dist/$APK_NAME
═══════════════════════════════════════════════
Installation (désinstaller d'abord l'app officielle, signature différente) :
  adb uninstall com.s0und.s0undtv || true
  adb install -r dist/$APK_NAME
Suivre le blocage des pubs en direct :
  adb logcat | grep -i twouich
EOF
