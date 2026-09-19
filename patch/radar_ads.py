#!/usr/bin/env python3
"""
radar-ads.py -- radar multi-chaines + rejeu anti-fuite.

1. Sonde plusieurs directs Twitch cote PC : token GQL anonyme ->
   usher.ttvnw.net -> playlist de variante source (la methode d'AUDIT.md
   section 4.4). Le PC et l'app voient des etats pub differents (SSAI par
   session de token) : le radar ne fait qu'orienter et surveiller.
2. Pour chaque playlist capturee, rejoue le **miroir Python** du sanitizer
   (patch/tests/test_sanitizer.py : la meme machine a etats que le smali)
   et verifie deux choses :
     - aucun marqueur publicitaire ne survit au nettoyage (anti-fuite) ;
     - la sentinelle « marqueur pub inconnu » du miroir reste muette —
       si elle parle, Twitch sert un format que les regles ne couvrent pas.

Codes de sortie :
    0 : au moins un pod observe et AUCUN probleme de couverture ; ou rien
        pu etre teste (offline / toutes chaines hors ligne) — l'absence de
        preuve n'est pas une alerte.
    1 : un marqueur ressemblant a une pub n'est PAS couvert par les regles
        (sentinelle du miroir, ou marqueur pub ayant survécu au nettoyage).
        Details sur stderr, ligne HLS brute incluse.

Usage :
    python patch/radar_ads.py                     # liste par defaut, 5 cycles
    python patch/radar_ads.py --cycles 8 ch1 ch2  # cibler d'autres chaines
    python patch/radar_ads.py --quiet             # resume seul (pour la CI)
"""
from __future__ import annotations

import json
import pathlib
import sys
import threading
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
TESTS = pathlib.Path(__file__).resolve().parent / "tests"
sys.path.insert(0, str(TESTS))

# Import PAR MODULE : les champs de sentinelle du miroir sont des variables
# globales reécrites par sanitize() — un import par valeur figerait False.
import test_sanitizer as mirror  # noqa: E402

CHANNELS = ["xqc", "kaicenat", "jynxzi", "ddg", "admiralbulldog"]
CYCLES = 5
WAIT = 10          # s entre les cycles
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
GQL = "https://gql.twitch.tv/gql"
# Client-ID public du site Twitch (suffisant pour un token anonyme).
CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
# Persisted query PlaybackAccessToken (hash public, documente par Streamlink).
SHA256 = "0828119ded1c13477966434e15800ff57ddacf13ba1911c129dc2200705b0712"


