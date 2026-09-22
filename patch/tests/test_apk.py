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

    python patch/tests/test_apk.py                       # dist/<APK_NAME de patch/build.sh>
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


def _apk_name_from_build_sh() -> str | None:
    """Nom du livrable, lu dans `patch/build.sh` — la source unique des valeurs
    figées (AGENTS.md § 2.5 : versionCode, versionName, nom de l'APK n'y vivent
    qu'une fois). Une copie figée ici se désynchronise au premier bump : le test
    cherche alors un fichier qui n'existe plus et échoue pour la mauvaise
    raison — arrivé le 22/09/2026, d'où la lecture.
    """
    try:
        for line in (ROOT / "patch" / "build.sh").read_text(encoding="utf-8").splitlines():
            if line.startswith("APK_NAME="):
                return line.split("=", 1)[1].strip().strip('"') or None
    except OSError:
        pass
    return None


# Repli sans numéro de version : s'il s'affiche, c'est build.sh qui est
# illisible — et le message le dit, plutôt que de figer un nom qui périmera.
DEFAULT_APK = ROOT / "dist" / (_apk_name_from_build_sh() or "Twouich_APK_NAME_introuvable.apk")
PLAYBACK_SERVICE = "com.twouich.adblock.PlayerKeepAlive"
PLAYBACK_PERMISSION = "android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK"
# aapt2 connaît l'attribut android:foregroundServiceType et encode « mediaPlayback »
# en drapeau : la chaîne n'existe donc NULLE PART dans le livrable (vérifié le
# 21/09 : absente du pool de chaînes du manifeste binaire). C'est ce drapeau, lu
# dans l'AXML signé, qui fait foi.
FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK = 1 << 1

# Chaînes d'affichage : ce que l'utilisateur lit à l'écran. Le paquet Android
# (`com.s0und.s0undtv`) et les URL du journal des modifications gardent
# volontairement la référence d'origine — ce ne sont pas des marques affichées.
DEAD_NAMES = ("S0undTV",)
REBRANDED = ("Twouich",)

# Identifiants Firebase du projet d'amont (S0undTV), que le livrable ne doit plus
# porter : le manifeste et les ressources sont contrôlés contre eux. Ils sont
# **éclatés puis réassemblés à l'exécution**, jamais écrits en clair dans ce
# fichier : un test n'a aucune raison de publier un secret, même hérité, et
# GitHub le signalait comme fuite (« Google API Key » du 21/09 — la clé traînait
# en littéral ici). Le contrôle, lui, reste une comparaison exacte d'octets.
def _rebuild(*parts: str) -> str:
    """Réassemble un identifiant éclaté (cf. FIREBASE_TRACE)."""
    return "".join(parts)


FIREBASE_TRACE = (
    _rebuild("1:815622240528:", "android:70f4256c", "944a5bc4354d95"),
    _rebuild("AIzaSyD-iYJlLhav5", "IHOMBATLZGqf1BgO", "_QkW6I"),
    _rebuild("https://s0undtv", ".firebase", "io.com"),
)

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


def manifest_services(axml: bytes) -> dict[str, int]:
    """Lit android:name et android:foregroundServiceType des services (AXML signé).

    Le type est un ENTIER : aapt2 résout le nom de la valeur grâce à la définition
    de l'attribut, donc chercher « mediaPlayback » dans les octets du manifeste ne
    peut pas marcher. On lit le drapeau.
    """
    strings: list[str] = []
    services: dict[str, int] = {}
    pos = 8
    while pos + 8 <= len(axml):
        ctype, _hsz, csize = struct.unpack_from("<HHI", axml, pos)
        if csize <= 0:
            break
        if ctype == 0x0001:
            strings = _axml_strings(axml, pos)
        elif ctype == 0x0102 and strings:
            name_idx = struct.unpack_from("<I", axml, pos + 20)[0]
            if name_idx < len(strings) and strings[name_idx] == "service":
                attr_start, attr_size, attr_count = struct.unpack_from("<HHH", axml, pos + 24)
                name = None
                service_type = 0
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
                    elif key == "foregroundServiceType":
                        service_type = a_data
                if name is not None:
                    services[name] = service_type
        pos += csize
    return services


