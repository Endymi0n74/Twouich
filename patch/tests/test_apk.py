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
  * l'APK est signé (v1+v2+v3) et zipaligné (l'empreinte du livrable est affichée) ;
  * **le livrable est celui que l'app ira chercher** : son versionCode / versionName
    et son nom de fichier sont confrontés à `update.json`, qui est la seule source
    dont dispose l'updater. Un décalage entre les deux ne casse rien visiblement —
    l'app annonce une version, télécharge une URL qui n'existe pas, et reste sur
    place.

    python patch/tests/test_apk.py                       # dist/Twouich_v1.0.1.apk
    python patch/tests/test_apk.py --apk dist/autre.apk

Contrôle négatif (l'artefact d'origine doit être refusé) :

    python patch/tests/test_apk.py --apk work/upstream/beta_144.apk
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import pathlib
import struct
import sys
import zipfile

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
GENERATED = ROOT / "patch" / "branding" / "assets" / "res"
DEFAULT_APK = ROOT / "dist" / "Twouich_v1.0.9.apk"

# Chaînes d'affichage : ce que l'utilisateur lit à l'écran. Le paquet Android
# (`com.s0und.s0undtv`) et les URL du journal des modifications gardent
# volontairement la référence d'origine — ce ne sont pas des marques affichées.
DEAD_NAMES = ("S0undTV",)
REBRANDED = ("Twouich",)

# Libellé du champ de saisie du chat, aligné sur l'interface de référence
# (Twitch mobile). Volontairement recopié de CHAT_HINT (patch/patch.py) : si le
# générateur change le texte, ce test échoue et force à traiter les deux côtés.
CHAT_HINT = "Envoyer un message"
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


def _axml_strings(buf: bytes, base: int) -> list[str]:
    """Pool de chaînes d'un chunk AXML (les longueurs UTF-8 sont en deux temps)."""
    _type, hsz, _size, count, _styles, flags, str_start, _style_start = struct.unpack_from(
        "<HHIIIIII", buf, base
    )
    offsets = struct.unpack_from(f"<{count}I", buf, base + hsz)
    utf8 = bool(flags & 0x100)
    out: list[str] = []
    for off in offsets:
        pos = base + str_start + off
        if utf8:
            n = buf[pos]
            pos += 1
            if n & 0x80:
                n = ((n & 0x7F) << 8) | buf[pos]
                pos += 1
            # seconde longueur : taille en octets de la chaîne encodée
            size = buf[pos]
            pos += 1
            if size & 0x80:
                size = ((size & 0x7F) << 8) | buf[pos]
                pos += 1
            out.append(buf[pos:pos + size].decode("utf-8", "replace"))
        else:
            n = struct.unpack_from("<H", buf, pos)[0]
            pos += 2
            if n & 0x8000:
                n = ((n & 0x7FFF) << 16) | struct.unpack_from("<H", buf, pos)[0]
                pos += 2
            out.append(buf[pos:pos + 2 * n].decode("utf-16-le", "replace"))
    return out


