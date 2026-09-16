#!/usr/bin/env python3
"""
patch.py — applique les modifications Twouich sur l'arbre apktool de S0undTV.

Source de vérité : ce script + patch/smali/. Il est idempotent (relancer ne
casse rien) et *échoue bruyamment* si un motif attendu a disparu, pour qu'un
changement en amont (nouvelle beta) ne passe jamais inaperçu.

Usage:
    python patch.py --decoded work/decoded [--version-code 148 --version-name v1.0.1]
"""
from __future__ import annotations

import argparse
import datetime
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
DEFAULT_APK_NAME = "Twouich_v1.0.3.apk"

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

# The upstream updater compared releases to a hard-coded 144, so it repeatedly
# offered the already-installed build. Read the installed package version instead.
UPDATE_VERSION_CALL = "    invoke-direct {p0}, Lcom/s0und/s0undtv/helpers/a;->i()I\n\n    move-result v1"
UPDATE_VERSION_METHOD = """.method private i()I
    .locals 3

    :try_start_0
    iget-object v0, p0, Lcom/s0und/s0undtv/helpers/UpdateHelper;->a:Ljava/lang/ref/WeakReference;
    invoke-virtual {v0}, Ljava/lang/ref/Reference;->get()Ljava/lang/Object;
    move-result-object v0
    check-cast v0, Landroid/content/Context;
    invoke-virtual {v0}, Landroid/content/Context;->getPackageManager()Landroid/content/pm/PackageManager;
    move-result-object v1
    invoke-virtual {v0}, Landroid/content/Context;->getPackageName()Ljava/lang/String;
    move-result-object v2
    const/4 v0, 0x0
    invoke-virtual {v1, v2, v0}, Landroid/content/pm/PackageManager;->getPackageInfo(Ljava/lang/String;I)Landroid/content/pm/PackageInfo;
    move-result-object v0
    iget v0, v0, Landroid/content/pm/PackageInfo;->versionCode:I
    return v0
    :try_end_0
    .catch Ljava/lang/Exception; {:try_start_0 .. :try_end_0} :catch_0

    :catch_0
    move-exception v0
    const/4 v0, -0x1
    return v0
.end method

"""

# Étape 3b : le socle upstream est un build beta — le flag gravé
# Lcom/s0und/s0undtv/b;->a:Z = true fait écrire pref_update_channel = "1"
# (Beta) au premier lancement de TOUTE installation neuve (MainApp.p()).
# Or, sur le canal Beta, l'updater n'accepte que des entrées ReleaseType: 1 :
# une update.json ne publiant qu'une entrée stable n'y produit AUCUN dialogue,
# sans erreur nulle part. Forcer le flag à false rend le canal stable par
# défaut : g() lit "0" quand la préférence est absente, ce qui est exactement
# ce que nous publions.
BETA_FLAG_PATH = "smali/com/s0und/s0undtv/b.smali"
BETA_FLAG_OLD = ".field public static final a:Z = true"
BETA_FLAG_NEW = ".field public static final a:Z = false"


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
    <b>client: </b>an Android TV client for Twitch<br>
    <b>sources: </b><a href="https://github.com/Endymi0n74/Twouich">Twouich project</a><br>
    <b>based on: </b><a href="https://github.com/S0und/S0undTV">the original project</a><br>
    <b>credits: </b>thanks to the original authors and contributors. This build redistributes only patched binaries and the patches themselves.<br>
    </p>

    <hr>
    <h1>Contact</h1>"""

CHANGELOG_OLD = """    <hr>
    <h1>beta_144 (2025.12.28)</h1>"""
# Le titre porte la version réellement construite (passée par build.sh) : la page
# « Nouveautés » de l'app cite donc la release d'où vient le build, pas celle d'avant.
CHANGELOG_NEW = """    <hr>
    <h1>Twouich {version} ({date})</h1>
    <p class="spacing"><a href="https://github.com/Endymi0n74/Twouich">Twouich</a> — un client Android TV pour Twitch.</p>

    <h3>Ce qui change</h3>
    <ul>
        <li>Blocage des publicités SSAI dans les playlists Twitch avant lecture.</li>
        <li>Nouvelle identité Twouich : splash, icônes, bannière TV, thème violet et interface revue.</li>
        <li>Accent par défaut recoloré aux couleurs Twouich : plus de rouge d'origine dans l'interface.</li>
        <li>Mise à jour automatique depuis les releases Twouich.</li>
    </ul>

    <h3>Source et remerciements</h3>
    <ul>
        <li>Projet d'origine : <a href="https://github.com/S0und/S0undTV">S0undTV</a>.</li>
        <li>Merci à ses auteurs et contributeurs pour le travail initial.</li>
        <li>Ce projet redistribue uniquement des binaires patchés et les patchs associés.</li>
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


