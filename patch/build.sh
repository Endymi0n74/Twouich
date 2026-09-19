#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# build.sh — Twouich : APK Android TV Twitch + anti-pub
# ═══════════════════════════════════════════════════════════════════════
# Usage :  cd /d/Codex/Twouich && bash patch/build.sh
#
# Chaîne : APK upstream → apktool d → patch.py → apktool b → signature
#          v1+v2+v3 → vérification → dist/Twouich_v1.0.1.apk
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

# Mode CI : SKIP_SIGNING=1 rejoue la chaîne jusqu'à l'APK NON signé.
# L'objectif est la détection de rupture (patch.py échoue bruitamment si un motif
# upstream a changé, apktool b si le smali ne compile plus), pas la production
# d'un livrable : aucune clé de signature n'est nécessaire, et la CI ne doit
# JAMAIS en obtenir une — c'est ce qui garantit que seul le mainteneur produit
# des mises à jour installables par-dessus Twouich.
SKIP_SIGNING="${SKIP_SIGNING:-0}"

KEYSTORE="keys/twouich.keystore"
KEY_ALIAS="${KEY_ALIAS:-twouich-dev}"
# Le mot de passe du keystore n'est PAS écrit ici : ce dépôt est public, et une
# clé de signature dont le mot de passe est public permet à n'importe qui de
# signer un APK qu'Android acceptera comme une mise à jour de Twouich. Il vient
# de l'environnement (`KEY_PASS=…` — mode CI), sinon de `keys/keystore.properties`
# (ignoré par git, machine du mainteneur).
KEY_PASS="${KEY_PASS:-}"
KEY_PROPS="keys/keystore.properties"
if [ -z "$KEY_PASS" ] && [ -f "$KEY_PROPS" ]; then
    _alias="$(sed -n 's/^keyAlias=//p' "$KEY_PROPS" | head -1)"
    [ -n "$_alias" ] && KEY_ALIAS="$_alias"
    KEY_PASS="$(sed -n 's/^storePassword=//p' "$KEY_PROPS" | head -1)"
fi
if [ "$SKIP_SIGNING" != "1" ] && [ -z "$KEY_PASS" ]; then
    echo "❌ mot de passe du keystore introuvable."
    echo "   Ce script n'en contient aucun (dépôt public). Créer $KEY_PROPS :"
    echo "     keyAlias=$KEY_ALIAS"
    echo "     storePassword=<le mot de passe de la clé>"
    echo "   ou lancer : KEY_PASS=… bash patch/build.sh"
    exit 1
fi

VERSION_CODE=155
VERSION_NAME="v1.0.8"
APK_NAME="Twouich_v1.0.8.apk"
# Date AFFICHÉE dans la page « Nouveautés » embarquée — constante figée par
# version, jamais la date du jour : sinon chaque rebuild change les octets du
# livrable (build reproductible). À faire évoluer au prochain bump de version.
VERSION_RELEASE_DATE="2026.09.19"

echo "═══════════════════════════════════════════════"
echo "  Twouich — build $VERSION_NAME ($VERSION_CODE)"
echo "═══════════════════════════════════════════════"

# ── 0. Outils ──
if [ "$SKIP_SIGNING" = "1" ]; then
    # Mode CI : apktool seul suffit (pas de signature).
    [ -f "$APKTOOL" ] || { echo "❌ outil manquant : $APKTOOL"; exit 1; }
else
    for tool in "$APKTOOL" "$SIGNER"; do
        [ -f "$tool" ] || { echo "❌ outil manquant : $tool"; exit 1; }
    done
fi
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
# Sonde robuste à `pipefail` (GitHub Actions lance bash avec -o pipefail) : le
# fichier peut être absent (premier build), et sed sortirait alors en erreur.
DECODED_VERSION=""
if [ -f "$DECODED/apktool.yml" ]; then
    DECODED_VERSION="$(sed -n 's/^ *versionName: //p' "$DECODED/apktool.yml" | head -1)" || DECODED_VERSION=""
fi
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
    --version-code "$VERSION_CODE" --version-name "$VERSION_NAME" --apk-name "$APK_NAME" \
    --release-date "$VERSION_RELEASE_DATE"

# ── 4. Recompilation ──
echo "🔨 apktool b…"
rm -f "$BUILD_DIR/twouich_unsigned.apk"
java -jar "$APKTOOL" b -f -o "$BUILD_DIR/twouich_unsigned.apk" "$DECODED" 2>&1 | tail -5

# ── 4b. Canonisation ZIP : horodatage constant + ordre des entrées ──
# apktool estampille chaque entrée à l'heure du build et ordonne les entrées
# selon l'énumération du système de fichiers (Windows ≠ Linux) : réécrire
# l'horodatage vers 1980-01-01 et retrier les entrées par nom
# (patch/normalize_apk.py, réécriture au niveau octet) rend le build
# reproductible sur toute plateforme. Doit rester AVANT la signature : les
# blocs v2/v3 couvrent le central directory. Idempotent.
python patch/normalize_apk.py "$BUILD_DIR/twouich_unsigned.apk"
if python patch/normalize_apk.py --check "$BUILD_DIR/twouich_unsigned.apk" >/dev/null; then
    echo "✅ Build reproductible : ZIP canonique (horodatage + ordre)"
else
    echo "❌ ZIP non canonique — build non reproductible"
    exit 1
fi

# ── 5. Clé de signature (sautée en mode CI) ──
if [ "$SKIP_SIGNING" = "1" ]; then
    echo "⏭️  Mode CI : signature sautée (APK non signé, détection de rupture uniquement)"
fi
mkdir -p keys
if [ "$SKIP_SIGNING" != "1" ] && [ ! -f "$KEYSTORE" ]; then
    echo "🔑 Création de la clé Twouich (à sauvegarder !)…"
    keytool -genkeypair -v -keystore "$KEYSTORE" -alias "$KEY_ALIAS" \
        -keyalg RSA -keysize 2048 -validity 10000 \
        -storepass "$KEY_PASS" -keypass "$KEY_PASS" \
        -dname "CN=Twouich, OU=Twouich, O=Twouich, L=Paris, C=FR" >/dev/null
fi

# ── 6. Signature v1+v2+v3 (+ zipalign intégré) — sautée en mode CI ──
if [ "$SKIP_SIGNING" = "1" ]; then
    echo "🧾 APK non signé :"
    sha256sum "$BUILD_DIR/twouich_unsigned.apk"
    ls -l "$BUILD_DIR/twouich_unsigned.apk"
    cat <<EOF

═══════════════════════════════════════════════
  BUILD CI TERMINÉ (sans signature) → $BUILD_DIR/twouich_unsigned.apk
═══════════════════════════════════════════════
EOF
    exit 0
fi
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
