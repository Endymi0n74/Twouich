#!/usr/bin/env python3
"""
test_brand.py — garde-fou sur l'identité visuelle Twouich.

Pourquoi ce test existe
-----------------------
L'APK embarque la marque à deux endroits qu'on ne voit pas dans le code : des
images (écran de démarrage, icônes, bannière) et des couleurs. Un asset oublié
ne se plaint jamais — il s'installe, démarre, et affiche encore la marque d'avant.

Le 2026-09-15, la refonte a justement découvert trois visuels portant le
mot-symbole S0und **dans l'interface** (en-tête de liste, icône interne, avatar
par défaut) qu'aucune lecture de code ne signalait : seul un balayage des pixels
les a sortis. Ce fichier fige ce balayage, et les autres invariants du
générateur :

  * les assets versionnés sont *exactement* ce que le générateur produit
    (aucune dérive possible entre le code et les images livrées) ;
  * le rouge de S0und ne peut pas revenir par une retouche du générateur ;
  * la composition du splash tient dans un écran 720p : le PNG est posé à
    taille réelle (nodpi) au centre de la fenêtre, donc un écran plus petit le
    rogne — le mot-symbole doit rester entier ;
  * les icônes existent dans les cinq densités, à la bonne taille (un launcher
    refuse une icône manquante ou d'une densité inattendue).

    python patch/tests/test_brand.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import sys
import tempfile

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
GENERATOR = ROOT / "patch" / "branding" / "make_brand.py"
VERSIONED = ROOT / "patch" / "branding" / "assets"

DEAD_RED = (0xA3, 0x0F, 0x2C)  # #a30f2c, le rouge de S0und
TOLERANCE = 24                 # somme des écarts par canal
SAFE = (1280, 720)             # écran le plus petit visé : ce qui est rogné hors de là
ICON_SIZES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}

spec = importlib.util.spec_from_file_location("make_brand", GENERATOR)
make_brand = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make_brand)


def check(name: str, condition: bool, detail: str = "") -> bool:
    print(f"{'✅' if condition else '❌'} {name}{(' — ' + detail) if detail and not condition else ''}")
    return condition


def expected_assets() -> set[str]:
    """Les visuels qui doivent partir dans l'APK, sans exception."""
    names = {
        "drawable-nodpi/twouich_splash.png",
        "drawable-nodpi/twouich_wordmark.png",
        "drawable/s0undtv_logo_with_text_2.xml",
        "drawable/s0undtv_logo_2.xml",
        "drawable/banner.png",
        "drawable/banner_320_180.png",
        "drawable/app_icon.png",
        "drawable/logo_experimental.png",
        "drawable-xxhdpi/header_logo.png",
        "drawable-xxhdpi/channel_logo.png",
    }
    for density in make_brand.DENSITIES:
        for icon in ("ic_launcher", "ic_launcher_round", "ic_launcher_foreground"):
            names.add(f"mipmap-{density}/{icon}.webp")
    for shot in sorted(make_brand.TUTORIAL_DIR.glob("tut_*.webp")):
        names.add(f"drawable/{shot.name}")
    return names


def family_red_ratio(img: Image.Image) -> float:
    """Part de pixels appartenant encore à la famille rouge du thème S0und."""
    anchors = np.array([s for s, _ in make_brand.TUTORIAL_SWAP], dtype=np.float32)
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32)
    dist = np.linalg.norm(rgb[..., None, :] - anchors[None, None, :, :], axis=-1).min(-1)
    return float((dist <= 18).mean())


def red_ratio(img: Image.Image) -> float:
    pixels = np.asarray(img.convert("RGB"), dtype=np.int16)
    return float((np.abs(pixels - np.array(DEAD_RED, dtype=np.int16)).sum(axis=2) <= TOLERANCE).mean())