def find_factory(decoded: pathlib.Path) -> pathlib.Path:
    """Localise la fabrique de sources de données (Lz3/u$b) dans l'arbre décodé.

    apktool place les classes du dex secondaire sous `smali_classes2/`, et le
    nommage `z3.1`/`z3` varie selon la plateforme/le nombre de dex : le chemin
    n'est pas supposé, il est localisé — et l'absence reste une erreur bruyante
    (c'est la détection de rupture, pas une tolérance).
    """
    candidates = [
        decoded / "smali" / "z3.1" / "u$b.smali",  # décoder Windows
        decoded / "smali" / "z3" / "u$b.smali",    # décodages Linux/CI
        decoded / "smali_classes2" / "z3" / "u$b.smali",
    ]
    for c in candidates:
        if c.is_file():
            return c
    fail("factory ExoPlayer introuvable (z3/u$b.smali) — socle upstream changé ?")


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

    factory = find_factory(decoded)
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


def install_branding(decoded: pathlib.Path, here: pathlib.Path, version_name: str) -> dict[str, str]:
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

    # 4b. L'accent d'usine est l'index 0 (« Red (default) », prefs_accent_color =
    #     "0") : c'est lui que les installations — neuves comme existantes —
    #     affichent, et c'est le rouge visible sur les cartes focalisées. Plutôt
    #     que de déplacer l'index par défaut (fragile côté smali, et muet pour
    #     les installations existantes qui gardent la valeur sauvegardée), on
    #     recolore la famille theme_red* avec la palette de marque : l'accent
    #     « par défaut » est visuellement Twouich, et le rouge de S0und sort des
    #     couleurs sélectionnables.
    replace_once(
        colors,
        '<color name="theme_red">#a30f2c</color>',
        f'<color name="theme_red">{brand["brand"]}</color>',
        "accent par défaut : theme_red → couleur de marque",
    )
    replace_once(
        colors,
        '<color name="theme_red_bright">#db002c</color>',
        '<color name="theme_red_bright">#a970ff</color>',
        "accent par défaut : theme_red_bright → accent clair",
    )
    replace_once(
        colors,
        '<color name="theme_red_dark">#4d000f</color>',
        f'<color name="theme_red_dark">{brand["brand_dark"]}</color>',
        "accent par défaut : theme_red_dark → fond sombre de marque",
    )
    replace_once(
        colors,
        '<color name="theme_red_main_background">#1f0006</color>',
        '<color name="theme_red_main_background">#130c1f</color>',
        "accent par défaut : theme_red_main_background → fond principal de marque",
    )
    replace_once(
        decoded / "res" / "values" / "arrays.xml",
        "<item>Red (default)</item>",
        "<item>Twouich</item>",
        "réglages : libellé de l'accent par défaut",
    )

    # 5. Pages embarquées (À propos / Nouveautés) : fond rouge → fond sombre, et
    #    l'en-tête dit ce qu'est ce build.
    about = decoded / "assets" / "S0undTV_about.html"
    replace_once(about, ABOUT_OLD, ABOUT_NEW, "page À propos : en-tête Twouich")
    replace_once(about, "background-color: #a30f2d00;", "background-color: #0e0e10;",
                 "page À propos : fond")
    # L'ancien contact block contenait le Discord et le test beta. Les crédits
    # ci-dessus remplacent cette section : ne laissez pas une page de compatibilité
    # technique devenir une surface de marque ou de support historique.
    about_text = about.read_text(encoding="utf-8")
    about_text = re.sub(r"(?m)^\s*<b>discord:.*?\n", "", about_text)
    about_text = re.sub(r"(?m)^\s*<b>beta:.*?\n", "", about_text)
    about.write_text(about_text, encoding="utf-8")

    changelog = decoded / "assets" / "S0undTV_changelog.html"
    changelog_new = CHANGELOG_NEW.format(
        version=version_name, date=datetime.date.today().strftime("%Y.%m.%d")
    )
    if f"<h1>Twouich {version_name}" in changelog.read_text(encoding="utf-8"):
        log("déjà appliqué : page Nouveautés : entrée Twouich")
    else:
        replace_once(
            changelog,
            CHANGELOG_OLD,
            changelog_new,
            "page Nouveautés : entrée Twouich",
        )
    replace_once(changelog, "background-color: #a30f2d;", "background-color: #0e0e10;",
                 "page Nouveautés : fond rouge → sombre")
    # Repartir de zéro signifie réellement supprimer l'historique HTML hérité :
    # le changelog ne garde que l'entrée Twouich courante et le lien de crédits
    # vers le projet source.
    changelog_text = changelog.read_text(encoding="utf-8")
    historical = re.search(r"\n\s*<h1>beta_144\b", changelog_text)
    if historical:
        changelog_text = changelog_text[:historical.start()] + "\n</body>\n</html>\n"
    # No inherited support channel or historical invitation survives in the new
    # page; credits point only to the source project above.
    changelog_text = re.sub(r"(?im)^.*(?:discord|discord channel|zmNjK2S).*$\n?", "", changelog_text)
    changelog.write_text(changelog_text, encoding="utf-8")
    return brand


