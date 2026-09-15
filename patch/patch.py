#!/usr/bin/env python3
"""
patch.py — applique les modifications Twouich sur l'arbre apktool de S0undTV.

Source de vérité : ce script + patch/smali/. Il est idempotent (relancer ne
casse rien) et *échoue bruyamment* si un motif attendu a disparu, pour qu'un
changement en amont (nouvelle beta) ne passe jamais inaperçu.

Usage:
    python patch.py --decoded work/decoded [--version-code 145 --version-name v1.5.10x-twouich1]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import sys

# Console Windows (cp1252) : sans cela, les flèches/accents cassent le script.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

REPO = "Endymi0n74/Twouich"
UPSTREAM = "S0und/S0undTV"
DEFAULT_APK_NAME = "Twouich_beta144_ttv1.apk"

# ── Étape 1 : greffon anti-pub ────────────────────────────────────────────
GRAFT_DIR = "com/twouich/adblock"

# Méthode remplacée dans z3/u$b (Factory OkHttpDataSource d'ExoPlayer, Lz3/l$a).
# Chaque source de données HLS passe désormais par notre wrapper.
FACTORY_OLD = re.compile(
    r"\.method public bridge synthetic a\(\)Lz3/l;\r?\n.*?\r?\n\.end method",
    re.DOTALL,
)
FACTORY_NEW = """.method public bridge synthetic a()Lz3/l;
    .locals 2

    invoke-virtual {p0}, Lz3/u$b;->b()Lz3/u;

    move-result-object v0

    new-instance v1, Lcom/twouich/adblock/AdBlockDataSource;

    invoke-direct {v1, v0}, Lcom/twouich/adblock/AdBlockDataSource;-><init>(Lz3/l;)V

    return-object v1
