#!/usr/bin/env python3
"""
test_sanitizer.py — test de règles du nettoyage de playlist.

Ce fichier est le **miroir en Python** de la machine à états de
`patch/smali/com/twouich/adblock/PlaylistSanitizer.smali` : il sert à figer le
comportement attendu sur des playlists réalistes (pub SSAI, pub côté client,
titre Amazon, daterange non publicitaire), sur une playlist SSAI **réelle**
capturée le 18/09/2026 (fixtures/ssai-2026-09-18.m3u8) et à détecter toute
divergence lors d'une modification du smali.

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
# Miroir du champ statique PlaylistSanitizer.suspicious (sentinelle de format)
suspicious = False
# Derniere ligne rapportee par la sentinelle (miroir du Log.w « marqueur pub inconnu »)
last_suspicious_line = ""


def suspicious_tag(t: str) -> bool:
    """Miroir de PlaylistSanitizer.b(String) : cette balise ressemble-t-elle a un
    marqueur publicitaire qu'aucune regle connue ne couvre ?

    Couvre le scenario « Twitch renomme son format » :
      - famille CUE client-side : #EXT-X-CUE* autre que CUE-OUT/CUE-IN ;
      - plage SSAI : un DATERANGE porteur d'attributs de diffusion pub
        (X-TV-TWITCH-AD-*) sans etre la classe connue stitched-ad —
        en excluant explicitement twitch-ad-quartile (metadonnee de pod connue).
    Les DATERANGE utilitaires reelles (timestamp, twitch-session,
    twitch-stream-source, twitch-trigger) n'emportent aucun attribut
    X-TV-TWITCH-AD-* et restent donc muettes.
    """
    if t.startswith("#EXT-X-CUE"):
        return not (t.startswith("#EXT-X-CUE-OUT") or t.startswith("#EXT-X-CUE-IN"))
    if t.startswith("#EXT-X-DATERANGE"):
        if "X-TV-TWITCH-AD-" not in t:
            return False
        if "stitched-ad" in t:
            return False
        return "quartile" not in t
    return False


def sanitize(body: str) -> str:
    """Transcription fidèle de PlaylistSanitizer.a(String)."""
    global last_cut, suspicious, last_suspicious_line
    last_cut = 0
    suspicious = False
    last_suspicious_line = ""
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
        # sentinelle « marqueur pub inconnu » (miroir de l'appel b() du smali,
        # pose au meme endroit — :not_in_ad) : observation pure, aucune
        # modification du nettoyage.
        if suspicious_tag(t):
            suspicious = True
            if not last_suspicious_line:
                last_suspicious_line = t
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

# ── Fixture réelle : pod SSAI capturé le 18/09/2026 (cluster EU) ─────────
# Playlist de variante servie pendant une coupure publicitaire réelle, récupérée
# par refetch côté PC synchronisé avec le logcat de l'appareil. Session,
# tracking (RADS token, beacon, SESSIONID) et chemins de segments neutralisés ;
# structure, dates, IDs de plage et attributs conservés à l'identique.
# Elle fige le format réel du jour : DATERANGE twitch-stitched-ad +
# twitch-ad-quartile, #EXT-X-START, flux de substitution MEDIA-SEQUENCE:0,
# titres EXTINF "Amazon|<creative-id>".
REAL_SSAI_2026_09_18 = (
    pathlib.Path(__file__).parent / "fixtures" / "ssai-2026-09-18.m3u8"
).read_text(encoding="utf-8").replace("\r\n", "\n")


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

    # 9. playlist SSAI réelle du 18/09/2026 : le pod entier part, rien ne fuit
    #    et les métadonnées non publicitaires survivent (le lecteur en dépend).
    #    Recoupage : les 3 URI retirés correspondent exactement à la première
    #    trace du pod sur l'appareil ce jour-là
    #    (playlist nettoyee 28689 -> 12390 octets, segments pub retires : 3).
    out = sanitize(REAL_SSAI_2026_09_18)
    ok &= check("réelle 18/09 : les 3 segments pub partent", len(segments(out)) == 0, str(segments(out)))
    # NB : l'attribut X-TV-TWITCH-STREAM-SOURCE="Amazon|…" de la DATERANGE
    # twitch-stream-source SURVIT au nettoyage (c'est une plage non publicitaire) ;
    # on vérifie donc l'absence de marqueur Amazon sur les lignes de segments.
    ok &= check("réelle 18/09 : aucun EXTINF Amazon restant",
                not any(l.startswith("#EXTINF") and "Amazon" in l for l in out.splitlines()))
    ok &= check("réelle 18/09 : plage stitched-ad retirée", "twitch-stitched-ad" not in out)
    ok &= check("réelle 18/09 : DATERANGE twitch-session conservée", 'CLASS="twitch-session"' in out)
    ok &= check("réelle 18/09 : SESSIONID de la session conservé", "X-TV-TWITCH-SESSIONID" in out)
    ok &= check("réelle 18/09 : EXT-X-START conservé", "#EXT-X-START:TIME-OFFSET=0.000" in out)
    ok &= check("réelle 18/09 : discontinuité conservée", out.count("#EXT-X-DISCONTINUITY") == 1)
    ok &= check("réelle 18/09 : PROGRAM-DATE-TIME conservés", out.count("#EXT-X-PROGRAM-DATE-TIME") == 3)
    ok &= check("réelle 18/09 : en-tête TWITCH conservé", "#EXT-X-TWITCH-ELAPSED-SECS:44175.583" in out)
    ok &= check("réelle 18/09 : idempotence", out == sanitize(out))
    sanitize(REAL_SSAI_2026_09_18)
    ok &= check("compteur réelle 18/09 = 3", last_cut == 3, str(last_cut))

    # 10. sentinelle « marqueur pub inconnu » : observation pure (aucune
    #     modification du nettoyage), qui doit se taire sur tout ce que Twitch
    #     sert aujourd'hui et parler si le format change un jour.
    sanitize(REAL_SSAI_2026_09_18)
    ok &= check("sentinelle : fixture réelle 18/09 silencieuse", not suspicious)

    # les balises connues du monde réel ne parlent pas (lignes issues de la
    # capture du 18/09, formes identiques)
    KNOWN_TAGS = [
        ("DATERANGE timestamp",
         '#EXT-X-DATERANGE:ID="playlist-creation-1789717104",CLASS="timestamp",START-DATE="2026-09-18T07:38:24.811Z",X-SERVER-TIME="1789717104.81"'),
        ("DATERANGE twitch-session",
         '#EXT-X-DATERANGE:ID="playlist-session-1789717104",CLASS="twitch-session",X-TV-TWITCH-SESSIONID="0"'),
        ("DATERANGE twitch-stream-source (attribut Amazon)",
         '#EXT-X-DATERANGE:ID="source-1789717100",CLASS="twitch-stream-source",X-TV-TWITCH-STREAM-SOURCE="Amazon|2474283100494"'),
        ("DATERANGE twitch-trigger",
         '#EXT-X-DATERANGE:ID="trigger-1789717100",CLASS="twitch-trigger",X-TV-TWITCH-TRIGGER-URL="https://euw33.playlist.ttvnw.net/trigger/x"'),
        ("DATERANGE twitch-ad-quartile",
         '#EXT-X-DATERANGE:ID="quartile-1789717100-0",CLASS="twitch-ad-quartile",DURATION=2.000,X-TV-TWITCH-AD-QUARTILE="0"'),
        ("DATERANGE twitch-stitched-ad",
         '#EXT-X-DATERANGE:ID="stitched-ad-1789717100-30235000000",CLASS="twitch-stitched-ad",X-TV-TWITCH-AD-ROLL-TYPE="PREROLL"'),
    ]
    for name, tag in KNOWN_TAGS:
        sanitize(f"#EXTM3U\n{tag}\n#EXTINF:2.000,\nhttps://seg.example/1.ts\n")
        ok &= check(f"sentinelle : silence sur {name}", not suspicious, last_suspicious_line)

    # scénario cible : Twitch renomme la classe SSAI — le DATERANGE porte les
    # mêmes attributs de diffusion pub (X-TV-TWITCH-AD-*) sous un autre nom.
    RENAMED = """#EXTM3U