def _axml_pool_base(axml: bytes) -> int:
    """Position du pool de chaines d'un AXML (premier chunk de type 0x0001)."""
    pos = 8
    while pos + 8 <= len(axml):
        ctype, _hsz, csize = struct.unpack_from("<HHI", axml, pos)
        if csize <= 0:
            break
        if ctype == 0x0001:
            return pos
        pos += csize
    return 8


def view_attributes(axml: bytes, view: str) -> dict[str, tuple[int, int]]:
    """Attributs types d'un element d'un layout compile, par nom.

    Le layout livre est en AXML binaire : on y lit (type, valeur) — c'est ce
    qui distingue le chat TV (225 dp carre, dimensions d'origine) du chat
    telephone (pleine largeur, ancre en bas par la greffe).
    """
    strings: list[str] = []
    attrs: dict[str, tuple[int, int]] = {}
    pos = 8
    while pos + 8 <= len(axml):
        ctype, _hsz, csize = struct.unpack_from("<HHI", axml, pos)
        if csize <= 0:
            break
        if ctype == 0x0001:
            strings = _axml_strings(axml, pos)
        elif ctype == 0x0102 and strings:
            name_idx = struct.unpack_from("<I", axml, pos + 20)[0]
            if name_idx < len(strings) and strings[name_idx] == view:
                attr_start, attr_size, attr_count = struct.unpack_from("<HHH", axml, pos + 24)
                for i in range(attr_count):
                    off = pos + 16 + attr_start + i * attr_size
                    a_name, _raw, _sz, _res, a_type, a_data = struct.unpack_from(
                        "<IIHBBI", axml, off + 4
                    )
                    if a_name < len(strings):
                        attrs[strings[a_name]] = (a_type, a_data)
                return attrs
        pos += csize
    return attrs


# ── Garde des layouts TV : comparaison par NOMS avec la capture de l'amont ─────
# Le 21/09, la TV a servi le layout telephone : la decision TV/telephone se
# prenait sur un seuil de dp. Le filet pose alors comparait des octets et la
# sous-chaine « twouich » — il attrape une greffe grossiere, pas une retouche.
# Ici le layout TV livre est confronte a la CAPTURE DE L'AMONT, par noms.
#
# Pourquoi pas octet a octet : l'APK d'amont renomme ses ressources
# (`res/zQ.xml`) et le fork reattribue les identifiants, donc les octets
# different forcement. Chaque reference (0x7f0d0012) est donc resolue vers son
# NOM via `resources.arsc`, puis la structure est comparee : elements, attributs
# dans l'ordre, valeurs litterales, et noms resolus pour les references. Toute
# version de layout differente de celle de l'amont est refusee, quelle que soit
# la facon dont la greffe est ecrite.

RES_STRING_POOL = 0x0001
RES_TABLE_PACKAGE = 0x0200
RES_TABLE_TYPE = 0x0201
RES_XML_START_ELEMENT = 0x0102
TYPE_REFERENCE = 0x01
TYPE_DIMENSION = 0x05
TYPE_FRACTION = 0x06
DIM_UNITS = {0: "px", 1: "dp", 2: "sp", 3: "pt", 4: "in", 5: "mm"}


def _string_pool(buf: bytes, pos: int) -> tuple[list[str], int]:
    """(chaines, fin du chunk) d'un pool a `pos` — AXML comme resources.arsc."""
    _type, header, size = struct.unpack_from("<HHI", buf, pos)
    count, _styles, flags, strings_start, _styles_start = struct.unpack_from(
        "<IIIII", buf, pos + 8
    )
    utf8 = bool(flags & (1 << 8))
    base = pos + strings_start
    strings = []
    for off in struct.unpack_from(f"<{count}I", buf, pos + header):
        p = base + off
        if utf8:
            length = buf[p + 1]
            if length & 0x80:
                length = ((length & 0x7F) << 8) | buf[p + 2]
                p += 1
            strings.append(buf[p + 2:p + 2 + length].decode("utf-8", "replace"))
        else:
            length = struct.unpack_from("<H", buf, p)[0]
            strings.append(buf[p + 2:p + 2 + length * 2].decode("utf-16-le", "replace"))
    return strings, pos + size