.end method"""

# Self-test embarqué : exécuté une fois par démarrage, il rejoue des playlists
# publicitaires Twitch réelles dans le code compilé et publie son verdict sur
# logcat. C'est la seule preuve déterministe que le filtre agit vraiment : les
# quatre bugs qui ont cassé la lecture étaient invisibles pour les tests hors
# appareil et n'apparaissaient qu'à la lecture d'une vraie playlist.
SELFTEST_PATH = "smali/com/s0und/s0undtv/MainApp.smali"
APP_ONCREATE = re.compile(
    r"(?m)^([ \t]*invoke-super \{p0\}, Landroid/app/Application;->onCreate\(\)V\r?\n)"
)
SELFTEST_HOOK = (
    r"\1\n    invoke-static {}, Lcom/twouich/adblock/SelfTest;->run()V\n"
)

# Étape 3 : mise à jour automatique — tout doit pointer vers notre dépôt,
# plus jamais vers celui de S0und (sinon l'app tenterait de s'écraser elle-même).
URL_FILES = [
    "smali_classes2/com/s0und/s0undtv/helpers/UpdateHelper.smali",
    "smali_classes2/com/s0und/s0undtv/helpers/a.smali",
]
DEAD_UPDATE_URL = "https://share.s0und.cloudns.cl/app-release.apk"


# ── Étape 2 : identité visuelle ───────────────────────────────────────────
# L'arbre `patch/branding/assets/res/` est produit par make_brand.py et recopié
# tel quel : une seule source de vérité pour l'écran de démarrage, les icônes et
# la bannière. Tout le reste (nom affiché, thème, palette) est réécrit ici.
BRAND_DIR = "branding/assets"
BRAND_RES = "branding/assets/res"
BRAND_JSON = "branding/assets/brand.json"
BRAND_EMIT = "python patch/branding/make_brand.py emit"

# Le rouge de S0und : il ne doit plus subsister sur aucune surface d'identité
# (écran de démarrage, bannière, icônes, pages embarquées). Seule la palette des
# thèmes garde sa teinte rouge — c'est un choix d'utilisateur, pas la marque.
DEAD_RED = "a30f2c"
PALETTE_FILES = {"values/colors.xml", "values/public.xml"}
TEXT_SUFFIXES = {".xml", ".html", ".htm", ".js", ".css", ".json", ".txt"}

APP_NAME_OLD = '<string name="app_name">S0undTV</string>'
APP_NAME_NEW = '<string name="app_name">Twouich</string>'
APP_LABEL_OLD = 'android:label="Sound TV"'
APP_LABEL_NEW = 'android:label="Twouich"'

# Les activités déclarent un thème rouge dans le manifeste ; le thème retenu à
# l'exécution est choisi par la préférence (sombre par défaut). On aligne la
# déclaration sur le violet Twitch : plus aucun aplat rouge au lancement.
MANIFEST_THEMES = [
    ("@style/AppTheme_Red", "@style/AppTheme_Purple"),
    ("@style/LeanbackPreferencesRed", "@style/LeanbackPreferencesPurple"),
]
SPLASH_THEME = "SplashScreenThemeVector"

BRAND_PAGES = ["assets/S0undTV_about.html", "assets/S0undTV_changelog.html"]

ABOUT_OLD = """<body>
    <h1>Contact</h1>"""
ABOUT_NEW = """<body>
    <h1>Twouich</h1>
    <p class="spacing">
    <b>client: </b>an Android TV client for Twitch — unofficial build, based on S0undTV<br>
    <b>sources: </b>https://github.com/Endymi0n74/Twouich <br>
    </p>

    <hr>
    <h1>Contact</h1>"""

CHANGELOG_OLD = """    <hr>
    <h1>beta_144 (2025.12.28)</h1>"""
CHANGELOG_NEW = """    <hr>
    <h1>Twouich v1.5.10x-twouich1 (2026.09.15)</h1>
    <p class="spacing">build du dépôt https://github.com/Endymi0n74/Twouich</p>

    <h3>Identité</h3>
    <ul>
        <li>écran de démarrage, icônes de lancement et bannière TV aux couleurs Twouich</li>
        <li>nom affiché : <b>Twouich</b> — le paquet reste <code>com.s0und.s0undtv</code>, ce qui permet de mettre l'app à jour sans la réinstaller</li>
        <li>thème par défaut violet Twitch au lieu du rouge S0und</li>
    </ul>

    <h3>Anti-publicité</h3>
    <ul>
        <li>les plages publicitaires Twitch (SSAI : <code>stitched-ad</code>, blocs <code>CUE-OUT</code>/<code>CUE-IN</code>) sont retirées de la playlist avant le lecteur</li>
        <li>un self-test rejoue des playlists publicitaires réelles à chaque démarrage et publie son verdict dans logcat (tag <code>Twouich</code>)</li>
    </ul>

    <h3>Mise à jour</h3>
    <ul>
        <li>l'updater pointe vers les releases de ce dépôt, plus vers celui de S0und</li>
    </ul>

    <hr>

    <h1>beta_144 (2025.12.28)</h1>"""


def log(msg: str) -> None:
    print(f"  {msg}")


def fail(msg: str) -> None:
    print(f"\n❌ {msg}", file=sys.stderr)
    sys.exit(1)


def replace_once(path: pathlib.Path, old: str, new: str, what: str) -> bool:
    """Remplace un motif unique, en respectant la convention de fin de ligne du
    fichier : l'arbre apktool est en CRLF (les pages HTML aussi) alors que les
    motifs de ce script sont écrits en LF."""
    text = path.read_text(encoding="utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"
    if nl != "\n":
        old = old.replace("\n", nl)
        new = new.replace("\n", nl)
    if new in text and old not in text:
        log(f"déjà appliqué : {what}")
        return False
    if old not in text:
        fail(f"motif introuvable ({what}) dans {path} — la cible a changé, adapter patch.py")
    path.write_text(text.replace(old, new), encoding="utf-8")
    log(f"appliqué : {what}")
    return True


def install_graft(decoded: pathlib.Path, here: pathlib.Path) -> None:
    print("[1/5] Greffon anti-pub (AdBlockDataSource + PlaylistSanitizer + self-test)")
    src = here / "smali" / GRAFT_DIR
    dst = decoded / "smali_classes2" / GRAFT_DIR
    if not src.is_dir():
        fail(f"greffon absent : {src}")
    dst.mkdir(parents=True, exist_ok=True)
    for f in sorted(src.glob("*.smali")):
        shutil.copy2(f, dst / f.name)
        log(f"copié : {f.name}")

    factory = decoded / "smali" / "z3.1" / "u$b.smali"
    if not factory.is_file():
        fail(f"factory ExoPlayer introuvable : {factory}")
    text = factory.read_text(encoding="utf-8")
    if "AdBlockDataSource" in text:
        log("injection déjà présente dans z3/u$b.a()")
        return
    new_text, count = FACTORY_OLD.subn(FACTORY_NEW, text)
    if count != 1:
        fail(f"méthode z3/u$b.a() attendue 1 fois, trouvée {count} fois")
    factory.write_text(new_text, encoding="utf-8")
    log("injecté : z3/u$b.a() renvoie AdBlockDataSource")


def install_selftest(decoded: pathlib.Path) -> None:
    """Branche le self-test sur le démarrage de l'application (une fois par
    processus). Le point d'ancrage est MainApp.onCreate : il existe dans toutes
    les betas, s'exécute avant toute activité et n'exige aucun écran dédié."""
    path = decoded / SELFTEST_PATH
    if not path.is_file():
        fail(f"classe Application introuvable : {SELFTEST_PATH}")
    text = path.read_text(encoding="utf-8")
    if "Lcom/twouich/adblock/SelfTest;" in text:
        log("injection déjà présente dans MainApp.onCreate()")
        return
    new_text, count = APP_ONCREATE.subn(SELFTEST_HOOK, text)
    if count != 1:
        fail(
            "méthode MainApp.onCreate() attendue 1 fois, "
            f"trouvée {count} fois — la cible a changé, adapter patch.py"
        )
    path.write_text(new_text, encoding="utf-8")
    log("injecté : MainApp.onCreate() exécute SelfTest.run()")


def replace_in_style(path: pathlib.Path, style: str, old: str, new: str, what: str) -> bool:
    """Remplace un attribut *dans un seul bloc <style name="style">*.

    Le même couple clé/valeur existe dans une dizaine de thèmes : réécrire le
    fichier entier changerait aussi les thèmes que l'utilisateur peut choisir.
    """
    text = path.read_text(encoding="utf-8")
    match = re.search(
        rf'(<style name="{re.escape(style)}"[^>]*>)(.*?)(</style>)', text, re.DOTALL
    )
    if match is None:
        fail(f"style introuvable : {style} dans {path.name}")
    body = match.group(2)
    if new in body and old not in body:
        log(f"déjà appliqué : {what}")
        return False
    if old not in body:
        fail(f"motif introuvable ({what}) dans {path.name} → style {style}")
    path.write_text(text[: match.start(2)] + body.replace(old, new) + text[match.end(2) :],
                    encoding="utf-8")
    log(f"appliqué : {what}")
    return True


def install_branding(decoded: pathlib.Path, here: pathlib.Path) -> dict[str, str]:
    print("[2/5] Identité Twouich (écran de démarrage, icônes, bannière, nom)")
    res = here / BRAND_RES
    if not (here / BRAND_JSON).is_file() or not res.is_dir():
        fail(f"assets de marque absents ({here / BRAND_DIR}) — lancer : {BRAND_EMIT}")
    brand = json.loads((here / BRAND_JSON).read_text(encoding="utf-8"))

    # 1. L'arborescence res/ du générateur est recopiée telle quelle : splash,
    #    bannière et icônes de lancement (mêmes noms de fichiers que l'original,
    #    donc aucun renommage de ressource à propager ailleurs).
    copied = 0
    for src in sorted(res.rglob("*")):
        if src.is_file():
            dst = decoded / "res" / src.relative_to(res)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
    log(f"{copied} assets copiés dans res/ — piste {brand['variant']} « {brand['label']} »")

    # 2. Nom affiché : launcher, réglages, notification.
    strings = decoded / "res" / "values" / "strings.xml"
    replace_once(strings, APP_NAME_OLD, APP_NAME_NEW, "nom de l'application (app_name)")
    replace_once(
        strings,
        "section -> S0undTV. Notifications should be turned ON.",
        "section -> Twouich. Notifications should be turned ON.",
        "nom dans le résumé de la notification de test",
    )
    manifest = decoded / "AndroidManifest.xml"
    replace_once(manifest, APP_LABEL_OLD, APP_LABEL_NEW, "libellé de l'application (manifeste)")

    # 3. Plus aucun thème rouge déclaré, et le splash n'emprunte plus le rouge
    #    au thème rouge : la couleur d'accent passe au violet Twitch.
    for old, new in MANIFEST_THEMES:
        replace_once(manifest, old, new, f"manifeste : {old} → {new}")
    replace_in_style(
        decoded / "res" / "values" / "styles.xml",
        SPLASH_THEME,
        "<item name=\"android:colorPrimary\">@color/theme_red</item>",
        "<item name=\"android:colorPrimary\">@color/theme_purple</item>",
        "splash : couleur d'accent rouge → violet Twitch",
    )

    # 4. Palette : l'icône adaptative prenait le rouge de S0und en fond, le thème
    #    « violet » de l'app était le violet Twitch d'avant (#6441a4).
    colors = decoded / "res" / "values" / "colors.xml"
    replace_once(
        colors,
        '<color name="ic_launcher_background">#a30f2c</color>',
        f'<color name="ic_launcher_background">{brand["brand"]}</color>',
        "fond de l'icône adaptative",
    )
    replace_once(colors, '<color name="theme_purple">#6441a4</color>',
                 f'<color name="theme_purple">{brand["brand"]}</color>',
                 "thème violet : teinte Twitch actuelle")
    replace_once(colors, '<color name="theme_purple_bright">#8658db</color>',
                 '<color name="theme_purple_bright">#a970ff</color>',
                 "thème violet : accent clair")

    # 5. Pages embarquées (À propos / Nouveautés) : fond rouge → fond sombre, et
    #    l'en-tête dit ce qu'est ce build.
    about = decoded / "assets" / "S0undTV_about.html"
    replace_once(about, ABOUT_OLD, ABOUT_NEW, "page À propos : en-tête Twouich")
    replace_once(about, "background-color: #a30f2d00;", "background-color: #0e0e10;",
                 "page À propos : fond")
    changelog = decoded / "assets" / "S0undTV_changelog.html"
    replace_once(changelog, CHANGELOG_OLD, CHANGELOG_NEW, "page Nouveautés : entrée Twouich")
    replace_once(changelog, "background-color: #a30f2d;", "background-color: #0e0e10;",
                 "page Nouveautés : fond rouge → sombre")
    return brand


def repoint_updater(decoded: pathlib.Path, apk_name: str) -> None:
    print("[3/5] Mise à jour automatique → dépôt Twouich")
    for rel in URL_FILES:
        path = decoded / rel
        if not path.is_file():
            fail(f"fichier attendu absent : {rel}")
        # Couvre github.com/<repo> ET raw.githubusercontent.com/<repo>
        replace_once(
            path,
            UPSTREAM,
            REPO,
            f"{path.name} : URLs de release",
        )

    service = decoded / "smali_classes2/com/s0und/s0undtv/service/AutoUpdateService.smali"
    if service.is_file():
        replace_once(
            service,
            DEAD_UPDATE_URL,
            f"https://github.com/{REPO}/releases/latest/download/{apk_name}",
            "AutoUpdateService : endpoint cloudns mort",
        )


def check_brand_assets(decoded: pathlib.Path, here: pathlib.Path) -> int:
    """Vérifie que chaque asset émis par le générateur est bien posé dans l'APK,
    octet pour octet. Un APK dont l'écran de démarrage n'a pas été remplacé est le
    pire des cas : il s'installe, démarre, et affiche encore la marque d'avant."""
    res = here / BRAND_RES
    checked = 0
    for src in sorted(res.rglob("*")):
        if not src.is_file():
            continue
        dst = decoded / "res" / src.relative_to(res)
        if not dst.is_file() or dst.stat().st_size != src.stat().st_size:
            fail(f"asset de marque absent ou différent : {dst.relative_to(decoded)}")
        checked += 1
    if checked == 0:
        fail("aucun asset de marque dans l'arbre décodé")
    return checked


def scan_dead_red(decoded: pathlib.Path) -> list[str]:
    """Fichiers d'identité portant encore le rouge de S0und (#a30f2c).

    La palette (`values/colors.xml`, `values/public.xml`) est exclue : le rouge y
    reste un thème que l'utilisateur peut choisir, ce n'est pas la marque.
    """
    found: list[str] = []
    for root in (decoded / "res", decoded / "assets"):
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            rel = path.relative_to(decoded).as_posix()
            if rel.removeprefix("res/") in PALETTE_FILES:
                continue
            if DEAD_RED in path.read_text(encoding="utf-8", errors="ignore").lower():
                found.append(rel)
    return found


def set_manifest_version(decoded: pathlib.Path, code: int, name: str) -> None:
    """apktool 3 sort versionCode/versionName du manifest vers apktool.yml et ne
    les réinjecte pas au build : on les réécrit donc explicitement dans le manifest,
    sinon l'APK produit n'a plus aucune version (installation refusée)."""
    manifest = decoded / "AndroidManifest.xml"
    text = manifest.read_text(encoding="utf-8")
    attrs = f'android:versionCode="{code}" android:versionName="{name}"'
    if attrs in text:
        log("déjà appliqué (manifest)")
        return
    # manifeste déjà porteur d'attributs de version : on les remplace
    new = re.sub(
        r'(\s)android:versionCode="[^"]*"',
        rf'\g<1>android:versionCode="{code}"',
        text,
        count=1,
    )
    new = re.sub(
        r'(\s)android:versionName="[^"]*"',
        rf'\g<1>android:versionName="{name}"',
        new,
        count=1,
    )
    if "android:versionCode" not in new:
        m = re.search(r'(package="[^"]*")', new)
        if not m:
            fail("élément <manifest package=…> introuvable")
        new = new[: m.end()] + " " + attrs + new[m.end() :]
    manifest.write_text(new, encoding="utf-8")
    log(f"manifest : versionCode={code} versionName={name}")


def bump_version(decoded: pathlib.Path, code: int, name: str) -> None:
    print(f"[4/5] Version → {name} (versionCode {code})")
    set_manifest_version(decoded, code, name)
    yml = decoded / "apktool.yml"
    text = yml.read_text(encoding="utf-8")
    if f"versionCode: {code}" in text and f"versionName: {name}" in text:
        log("déjà appliqué")
        return
    new = re.sub(r"(?m)^(\s*versionCode: )[^\r\n]*", rf"\g<1>{code}", text, count=1)
    new = re.sub(r"(?m)^(\s*versionName: )[^\r\n]*", rf"\g<1>{name}", new, count=1)
    if new == text:
        fail("versionInfo introuvable dans apktool.yml")
    yml.write_text(new, encoding="utf-8")
    log(f"versionCode={code} versionName={name}")


def main() -> int:
    here = pathlib.Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--decoded", required=True, type=pathlib.Path)
    parser.add_argument("--version-code", type=int, default=145)
    parser.add_argument("--version-name", default="v1.5.10x-twouich1")
    parser.add_argument("--apk-name", default=DEFAULT_APK_NAME)
    args = parser.parse_args()

    decoded: pathlib.Path = args.decoded.resolve()
    if not (decoded / "apktool.yml").is_file():
        fail(f"arbre apktool invalide : {decoded}")

    install_graft(decoded, here)
    brand = install_branding(decoded, here)
    install_selftest(decoded)
    repoint_updater(decoded, args.apk_name)
    bump_version(decoded, args.version_code, args.version_name)

    print("[5/5] Contrôles")
    checks = 0
    for rel, needle in [
        ("smali/z3.1/u$b.smali", "AdBlockDataSource"),
        ("smali_classes2/com/twouich/adblock/AdBlockDataSource.smali", "PROXY_HOST"),
        ("smali_classes2/com/twouich/adblock/PlaylistSanitizer.smali", "stitched-ad"),
        ("smali_classes2/com/twouich/adblock/SelfTest.smali", "SELFTEST"),
        ("smali_classes2/com/twouich/adblock/SelfTest$Fake.smali", "Lz3/l;"),
        (SELFTEST_PATH, "SelfTest;->run()V"),
        ("smali_classes2/com/s0und/s0undtv/helpers/UpdateHelper.smali", f"raw.githubusercontent.com/{REPO}"),
        ("smali_classes2/com/s0und/s0undtv/helpers/a.smali", f"github.com/{REPO}/releases/download/"),
        ("res/values/strings.xml", APP_NAME_NEW),
        ("AndroidManifest.xml", APP_LABEL_NEW),
        ("res/drawable/s0undtv_logo_with_text_2.xml", "@drawable/twouich_splash"),
        ("res/values/colors.xml", f'<color name="ic_launcher_background">{brand["brand"]}</color>'),
        ("assets/S0undTV_about.html", "Twouich"),
        ("assets/S0undTV_changelog.html", "Twouich"),
    ]:
        path = decoded / rel
        if not path.is_file() or needle not in path.read_text(encoding="utf-8"):
            fail(f"contrôle échoué : {needle!r} absent de {rel}")
        checks += 1
    assets = check_brand_assets(decoded, here)
    checks += assets
    logos = scan_dead_red(decoded)
    if logos:
        fail("le rouge de S0und subsiste sur : " + ", ".join(logos))
    checks += 1
    log(f"{checks} contrôles OK ({assets} assets de marque + 1 balayage du rouge)")
    print("\n✅ patch.py terminé")
    return 0


if __name__ == "__main__":
    sys.exit(main())