def gql_token(channel: str) -> tuple[str, str]:
    body = json.dumps({
        "operationName": "PlaybackAccessToken",
        "extensions": {"persistedQuery": {"version": 1, "sha256Hash": SHA256}},
        "variables": {
            "isLive": True, "isVod": False, "vodID": "",
            "login": channel, "platform": "web", "playerType": "site",
        },
    }).encode()
    req = urllib.request.Request(GQL, data=body, headers={
        "Client-ID": CLIENT_ID, "Content-Type": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        j = json.load(r)
    st = j["data"]["streamPlaybackAccessToken"]
    return st["value"], st["signature"]


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Referer": "https://www.twitch.tv/"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", "replace")


def source_playlist(channel: str, token: str, sig: str) -> str:
    q = urllib.parse.urlencode({
        "acmb": "e30=", "allow_audio_only": "true", "allow_source": "true",
        "p": str(int(time.time())), "platform": "web",
        "playlist_include_framerate": "true", "sig": sig,
        "supported_codecs": "av1,h265,h264", "token": token,
    })
    master = fetch(f"https://usher.ttvnw.net/api/channel/hls/{channel}.m3u8?{q}")
    for line in master.splitlines():
        if line and not line.startswith("#"):
            return fetch(line)          # premiere variante = source
    raise RuntimeError("variante introuvable dans la playlist maitre")


def pod_metrics(playlist: str) -> tuple[int, int, float]:
    """(plages stitched-ad, segments Amazon, duree cumulee des segments pub)"""
    ranges = segs = 0
    secs = 0.0
    for line in playlist.splitlines():
        if line.startswith("#EXT-X-DATERANGE") and "stitched-ad" in line:
            ranges += 1
        elif line.startswith("#EXTINF") and "Amazon" in line:
            segs += 1
            try:
                secs += float(line.split(":", 1)[1].split(",")[0])
            except (ValueError, IndexError):
                pass
    return ranges, segs, secs


def probe(channel: str, board: dict) -> None:
    """Un sondage : capture, metriques de pod, rejeu anti-fuite dans le miroir."""
    try:
        token, sig = gql_token(channel)
        playlist = source_playlist(channel, token, sig)
        ranges, segs, secs = pod_metrics(playlist)

        # ── rejeu anti-fuite : le miroir du sanitizer fait foi ──
        cleaned = mirror.sanitize(playlist)
        survived = [l for l in cleaned.splitlines()
                    if (l.startswith("#EXT-X-DATERANGE") and "stitched-ad" in l)
                    or (l.startswith("#EXTINF") and "Amazon" in l)]
        suspicious = bool(mirror.suspicious)
        board.setdefault(channel, []).append({
            "ok": True, "ranges": ranges, "segs": segs, "secs": secs,
            "survived": survived, "suspicious": suspicious,
            "line": mirror.last_suspicious_line,
        })
    except Exception as e:  # noqa: BLE001
        board.setdefault(channel, []).append({"ok": False, "err": f"{type(e).__name__}: {e}"[:120]})


def main() -> int:
    argv = sys.argv[1:]
    cycles = CYCLES
    if "--cycles" in argv:
        i = argv.index("--cycles")
        cycles = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    quiet = "--quiet" in argv
    channels = [a for a in argv if not a.startswith("--")] or CHANNELS

    board: dict = {c: [] for c in channels}
    print(f"radar : {', '.join(channels)} — {cycles} cycle(s) a {WAIT} s d'ecart")

    for cycle in range(1, cycles + 1):
        threads = [threading.Thread(target=probe, args=(c, board), daemon=True)
                   for c in channels]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        if not quiet:
            print(f"--- cycle {cycle}/{cycles}")
            for c in channels:
                b = board[c][-1]
                if not b["ok"]:
                    print(f"    {c:<16} ERREUR  {b['err']}")
                else:
                    print(f"    {c:<16} plages={b['ranges']:<3} segments={b['segs']:<4} "
                          f"duree={b['secs']:6.1f} s  fuites={len(b['survived'])}  "
                          f"sentinelle={'🚨' if b['suspicious'] else '—'}")
        if cycle < cycles:
            time.sleep(WAIT)

    # ── verdict global ──
    answered = sum(1 for c in channels for b in board[c] if b["ok"])
    pods_seen = sum(1 for c in channels for b in board[c]
                    if b["ok"] and (b["ranges"] or b["segs"]))
    leaks: list[str] = []
    for c in channels:
        for b in board[c]:
            if not b["ok"]:
                continue
            if b["suspicious"]:
                leaks.append(b["line"] or "sentinelle du miroir déclenchée")
            for l in b["survived"]:
                leaks.append(f"marqueur pub survécu au nettoyage : {l}")

    print("\n=== VERDICT ===")
    print(f"    reponses               : {answered}/{len(channels) * cycles} sondages")
    print(f"    playlists avec pod     : {pods_seen}")
    print(f"    marqueurs non reconnus : {len(leaks)}")

    if leaks:
        for l in leaks[:3]:
            print(f"    🚨 {l[:160]}", file=sys.stderr)
        print("\n❌ ECHEC ANTI-FUITE : Twitch sert un marqueur que les regles ne couvrent pas."
              "\n   Capturer la playlist brute (methode AUDIT.md section 4.4), ajouter la regle"
              "\n   dans patch/smali/com/twouich/adblock/PlaylistSanitizer.smali + un cas fige"
              "\n   dans patch/tests/test_sanitizer.py, puis rebuild.", file=sys.stderr)
        return 1
    if answered == 0:
        print("    (offline ou toutes les chaines sont hors ligne : rien n'a pu etre teste)",
              file=sys.stderr)
        return 0
    if pods_seen == 0:
        print("    (aucun pod observe : l'anti-fuite n'a pas eu d'occasion d'etre verifiee)",
              file=sys.stderr)
        return 0
    print("    ✅ anti-fuite vert : aucun marqueur pub hors regles, sentinelle muette.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
