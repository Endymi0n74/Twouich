#!/usr/bin/env python3
"""
make_brand.py — identité visuelle Twouich : une seule source de vérité.

Tout le visuel de marque est **calculé** ici, jamais retouché à la main :
le mot-symbole, la tagline, la palette et la composition sont décrits une fois
et déclinés en trois sorties cohérentes :

  * `emit`    : les assets Android écrits dans `patch/branding/assets/<piste>/res/`,
                au format **exact** de l'arbre `res/` de l'APK (écran de démarrage,
                bannière TV 320×180, icônes de lancement + icône adaptative) :
                `patch.py` n'a plus qu'à recopier l'arborescence ;
  * `preview` : une page HTML autonome (PNG en données de base64) pour
                comparer les pistes retenues ;
  * `dump`    : un rendu ASCII grossier du splash, pour vérifier la
                composition sans ouvrir d'image.

    python patch/branding/make_brand.py preview --out work/branding/preview.html
    python patch/branding/make_brand.py dump --variant C
    python patch/branding/make_brand.py emit              # piste livrée (SHIPPING)
    python patch/branding/make_brand.py emit --variant B  # pour changer d'identité

La piste **livrée** est `SHIPPING` ; les trois restent disponibles, une seule
constante à changer (ou `--variant`). Les assets émis sont versionnés : le build
ne dépend donc pas des polices Windows pour produire un APK identique.

`emit` produit aussi `patch/branding/assets/brand.json` : la palette que
`patch.py` reporte dans `colors.xml` (icône adaptative, thème violet).

Polices utilisées (Windows) : Bahnschrift en « Bold SemiCondensed » pour le
mot-symbole, Segoe UI Semibold pour la tagline. Si une police manque, le script
échoue bruyamment : mieux vaut un échec qu'un visuel approximatif.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import pathlib
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
FONT_DIR = pathlib.Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"

WORD_FONT = ("bahnschrift.ttf", "Bold SemiCondensed")
MONO_FONT = ("bahnschrift.ttf", "Bold")
TAG_FONT = ("seguisb.ttf", None)

BRAND = "#9146ff"  # violet Twitch

# ── Les pistes ────────────────────────────────────────────────────────────
# bg : (haut, bas) du fond — un seul ton, ou un dégradé diagonal.
VARIANTS = {
    "A": {
        "label": "Violet Twitch",
        "idea": "Fond violet Twitch plein, mot-symbole blanc. Le plus lisible de loin, "
                "et cohérent avec l'accent violet déjà présent dans l'interface.",
        "bg": (BRAND, BRAND),
        "word": "#ffffff",
        "tag": "#ffffff",
        "tag_alpha": 0.86,
        "monogram": False,
        "swatches": [("#9146ff", "fond"), ("#ffffff", "mot-symbole")],
    },
    "B": {
        "label": "Noir Twitch",
        "idea": "Fond noir Twitch, mot-symbole violet. Sobre : le splash annonce la couleur "
                "sans éblouir, et se fond dans l'interface sombre de l'app.",
        "bg": ("#0e0e10", "#0e0e10"),
        "word": BRAND,
        "tag": "#adadb8",
        "tag_alpha": 1.0,
        "monogram": False,
        "swatches": [("#0e0e10", "fond"), ("#9146ff", "mot-symbole"), ("#adadb8", "tagline")],
    },
    "C": {
        "label": "Dégradé + monogramme",
        "idea": "Dégradé violet → noir, monogramme « T » en pastille puis le nom dessous. "
                "Le plus « produit » : la pastille sert aussi d'icône.",
        "bg": (BRAND, "#150826"),
        "word": "#ffffff",
        "tag": "#e6d8ff",
        "tag_alpha": 0.92,
        "monogram": True,
        "swatches": [("#9146ff", "dégradé haut"), ("#150826", "dégradé bas"), ("#ffffff", "texte")],
    },
}

SHIPPING = "C"  # piste livrée dans l'APK (générer les assets avec `emit`)
TAGLINE = "an Android TV client for Twitch"


def rel(path: pathlib.Path) -> str:
    """Chemin lisible, relatif au dépôt quand c'est possible."""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def fail(msg: str) -> None:
    print(f"\n❌ {msg}", file=sys.stderr)
    sys.exit(1)


def font(name: str, size: int, variation: str | None):
    path = FONT_DIR / name
    if not path.is_file():
        fail(f"police introuvable : {path} (requis pour générer les visuels)")
    f = ImageFont.truetype(str(path), size)
    if variation:
        try:
            f.set_variation_by_name(variation)
        except OSError:
            fail(f"variation « {variation} » indisponible dans {name}")
    return f