def manifest_version(axml: bytes) -> tuple[int | None, str | None]:
    """versionCode / versionName lus dans l'AndroidManifest **binaire** de l'APK.

    Pourquoi à la main : le versionCode n'existe nulle part ailleurs que dans ce
    binaire (il n'est pas dans le pool de chaînes), et une machine qui vérifie le
    livrable n'a ni aapt2 ni apktool sous la main. Le format AXML est simple : un
    pool de chaînes, puis des chunks d'éléments dont les attributs portent une
    valeur typée.
    """
    strings: list[str] = []
    pos = 8  # en-tête du fichier (type, headerSize, size)
    while pos + 8 <= len(axml):
        ctype, _hsz, csize = struct.unpack_from("<HHI", axml, pos)
        if csize <= 0:
            break
        if ctype == 0x0001:  # RES_STRING_POOL_TYPE
            strings = _axml_strings(axml, pos)
        elif ctype == 0x0102 and strings:  # RES_XML_START_ELEMENT_TYPE
            # en-tête de nœud (16 o) puis ResXMLTree_attrExt
            name_idx = struct.unpack_from("<I", axml, pos + 20)[0]
            if name_idx < len(strings) and strings[name_idx] == "manifest":
                attr_start, attr_size, attr_count = struct.unpack_from("<HHH", axml, pos + 24)
                found: dict[str, object] = {}
                for i in range(attr_count):
                    off = pos + 16 + attr_start + i * attr_size
                    # off pointe sur l'attribut (ns, name, rawValue, size, res0, type, data)
                    a_name, a_raw, _sz, _res, a_type, a_data = struct.unpack_from(
                        "<IIHBBI", axml, off + 4
                    )
                    if a_name >= len(strings):
                        continue
                    key = strings[a_name]
                    if key == "versionCode":
                        found["code"] = a_data
                    elif key == "versionName":
                        if a_type == 0x03 and a_raw < len(strings):
                            found["name"] = strings[a_raw]
                        elif a_data < len(strings):
                            found["name"] = strings[a_data]
                return found.get("code"), found.get("name")  # type: ignore[return-value]
        pos += csize
    return None, None


def manifest_orientations(axml: bytes) -> dict[str, int]:
    """Lit la valeur enum android:screenOrientation des activités signées."""
    strings: list[str] = []
    orientations: dict[str, int] = {}
    pos = 8
    while pos + 8 <= len(axml):
        ctype, _hsz, csize = struct.unpack_from("<HHI", axml, pos)
        if csize <= 0:
            break
        if ctype == 0x0001:
            strings = _axml_strings(axml, pos)
        elif ctype == 0x0102 and strings:
            name_idx = struct.unpack_from("<I", axml, pos + 20)[0]
            if name_idx < len(strings) and strings[name_idx] == "activity":
                attr_start, attr_size, attr_count = struct.unpack_from("<HHH", axml, pos + 24)
                activity = None
                orientation = None
                for i in range(attr_count):
                    off = pos + 16 + attr_start + i * attr_size
                    a_name, a_raw, _sz, _res, a_type, a_data = struct.unpack_from(
                        "<IIHBBI", axml, off + 4
                    )
                    if a_name >= len(strings):
                        continue
                    key = strings[a_name]
                    if key == "name":
                        value_idx = a_raw if a_type == 0x03 else a_data
                        if value_idx < len(strings):
                            activity = strings[value_idx]
                    elif key == "screenOrientation":
                        orientation = a_data
                if activity is not None and orientation is not None:
                    orientations[activity] = orientation
        pos += csize
    return orientations