def digest(paths: list[pathlib.Path], base: pathlib.Path) -> str:
    """Empreinte de l'arbre : chemins relatifs à `base` plus contenu des fichiers."""
    sha = hashlib.sha256()
    for path in sorted(paths):
        sha.update(path.relative_to(base).as_posix().encode())
        sha.update(path.read_bytes())
    return sha.hexdigest()


def emit_into(target: pathlib.Path) -> list[pathlib.Path]:
    return make_brand.emit(make_brand.SHIPPING, target)


def main() -> int:
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        fresh = pathlib.Path(tmp)
        written = emit_into(fresh)
        res = fresh / "res"
        emitted = {p.relative_to(res).as_posix(): p for p in written
                   if p.is_file() and res in p.parents}

        # 1. L'émission couvre exactement les visuels attendus : un asset oublié
        #    (c'est ainsi que header_logo/app_icon ont été trouvés) sort ici.
        got = {rel for rel in emitted if rel.endswith((".png", ".webp", ".xml"))}
        ok &= check("assets émis == assets attendus", got == expected_assets(),
                    f"manquants {(expected_assets() - got)} / en trop {(got - expected_assets())}")

        # 2. Ce qui est versionné est ce que le générateur produit : aucune dérive
        #    entre le code et les images livrées, et le build n'a pas besoin des
        #    polices Windows pour reconstruire l'APK à l'identique.
        versioned = [p for p in VERSIONED.rglob("*") if p.is_file()]
        ok &= check("assets versionnés == émission fraîche",
                    digest(versioned, VERSIONED) == digest(written, fresh),
                    "relancer : python patch/branding/make_brand.py emit")

        # 3a. La famille rouge du thème S0und n'existe plus dans **aucun** visuel
        #     livré, captures du tutoriel comprises : c'est le contrôle qui
        #     manquait quand ces six images sont parties avec la marque d'avant.
        #     Le seuil n'est pas zéro : le WebP étant lossy, l'angle arrondi d'une
        #     icône laisse quelques pixels de bruit (3 px mesurés, 0,014 %). Les
        #     captures du tutoriel, elles, mesurent 0,0000 % — l'écart qui compte
        #     est de trois ordres de grandeur (jusqu'à 36,7 % avant remappage).
        worst_family = max(((family_red_ratio(Image.open(p)), rel) for rel, p in emitted.items()
                            if rel.endswith((".png", ".webp"))), default=(0.0, "aucun"))
        ok &= check("famille rouge S0und absente des visuels", worst_family[0] < 2e-4,
                    f"{worst_family[1]} à {worst_family[0] * 100:.3f}%")

        # 3b. Les visuels **générés** (tout sauf les captures) ne contiennent que
        #     la palette de marque : même un rouge de contenu y serait un défaut.
        worst = max(((red_ratio(Image.open(p)), rel) for rel, p in emitted.items()
                     if rel.endswith((".png", ".webp"))
                     and not pathlib.Path(rel).name.startswith("tut_")), default=(0.0, "aucun"))
        ok &= check("visuels générés sans rouge", worst[0] < 0.001,
                    f"{worst[1]} à {worst[0] * 100:.1f}%")

        # 4. La composition tient dans la fenêtre la plus petite : le PNG est posé
        #    à taille réelle, donc un écran 720p rogne ce qui dépasse.
        splash = Image.open(emitted["drawable-nodpi/twouich_splash.png"]).convert("RGBA")
        box = splash.getbbox()
        inside = box[2] - box[0] <= SAFE[0] and box[3] - box[1] <= SAFE[1]
        ok &= check("splash entier en 720p", inside,
                    f"contenu {box[2] - box[0]}×{box[3] - box[1]} pour {SAFE[0]}×{SAFE[1]}")
        # La composition est centrée sur la largeur (le dessin des lettres est
        # calé sur les chasses, l'encre peut donc être à quelques pixels près).
        # Le centrage vertical, lui, dépend du dessin : il n'est pas testé ici.
        dx = (box[0] + box[2]) / 2 - splash.width / 2
        ok &= check("composition centrée en largeur", abs(dx) <= splash.width * 0.02,
                    f"décalage {dx:.0f} px")

        # 5. Le mot-symbole est bien là : assez d'encre dans la bande médiane
        #    (garde-fou contre une génération silencieusement vide, si une police
        #    ou une variation disparaissait).
        alpha = np.asarray(splash)[..., 3]
        band = alpha[int(splash.height * 0.35):int(splash.height * 0.80)]
        ok &= check("mot-symbole présent", float((band > 40).mean()) > 0.03,
                    f"encre {(band > 40).mean() * 100:.1f}%")

        # 6. Les deux XML de l'écran de démarrage : plus de rouge, et ils pointent
        #    sur les PNG émis (une référence morte afficherait un écran vide).
        for rel, png in (("drawable/s0undtv_logo_with_text_2.xml", "twouich_splash"),
                         ("drawable/s0undtv_logo_2.xml", "twouich_wordmark")):
            xml = emitted[rel].read_text(encoding="utf-8")
            ok &= check(f"{rel} : dégradé de marque, pas de rouge",
                        "#a30f2c" not in xml.lower()
                        and f"@drawable/{png}" in xml
                        and make_brand.VARIANTS[make_brand.SHIPPING]["bg"][0] in xml, xml[:120])

        # 7. brand.json (lu par patch.py pour colors.xml) décrit la même palette
        #    que les XML : une seule source de vérité, deux lecteurs.
        import json
        brand = json.loads((fresh / "brand.json").read_text(encoding="utf-8"))
        ok &= check("brand.json == palette des XML",
                    brand["brand"] == make_brand.VARIANTS[brand["variant"]]["bg"][0]
                    and brand["variant"] == make_brand.SHIPPING, json.dumps(brand))

        # 8. Icônes : cinq densités, tailles exactes, avant-plan adaptatif à 108dp
        #    de côté (la zone sûre d'une icône adaptative, sinon le glyphe est rogné).
        bad = []
        for density, size in ICON_SIZES.items():
            for icon, factor in (("ic_launcher", 1), ("ic_launcher_round", 1),
                                 ("ic_launcher_foreground", 108 / 48)):
                path = emitted.get(f"mipmap-{density}/{icon}.webp")
                want = int(size * factor)
                if path is None or Image.open(path).size != (want, want):
                    bad.append(f"{density}/{icon}")
        ok &= check("icônes aux bonnes tailles", not bad, ", ".join(bad))

        # 8b. Les captures du tutoriel restent au format de l'écran Android TV :
        #     elles sont posées en plein écran par l'onboarding.
        shots = {rel: p for rel, p in emitted.items() if pathlib.Path(rel).name.startswith("tut_")}
        wrong = [rel for rel, p in shots.items() if Image.open(p).size != (1920, 1080)]
        ok &= check(f"{len(shots)} captures du tutoriel en 1920×1080",
                    len(shots) == 6 and not wrong, ", ".join(wrong))

        # 9. Les trois pistes se rendent et donnent des visuels distincts : le
        #    choix d'identité reste une constante, pas un chemin mort.
        renders = {}
        for variant in sorted(make_brand.VARIANTS):
            img = make_brand.render_splash(variant)
            renders[variant] = hashlib.sha256(img.tobytes()).hexdigest()
        ok &= check("trois pistes distinctes", len(set(renders.values())) == 3)

        # 10. Emission rejouable : deux passes donnent les mêmes octets (le build
        #     régénère les assets à chaque fois, il ne doit rien produire d'autre).
        with tempfile.TemporaryDirectory() as tmp2:
            again = emit_into(pathlib.Path(tmp2))
            ok &= check("émission idempotente",
                        digest(again, pathlib.Path(tmp2)) == digest(written, fresh))

    print("\n" + ("✅ identité conforme" if ok else "❌ divergence détectée"))
    return 0 if ok else 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