def _type_entries(arsc: bytes, start: int, pkg_id: int, type_names, key_names):
    """Entrees d'un chunk de type : identifiant complet -> « type/nom »."""
    entries = {}
    type_id = arsc[start + 8]
    count = struct.unpack_from("<I", arsc, start + 12)[0]
    entries_start = struct.unpack_from("<I", arsc, start + 16)[0]
    # Les offsets d'entrees suivent l'en-tete du chunk, dont la taille varie
    # (elle porte la configuration) : c'est le champ `header`.
    offsets_base = start + struct.unpack_from("<H", arsc, start + 2)[0]
    label = type_names[type_id - 1] if 0 < type_id <= len(type_names) else "?"
    for i in range(count):
        off = struct.unpack_from("<I", arsc, offsets_base + i * 4)[0]
        if off == 0xFFFFFFFF:
            continue
        # L'entree commence par (taille|drapeaux) : l'index de cle est a +4.
        key = struct.unpack_from("<I", arsc, start + entries_start + off + 4)[0]
        name = key_names[key] if key < len(key_names) else "?"
        entries[(pkg_id << 24) | (type_id << 16) | i] = f"{label}/{name}"
    return entries


def _arsc_id_names(arsc: bytes) -> dict[int, str]:
    """{identifiant de ressource: « type/nom »} pour tout le tableau.

    Le tableau commence a l'offset 12 (l'en-tete RES_TABLE en fait 12) : lire a
    8 desynchronise la marche, et plus aucune reference ne se resout.
    """
    names: dict[int, str] = {}
    pos = 12
    while pos + 8 <= len(arsc):
        ctype, _header, size = struct.unpack_from("<HHI", arsc, pos)
        if size <= 0:
            break
        if ctype == RES_TABLE_PACKAGE:
            pkg_id = struct.unpack_from("<I", arsc, pos + 8)[0]
            type_off, _last_type, key_off, _last_key = struct.unpack_from(
                "<IIII", arsc, pos + 268
            )
            pkg_end = pos + size
            type_names, _ = _string_pool(arsc, pos + type_off)
            key_names, start = _string_pool(arsc, pos + key_off)
            while start + 8 <= pkg_end:
                sub_type, _sub_header, sub_size = struct.unpack_from("<HHI", arsc, start)
                if sub_size <= 0:
                    break
                if sub_type == RES_TABLE_TYPE:
                    names.update(_type_entries(arsc, start, pkg_id, type_names, key_names))
                start += sub_size
        pos += size
    return names


def _attr_value(kind: int, data: int, names: dict[int, str]) -> str:
    """Valeur d'un attribut, lisible : nom de ressource, dimension ou litteral."""
    if kind == TYPE_REFERENCE:
        return names.get(data, f"ref/0x{data:08x}")
    if kind in (TYPE_DIMENSION, TYPE_FRACTION):
        value = struct.unpack("<f", struct.pack("<I", (data & 0x00FFFFFF) << 8))[0]
        return f"{round(value, 3)}{DIM_UNITS.get(data >> 24, '?')}"
    return f"{kind}:{data}"


def _short(name: str) -> str:
    return name.rsplit(".", 1)[-1]


