#!/usr/bin/env python3
"""
test_radar.py — vérifie le rejeu anti-fuite de patch/radar-ads.py.

Le radar sonde Twitch en réseau ; ce test, lui, est **hors réseau** : il
stubbe la chaîne GQL/usher et vérifie la logique qui fait foi —

  1. la playlist SSAI **réelle** capturée le 18/09 (fixtures/), passée
     dans le vrai chemin `probe()` du radar : pod détecté, **0 fuite**,
     sentinelle muette — le cas nominal ;
  2. MUTATION — un sanitizer qui ne retire plus rien : le radar doit voir
     les marqueurs survivre au nettoyage (champ `survived`) ;
  3. MUTATION — un format renommé (`stitched-ad`/`quartile` absents) :
     la sentinelle du miroir doit parler, ligne HLS brute à l'appui.

    python patch/tests/test_radar.py
"""
from __future__ import annotations

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "patch"))

import radar_ads as radar  # noqa: E402
import test_sanitizer as mirror  # noqa: E402

FIXTURE = ROOT / "patch" / "tests" / "fixtures" / "ssai-2026-09-18.m3u8"

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        print(f"  ✅ {name}")
        PASS += 1
    else:
        print(f"  ❌ {name}{f' — {detail}' if detail else ''}")
        FAIL += 1


def run_probe(playlist: str) -> dict:
    """Passe `playlist` dans le vrai probe() du radar, réseau stubbé."""
    radar.gql_token = lambda ch: ("token-stubbe", "signature-stubbee")
    radar.source_playlist = lambda ch, tok, sig: playlist
    board: dict = {}
    radar.probe("chaine-stubbee", board)
    return board["chaine-stubbee"][-1]


fixture = FIXTURE.read_text(encoding="utf-8")

# ── préconditions : la fixture est bien celle du 18/09 ──
r0, s0, _ = radar.pod_metrics(fixture)
check("fixture : plages stitched-ad >= 1", r0 >= 1, f"r0={r0}")
check("fixture : 3 segments Amazon", s0 == 3, f"s0={s0}")

# ── 1. cas nominal : la fixture dans le vrai chemin probe() ──
mirror.sanitize  # (référence vivante : le radar utilise le miroir importé)
b = run_probe(fixture)
check("nominal : probe ok", b["ok"] is True)
check("nominal : pod détecté (plages>=1, segments=3)",
      b["ok"] and b["ranges"] >= 1 and b["segs"] == 3)
check("nominal : 0 marqueur survit au nettoyage",
      b["ok"] and b["survived"] == [], f"survived={b.get('survived')}")
check("nominal : sentinelle muette", b["ok"] and b["suspicious"] is False)

# ── 2. mutation : sanitizer affaibli (ne retire plus rien) ──
real_sanitize = mirror.sanitize
mirror.sanitize = lambda body: body           # le sanitizer ne fait plus rien
b2 = run_probe(fixture)
mirror.sanitize = real_sanitize
check("mutation sans-règles : les marqueurs pub survivent",
      len(b2["survived"]) >= 4, f"survived={len(b2['survived'])}")

# ── 3. mutation : Twitch renomme son format ──
renamed = fixture.replace("stitched-ad", "renamed-ad").replace("quartile", "renamed-quartile")
r3, s3, _ = radar.pod_metrics(renamed)
check("mutation format renommé : plus aucun marqueur connu côté métriques",
      r3 == 0 and s3 == 3, f"r3={r3} s3={s3}")
b3 = run_probe(renamed)
check("mutation format renommé : la sentinelle du miroir parle",
      b3["ok"] and b3["suspicious"] is True)
check("mutation format renommé : la ligne HLS brute est capturée",
      b3["ok"] and "X-TV-TWITCH-AD" in (b3["line"] or ""), f"line={b3.get('line')!r}")

print()
if FAIL == 0:
    print(f"✅ rejeu anti-fuite conforme ({PASS}/{PASS})")
    sys.exit(0)
print(f"❌ {FAIL} échec(s) sur {PASS + FAIL}")
sys.exit(1)
