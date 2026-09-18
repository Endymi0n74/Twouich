#!/usr/bin/env python3
"""
test_normalize_apk.py — vérifie patch/normalize_apk.py.

Le normaliseur réécrit l'horodatage ZIP d'un APK au niveau octet. Ce test
garantit qu'il ne touche QUE l'horodatage (header local + central directory),
en s'appuyant sur un ZIP synthétique aux propriétés connues :

  * CRC et octets compressés inchangés après normalisation ;
  * les seuls octets modifiés sont les 4 (date+time) du central directory et
    les 4 du header local, pour chaque entrée — rien d'autre ;
  * une fausse signature EOCD glissée dans les données d'une entrée stockée
    ne le trompe pas (le candidat retenu doit recouper ses propres champs) ;
  * idempotence : normaliser deux fois ne change plus rien ;
  * --check ne modifie rien et rend 0/1 selon l'état.

    python patch/tests/test_normalize_apk.py
"""
from __future__ import annotations

import io
import pathlib
import struct
import subprocess
import sys
import tempfile
import zipfile

HERE = pathlib.Path(__file__).resolve().parent
NORMALIZE = HERE.parent / "normalize_apk.py"
STAMP = b"\x00\x00\x21\x00"  # 1980-01-01 00:00:00, tel qu'écrit par le normaliseur

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

failures: list[str] = []


def check(label: str, cond: bool) -> None:
    print(("✅" if cond else "❌"), label)
    if not cond:
        failures.append(label)


def make_synthetic_zip() -> tuple[bytes, list[str]]:
    """ZIP de référence : deflate + store, noms non triés, fausse signature EOCD.

    Retourne (octets, noms des entrées).
    """
    buf = io.BytesIO()
    names = ["classes.dex", "res/values.xml", "assets/x.bin", "META-INF/MANIFEST.MF"]
    contents = [
        b"\xde\xad\xbe\xef" * 512,                       # deflate
        b"<resources></resources>",                      # deflate
        b"PK\x05\x06" + b"\x00" * 30 + b"leurre EOCD",   # STORED + fausse signature
        b"Manifest-Version: 1.0\r\n\r\n",                # STORED
    ]
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data, method in zip(names, contents,
                                      [zipfile.ZIP_DEFLATED, zipfile.ZIP_DEFLATED,
                                       zipfile.ZIP_STORED, zipfile.ZIP_STORED]):
            zi = zipfile.ZipInfo(name, date_time=(2026, 9, 18, 10, 53, 42))
            zi.compress_type = method
            zf.writestr(zi, data)
    return buf.getvalue(), names


def entry_map(data: bytes) -> dict[str, tuple]:
    """(name -> (crc, compress_type, compress_size, file_size, header_offset))."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {zi.filename: (zi.CRC, zi.compress_type, zi.compress_size,
                              zi.file_size, zi.header_offset)
                for zi in zf.infolist()}


def timestamps(data: bytes) -> set[tuple]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {zi.date_time for zi in zf.infolist()}


def diff_offsets(a: bytes, b: bytes) -> list[int]:
    assert len(a) == len(b), "la taille du ZIP ne doit pas changer"
    return [i for i, (x, y) in enumerate(zip(a, b)) if x != y]


def stamp_positions(data: bytes) -> set[int]:
    """Offsets des 4 octets d'horodatage (CDH + LFH) pour chaque entrée."""
    positions: set[int] = set()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for zi in zf.infolist():
            positions.update(range(zi.header_offset + 10, zi.header_offset + 14))
            positions.update(range(zi.header_offset + 12, zi.header_offset + 16))
    # Compléter avec les offsets CDH : le central directory commence après
    # la dernière entrée ; on le localise par l'EOCD.
    eocd = data.rfind(b"PK\x05\x06")
    n, cd_size, cd_off = struct.unpack_from("<H", data, eocd + 10)[0], \
        struct.unpack_from("<I", data, eocd + 12)[0], \
        struct.unpack_from("<I", data, eocd + 16)[0]
    off = cd_off
    for _ in range(n):
        nlen, elen, clen = struct.unpack_from("<HHH", data, off + 28)
        lfh_off = struct.unpack_from("<I", data, off + 42)[0]
        positions.update(range(off + 12, off + 16))
        positions.update(range(lfh_off + 10, lfh_off + 14))
        off += 46 + nlen + elen + clen
    return positions


def main() -> int:
    original, names = make_synthetic_zip()

    # 1. État initial : horodatages variables, non normalisé.
    check("ZIP synthétique à horodatages variables",
          timestamps(original) == {(2026, 9, 18, 10, 53, 42)})

    with tempfile.TemporaryDirectory() as tmp:
        apk = pathlib.Path(tmp) / "test.apk"
        apk.write_bytes(original)

        check("--check avant normalisation -> 1",
              subprocess.run([sys.executable, str(NORMALIZE), "--check", str(apk)],
                             capture_output=True).returncode == 1)

        # 2. Normalisation.
        r = subprocess.run([sys.executable, str(NORMALIZE), str(apk)],
                           capture_output=True, text=True, encoding="utf-8")
        check("normalisation réussie", r.returncode == 0)
        normalized = apk.read_bytes()

    # 3. Contenu intact : CRC, méthodes, tailles, offsets identiques.
    check("CRC / méthodes / tailles / offsets intacts",
          entry_map(original) == entry_map(normalized))

    # 4. Horodatages tous à la constante.
    check("tous les horodatages = 1980-01-01 00:00:00",
          timestamps(normalized) == {(1980, 1, 1, 0, 0, 0)})

    # 5. Seuls les octets d'horodatage ont changé.
    changed = diff_offsets(original, normalized)
    check(f"seuls les octets d'horodatage changent ({len(changed)} octets)",
          set(changed) <= stamp_positions(original)
          and len(changed) == 8 * len(names))

    # 6. Idempotence + --check après coup.
    with tempfile.TemporaryDirectory() as tmp:
        apk = pathlib.Path(tmp) / "test.apk"
        apk.write_bytes(normalized)
        r2 = subprocess.run([sys.executable, str(NORMALIZE), str(apk)],
                            capture_output=True, text=True, encoding="utf-8")
        check("seconde normalisation : 0 entrée corrigée", "déjà normalisé" in r2.stdout)
        check("seconde normalisation : octets identiques", apk.read_bytes() == normalized)
        check("--check après normalisation -> 0",
              subprocess.run([sys.executable, str(NORMALIZE), "--check", str(apk)],
                             capture_output=True).returncode == 0)

    # 7. Cas réel : si l'APK non signé du build est présent, il doit être
    # normalisé (build.sh le fait systématiquement depuis l'étape 4b).
    real = HERE.parent.parent / "work" / "build" / "twouich_unsigned.apk"
    if real.exists():
        rc = subprocess.run([sys.executable, str(NORMALIZE), "--check", str(real)],
                            capture_output=True).returncode
        check(f"APK du build normalisé ({real.name})", rc == 0)
    else:
        print("ℹ️  work/build/twouich_unsigned.apk absent — contrôle réel sauté")

    print()
    if failures:
        print(f"❌ {len(failures)} échec(s) : {failures}")
        return 1
    print("✅ normalize_apk conforme")
    return 0


if __name__ == "__main__":
    sys.exit(main())