def patch_update_version_comparison(decoded: pathlib.Path) -> None:
    path = decoded / "smali_classes2/com/s0und/s0undtv/helpers/a.smali"
    text = path.read_text(encoding="utf-8")
    old = "    const/16 v1, 0x90"
    if UPDATE_VERSION_CALL in text:
        log("déjà appliqué : comparaison avec la version installée")
        return
    if old not in text:
        fail("comparaison de version figée introuvable dans helpers/a.smali")
    text = text.replace(old, UPDATE_VERSION_CALL, 1)
    marker = ".method b()V\n"
    if marker not in text:
        fail("point d'insertion de la méthode de version introuvable")
    text = text.replace(marker, UPDATE_VERSION_METHOD + marker, 1)
    path.write_text(text, encoding="utf-8")
    log("corrigé : l'updater compare désormais la version installée")


def force_stable_channel(decoded: pathlib.Path) -> None:
    """Étape 3b — Toute installation neuve démarre en canal Beta.

    Cause racine (mesurée sur appareil le 16/09) : le socle upstream est un
    build beta, flag gravé `b.a = true`, et MainApp.p() en déduit
    pref_update_channel = "1" au premier lancement. Or le canal Beta ne voit
    que des entrées ReleaseType: 1 — notre publication stable y est muette.
    Remettre le flag à false supprime l'impasse pour les nouveaux utilisateurs
    (les installations existantes gardent leur préférence, c'est voulu).
    """
    path = decoded / BETA_FLAG_PATH
    if not path.is_file():
        fail(f"fichier attendu absent : {BETA_FLAG_PATH}")
    text = path.read_text(encoding="utf-8")
    if BETA_FLAG_NEW in text:
        log("déjà appliqué : flag beta désactivé (canal stable par défaut)")
        return
    if BETA_FLAG_OLD not in text:
        fail(f"champ beta introuvable dans {BETA_FLAG_PATH} (attendu : {BETA_FLAG_OLD!r})")
    path.write_text(text.replace(BETA_FLAG_OLD, BETA_FLAG_NEW, 1), encoding="utf-8")
    log("corrigé : le flag beta gravé est désactivé (canal stable par défaut)")


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

    patch_update_version_comparison(decoded)
    force_stable_channel(decoded)

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

    La palette (`values/colors.xml`, `values/public.xml`) est exclue : la famille
    `theme_red*` y est recolorée par ailleurs (elle porte l'accent par défaut),
    et les identifiants de ressources ne sont pas des chaînes affichées.
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
    parser.add_argument("--version-code", type=int, default=150)
    parser.add_argument("--version-name", default="v1.0.3")
    parser.add_argument("--apk-name", default=DEFAULT_APK_NAME)
    args = parser.parse_args()

    decoded: pathlib.Path = args.decoded.resolve()
    if not (decoded / "apktool.yml").is_file():
        fail(f"arbre apktool invalide : {decoded}")

    install_graft(decoded, here)
    brand = install_branding(decoded, here, args.version_name)
    install_selftest(decoded)
    repoint_updater(decoded, args.apk_name)
    bump_version(decoded, args.version_code, args.version_name)

    print("[5/5] Contrôles")
    checks = 0
    for rel_or_marker, needle in [
        (None, "AdBlockDataSource"),  # fabrique : chemin variable (voir find_factory)
        ("smali_classes2/com/twouich/adblock/AdBlockDataSource.smali", "PROXY_HOST"),
        ("smali_classes2/com/twouich/adblock/PlaylistSanitizer.smali", "stitched-ad"),
        ("smali_classes2/com/twouich/adblock/SelfTest.smali", "SELFTEST"),
        ("smali_classes2/com/twouich/adblock/SelfTest$Fake.smali", "Lz3/l;"),
        (SELFTEST_PATH, "SelfTest;->run()V"),
        ("smali_classes2/com/s0und/s0undtv/helpers/UpdateHelper.smali", f"raw.githubusercontent.com/{REPO}"),
        ("smali_classes2/com/s0und/s0undtv/helpers/a.smali", f"github.com/{REPO}/releases/download/"),
        ("smali_classes2/com/s0und/s0undtv/helpers/a.smali", "PackageManager;->getPackageInfo"),
        (BETA_FLAG_PATH, BETA_FLAG_NEW),
        ("res/values/strings.xml", APP_NAME_NEW),
        ("AndroidManifest.xml", APP_LABEL_NEW),
        ("res/drawable/s0undtv_logo_with_text_2.xml", "@drawable/twouich_splash"),
        ("res/values/colors.xml", f'<color name="ic_launcher_background">{brand["brand"]}</color>'),
        ("res/values/colors.xml", f'<color name="theme_red">{brand["brand"]}</color>'),
        ("res/values/arrays.xml", "<item>Twouich</item>"),
        ("assets/S0undTV_about.html", "Twouich"),
        ("assets/S0undTV_changelog.html", "Twouich"),
    ]:
        if rel_or_marker is None:
            path = find_factory(decoded)
        else:
            path = decoded / rel_or_marker
        if not path.is_file() or needle not in path.read_text(encoding="utf-8"):
            fail(f"contrôle échoué : {needle!r} absent de {path.relative_to(decoded)}")
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