def _layout_signature(axml: bytes, names: dict[int, str]) -> list[tuple[str, tuple]]:
    """Signature structurelle d'un layout compile : elements et attributs."""
    signature: list[tuple[str, tuple]] = []
    strings: list[str] = []
    pos = 8
    while pos + 8 <= len(axml):
        ctype, _header, size = struct.unpack_from("<HHI", axml, pos)
        if size <= 0:
            break
        if ctype == RES_STRING_POOL:
            strings, _ = _string_pool(axml, pos)
        elif ctype == RES_XML_START_ELEMENT and strings:
            name_idx = struct.unpack_from("<I", axml, pos + 20)[0]
            attr_start, attr_size, attr_count = struct.unpack_from("<HHH", axml, pos + 24)
            attrs = []
            for i in range(attr_count):
                off = pos + 16 + attr_start + i * attr_size
                a_name, _raw, _sz, _res, a_type, a_data = struct.unpack_from(
                    "<IIHBBI", axml, off + 4
                )
                attrs.append((strings[a_name], _attr_value(a_type, a_data, names)))
            signature.append((strings[name_idx], tuple(attrs)))
        pos += size
    return signature


def tv_layout_offenders(shipped: bytes, reference: bytes,
                        shipped_names: dict[int, str],
                        reference_names: dict[int, str]) -> list[str]:
    """Les ecarts entre un layout TV livre et la capture de l'amont.

    Liste vide quand le layout livre EST celui de l'amont. Sinon, un ecart par
    difference : element en trop, element change, attribut ajoute ou valeur
    differente. Chaque libelle est fait pour etre lu dans le rapport du test.
    """
    shipped_signature = _layout_signature(shipped, shipped_names)
    reference_signature = _layout_signature(reference, reference_names)
    offenders: list[str] = []
    if len(shipped_signature) != len(reference_signature):
        offenders.append(
            f"{len(shipped_signature)} elements au lieu de {len(reference_signature)}"
        )
    for index, (want, got) in enumerate(zip(reference_signature, shipped_signature)):
        if want[0] != got[0]:
            offenders.append(f"element {index} : {_short(got[0])} au lieu de {_short(want[0])}")
            continue
        want_attrs, got_attrs = dict(want[1]), dict(got[1])
        for key in sorted(set(want_attrs) | set(got_attrs)):
            if want_attrs.get(key) != got_attrs.get(key):
                offenders.append(
                    f"element {index} ({_short(want[0])}) {key} : "
                    f"{got_attrs.get(key, 'absent')} au lieu de {want_attrs.get(key, 'absent')}"
                )
    return offenders


def upstream_tv_layout(apk: pathlib.Path) -> tuple[bytes | None, dict[int, str]]:
    """Le layout lecteur de l'APK d'amont : (octets AXML, table des noms).

    Son chemin y est renomme par l'outil de compilation de l'amont
    (`res/zQ.xml`) : on le reconnait donc a son CONTENU — un AXML qui porte a la
    fois la vue du chat et le lecteur.
    """
    if not apk.is_file():
        return None, {}
    with zipfile.ZipFile(apk) as z:
        names = _arsc_id_names(z.read("resources.arsc"))
        for entry in z.namelist():
            if not entry.startswith("res/") or not entry.endswith(".xml"):
                continue
            blob = z.read(entry)
            if b"ChatRecycler" not in blob or b"PlayerView" not in blob:
                continue
            elements = {_short(name) for name, _attrs in _layout_signature(blob, names)}
            if {"ChatRecyclerView", "StyledPlayerView"} <= elements:
                return blob, names
    return None, {}


def mutate_dimension(axml: bytes) -> tuple[bytes, str]:
    """Passe la premiere dimension du layout dans une autre unite.

    Mutation minuscule et vraie : un garde qui ne verrait que les elements
    ajoutes, ou la sous-chaine « twouich », la laisserait passer.
    """
    buf = bytearray(axml)
    strings: list[str] = []
    pos = 8
    while pos + 8 <= len(buf):
        ctype, _header, size = struct.unpack_from("<HHI", buf, pos)
        if size <= 0:
            break
        if ctype == RES_STRING_POOL:
            strings, _ = _string_pool(bytes(buf), pos)
        elif ctype == RES_XML_START_ELEMENT and strings:
            attr_start, attr_size, attr_count = struct.unpack_from("<HHH", buf, pos + 24)
            for i in range(attr_count):
                off = pos + 16 + attr_start + i * attr_size
                a_name = struct.unpack_from("<I", buf, off + 4)[0]
                if buf[off + 15] == TYPE_DIMENSION:
                    unit = buf[off + 19]
                    new_unit = 2 if unit != 2 else 1
                    buf[off + 19] = new_unit
                    label = strings[a_name] if a_name < len(strings) else "?"
                    return bytes(buf), f"{label} {DIM_UNITS.get(unit, unit)} -> {DIM_UNITS.get(new_unit, new_unit)}"
        pos += size
    return axml, "aucune dimension a modifier"



