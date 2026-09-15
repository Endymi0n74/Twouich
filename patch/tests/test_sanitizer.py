#!/usr/bin/env python3
"""
test_sanitizer.py — test de règles du nettoyage de playlist.

Ce fichier est le **miroir en Python** de la machine à états de
`patch/smali/com/twouich/adblock/PlaylistSanitizer.smali` : il sert à figer le
comportement attendu sur des playlists réalistes (pub SSAI, pub côté client,
titre Amazon, daterange non publicitaire) et à détecter toute divergence lors
d'une modification du smali.

    python patch/tests/test_sanitizer.py
"""
from __future__ import annotations

import pathlib
import re
import sys

AD_MARKER = "stitched-ad"
AMAZON_MARKER = "Amazon"

# Miroir du champ statique PlaylistSanitizer.lastCut
last_cut = 0


def sanitize(body: str) -> str:
    """Transcription fidèle de PlaylistSanitizer.a(String)."""
    global last_cut
    last_cut = 0
    if body is None:
        return None
    if "#EXTM3U" not in body:
        return body

    out: list[str] = []
    in_ad = False
    in_cue = False
    skip_uri = False

    def drop(line: str) -> None:
        global last_cut
        if not line.startswith("#"):
            last_cut += 1

    for raw in body.split("\n"):
        t = raw.strip()
        if not t:
            continue
        if skip_uri:
            skip_uri = False
            drop(t)
            continue
        if t.startswith("#EXT-X-DATERANGE") and AD_MARKER in t:
            in_ad = True
            drop(t)
            continue
        if t.startswith("#EXT-X-CUE-OUT"):
            in_cue = True
            drop(t)
            continue
        if t.startswith("#EXT-X-CUE-IN"):
            in_cue = False
            drop(t)
            continue
        if t.startswith("#EXT-X-DISCONTINUITY"):
            in_ad = False
            out.append(t)
            continue
        if t.startswith("#EXT-X-TWITCH-LIVE-SEQUENCE"):
            in_ad = False
            out.append(t)
            continue
        if in_ad or in_cue:
            drop(t)
            continue
        if t.startswith("#EXTINF") and AMAZON_MARKER in t:
            skip_uri = True
            drop(t)
            continue
        out.append(t)
    return "".join(line + "\n" for line in out)


