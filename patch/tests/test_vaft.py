#!/usr/bin/env python3
"""
test_vaft.py — decision du secours « flux propre » (VaftFallback.smali).

Pourquoi ce test existe
-----------------------
L'ancien VaFT etait du code mort : il recevait la playlist DEJA nettoyee (donc
sans `stitched-ad`), ne se declenchait jamais, et sa verification finale etait
inversee (il n'acceptait un flux de secours que s'il contenait encore une pub).
Pendant ce temps, un pod laissait le lecteur sans segment : image figee et roue
de chargement pendant toute la duree de la pub — le blocage que l'on supprime.

Ce test verrouille la decision, hors reseau et hors appareil :
  - une playlist de pod (preroll ou midroll) demande le secours ;
  - une playlist de contenu ne le demande pas (cas normal, toutes les 2 s) ;
  - une VOD n'est jamais remplacee par un direct (`#EXT-X-ENDLIST`) ;
  - un flux de secours qui contient ENCORE une pub est refuse — l'inversion
    qui rendait l'ancien code inoperant est donc un cas de test explicite.

Miroir de `VaftFallback.a()` et `VaftFallback.c()` ; le smali reste la source.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "ssai-2026-09-18.m3u8"

checks: list[tuple[str, bool, str]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    checks.append((label, bool(condition), detail))


def has_ads(text: str) -> bool:
    """Miroir de VaftFallback.c(String)Z."""
    return (
        "stitched-ad" in text
        or "X-TV-TWITCH-AD-QUARTILE" in text
        or "#EXT-X-CUE-OUT" in text
        or "Amazon" in text
    )


def needs_backup(text: str, channel: str) -> bool:
    """Miroir de VaftFallback.a(String)String : quand tente-t-on l'embed ?"""
    if not text or not channel:
        return False
    if "#EXT-X-ENDLIST" in text:      # VOD : jamais de substitution par un direct
        return False
    return has_ads(text)


def backup_usable(text: str) -> bool:
    """Un flux de secours n'est servi que s'il est propre (miroir de :use_clean)."""
    return text is not None and "#EXTM3U" in text and not has_ads(text)


def main() -> int:
    pod = FIXTURE.read_text(encoding="utf-8")
    content = (
        "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:2\n"
        "#EXT-X-MEDIA-SEQUENCE:812\n#EXT-X-TWITCH-LIVE-SEQUENCE:1204\n"
        "#EXTINF:2.000,live\nhttps://video.example/seg1.ts\n"
    )
    vod = (
        "#EXTM3U\n#EXT-X-PLAYLIST-TYPE:VOD\n#EXT-X-ENDLIST\n"
        "#EXTINF:10.000,Amazon Prime documentary\nhttps://vod.example/seg1.ts\n"
    )
    dirty_backup = pod  # un secours qui porte encore une pub

    check("playlist de pod (preroll) : le secours est demande", needs_backup(pod, "ddg"))
    check("playlist de contenu : aucun secours (cas normal)", not needs_backup(content, "ddg"))
    check("chaine inconnue : aucun secours", not needs_backup(pod, ""))
    check("VOD avec EXTINF « Amazon » : jamais remplacee par un direct",
          not needs_backup(vod, "ddg"))
    check("marqueur quartile seul : pub reconnue",
          has_ads('#EXT-X-DATERANGE:CLASS="twitch-ad-quartile",X-TV-TWITCH-AD-QUARTILE="0"'))
    check("bloc CUE-OUT : pub reconnue", has_ads("#EXT-X-CUE-OUT:30"))
    check("contenu pur : aucune pub detectee", not has_ads(content))

    # La polarite qui a rendu l'ancien code inoperant.
    check("flux de secours propre : accepte", backup_usable(content))
    check("flux de secours contenant encore une pub : refuse", not backup_usable(dirty_backup))

    # Et le nettoyage local reste le filet : le fixture pod est bien vide de pub.
    sys.path.insert(0, str(HERE))
    import test_sanitizer as mirror  # noqa: E402

    cleaned = mirror.sanitize(pod)
    check("filet local : le pod disparait du fixture",
          not has_ads(cleaned) and mirror.last_cut > 0,
          f"last_cut={mirror.last_cut}")

    # Polarite REELLE des branches du smali. Le miroir Python ci-dessus etait
    # juste alors que le smali, lui, sortait par un garde inverse a chaque
    # etape : le secours ne s'executait jamais cote appareil (mesure du
    # 23/10/2026, sonde app_process sur BlueStacks). Un miroir ne peut pas
    # attraper cela, donc on lit la source.
    smali = (HERE.parent / "smali/com/twouich/adblock/VaftFallback.smali").read_text(
        encoding="utf-8")

    def n(line: str) -> int:
        want = line.strip()
        return sum(1 for row in smali.splitlines() if row.strip() == want)

    check("smali : entree, p0 nul -> playlist brute",
          n("if-eqz p0, :ret_raw") == 1 and n("if-nez p0, :ret_raw") == 0)
    check("smali : chaine absente -> playlist brute",
          n("if-eqz v0, :ret_raw") >= 1)
    check("smali : echec de d()/e() -> playlist brute",
          n("if-eqz v1, :ret_raw") == 3)
    check("smali : secours servi seulement s'il est propre",
          n("if-eqz v2, :use_clean") == 1)
    check("smali : cache de variante encore valide -> pas de backoff",
          n("if-eqz v4, :backoff") == 1)
    check("smali : c() distingue CUE-OUT absent et Amazon absent",
          n("if-eqz v0, :maybe_amazon") == 1 and n("if-eqz v0, :no") == 1)
    check("smali : plus aucun garde d'entree inverse",
          n("if-nez v0, :ret_raw") == 1)

    # Capture precoce : la chaine doit etre connue AVANT la premiere playlist
    # du lecteur (elle vient de l'intent), sinon le secours n'est pas arme.
    data_source = (HERE.parent / "smali/com/twouich/adblock/AdBlockDataSource.smali")\
        .read_text(encoding="utf-8")
    check("capture : point unique twouichSetChannel present",
          ".method public static twouichSetChannel(Ljava/lang/String;)V" in data_source
          and data_source.count("->twouichSetChannel(Ljava/lang/String;)V") == 1)
    check("capture : login de plus de 25 caracteres refuse",
          "const/16 v1, 0x19" in data_source and "if-gt v0, v1, :done" in data_source)
    patch = (HERE.parent / "patch.py").read_text(encoding="utf-8")
    check("capture : posee dans onCreate et dans x3 (point d'ecriture unique)",
          "install_early_channel_capture(final)" in patch
          and "secours anti-pub : deeplink" in patch
          and "twouichSetChannel(Ljava/lang/String;)V" in patch)

    failures = [c for c in checks if not c[1]]
    for label, ok, detail in checks:
        print(("[OK ] " if ok else "[KO ] ") + label + (f"  — {detail}" if detail and not ok else ""))
    print()
    if failures:
        print(f"❌ {len(failures)} verification(s) en echec")
        return 1
    print(f"✅ {len(checks)}/{len(checks)} verifications passees")
    return 0


if __name__ == "__main__":
    sys.exit(main())
