#!/usr/bin/env python3
"""
test_normalize_apk.py — vérifie patch/normalize_apk.py.

Le normaliseur canonise un APK ZIP au niveau octet : horodatage constant
(header local + central directory) ET ordre des entrées trié par nom. Ce test
garantit qu'il ne touche QUE cela, sur des ZIP synthétiques aux propriétés
connues :

  * CRC et octets compressés inchangés après normalisation ;
  * sur un ZIP déjà dans l'ordre canonique, les seuls octets modifiés sont
    les 4 (date+time) du central directory et les 4 du header local, par
    entrée — rien d'autre ;
  * INVARIANCE D'ORDRE : deux ZIP de même contenu écrits dans des ordres
    différents (l'équivalent jouet de Windows vs Linux) produisent après
    normalisation exactement les mêmes octets ;
  * entrées « streamées » (descripteur de données, flag 0x0008 — le mode
    d'écriture d'apktool) : descripteur recopié intact, contenu vérifié,
    même invariance d'ordre ;
  * une fausse signature EOCD glissée dans les données d'une entrée stockée
    ne le trompe pas (le candidat retenu doit recouper ses propres champs) ;
  * idempotence : normaliser deux fois ne change rien, à l'octet près ;
  * --check ne modifie rien et rend 0/1 selon l'état (horodatage + ordre).

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
import zlib

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


# ── ZIP synthétique classique (via zipfile) ─────────────────────────────
# contenu par nom : (données, méthode) — l'entrée `assets/x.bin` est STORED et
# contient une fausse signature EOCD : le parseur ne doit pas s'y laisser prendre.
CONTENTS: dict[str, tuple[bytes, int]] = {
    "classes.dex": (b"\xde\xad\xbe\xef" * 512, zipfile.ZIP_DEFLATED),
    "res/values.xml": (b"<resources></resources>", zipfile.ZIP_DEFLATED),
    "assets/x.bin": (b"PK\x05\x06" + b"\x00" * 30 + b"leurre EOCD", zipfile.ZIP_STORED),
    "META-INF/MANIFEST.MF": (b"Manifest-Version: 1.0\r\n\r\n", zipfile.ZIP_STORED),
}


def build_zip(order: list[str]) -> bytes:
    """ZIP avec les entrées écrites dans `order` (horodatage de build variable)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in order:
            data, method = CONTENTS[name]
            zi = zipfile.ZipInfo(name, date_time=(2026, 9, 18, 10, 53, 42))
            zi.compress_type = method
            zf.writestr(zi, data)
    return buf.getvalue()


def entry_map(data: bytes) -> dict[str, tuple]:
    """(name -> (crc, méthode, tailles)) — sans l'offset, qui change avec l'ordre."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {zi.filename: (zi.CRC, zi.compress_type, zi.compress_size, zi.file_size)
                for zi in zf.infolist()}


def entry_order(data: bytes) -> list[str]:
    """Ordre réel des entrées (central directory), pas l'ordre alphabétique."""
    eocd = data.rfind(b"PK\x05\x06")
    n, cd_size, cd_off = (struct.unpack_from("<H", data, eocd + 10)[0],
                          struct.unpack_from("<I", data, eocd + 12)[0],
                          struct.unpack_from("<I", data, eocd + 16)[0])
    names: list[str] = []
    off = cd_off
    for _ in range(n):
        nlen, elen, clen = struct.unpack_from("<HHH", data, off + 28)
        names.append(data[off + 46:off + 46 + nlen].decode())
        off += 46 + nlen + elen + clen
    return names


def timestamps(data: bytes) -> set[tuple]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {zi.date_time for zi in zf.infolist()}


def diff_offsets(a: bytes, b: bytes) -> list[int]:
    assert len(a) == len(b), "la taille du ZIP ne doit pas changer"
    return [i for i, (x, y) in enumerate(zip(a, b)) if x != y]


def stamp_positions(data: bytes) -> set[int]:
    """Offsets des 4 octets d'horodatage (CDH + LFH) pour chaque entrée."""
    positions: set[int] = set()
    eocd = data.rfind(b"PK\x05\x06")
    n, cd_size, cd_off = (struct.unpack_from("<H", data, eocd + 10)[0],
                          struct.unpack_from("<I", data, eocd + 12)[0],
                          struct.unpack_from("<I", data, eocd + 16)[0])
    off = cd_off
    for _ in range(n):
        nlen, elen, clen = struct.unpack_from("<HHH", data, off + 28)
        lfh_off = struct.unpack_from("<I", data, off + 42)[0]
        positions.update(range(off + 12, off + 16))
        positions.update(range(lfh_off + 10, lfh_off + 14))
        off += 46 + nlen + elen + clen
    return positions


def run_normalize(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(NORMALIZE), *argv],
                          capture_output=True, text=True, encoding="utf-8")


def run_check(apk: pathlib.Path) -> int:
    return subprocess.run([sys.executable, str(NORMALIZE), "--check", str(apk)],
                          capture_output=True).returncode


