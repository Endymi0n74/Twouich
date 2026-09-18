#!/usr/bin/env python3
"""
normalize_apk.py — rend le build reproductible au sens strict.

apktool estampille chaque entrée ZIP (header local + central directory) à
l'heure du build : deux exécutions de la même recette produisent donc des
octets différents, alors même que toutes les entrées restent identiques au
CRC. Ce script réécrit l'horodatage DOS de chaque entrée vers une constante
(1980-01-01 00:00:00 — le minimum encodable au format ZIP) et **rien d'autre** :

  * les octets compressés, les CRC et l'ordre des entrées sont intacts —
    la comparaison `unzip -v` avec un APK historique reste significative ;
  * la réécriture se fait au niveau octet, pas via `zipfile` (qui
    recompresserait et changerait les CRC) ;
  * chaque horodatage existe en DEUX exemplaires (header local + entrée du
    central directory) : les deux sont corrigés, l'égalité des noms
    LFH/CDH servant de garde-fou d'intégrité ;
  * à exécuter APRÈS `apktool b` et AVANT la signature : les blocs v2/v3
    d'apksig couvrent le central directory, normaliser après les casserait ;
  * le résultat est idempotent : normaliser deux fois ne change rien.

    python patch/normalize_apk.py work/build/twouich_unsigned.apk   # in-place
    python patch/normalize_apk.py --check dist/Twouich_v1.0.4.apk   # 0 = normalisé
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
        (n_entries, cd_size, cd_off) = struct.unpack_from("<HxxHII", data, pos + 8)[0], \
            struct.unpack_from("<I", data, pos + 12)[0], \
            struct.unpack_from("<I", data, pos + 16)[0]
        if cd_off + cd_size == pos and n_entries > 0:
            return pos


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


def count_unnormalized(data: bytes) -> int:
    """Nombre d'entrées dont l'horodatage (CDH) diffère de la constante."""
    eocd = find_eocd(data)
    n_entries, cd_size, cd_off = struct.unpack_from("<H", data, eocd + 10)[0], \
        struct.unpack_from("<I", data, eocd + 12)[0], \
        struct.unpack_from("<I", data, eocd + 16)[0]
    if data.rfind(ZIP64_EOCD_SIG) != -1:
        raise ValueError("ZIP64 non supporté (pas attendu pour un APK apktool)")
    bad = 0
    for off, _lfh_off, _name in _iter_cd_entries(data, cd_off, cd_size, n_entries):
        if data[off + 12:off + 16] != STAMP:
            bad += 1
    return bad


def normalize(path: str | pathlib.Path) -> int:
    """Normalise l'horodatage ZIP de `path` in-place. Retourne le nb d'entrées corrigées.

    Seuls les 4 octets date+time de chaque entrée sont modifiés, dans le
    central directory ET dans le header local correspondant. Tout le reste
    (octets compressés, CRC, champs extra, ordre) est intact.
    """
    data = bytearray(pathlib.Path(path).read_bytes())
    if data.rfind(ZIP64_EOCD_SIG) != -1:
        raise ValueError("ZIP64 non supporté (pas attendu pour un APK apktool)")
    eocd = find_eocd(data)
    n_entries, cd_size, cd_off = struct.unpack_from("<H", data, eocd + 10)[0], \
        struct.unpack_from("<I", data, eocd + 12)[0], \
        struct.unpack_from("<I", data, eocd + 16)[0]

    patched = 0
    for off, lfh_off, name in _iter_cd_entries(data, cd_off, cd_size, n_entries):
        if data[off + 12:off + 16] != STAMP:
            data[off + 12:off + 16] = STAMP
            patched += 1
        # Header local correspondant : même correction, garde-fou d'intégrité.
        if data[lfh_off:lfh_off + 4] != LFH_SIG:
            raise ValueError(f"header local introuvable @ {lfh_off} ({name!r})")
        nlen_lfh = struct.unpack_from("<H", data, lfh_off + 26)[0]
        if data[lfh_off + 30:lfh_off + 30 + nlen_lfh] != name:
            raise ValueError(f"nom LFH ≠ nom CDH pour {name!r} — abandon par précaution")
        if data[lfh_off + 10:lfh_off + 14] != STAMP:
            data[lfh_off + 10:lfh_off + 14] = STAMP

    pathlib.Path(path).write_bytes(bytes(data))
    return patched


def main() -> int:
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Normalise l'horodatage ZIP d'un APK")
    parser.add_argument("apk", help="APK à normaliser (in-place) ou à vérifier (--check)")
    parser.add_argument("--check", action="store_true",
                        help="ne modifie rien : exit 0 si déjà normalisé, 1 sinon")
    args = parser.parse_args()

    data = pathlib.Path(args.apk).read_bytes()
    if args.check:
        bad = count_unnormalized(data)
        if bad:
            print(f"❌ {bad} entrée(s) non normalisée(s) dans {args.apk}")
            return 1
        print(f"✅ horodatage ZIP normalisé ({STAMP_ISO}) : {args.apk}")
        return 0

    patched = normalize(args.apk)
    if patched == 0:
        print(f"✅ déjà normalisé ({STAMP_ISO}) : {args.apk}")
    else:
        print(f"✅ {patched} entrée(s) horodatées → {STAMP_ISO} : {args.apk}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