# ── Jeux d'essai ─────────────────────────────────────────────────────────
LIVE_WITH_SSAI_AD = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:4
#EXT-X-MEDIA-SEQUENCE:1200
#EXTINF:2.000,
https://video-weaver.example/hls/seg1200.ts
#EXTINF:2.000,
https://video-weaver.example/hls/seg1201.ts
#EXT-X-DISCONTINUITY
#EXT-X-DATERANGE:ID="stitched-ad-1757920000-1234",CLASS="twitch-stitched-ad",START-DATE="2026-09-15T09:00:00.000Z",DURATION=6.000
#EXTINF:2.000,
https://video-weaver.example/hls/ad1.ts
#EXTINF:2.000,
https://video-weaver.example/hls/ad2.ts
#EXTINF:2.000,
https://video-weaver.example/hls/ad3.ts
#EXT-X-DISCONTINUITY
#EXT-X-TWITCH-LIVE-SEQUENCE:1206
#EXTINF:2.000,
https://video-weaver.example/hls/seg1206.ts
"""

CUE_BLOCK = """#EXTM3U
#EXTINF:2.000,
https://video-weaver.example/hls/seg1.ts
#EXT-X-CUE-OUT:30.000
#EXTINF:6.000,
https://video-weaver.example/hls/client-ad.ts
#EXT-X-CUE-IN
#EXTINF:2.000,
https://video-weaver.example/hls/seg2.ts
"""

AMAZON_TITLE = """#EXTM3U
#EXTINF:2.000,
https://video-weaver.example/hls/seg1.ts
#EXTINF:10.000,Amazon
https://video-weaver.example/hls/ssai.ts
#EXTINF:2.000,
https://video-weaver.example/hls/seg2.ts
"""

NON_AD_DATERANGE = """#EXTM3U
#EXT-X-DATERANGE:ID="playlist-creation-1757920000",CLASS="twitch-playlist",START-DATE="2026-09-15T09:00:00.000Z"
#EXTINF:2.000,
https://video-weaver.example/hls/seg1.ts
"""

MASTER = """#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=6624000,RESOLUTION=1920x1080,CODECS="avc1.64002a,mp4a.40.2",STABLE-VARIANT-ID="1080p60"
https://video-weaver.example/hls/1080p60/index-dvr.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=3000000,RESOLUTION=1280x720
https://video-weaver.example/hls/720p/index-dvr.m3u8
"""


def segments(text: str) -> list[str]:
    return [l for l in text.splitlines() if l.startswith("https://")]


def check(name: str, condition: bool, detail: str = "") -> bool:
    print(f"{'✅' if condition else '❌'} {name}{(' — ' + detail) if detail and not condition else ''}")
    return condition


def main() -> int:
    ok = True

    # 1. tout ce qui n'est pas une playlist est rendu tel quel
    ok &= check("non-playlist inchangée", sanitize("bonjour") == "bonjour")
    ok &= check("null géré", sanitize(None) is None)

    # 2. pub SSAI : les 3 segments pub partent, le contenu reste
    out = sanitize(LIVE_WITH_SSAI_AD)
    ok &= check("SSAI : segments pub retirés", len(segments(out)) == 3, str(segments(out)))
    ok &= check("SSAI : aucun segment ad*", not any("ad" in s.split("/")[-1] for s in segments(out)))
    ok &= check("SSAI : tag de plage pub retiré", "stitched-ad" not in out)
    ok &= check("SSAI : discontinuité conservée", out.count("#EXT-X-DISCONTINUITY") == 2)
    ok &= check("SSAI : séquence live conservée", "#EXT-X-TWITCH-LIVE-SEQUENCE:1206" in out)
    ok &= check("SSAI : contenu repris après la pub", "seg1206.ts" in out)

    # 3. bloc CUE-OUT / CUE-IN
    out = sanitize(CUE_BLOCK)
    ok &= check("CUE : segment pub retiré", len(segments(out)) == 2, str(segments(out)))
    ok &= check("CUE : tags retirés", "CUE-OUT" not in out and "CUE-IN" not in out)

    # 4. titre Amazon : le segment ET son URI partent
    out = sanitize(AMAZON_TITLE)
    ok &= check("Amazon : segment retiré", len(segments(out)) == 2, str(segments(out)))
    ok &= check("Amazon : URI non orpheline", "ssai.ts" not in out)

    # 5. les plages non publicitaires sont intouchées
    out = sanitize(NON_AD_DATERANGE)
    ok &= check("daterange non pub conservée", 'ID="playlist-creation-1757920000"' in out)
    ok &= check("daterange non pub : segment conservé", len(segments(out)) == 1)

    # 6. playlist maître : aucune perte
    out = sanitize(MASTER)
    ok &= check("master : variantes conservées", len(segments(out)) == 2)
    ok &= check("master : métadonnées conservées", 'STABLE-VARIANT-ID="1080p60"' in out)

    # 7. idempotence
    once = sanitize(LIVE_WITH_SSAI_AD)
    twice = sanitize(once)
    ok &= check("idempotent", once == twice)

    # 8. compteur lastCut (lu par la trace logcat sur l'appareil)
    sanitize(LIVE_WITH_SSAI_AD)
    ok &= check("compteur SSAI = 3", last_cut == 3, str(last_cut))
    sanitize(CUE_BLOCK)
    ok &= check("compteur CUE = 1", last_cut == 1, str(last_cut))
    sanitize(AMAZON_TITLE)
    ok &= check("compteur Amazon = 1", last_cut == 1, str(last_cut))
    sanitize(NON_AD_DATERANGE)
    ok &= check("compteur sans pub = 0", last_cut == 0, str(last_cut))
    sanitize(MASTER)
    ok &= check("compteur master = 0", last_cut == 0, str(last_cut))

    print("\n" + ("✅ règles conformes" if ok else "❌ divergence détectée"))
    return 0 if ok else 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
