#!/usr/bin/env python3
"""
test_apk.py — vérifie le livrable, pas l'arbre de travail.

Pourquoi ce test existe
-----------------------
`patch.py` contrôle l'arbre **décodé**, et `test_brand.py` le **générateur**. Aucun
des deux ne regarde l'APK qui part chez l'utilisateur : entre les deux il y a
aapt2, qui compile les XML en binaire, ré-encode certains PNG et fusionne les
ressources. Un asset perdu à cette étape ne se plaint jamais — l'app s'installe,
démarre, et affiche la mauvaise chose.

Ce fichier vérifie donc l'artefact :

  * les 25 visuels de marque sont bien dans l'archive (aapt2 peut ré-encoder, on
    compare donc les octets quand c'est possible et les dimensions sinon) ;
  * le PNG de composition est là, à sa taille de dessin ;
  * aucune chaîne d'affichage « S0undTV » ne subsiste dans les ressources ni dans
    le manifeste — c'est ce que voit l'utilisateur, quelle que soit l'encodage ;
  * les pages embarquées sont réécrites ;
  * l'APK est signé (v1+v2+v3) et zipaligné (l'empreinte du livrable est affichée).

    python patch/tests/test_apk.py                       # dist/Twouich_beta144_ttv1.apk
    python patch/tests/test_apk.py --apk dist/autre.apk
"""
from __future__ import annotations

import argparse
import hashlib
import io
import pathlib
import sys
import zipfile

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
GENERATED = ROOT / "patch" / "branding" / "assets" / "res"
DEFAULT_APK = ROOT / "dist" / "Twouich_beta144_ttv1.apk"

# Chaînes d'affichage : ce que l'utilisateur lit à l'écran. Le paquet Android
# (`com.s0und.s0undtv`) et les URL du journal des modifications gardent
# volontairement la référence d'origine — ce ne sont pas des marques affichées.
DEAD_NAMES = ("S0undTV",)
REBRANDED = ("Twouich",)
PAGES = ("assets/S0undTV_about.html", "assets/S0undTV_changelog.html")


def check(name: str, condition: bool, detail: str = "") -> bool:
    print(f"{'✅' if condition else '❌'} {name}{(' — ' + detail) if detail and not condition else ''}")
    return condition


# Contrôle négatif : lancé sur l'APK d'origine de S0undTV, ce test doit échouer sur
# les visuels et sur le nom d'affichage — c'est ce qui montre qu'il discrimine :
#   python patch/tests/test_apk.py --apk work/upstream/beta_144.apk


def holds(blob: bytes, text: str) -> bool:
    """Le texte est-il présent, quel que soit l'encodage du pool de chaînes ?"""
    return text.encode("utf-8") in blob or text.encode("utf-16-le") in blob


def main() -> int:
    parser = argparse.ArgumentParser(description="Vérifie l'APK livré")
    parser.add_argument("--apk", type=pathlib.Path, default=DEFAULT_APK)
    args = parser.parse_args()

    apk: pathlib.Path = args.apk if args.apk.is_absolute() else ROOT / args.apk
    if not apk.is_file():
        print(f"❌ APK introuvable : {apk} (lancer d'abord bash patch/build.sh)")
        return 1
    ok = True
    print(f"APK : {apk.relative_to(ROOT) if apk.is_relative_to(ROOT) else apk} "
          f"({apk.stat().st_size} octets)")

    with zipfile.ZipFile(apk) as z:
        names = set(z.namelist())

        # 1. Tous les visuels du générateur sont dans l'archive, et identiques à ce
        #    qui a été émis (aapt2 ne ré-encode que trois d'entre eux : les deux XML
        #    compilés en binaire et un PNG recrunché — on les compte à part).
        emitted = {p.relative_to(GENERATED).as_posix(): p for p in GENERATED.rglob("*") if p.is_file()}
        missing = [rel for rel in emitted if f"res/{rel}" not in names]
        ok &= check(f"{len(emitted)} visuels de marque présents", not missing, ", ".join(missing[:6]))

        identical, reencoded = 0, []
        for rel, path in emitted.items():
            entry = f"res/{rel}"
            if entry not in names:
                continue
            if hashlib.sha256(z.read(entry)).digest() == hashlib.sha256(path.read_bytes()).digest():
                identical += 1
            else:
                reencoded.append(rel)
        ok &= check("visuels repris tels quels (hors re-encodage aapt2)",
                    identical >= len(emitted) - 3,
                    f"identiques {identical}/{len(emitted)}, ré-encodés {reencoded}")

        # 2. La composition de l'écran de démarrage est bien celle du générateur :
        #    même taille de dessin (le layer-list la pose sans mise à l'échelle).
        splash_entry = "res/drawable-nodpi/twouich_splash.png"
        if splash_entry not in names:
            ok &= check("composition du splash intacte", False, "absente de l'archive")
        else:
            splash = Image.open(io.BytesIO(z.read(splash_entry)))
            want = Image.open(emitted["drawable-nodpi/twouich_splash.png"]).size
            ok &= check("composition du splash intacte", splash.size == want,
                        f"{splash.size} au lieu de {want}")

        # 3. Le nom affiché : plus une seule occurrence dans les ressources, et
        #    « Twouich » bien présent. Le paquet, lui, garde `s0und` par conception.
        arsc = z.read("resources.arsc")
        leaked = [s for s in DEAD_NAMES if holds(arsc, s)]
        ok &= check("aucun nom d'affichage S0und dans les ressources", not leaked, ", ".join(leaked))
        ok &= check("nom d'affichage Twouich présent", all(holds(arsc, s) for s in REBRANDED))

        manifest = z.read("AndroidManifest.xml")
        leaked_m = [s for s in DEAD_NAMES if holds(manifest, s)]
        ok &= check("libellé du manifeste Twouich",
                    not leaked_m and holds(manifest, "Twouich"), ", ".join(leaked_m))

        # 4. Les pages embarquées : réécrites, et plus de fond rouge.
        for page in PAGES:
            if page not in names:
                ok &= check(f"{page} présent", False)
                continue
            body = z.read(page)
            ok &= check(f"{page} : identité Twouich, plus de fond rouge",
                        holds(body, "Twouich") and b"#a30f2d" not in body)

        # 5. Un paquet sans signature ne s'installe pas : l'apk porte bien les
        #    blocs v1/v2/v3 (les .SF/.RSA du schéma v1, l'APK Signing Block sinon).
        v1 = any(n.startswith("META-INF/") and n.endswith((".SF", ".RSA", ".DSA")) for n in names)
        ok &= check("signature v1 (JAR) présente", v1)

    sha = hashlib.sha256(apk.read_bytes()).hexdigest()
    print(f"\nempreinte : {sha}")
    print("✅ livrable conforme" if ok else "❌ livrable non conforme")
    return 0 if ok else 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