def normalize_copy(data: bytes, tmp: pathlib.Path, name: str) -> bytes:
    apk = tmp / name
    apk.write_bytes(data)
    r = run_normalize(str(apk))
    assert r.returncode == 0, f"normalisation échouée : {r.stderr}"
    return apk.read_bytes()


# ── ZIP à entrées « streamées » (descripteur de données), construit à la main ──
# `apktool b` écrit en flux : LFH avec CRC/tailles à zéro + flag 0x0008, données,
# descripteur 12 octets (sans signature) portant les valeurs réelles. zipfile ne
# produit pas cela : on assemble les octets pour reproduire le format réel.
STREAMED_NAME = "a-streamed.bin"
STREAMED_DATA = b"\x5a\x5a" * 300
STREAMED_CRC = zlib.crc32(STREAMED_DATA) & 0xFFFFFFFF
PLAIN_NAME = "z-plain.txt"
PLAIN_DATA = b"plain entry, written with sizes in the LFH"
PLAIN_CRC = zlib.crc32(PLAIN_DATA) & 0xFFFFFFFF
DOS_TIME = 0
DOS_DATE = (2026 - 1980) << 9 | 9 << 5 | 18


def build_streamed_zip(streamed_first: bool) -> bytes:
    """ZIP de deux entrées (une streamée, une classique) dans l'ordre demandé."""
    specs = [(STREAMED_NAME.encode(), STREAMED_DATA, STREAMED_CRC, True),
             (PLAIN_NAME.encode(), PLAIN_DATA, PLAIN_CRC, False)]
    if not streamed_first:
        specs.reverse()

    def entry_lfh(name: bytes, data: bytes, crc: int, streamed: bool) -> bytes:
        csize = len(data)
        flags = 0x0008 if streamed else 0
        return (b"PK\x03\x04"
                + struct.pack("<HHHHHIIIHH", 20, flags, 0, DOS_TIME, DOS_DATE,
                              0 if streamed else crc, 0 if streamed else csize,
                              0 if streamed else csize, len(name), 0)
                + name + data
                + (struct.pack("<III", crc, csize, csize) if streamed else b""))

    locals_lfh = [entry_lfh(n, d, c, s) for n, d, c, s in specs]
    offsets: list[int] = []
    pos = 0
    for l in locals_lfh:
        offsets.append(pos)
        pos += len(l)
    out = bytearray(b"".join(locals_lfh))
    cd_off = len(out)
    for (name, data, crc, streamed), off in zip(specs, offsets):
        csize = len(data)
        flags = 0x0008 if streamed else 0
        out += (b"PK\x01\x02"
                + struct.pack("<HHHHHHIIIHHHHHII", 20, 20, flags, 0, DOS_TIME, DOS_DATE,
                              crc, csize, csize, len(name), 0, 0, 0, 0, 0, off)
                + name)
    out += b"PK\x05\x06" + struct.pack("<HHHHIIH", 0, 0, len(specs), len(specs),
                                       len(out) - cd_off, cd_off, 0)
    return bytes(out)


def streamed_entry_bytes(data: bytes, name: str) -> bytes:
    """Octets (LFH + données + descripteur) de l'entrée `name` dans le ZIP brut."""
    eocd = data.rfind(b"PK\x05\x06")
    n, _cd_size, cd_off = (struct.unpack_from("<H", data, eocd + 10)[0],
                           struct.unpack_from("<I", data, eocd + 12)[0],
                           struct.unpack_from("<I", data, eocd + 16)[0])
    off = cd_off
    for _ in range(n):
        nlen, elen, clen = struct.unpack_from("<HHH", data, off + 28)
        lfh_off = struct.unpack_from("<I", data, off + 42)[0]
        raw = data[off + 46:off + 46 + nlen]
        flags = struct.unpack_from("<H", data, off + 8)[0]
        comp = struct.unpack_from("<I", data, off + 20)[0]
        nl, el = struct.unpack_from("<HH", data, lfh_off + 26)
        end = lfh_off + 30 + nl + el + comp + (12 if flags & 8 else 0)
        if raw.decode() == name:
            return data[lfh_off:end]
        off += 46 + nlen + elen + clen
    raise KeyError(name)


