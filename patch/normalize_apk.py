#!/usr/bin/env python3
"""
normalize_apk.py — rend le build reproductible au sens strict, sur toute plateforme.

Deux non-déterminismes du ZIP produit par `apktool b` sont réécrits ici :

1. **L'horodatage** — chaque entrée (header local + central directory) est
   estampillée à l'heure du build : réécrite vers une constante
   (1980-01-01 00:00:00 — le minimum encodable au format ZIP).

2. **L'ordre des entrées** — apktool énumère le système de fichiers, donc
   l'ordre du ZIP dépend de la plateforme de build (Windows ≠ Linux). Or
   l'ordre décale les offsets, donc les digests `MANIFEST.MF` (signature v1)
   et le bloc v2 signe un fichier différent : le SHA-256 du livrable ne se
   reproduisait qu'à plateforme identique. Les entrées sont re-séquencées
   ici par tri sur le **nom brut en octets** (comparaison canonique, sans
   décodage) ; les offsets du central directory et de l'EOCD sont recalculés.

Ce que le script ne change PAS, pour chaque entrée : les octets compressés,
les CRC, les tailles, les flags, la méthode, les champs extra, le commentaire —
tous copiés tels quels. En particulier :

  * la réécriture se fait au niveau octet, pas via `zipfile` (qui
    recompresserait et changerait les CRC) ;
  * chaque horodatage existe en DEUX exemplaires (header local + entrée du
    central directory) : les deux sont corrigés, l'égalité des noms
    LFH/CDH servant de garde-fou d'intégrité ;
  * à exécuter APRÈS `apktool b` et AVANT la signature (et zipalign) : les
    blocs v2/v3 d'apksig couvrent le central directory, normaliser après les
    casserait ;
  * le résultat est idempotent : normaliser deux fois ne change rien, et un
    fichier déjà canonique est reconstruit à l'octet près.

Deux cas restent refusés bruyamment : les noms dupliqués (l'ordre ne serait
plus canonique) et un ZIP64 (pas attendu pour un APK apktool). Les
**descripteurs de données** (flag 0x0008 — `apktool b` écrit en flux et en
utilise massivement : LFH avec CRC/tailles à zéro, descripteur 12 octets
après les données, valeurs réelles dans le central directory) sont en
revanche supportés et recopiés tels quels : leur longueur (12, ou 16 avec
la signature optionnelle `PK\x07\x08`) est déduite de la disposition
séquentielle d'origine — offset du header local suivant, ou début du
central directory pour la dernière entrée.

    python patch/normalize_apk.py work/build/twouich_unsigned.apk   # in-place
    python patch/normalize_apk.py --check dist/Twouich_v1.0.4.apk   # 0 = canonique
"""
from __future__ import annotations

import argparse
import pathlib
import struct
import sys

# EOCD (end of central directory) et signatures de structure ZIP.
EOCD_SIG = b"PK\x05\x06"
ZIP64_EOCD_SIG = b"PK\x06\x06"
LFH_SIG = b"PK\x03\x04"  # local file header
CDH_SIG = b"PK\x01\x02"  # central directory header
DATA_DESCRIPTOR_FLAG = 0x0008

# Horodatage DOS constant : 1980-01-01 00:00:00.
# Mot 1 (mod time) = 0x0000 ; mot 2 (mod date) = 0x0021 ((1980-1980)<<9 | 1<<5 | 1).
STAMP = b"\x00\x00\x21\x00"
STAMP_ISO = "1980-01-01 00:00:00"


def find_eocd(data: bytes) -> int:
    """Retourne l'offset de l'EOCD valide, ou lève ValueError.

    Un fichier stocké sans compression peut contenir la signature par hasard :
    on ne retient un candidat que si ses propres champs se recoupent
    (nb d'entrées, fin du central directory juste avant l'EOCD).
    """
    pos = len(data)
    while True:
        pos = data.rfind(EOCD_SIG, 0, pos)
        if pos == -1:
            raise ValueError("EOCD introuvable — ce fichier n'est pas un ZIP")
        n_entries = struct.unpack_from("<H", data, pos + 10)[0]
        cd_size = struct.unpack_from("<I", data, pos + 12)[0]
        cd_off = struct.unpack_from("<I", data, pos + 16)[0]
        if cd_off + cd_size == pos and n_entries > 0:
            return pos