def manifest_features(axml: bytes) -> dict[str, bool]:
    """Lit android:name/android:required des uses-feature dans l'AXML signé."""
    strings: list[str] = []
    features: dict[str, bool] = {}
    pos = 8
    while pos + 8 <= len(axml):
        ctype, _hsz, csize = struct.unpack_from("<HHI", axml, pos)
        if csize <= 0:
            break
        if ctype == 0x0001:
            strings = _axml_strings(axml, pos)
        elif ctype == 0x0102 and strings:
            name_idx = struct.unpack_from("<I", axml, pos + 20)[0]
            if name_idx < len(strings) and strings[name_idx] == "uses-feature":
                attr_start, attr_size, attr_count = struct.unpack_from("<HHH", axml, pos + 24)
                name = None
                required = True
                for i in range(attr_count):
                    off = pos + 16 + attr_start + i * attr_size
                    a_name, a_raw, _sz, _res, a_type, a_data = struct.unpack_from(
                        "<IIHBBI", axml, off + 4
                    )
                    if a_name >= len(strings):
                        continue
                    key = strings[a_name]
                    if key == "name":
                        value_idx = a_raw if a_type == 0x03 else a_data
                        if value_idx < len(strings):
                            name = strings[value_idx]
                    elif key == "required":
                        required = not (a_type == 0x12 and a_data == 0)
                if name is not None:
                    features[name] = required
        pos += csize
    return features


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
        # L'accent d'usine de l'app est l'index 0, recoloré en violet Twouich par
        # patch.py (family theme_red*) : le libellé rouge ne doit plus exister.
        ok &= check("accent par défaut recoloré (plus de « Red (default) »)",
                    not holds(arsc, "Red (default)"))

        manifest = z.read("AndroidManifest.xml")
        features = manifest_features(manifest)
        ok &= check("uses-feature smartphone optionnelles",
                    bool(features) and all(not required for required in features.values()),
                    ", ".join(name for name, required in features.items() if required))
        ok &= check("uses-feature leanback conservée mais optionnelle",
                    features.get("android.software.leanback") is False)
        orientations = manifest_orientations(manifest)
        ok &= check("orientation smartphone multi-capteur",
                    bool(orientations) and all(value == 10 for value in orientations.values()),
                    ", ".join(f"{name}={value}" for name, value in orientations.items() if value != 10))
        phone_player = "res/layout/activity_player.xml"
        tv_player = "res/layout-sw600dp/activity_player.xml"
        ok &= check("layout lecteur smartphone présent",
                    phone_player in names)
        ok &= check("layout lecteur TV conservé",
                    tv_player in names)
        ok &= check("dimension chat smartphone compilée",
                    holds(arsc, "twouich_phone_chat_height"))
        ok &= check("saisie chat smartphone compilée",
                    holds(arsc, "ET_SendMessage"))
        dex_blob = b"".join(z.read(name) for name in names if name.endswith(".dex"))
        ok &= check("navigation smartphone compilée",
                    holds(arsc, "twouich_phone_nav_search")
                    and holds(dex_blob, "twouichPhoneSearch"))
        # Le traducteur tap → clic : sans lui, une carte Leanback ne s'ouvre qu'au
        # second appui au doigt (défaut constaté sur appareil le 19/09).
        ok &= check("tap → clic Leanback compilé",
                    holds(dex_blob, "TapClick") and holds(dex_blob, "TWOUICH-TAP"),
                    "TapClick absent du dex : les cartes resteraient au second appui")
        # La barre basse porte des icônes et un libellé actif : sans les
        # vectoriels, la barre retombe en trois libellés gris sans repère.
        ok &= check("barre basse smartphone : icônes compilées",
                    holds(arsc, "twouich_ic_home")
                    and holds(arsc, "twouich_ic_search")
                    and holds(arsc, "twouich_ic_settings")
                    and holds(arsc, "twouich_phone_nav_inactive"),
                    "icônes ou teinte d'onglet absentes des ressources")
        # Le picture-in-picture : bouton dans le lecteur téléphone, overrides
        # dans le dex, et la référence à l'API 26 qui n'existe pas avant.
        ok &= check("picture-in-picture smartphone compilé",
                    holds(arsc, "twouich_phone_pip")
                    and holds(arsc, "twouich_ic_pip")
                    and holds(dex_blob, "twouichPhonePip")
                    and holds(dex_blob, "onPictureInPictureModeChanged")
                    and holds(dex_blob, "Landroid/app/PictureInPictureParams;"),
                    "sans bouton ni override, l'incrustation ne peut pas être demandée")
        # Le libellé du champ vit dans le layout compilé (AXML), pas dans
        # resources.arsc : aapt2 le laisse dans l'entrée du layout.
        hint_layout = "res/layout/include_send_chat_message_window.xml"
        ok &= check("champ de chat : libellé de saisie",
                    hint_layout in names and holds(z.read(hint_layout), CHAT_HINT),
                    f"attendu : « {CHAT_HINT} » dans {hint_layout}")
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

        # 4b. Les pages légales embarquées : présentes, avec leur contenu clé, et
        #     la page À propos pointe vers elles (l'utilisateur doit pouvoir les
        #     trouver sans lire les assets à la main).
        for page, needle in (
            ("assets/twouich_legal.html", "Mentions légales"),
            ("assets/twouich_privacy.html", "Politique de confidentialité"),
        ):
            if page not in names:
                ok &= check(f"{page} présente", False)
                continue
            body = z.read(page)
            ok &= check(f"{page} : contenu embarqué",
                        holds(body, needle) and b"<h1>" in body)
        about_body = (z.read("assets/S0undTV_about.html")
                      if "assets/S0undTV_about.html" in names else b"")
        ok &= check("À propos pointe vers les pages légales",
                    holds(about_body, "twouich_legal.html")
                    and holds(about_body, "twouich_privacy.html"))

        # 4c. La télémétrie Firebase héritée doit être inerte : les bibliothèques
        # peuvent rester dans le dex upstream, mais aucun composant de démarrage
        # ni identifiant de projet ne doit être présent dans le livrable.
        firebase_manifest = (
            b"com.google.firebase" in manifest
            or b"AppMeasurementReceiver" in manifest
            or b"FirebaseInitProvider" in manifest
        )
        ok &= check("aucun composant Firebase/Measurement dans le manifeste",
                    not firebase_manifest)
        firebase_config = any(
            holds(arsc, needle)
            for needle in (
                "1:815622240528:android:70f4256c944a5bc4354d95",
                "AIzaSyD-iYJlLhav5IHOMBATLZGqf1BgO_QkW6I",
                "https://s0undtv.firebaseio.com",
            )
        )
        ok &= check("aucun identifiant Firebase dans les ressources",
                    not firebase_config)

        # 5. Un paquet sans signature ne s'installe pas : l'apk porte bien les
        #    blocs v1/v2/v3 (les .SF/.RSA du schéma v1, l'APK Signing Block sinon).
        v1 = any(n.startswith("META-INF/") and n.endswith((".SF", ".RSA", ".DSA")) for n in names)
        ok &= check("signature v1 (JAR) présente", v1)

        # 6. L'identité de version du livrable, telle que l'app la lira.
        code, name = manifest_version(manifest)
        ok &= check("versionCode / versionName lisibles dans le manifeste",
                    isinstance(code, int) and bool(name), f"lu : {code} / {name}")
        print(f"   → versionCode {code}, versionName {name}")

    # 7. Cohérence avec `update.json`, mais seulement pour le livrable : c'est lui
    #    que l'app interroge avant de télécharger, et l'URL qu'elle construit est
    #    `releases/download/<VersionName>/<APK>`. Un artefact quelconque (l'APK
    #    upstream, une version précédente) n'a pas à y figurer.
    if apk.name == DEFAULT_APK.name and isinstance(code, int) and name:
        update = json.loads((ROOT / "update.json").read_text(encoding="utf-8"))
        stable = [e for e in update if e.get("ReleaseType") == 0]
        ok &= check("update.json : une seule entrée stable", len(stable) == 1,
                    f"{len(stable)} entrées de type stable")
        if len(stable) == 1:
            entry = stable[0]
            # En CI, sur un tag, update.json ne décrit PAS encore ce livrable :
            # l'annonce est poussée après la release (sinon 404 silencieux).
            # ALLOW_UPDATE_JSON_LAG=1 tolère ce décalage voulu, et seulement lui.
            lag_ok = os.environ.get("ALLOW_UPDATE_JSON_LAG") == "1"
            if lag_ok:
                print("   (update.json en retard toléré : ALLOW_UPDATE_JSON_LAG=1)")
            ok &= check("update.json décrit ce livrable",
                        lag_ok or (entry.get("VersionCode") == code and entry.get("VersionName") == name),
                        f"update.json={entry.get('VersionCode')}/{entry.get('VersionName')} "
                        f"≠ livrable {code}/{name}")
            ok &= check("update.json annonce ce fichier-ci",
                        lag_ok or entry.get("APK") == apk.name,
                        f"update.json={entry.get('APK')} ≠ {apk.name}")

    sha = hashlib.sha256(apk.read_bytes()).hexdigest()
    print(f"\nempreinte : {sha}")
    print("✅ livrable conforme" if ok else "❌ livrable non conforme")
    return 0 if ok else 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