def main() -> int:
    canonical_order = sorted(CONTENTS)
    shuffled_a = ["res/values.xml", "META-INF/MANIFEST.MF", "assets/x.bin", "classes.dex"]
    shuffled_b = ["assets/x.bin", "classes.dex", "res/values.xml", "META-INF/MANIFEST.MF"]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = pathlib.Path(tmpdir)

        # ── A. ZIP déjà dans l'ordre canonique : seuls les horodatages bougent ──
        original = build_zip(canonical_order)
        apk = tmp / "canonical.apk"
        apk.write_bytes(original)

        check("ZIP synthétique à horodatages variables",
              timestamps(original) == {(2026, 9, 18, 10, 53, 42)})
        check("--check avant normalisation -> 1", run_check(apk) == 1)

        r = run_normalize(str(apk))
        check("normalisation réussie", r.returncode == 0)
        check("ordre déjà canonique signalé", "ordre déjà canonique" in r.stdout)
        normalized = apk.read_bytes()

        check("CRC / méthodes / tailles intacts",
              entry_map(original) == entry_map(normalized))
        check("ordre des entrées = tri par nom",
              entry_order(normalized) == sorted(entry_order(normalized)))
        check("tous les horodatages = 1980-01-01 00:00:00",
              timestamps(normalized) == {(1980, 1, 1, 0, 0, 0)})
        changed = diff_offsets(original, normalized)
        check(f"seuls les octets d'horodatage changent ({len(changed)} octets)",
              set(changed) <= stamp_positions(original)
              and len(changed) == 8 * len(CONTENTS))

        apk2 = tmp / "canonical-again.apk"
        apk2.write_bytes(normalized)
        r2 = run_normalize(str(apk2))
        check("seconde normalisation : déjà canonique", "déjà canonique" in r2.stdout)
        check("seconde normalisation : octets identiques", apk2.read_bytes() == normalized)
        check("--check après normalisation -> 0", run_check(apk2) == 0)

        # ── B. ZIP mélangé : canonisation + INVARIANCE D'ORDRE ──
        from_a = normalize_copy(build_zip(shuffled_a), tmp, "shuffled-a.apk")
        from_b = normalize_copy(build_zip(shuffled_b), tmp, "shuffled-b.apk")

        check("ordre mélangé canonisé", entry_order(from_a) == canonical_order)
        check("contenu intact après réordonnancement",
              entry_map(from_a) == entry_map(normalized))
        check("INVARIANCE D'ORDRE : mélangé A ≡ canonique (octets)",
              from_a == normalized)
        check("INVARIANCE D'ORDRE : mélangé B ≡ mélangé A (octets)",
              from_b == from_a)

        apk3 = tmp / "shuffled-a-again.apk"
        apk3.write_bytes(from_a)
        check("--check sur le mélangé normalisé -> 0", run_check(apk3) == 0)

        # ── C. Entrées streamées (descripteur de données, mode apktool) ──
        streamed_canonical = build_streamed_zip(streamed_first=True)
        norm_s1 = normalize_copy(streamed_canonical, tmp, "streamed-a.apk")
        norm_s2 = normalize_copy(build_streamed_zip(streamed_first=False), tmp, "streamed-b.apk")

        check("ZIP streamé canonisé (ordre trié)",
              entry_order(norm_s1) == sorted([STREAMED_NAME, PLAIN_NAME]))
        check("ZIP streamé : contenu intact (CRC lus par zipfile)",
              entry_map(streamed_canonical) == entry_map(norm_s1))
        check("ZIP streamé : horodatages normalisés (LFH et CDH)",
              timestamps(norm_s1) == {(1980, 1, 1, 0, 0, 0)})

        desc = streamed_entry_bytes(norm_s1, STREAMED_NAME)[-12:]
        # Structure du descripteur : (CRC, taille compressée, taille réelle).
        # Sans signature, le premier mot EST la CRC — le comparer à STREAMED_CRC
        # prouve à la fois l'absence de signature et la copie intacte.
        word1, csize_d, usize_d = struct.unpack("<III", desc)
        check("descripteur recopié intact (12 octets, sans signature, CRC réel)",
              word1 == STREAMED_CRC and csize_d == len(STREAMED_DATA)
              and usize_d == len(STREAMED_DATA))

        check("INVARIANCE D'ORDRE (streamé) : ordre 1 ≡ ordre 2 (octets)",
              norm_s1 == norm_s2)
        apk4 = tmp / "streamed-again.apk"
        apk4.write_bytes(norm_s1)
        check("ZIP streamé : idempotent", run_normalize(str(apk4)).returncode == 0
              and apk4.read_bytes() == norm_s1)
        check("--check sur le ZIP streamé normalisé -> 0", run_check(apk4) == 0)

        # ── D. APK réel du build, s'il est présent ──
        real = HERE.parent.parent / "work" / "build" / "twouich_unsigned.apk"
        if real.exists():
            real_before = real.read_bytes()
            r = run_normalize(str(real))
            real_after = real.read_bytes()
            check(f"APK réel canonisé sans erreur ({real.name})", r.returncode == 0)
            check("APK réel : ordre = tri par nom",
                  entry_order(real_after) == sorted(entry_order(real_after)))
            check("APK réel : contenu intact (par nom -> CRC)",
                  entry_map(real_before) == entry_map(real_after))
            with zipfile.ZipFile(io.BytesIO(real_after)) as zf:
                check("APK réel : CRC de toutes les entrées vérifiés par zipfile",
                      zf.testzip() is None)
            check("--check sur l'APK réel -> 0", run_check(real) == 0)
            check("APK réel : normalisation idempotente (octets identiques)",
                  run_normalize(str(real)).returncode == 0 and real.read_bytes() == real_after)
        else:
            print("ℹ️  work/build/twouich_unsigned.apk absent — contrôles réels sautés")

    print()
    if failures:
        print(f"❌ {len(failures)} échec(s) : {failures}")
        return 1
    print("✅ normalize_apk conforme")
    return 0


if __name__ == "__main__":
    sys.exit(main())