def _read_eocd(data: bytes, eocd_off: int) -> tuple[int, int, int]:
    """Champs utiles de l'EOCD : (nb entrées, taille CD, offset CD)."""
    if data.rfind(ZIP64_EOCD_SIG) != -1:
        raise ValueError("ZIP64 non supporté (pas attendu pour un APK apktool)")
    return (
        struct.unpack_from("<H", data, eocd_off + 10)[0],
        struct.unpack_from("<I", data, eocd_off + 12)[0],
        struct.unpack_from("<I", data, eocd_off + 16)[0],
    )


def _iter_cd_entries(data: bytes, cd_off: int, cd_size: int, n_entries: int):
    """Itère les entrées du central directory : (offset CDH, offset LFH, nom)."""
    off = cd_off
    for _ in range(n_entries):
        if data[off:off + 4] != CDH_SIG:
            raise ValueError(f"central directory corrompu (signature attendue @ {off})")
        nlen, elen, clen = struct.unpack_from("<HHH", data, off + 28)
        lfh_off = struct.unpack_from("<I", data, off + 42)[0]
        name = data[off + 46:off + 46 + nlen]
        yield off, lfh_off, name
        off += 46 + nlen + elen + clen
    if off != cd_off + cd_size:
        raise ValueError("central directory : taille annoncée ≠ parcourue")


class _Entry:
    """Une entrée ZIP complète : header local, données (+ descripteur), CDH.

    Les octets sont conservés tels quels ; seuls l'horodatage (4 octets,
    présent dans le LFH et le CDH) et l'offset du header local (dans le CDH)
    sont réécrits à la reconstruction.
    """

    __slots__ = ("name", "lfh", "body", "cdh")

    def __init__(self, name: bytes, lfh: bytes, body: bytes, cdh: bytes):
        self.name = name
        self.lfh = lfh
        self.body = body
        self.cdh = cdh


def _load_entries(data: bytes, eocd_off: int) -> list[_Entry]:
    """Découpe le ZIP en entrées complètes (LFH + données [+ descripteur] + CDH).

    La longueur du descripteur de données (entrées en flux, flag 0x0008)
    est déduite de la disposition séquentielle : les données d'une entrée
    s'arrêtent au header local suivant (ou au central directory pour la
    dernière). Déterministe, et validé : 12 octets, ou 16 avec signature.
    """
    n_entries, cd_size, cd_off = _read_eocd(data, eocd_off)
    cd_entries = list(_iter_cd_entries(data, cd_off, cd_size, n_entries))
    entries: list[_Entry] = []
    for i, (cdh_off, lfh_off, name) in enumerate(cd_entries):
        nlen_c, elen_c, clen_c = struct.unpack_from("<HHH", data, cdh_off + 28)
        cdh = bytes(data[cdh_off:cdh_off + 46 + nlen_c + elen_c + clen_c])
        flags = struct.unpack_from("<H", cdh, 8)[0]
        streamed = bool(flags & DATA_DESCRIPTOR_FLAG)
        comp_size = struct.unpack_from("<I", cdh, 20)[0]
        nlen_l = struct.unpack_from("<H", data, lfh_off + 26)[0]
        elen_l = struct.unpack_from("<H", data, lfh_off + 28)[0]
        lfh = bytes(data[lfh_off:lfh_off + 30 + nlen_l + elen_l])
        if data[lfh_off + 30:lfh_off + 30 + nlen_l] != name:
            raise ValueError(f"nom LFH ≠ nom CDH pour {name!r} — abandon par précaution")
        if not streamed and lfh[18:22] != cdh[20:24]:
            raise ValueError(f"taille compressée LFH ≠ CDH pour {name!r}")
        body_start = lfh_off + 30 + nlen_l + elen_l
        body_end = body_start + comp_size
        if streamed:
            # Fin réelle = début du header local suivant, ou du CD pour la dernière.
            boundary = cd_entries[i + 1][1] if i + 1 < len(cd_entries) else cd_off
            desc_len = boundary - body_end
            if desc_len not in (12, 16):
                raise ValueError(
                    f"descripteur de données de longueur inattendue ({desc_len}) pour {name!r}")
            if desc_len == 16:
                if data[body_end:body_end + 4] != b"PK\x07\x08":
                    raise ValueError(f"signature de descripteur absente pour {name!r}")
            desc = bytes(data[body_end:body_end + desc_len])
        else:
            desc = b""
        body = bytes(data[body_start:body_end])
        if len(body) != comp_size:
            raise ValueError(f"données de {name!r} tronquées")
        entries.append(_Entry(name, lfh, body + desc, cdh))
    return entries