#EXT-X-DATERANGE:ID="stitched-promo-1789717100",CLASS="twitch-stitched-promo",START-DATE="2026-09-18T07:38:20.212Z",X-TV-TWITCH-AD-ROLL-TYPE="PREROLL",X-TV-TWITCH-AD-POD-LENGTH="1"
#EXTINF:2.000,Amazon|2474283100494
https://seg.example/ad-1.ts
#EXTINF:2.000,
https://seg.example/live-1.ts
"""
    out = sanitize(RENAMED)
    ok &= check("sentinelle : pod SSAI renommé détecté", suspicious)
    ok &= check("sentinelle : la première ligne suspecte est rapportée",
                last_suspicious_line.startswith('#EXT-X-DATERANGE:ID="stitched-promo'), last_suspicious_line)
    ok &= check("sentinelle : nettoyage inchangé (observation pure)",
                'CLASS="twitch-stitched-promo"' in out)

    # famille CUE client-side : une balise inconnue parle, CUE-OUT/CUE-IN (qui
    # sont consommés comme bloc pub avant la sentinelle) restent muets
    sanitize("#EXTM3U\n#EXT-X-CUE-PREPARE:30.000\n#EXTINF:2.000,\nhttps://seg.example/1.ts\n")
    ok &= check("sentinelle : balise CUE inconnue détectée", suspicious)
    sanitize(CUE_BLOCK)
    ok &= check("sentinelle : CUE-OUT/CUE-IN reconnus restent muets", not suspicious)

    # une seule ligne par playlist (une alerte logcat, pas une pluie)
    sanitize("#EXTM3U\n#EXT-X-CUE-PREPARE:30.000\n#EXT-X-DATERANGE:CLASS=\"x-ad\",X-TV-TWITCH-AD-URL=\"https://t\"\n#EXTINF:2.000,\nhttps://seg.example/1.ts\n")
    ok &= check("sentinelle : une seule ligne rapportée par playlist",
                last_suspicious_line.startswith("#EXT-X-CUE-PREPARE"))

    # dans une zone pub déjà reconnue : rien ne parle (les tags d'un pod connu
    # ne sont pas des inconnus)
    sanitize("""#EXTM3U
#EXT-X-DATERANGE:ID="stitched-ad-1",CLASS="twitch-stitched-ad"
#EXT-X-CUE-PREPARE:5.000
#EXTINF:2.000,Amazon
https://seg.example/ad.ts
#EXT-X-DISCONTINUITY
#EXTINF:2.000,
https://seg.example/live.ts
""")
    ok &= check("sentinelle : muette dans une zone pub déjà reconnue", not suspicious)

    # l'état est réinitialisé à chaque playlist
    sanitize("#EXTM3U\n#EXT-X-CUE-PREPARE:30.000\n#EXTINF:2.000,\nhttps://seg.example/1.ts\n")
    sanitize("#EXTM3U\n#EXTINF:2.000,\nhttps://seg.example/1.ts\n")
    ok &= check("sentinelle : drapeau réinitialisé à chaque playlist", not suspicious)

    print("\n" + ("✅ règles conformes" if ok else "❌ divergence détectée"))
    return 0 if ok else 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