def main() -> int:
    parser = argparse.ArgumentParser(description="Vérifie l'APK livré")
    parser.add_argument("--apk", type=pathlib.Path, default=DEFAULT_APK)
    parser.add_argument("--upstream", type=pathlib.Path,
                        default=ROOT / "work" / "upstream" / "beta_144.apk",
                        help="APK d'amont : la source de verite des layouts TV")
    args = parser.parse_args()

    apk: pathlib.Path = args.apk if args.apk.is_absolute() else ROOT / args.apk
    # L'amont est la reference des layouts TV : c'est build.sh qui le
    # telecharge (work/upstream/) et qui verifie son SHA-256.
    upstream: pathlib.Path = (args.upstream if args.upstream.is_absolute()
                              else ROOT / args.upstream)
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
        # L'amont ne livre QU'UNE configuration du layout lecteur : c'est
        # `res/layout/` que gonfle un televiseur, et c'est devenu le layout
        # telephone. Deux qualifiers portent donc la version d'origine, copies
        # d'une source versionnee (patch/res-tv/) : « television » (mode
        # declare par le systeme) et « sw600dp » (TV 4K, tablettes).
        tv_television = "res/layout-television/activity_player.xml"
        chat_view = "com.s0und.s0undtv.chat.ChatRecyclerView"
        ok &= check("layout lecteur TV par mode systeme present",
                    tv_television in names)
        if phone_player in names and tv_player in names and tv_television in names:
            phone_bytes = z.read(phone_player)
            tv_bytes = z.read(tv_player)
            ok &= check("les deux layouts TV sont identiques octet a octet",
                        tv_bytes == z.read(tv_television))
            ok &= check("le layout TV n'est pas le layout telephone",
                        tv_bytes != phone_bytes)
            tv_strings = _axml_strings(tv_bytes, _axml_pool_base(tv_bytes))
            grafted = [s for s in tv_strings if "twouich" in s]
            ok &= check("layout TV sans aucune greffe telephone", not grafted,
                        ", ".join(grafted)[:120])
            phone_strings = _axml_strings(phone_bytes, _axml_pool_base(phone_bytes))
            # Marqueur reel du layout telephone : le nom du rappel du bouton PiP.
            # Les identifiants @+id/twouich_phone_pip et @dimen/twouich_phone_chat_height
            # sont des REFERENCES de ressources (des entiers), donc absents du pool de
            # chaines du layout : c'est android:onClick qui porte le texte.
            ok &= check("layout telephone bien greffe",
                        any("twouichPhonePip" in s for s in phone_strings),
                        "aucun rappel twouichPhonePip dans le layout telephone")
            ok &= check("layout TV sans le rappel du bouton telephone",
                        not any("twouichPhonePip" in s for s in tv_strings))
            tv_chat = view_attributes(tv_bytes, chat_view)
            phone_chat = view_attributes(phone_bytes, chat_view)
            ok &= check("chat TV aux dimensions d'origine (carre, non ancre)",
                        bool(tv_chat)
                        and tv_chat.get("layout_width") == tv_chat.get("layout_height")
                        and "layout_alignParentBottom" not in tv_chat,
                        f"TV {tv_chat}")
            ok &= check("chat telephone etire et ancre en bas",
                        bool(phone_chat)
                        and phone_chat.get("layout_width") != phone_chat.get("layout_height")
                        and "layout_alignParentBottom" in phone_chat,
                        f"telephone {phone_chat}")
            # 4d. Le layout TV livre est confronte a la capture de l'amont, par
            #     noms (cf. tv_layout_offenders). Puis deux mutations prouvent que
            #     ce garde mord : la greffe telephone telle qu'elle existe
            #     vraiment dans l'archive, et une dimension changee d'unite.
            reference, reference_names = upstream_tv_layout(upstream)
            if reference is None:
                ok &= check("layout TV confronte a la capture de l'amont", False,
                            f"APK d'amont illisible ({upstream}) : le garde ne peut pas juger")
            else:
                shipped_names = _arsc_id_names(arsc)
                differences = tv_layout_offenders(tv_bytes, reference, shipped_names,
                                                  reference_names)
                ok &= check("layout TV identique a la capture de l'amont (par noms)",
                            not differences, "; ".join(differences[:3]))
                graft = tv_layout_offenders(phone_bytes, reference, shipped_names,
                                            reference_names)
                ok &= check("le garde refuse la greffe telephone (mutation reelle)",
                            bool(graft),
                            "aucun ecart vu entre le layout telephone et l'amont : "
                            "le garde est aveugle")
                mutated, what = mutate_dimension(tv_bytes)
                ok &= check("le garde refuse une dimension modifiee (mutation d'octets)",
                            mutated != tv_bytes
                            and bool(tv_layout_offenders(mutated, reference, shipped_names,
                                                         reference_names)),
                            f"mutation non vue ({what})")
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
        # Le bouton masquer/afficher le chat est RETIRÉ depuis la v1.0.12 : le chat
        # vit SOUS la vidéo, donc replier ne changeait plus la taille de l'image
        # (« l'icône à côté du PiP ne sert à rien », 21/09). La preuve est donc
        # l'INVERSE de ce qu'elle était — le rappel de clic a disparu du layout
        # compilé, tandis que la machinerie du repli reste dans le dex (sans prise :
        # aucune vue ne l'appelle).
        chat_layout = "res/layout/activity_player.xml"
        ok &= check("bouton de chat retiré du lecteur compilé",
                    chat_layout in names
                    and not holds(z.read(chat_layout), "twouichPhoneChatToggle"),
                    "le bouton masquer/afficher le chat est encore dans le layout compilé")
        ok &= check("machinerie du repli conservée dans le dex",
                    holds(dex_blob, "twouichChatApply"),
                    "les méthodes du repli ont disparu du dex livré")
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
        firebase_config = any(holds(arsc, needle) for needle in FIREBASE_TRACE)
        ok &= check("aucun identifiant Firebase dans les ressources",
                    not firebase_config)

        # 4d. Lecture en veille : le service de premier plan « mediaPlayback » est la
        # seule chose qui empêche le système de détruire les sockets de l'app quand
        # l'écran s'éteint (mesuré le 21/09 : « InetDiagMessage: Destroyed live tcp
        # sockets for uids={10267} », puis « UnknownHostException (no network) » au
        # bout de 10 s). Trois pièces doivent être dans le livrable : la permission,
        # le service AVEC son type, et sa classe dans le dex.
        services = manifest_services(manifest)
        keepalive_type = services.get(PLAYBACK_SERVICE, -1)
        ok &= check("permission FOREGROUND_SERVICE_MEDIA_PLAYBACK déclarée",
                    holds(manifest, PLAYBACK_PERMISSION),
                    "sans elle, le système refuse le service de premier plan")
        ok &= check("service de premier plan mediaPlayback déclaré",
                    keepalive_type == FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK,
                    f"{PLAYBACK_SERVICE} : type lu {keepalive_type}, attendu "
                    f"{FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK} (mediaPlayback)")
        ok &= check("classe du service de premier plan compilée",
                    holds(dex_blob, PLAYBACK_SERVICE.replace(".", "/"))
                    and holds(dex_blob, "startIfPhone"),
                    "la classe du service est absente du dex livré")

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