def hex_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def blend(fg: tuple[int, int, int], bg: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    return tuple(round(f * alpha + b * (1 - alpha)) for f, b in zip(fg, bg))  # type: ignore[return-value]


def background(width: int, height: int, top: str, bottom: str) -> Image.Image:
    """Fond uni, ou dégradé diagonal du haut-gauche vers le bas-droit."""
    if top.lower() == bottom.lower():
        return Image.new("RGB", (width, height), hex_rgb(top))
    y, x = np.mgrid[0:height, 0:width].astype(np.float32)
    t = (x / max(width - 1, 1) + y / max(height - 1, 1)) / 2.0
    c0 = np.array(hex_rgb(top), dtype=np.float32)
    c1 = np.array(hex_rgb(bottom), dtype=np.float32)
    plane = c0[None, None, :] * (1 - t[..., None]) + c1[None, None, :] * t[..., None]
    return Image.fromarray(plane.round().astype(np.uint8))


def tracked(draw: ImageDraw.ImageDraw, text: str, f, tracking: float, center_x: float,
            baseline_y: float, fill) -> float:
    """Écrit `text` centré horizontalement, avec interlettrage (tracking)."""
    widths = [f.getlength(ch) for ch in text]
    total = sum(widths) + tracking * max(len(text) - 1, 0)
    x = center_x - total / 2
    for ch, w in zip(text, widths):
        draw.text((x, baseline_y), ch, font=f, fill=fill, anchor="ls")
        x += w + tracking
    return total


def load(spec: tuple[str, str | None], size: int):
    """Charge une police décrite par (fichier, variation)."""
    return font(spec[0], size, spec[1])


def fit_size(text: str, spec: tuple[str, str | None], target_width: float,
             reference: int = 200) -> int:
    """Taille de police donnant à `text` la largeur visée."""
    probe = load(spec, reference)
    measured = probe.getlength(text)
    if measured <= 0:
        fail(f"mesure impossible pour « {text} »")
    return max(8, int(round(reference * target_width / measured)))


def compose_wordmark(variant: str, img: Image.Image, width: int, height: int,
                     tagline: bool = True, blend_tag: bool = True) -> Image.Image:
    """Pose la composition de marque (monogramme, nom, tagline) sur `img`.

    `blend_tag` n'a de sens que sur un fond opaque : sur un PNG transparent, la
    tagline est écrite pleine, sinon son alpha se mélangerait au vide.
    """
    cfg = VARIANTS[variant]
    draw = ImageDraw.Draw(img)
    base = hex_rgb(cfg["bg"][0])

    word_size = fit_size("TWOUICH", WORD_FONT, target_width=width * 0.60)
    word = load(WORD_FONT, word_size)
    # tagline : l'original occupait ~6 % de la hauteur, on reste un cran en
    # dessous pour que le nom domine, mais lisible de loin (TV 1080p).
    tag_size = max(12, int(round(height * 0.040)))
    tag = load(TAG_FONT, tag_size)

    if cfg["monogram"]:
        side = height * 0.155
        x0 = width / 2 - side / 2
        y0 = height * 0.185
        draw.rounded_rectangle([x0, y0, x0 + side, y0 + side], radius=side * 0.28,
                               fill=(255, 255, 255, 255))
        glyph = load(MONO_FONT, int(side * 0.74))
        draw.text((width / 2, y0 + side * 0.60), "T", font=glyph, fill=base, anchor="mm")
        word_base = height * 0.665
        tag_base = height * 0.815
    else:
        word_base = height * 0.575
        tag_base = height * 0.795

    tracked(draw, "TWOUICH", word, word_size * 0.02, width / 2, word_base, cfg["word"])
    if tagline:
        fill = blend(hex_rgb(cfg["tag"]), base, cfg["tag_alpha"]) if blend_tag else cfg["tag"]
        tracked(draw, TAGLINE, tag, tag_size * 0.05, width / 2, tag_base, fill)
    return img


def render_splash(variant: str, width: int = 1920, height: int = 1080) -> Image.Image:
    """Écran de démarrage : fond de marque + composition complète."""
    return compose_wordmark(variant, background(width, height, *VARIANTS[variant]["bg"]),
                            width, height)


def render_wordmark(variant: str, width: int = 1920, height: int = 1080,
                    tagline: bool = True) -> Image.Image:
    """Composition sur fond transparent : posée par-dessus une couleur unie par
    l'écran de démarrage (`windowBackground`), elle se détache proprement quel
    que soit le tirage de l'écran — et le mot-symbole reste net en 4K."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    return compose_wordmark(variant, img, width, height, tagline=tagline, blend_tag=False)


def splash_xml(variant: str, tagline: bool = True) -> str:
    """`windowBackground` de l'écran de démarrage : dégradé de marque + composition.

    Le fond est un dégradé XML (pas une ressource nouvelle, pas un PNG étiré :
    aucune dépendance au tirage de l'écran) et la composition est un PNG
    transparent posé au centre. Rien n'est mis à l'échelle — le texte garde donc
    exactement le dessin validé, du 720p au 4K.
    """
    cfg = VARIANTS[variant]
    src = "@drawable/twouich_splash" if tagline else "@drawable/twouich_wordmark"
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!-- Généré par patch/branding/make_brand.py — identité Twouich -->\n'
        '<layer-list xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <item>\n'
        '        <shape android:shape="rectangle">\n'
        '            <gradient\n'
        '                android:angle="315"\n'
        '                android:type="linear"\n'
        f'                android:startColor="{cfg["bg"][0]}"\n'
        f'                android:endColor="{cfg["bg"][1]}" />\n'
        '        </shape>\n'
        '    </item>\n'
        '    <item>\n'
        f'        <bitmap android:gravity="center" android:src="{src}" />\n'
        '    </item>\n'
        '</layer-list>\n'
    )


def render_banner(variant: str, width: int = 320, height: int = 180) -> Image.Image:
    """Bannière Android TV : 320×180 exactement, mot-symbole seul (la tagline
    serait illisible à cette taille, l'écran de démarrage la porte déjà)."""
    cfg = VARIANTS[variant]
    img = background(width, height, *cfg["bg"])
    draw = ImageDraw.Draw(img)
    word_size = fit_size("TWOUICH", WORD_FONT, target_width=width * 0.74)
    word = load(WORD_FONT, word_size)
    tracked(draw, "TWOUICH", word, word_size * 0.02, width / 2, height * 0.635, cfg["word"])
    return img


def render_icon(variant: str, size: int, shape: str = "square",
                foreground: bool = False, supersample: int = 4) -> Image.Image:
    """Icône de lancement (carré arrondi / rond / à plat) ou avant-plan d'icône adaptative."""
    cfg = VARIANTS[variant]
    s = size * supersample
    if foreground:
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    else:
        img = background(s, s, *cfg["bg"]).convert("RGBA")
        if shape != "flat":
            mask = Image.new("L", (s, s), 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                [0, 0, s - 1, s - 1], radius=s * (0.5 if shape == "round" else 0.22), fill=255)
            img.putalpha(mask)

    draw = ImageDraw.Draw(img)
    ratio = 0.56 if foreground else 0.62
    glyph = load(MONO_FONT, int(s * ratio))
    fill = "#ffffff" if cfg["word"].lower() == "#ffffff" else cfg["word"]
    draw.text((s / 2, s * 0.53), "T", font=glyph, fill=fill, anchor="mm")
    return img.resize((size, size), Image.LANCZOS)


def render_header_logo(variant: str, size: int = 256) -> Image.Image:
    """Logo d'en-tête (au-dessus des listes) : bandeau de marque et mot-symbole,
    le reste transparent — l'original laissait voir le fond de l'écran."""
    cfg = VARIANTS[variant]
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    top, bottom = int(size * 0.30), int(size * 0.70)
    bar = background(size, bottom - top, *cfg["bg"])
    img.paste(bar, (0, top))
    draw = ImageDraw.Draw(img)
    word_size = fit_size("TWOUICH", WORD_FONT, target_width=size * 0.84)
    word = load(WORD_FONT, word_size)
    tracked(draw, "TWOUICH", word, word_size * 0.02, size / 2,
            (top + bottom) / 2 + word_size * 0.35, cfg["word"])
    return img


def render_plate(variant: str, size: int) -> Image.Image:
    """Plaque carrée opaque (icône interne, avatar par défaut) : fond de marque et
    mot-symbole centré."""
    cfg = VARIANTS[variant]
    img = background(size, size, *cfg["bg"])
    draw = ImageDraw.Draw(img)
    word_size = fit_size("TWOUICH", WORD_FONT, target_width=size * 0.80)
    word = load(WORD_FONT, word_size)
    tracked(draw, "TWOUICH", word, word_size * 0.02, size / 2, size * 0.5 + word_size * 0.35,
            cfg["word"])
    return img


def png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def data_uri(img: Image.Image) -> str:
    return "data:image/png;base64," + base64.b64encode(png_bytes(img)).decode()


def ascii_dump(img: Image.Image, cols: int = 104, rows: int = 30) -> str:
    grey = np.asarray(img.convert("L").resize((cols, rows), Image.BOX), dtype=np.float32) / 255.0
    ramp = " .:-=+*#%@"
    return "\n".join("".join(ramp[min(int(v * len(ramp)), len(ramp) - 1)] for v in row)
                     for row in grey)


# ── Captures du tutoriel ─────────────────────────────────────────────────
# Les six visuels de l'onboarding sont des captures d'écran réelles (1920×1080)
# prises par l'upstream, et elles montrent deux choses de l'ancienne marque :
# les **cadres d'annotation** dessinés en rouge, et pour `tut_5` un **panneau au
# thème rouge** (`#4d000f` + `#a30f2c`, un tiers de l'image).
#
# On ne les recapture pas : l'émulateur de test plafonne à 1280×720 et les
# agrandir donnerait des images plus floues que les actuelles, pour une mise en
# page qui n'a pas changé. On applique à la place **le même remappage qu'un
# changement de thème** : chaque couleur de la famille rouge prend la couleur de
# même rôle dans la palette Twouich. La composition, les vignettes et les textes
# ne bougent pas — seuls les rouges de marque changent de teinte.
TUTORIAL_DIR = ROOT / "patch" / "branding" / "tutorial"
TUTORIAL_SWAP = [  # (rouge S0und, violet Twouich), rôle par rôle
    ((0x4D, 0x00, 0x0F), (0x2F, 0x1F, 0x4D)),  # theme_red_dark   → theme_purple_dark
    ((0xA3, 0x0F, 0x2C), (0x91, 0x46, 0xFF)),  # theme_red        → theme_purple
    ((0xDB, 0x00, 0x2C), (0xA9, 0x70, 0xFF)),  # theme_red_bright → theme_purple_bright
]
RECOLOR_FULL = 40   # en deçà de cette distance : remplacement franc
RECOLOR_FADE = 130  # au-delà : pixel laissé intact


def red_mask(rgb: np.ndarray) -> np.ndarray:
    """Pixels franchement rouges : R domine les deux autres canaux.

    C'est le seul test qui distingue la marque S0und des gris du thème sombre,
    des vignettes vertes/bleues et du noir : mesurer la « distance au rouge »
    sans regarder le déséquilibre des canaux classe les pixels presque noirs
    comme rouges (leçon payée sur ces images).
    """
    return (rgb[..., 0] > 55) & (rgb[..., 0] > rgb[..., 1] + 25) & (rgb[..., 0] > rgb[..., 2] + 25)


def recolor_tutorial(img: Image.Image) -> Image.Image:
    """Remappe la famille rouge du thème S0und vers la palette Twouich."""
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32)
    sources = np.array([s for s, _ in TUTORIAL_SWAP], dtype=np.float32)
    targets = np.array([t for _, t in TUTORIAL_SWAP], dtype=np.float32)
    dist = np.linalg.norm(rgb[..., None, :] - sources[None, None, :, :], axis=-1)
    weights = 1.0 / np.maximum(dist, 1.0) ** 6
    weights /= weights.sum(axis=-1, keepdims=True)
    mapped = np.einsum("hwk,kc->hwc", weights, targets)
    strength = np.clip((RECOLOR_FADE - dist.min(axis=-1)) / (RECOLOR_FADE - RECOLOR_FULL),
                       0.0, 1.0)
    strength = np.where(red_mask(rgb), strength, 0.0)[..., None]
    return Image.fromarray(np.clip(rgb * (1 - strength) + mapped * strength, 0, 255).astype(np.uint8))


# ── Sorties ──────────────────────────────────────────────────────────────
# L'arborescence émise est celle de l'APK : `patch.py` recopie `res/` tel quel.
DENSITIES = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}


def emit(variant: str, out_root: pathlib.Path) -> list[pathlib.Path]:
    """Écrit les assets Android de la piste `variant` dans `out_root/res/`."""
    cfg = VARIANTS[variant]
    res = out_root / "res"
    written: list[pathlib.Path] = []

    def save(img: Image.Image, rel: str, fmt: str = "PNG", **kw) -> None:
        path = res / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path, format=fmt, **kw)
        written.append(path)

    def write(path: pathlib.Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        written.append(path)

    def text(rel: str, content: str) -> None:
        write(res / rel, content)

    # Écran de démarrage : la couleur de marque vient du `layer-list`, la
    # composition d'un PNG transparent posé au centre (net en 1080p et 4K).
    save(render_wordmark(variant), "drawable-nodpi/twouich_splash.png", optimize=True)
    save(render_wordmark(variant, tagline=False), "drawable-nodpi/twouich_wordmark.png", optimize=True)
    text("drawable/s0undtv_logo_with_text_2.xml", splash_xml(variant))
    text("drawable/s0undtv_logo_2.xml", splash_xml(variant, tagline=False))

    # Bannière Android TV : 320×180 dans la tuile du launcher, et son double
    # 1280×720 pour l'écran d'accueil TV / la fiche Play Store.
    save(render_banner(variant), "drawable/banner_320_180.png", optimize=True)
    save(render_banner(variant, 1280, 720), "drawable/banner.png", optimize=True)

    # Les six captures du tutoriel : remappées, jamais retouchées à la main.
    for shot in sorted(TUTORIAL_DIR.glob("tut_*.webp")):
        save(recolor_tutorial(Image.open(shot)), f"drawable/{shot.name}",
             fmt="WEBP", quality=92, method=6)

    # Ces trois visuels portaient le mot-symbole S0und **dans l'interface**
    # (en-tête de liste, icône interne, avatar par défaut) ; ils sont remplacés
    # à l'identique — mêmes chemins, mêmes tailles — pour qu'aucune surface ne
    # reste à l'ancienne marque.
    save(render_plate(variant, 320), "drawable/app_icon.png", optimize=True)
    save(render_banner(variant, 320, 180), "drawable/logo_experimental.png", optimize=True)
    save(render_header_logo(variant), "drawable-xxhdpi/header_logo.png", optimize=True)
    save(render_icon(variant, 300, "flat"), "drawable-xxhdpi/channel_logo.png", optimize=True)

    for name, dp in DENSITIES.items():
        save(render_icon(variant, dp, "square"), f"mipmap-{name}/ic_launcher.webp",
             fmt="WEBP", quality=95, method=6)
        save(render_icon(variant, dp, "round"), f"mipmap-{name}/ic_launcher_round.webp",
             fmt="WEBP", quality=95, method=6)
        # avant-plan adaptatif : 108dp de côté, glyphe dans la zone sûre centrale
        save(render_icon(variant, int(dp * 108 / 48), foreground=True),
             f"mipmap-{name}/ic_launcher_foreground.webp",
             fmt="WEBP", quality=95, method=6)

    # Palette de la piste, lisible par `patch.py` (couleurs de l'icône adaptative
    # et du thème) : le générateur reste la seule source de vérité des teintes.
    write(out_root / "brand.json", json.dumps({
        "variant": variant,
        "label": cfg["label"],
        "brand": cfg["bg"][0],
        "brand_dark": cfg["bg"][1],
        "wordmark": cfg["word"],
        "tagline": cfg["tag"],
    }, indent=2, ensure_ascii=False) + "\n")
    return written


def preview(out_path: pathlib.Path) -> None:
    """Page autonome : les trois pistes, avec leurs vrais assets."""
    cards = []
    for key, cfg in VARIANTS.items():
        splash = data_uri(render_splash(key).resize((960, 540), Image.LANCZOS))
        banner = data_uri(render_banner(key))
        icon = data_uri(render_icon(key, 192, "square"))
        round_icon = data_uri(render_icon(key, 192, "round"))
        swatches = "".join(
            f'<span class="sw"><i style="background:{c}"></i>{c} — {role}</span>'
            for c, role in cfg["swatches"]
        )
        cards.append(f"""
    <section class="card">
      <header>
        <h2><span class="tag">{key}</span> {cfg['label']}</h2>
        <p>{cfg['idea']}</p>
      </header>
      <div class="row">
        <div class="tv">
          <img src="{splash}" alt="écran de démarrage {key}">
          <span class="clock">14:38</span>
        </div>
        <div class="side">
          <div class="label">Bannière TV 320×180</div>
          <img class="banner" src="{banner}" alt="bannière {key}">
          <div class="label">Icône</div>
          <div class="icons">
            <img class="icon" src="{icon}" alt="icône {key}">
            <img class="icon" src="{round_icon}" alt="icône ronde {key}">
          </div>
        </div>
      </div>
      <div class="swatches">{swatches}</div>
    </section>""")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>Twouich — pistes d'identité visuelle</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 32px 28px 56px; background: #0b0b0e; color: #e8e8ef;
         font: 15px/1.5 "Segoe UI", system-ui, sans-serif; }}
  h1 {{ font-size: 26px; margin: 0 0 6px; letter-spacing: .01em; }}
  .intro {{ color: #9a9aa8; max-width: 900px; margin: 0 0 28px; }}
  .card {{ border: 1px solid #23232c; border-radius: 16px; padding: 20px 22px 18px;
           margin-bottom: 26px; background: #121218; }}
  .card header h2 {{ margin: 0 0 4px; font-size: 19px; }}
  .card header p {{ margin: 0 0 16px; color: #9a9aa8; }}
  .tag {{ display: inline-block; min-width: 26px; text-align: center; background: #9146ff;
          color: #fff; border-radius: 7px; padding: 1px 7px; margin-right: 8px; font-size: 15px; }}
  .row {{ display: flex; gap: 20px; flex-wrap: wrap; align-items: flex-start; }}
  .tv {{ position: relative; flex: 0 0 auto; border-radius: 10px; overflow: hidden;
         box-shadow: 0 10px 30px #0008; }}
  .tv img {{ display: block; width: 620px; max-width: 100%; }}
  .clock {{ position: absolute; top: 8px; right: 16px; color: #fff; font-size: 15px; opacity: .9; }}
  .side {{ flex: 1 1 220px; min-width: 220px; }}
  .label {{ color: #7c7c8c; font-size: 12px; text-transform: uppercase; letter-spacing: .08em;
            margin: 0 0 6px; }}
  .banner {{ display: block; width: 100%; max-width: 320px; border-radius: 8px; margin-bottom: 16px; }}
  .icons {{ display: flex; gap: 14px; }}
  .icon {{ width: 84px; height: 84px; border-radius: 18px; }}
  .swatches {{ margin-top: 16px; display: flex; gap: 18px; flex-wrap: wrap; color: #b9b9c6;
               font-size: 13px; }}
  .sw {{ display: inline-flex; align-items: center; gap: 8px; }}
  .sw i {{ width: 18px; height: 18px; border-radius: 5px; display: inline-block;
           border: 1px solid #ffffff22; }}
  footer {{ color: #6f6f7e; font-size: 13px; }}
</style>
</head>
<body>
  <h1>Twouich — trois pistes pour l'identité visuelle</h1>
  <p class="intro">Rendu par <code>patch/branding/make_brand.py</code> : ce que tu vois ici,
  c'est exactement ce qui partira dans l'APK (même composition, mêmes polices). L'écran de
  démarrage est affiché à l'échelle (1920×1080 réduit) ; la bannière est la vraie bannière
  Android TV 320×180, les icônes les vraies icônes de lancement.</p>
  {''.join(cards)}
  <footer>Piste retenue → à indiquer (A, B ou C) : le générateur produira les assets définitifs,
  puis <code>patch.py</code> les posera dans l'APK.</footer>
</body>
</html>
""", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Identité visuelle Twouich")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_emit = sub.add_parser("emit", help="écrit les assets Android (arbre res/)")
    p_emit.add_argument("--variant", default=SHIPPING, choices=sorted(VARIANTS))
    p_emit.add_argument("--out", type=pathlib.Path, default=ROOT / "patch" / "branding" / "assets")

    p_prev = sub.add_parser("preview", help="page HTML comparant les pistes")
    p_prev.add_argument("--out", type=pathlib.Path, default=ROOT / "work" / "branding" / "preview.html")

    p_dump = sub.add_parser("dump", help="rendu ASCII du splash (vérification)")
    p_dump.add_argument("--variant", required=True, choices=sorted(VARIANTS))
    p_dump.add_argument("--cols", type=int, default=104)
    p_dump.add_argument("--rows", type=int, default=30)

    args = parser.parse_args()

    if args.cmd == "emit":
        for path in emit(args.variant, args.out):
            print(f"  écrit : {rel(path)}")
        print(f"\n✅ assets piste {args.variant} ({VARIANTS[args.variant]['label']})")
        return 0

    if args.cmd == "preview":
        preview(args.out)
        print(f"✅ aperçu : {rel(args.out)}")
        return 0

    print(ascii_dump(render_splash(args.variant), args.cols, args.rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