def _entry_names(data: bytes) -> list[bytes]:
    """Noms des entrées, dans l'ordre du central directory."""
    eocd_off = find_eocd(data)
    n_entries, cd_size, cd_off = _read_eocd(data, eocd_off)
    return [name for _, _, name in _iter_cd_entries(data, cd_off, cd_size, n_entries)]


def issues(data: bytes) -> tuple[int, int]:
    """(nb d'horodatages non conformes, nb d'entrées hors ordre canonique)."""
    names = _entry_names(data)
    bad_stamps = 0
    eocd_off = find_eocd(data)
    n_entries, cd_size, cd_off = _read_eocd(data, eocd_off)
    for off, _, _ in _iter_cd_entries(data, cd_off, cd_size, n_entries):
        if data[off + 12:off + 16] != STAMP:
            bad_stamps += 1
    misplaced = sum(1 for a, b in zip(names, sorted(names)) if a != b)
    return bad_stamps, misplaced


def normalize(path: str | pathlib.Path) -> tuple[int, bool]:
    """Canonise `path` in-place (horodatage constant + ordre trié par nom).

    Retourne (nb d'horodatages corrigés, ordre réécrit ?). Si le fichier est
    déjà canonique, il est reconstruit à l'octet près et rien n'est écrit.
    """
    data = pathlib.Path(path).read_bytes()
    eocd_off = find_eocd(data)
    entries = _load_entries(data, eocd_off)

    names = [e.name for e in entries]
    if len(set(names)) != len(names):
        raise ValueError("noms d'entrées dupliqués — l'ordre ne serait plus canonique")
    ordered = sorted(entries, key=lambda e: e.name)
    reordered = [e.name for e in ordered] != names

    out = bytearray()
    new_offsets: dict[bytes, int] = {}
    for e in ordered:
        lfh = bytearray(e.lfh)
        lfh[10:14] = STAMP
        new_offsets[e.name] = len(out)
        out += lfh
        out += e.body

    cd_start = len(out)
    stamped = 0
    for e in ordered:
        cdh = bytearray(e.cdh)
        if cdh[12:16] != STAMP:
            stamped += 1
        cdh[12:16] = STAMP
        struct.pack_into("<I", cdh, 42, new_offsets[e.name])
        out += cdh
    cd_size = len(out) - cd_start

    # EOCD + commentaire éventuel : seuls cd_size et cd_off sont réécrits.
    eocd = bytearray(data[eocd_off:])
    struct.pack_into("<I", eocd, 12, cd_size)
    struct.pack_into("<I", eocd, 16, cd_start)
    out += eocd

    if bytes(out) == data:
        return 0, False  # déjà canonique : reconstruction identique, pas d'écriture
    pathlib.Path(path).write_bytes(bytes(out))
    return stamped, reordered


def main() -> int:
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Canonise un APK ZIP : horodatage constant + ordre des entrées trié par nom")
    parser.add_argument("apk", help="APK à normaliser (in-place) ou à vérifier (--check)")
    parser.add_argument("--check", action="store_true",
                        help="ne modifie rien : exit 0 si déjà canonique, 1 sinon")
    args = parser.parse_args()

    data = pathlib.Path(args.apk).read_bytes()
    if args.check:
        bad_stamps, misplaced = issues(data)
        if bad_stamps or misplaced:
            if bad_stamps:
                print(f"❌ {bad_stamps} entrée(s) non normalisée(s) dans {args.apk}")
            if misplaced:
                print(f"❌ ordre des entrées non canonique ({misplaced} mal placée(s)) : {args.apk}")
            return 1
        print(f"✅ ZIP canonique (horodatage {STAMP_ISO}, ordre trié par nom) : {args.apk}")
        return 0

    stamped, reordered = normalize(args.apk)
    if stamped == 0 and not reordered:
        print(f"✅ déjà canonique (horodatage {STAMP_ISO}, ordre trié) : {args.apk}")
    else:
        parts = []
        parts.append(f"{stamped} entrée(s) horodatées → {STAMP_ISO}" if stamped
                     else "horodatage déjà constant")
        parts.append("ordre des entrées canonisé (tri par nom)" if reordered
                     else "ordre déjà canonique")
        print(f"✅ {', '.join(parts)} : {args.apk}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
