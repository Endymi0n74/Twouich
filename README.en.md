# Twouich

[![CI](https://github.com/Endymi0n74/Twouich/actions/workflows/build.yml/badge.svg)](https://github.com/Endymi0n74/Twouich/actions/workflows/build.yml)
[![Latest release](https://img.shields.io/github/v/release/Endymi0n74/Twouich)](https://github.com/Endymi0n74/Twouich/releases/latest)

[🇫🇷 Français](README.md) · **🇬🇧 English**

Android TV client for Twitch, with local filtering of SSAI ad markers, VOD un-muting and VaFT anti-ad fallback.

> Independent project, not affiliated with Twitch Interactive, Inc.

![Twouich splash](images/splash-twouich.jpg)

![Twouich home](images/accueil-twouich.jpg)

## Features

- **Local SSAI**: removes `stitched-ad` / `Amazon` / `CUE-OUT` before ExoPlayer playback (`PlaylistSanitizer`, `AdBlockDataSource`)
- **Un-muted VOD** `v1.0.16`: `-unmuted` → `-muted` on `cloudfront` playlists (original audio, from `TwVodNoAdsJCed`)
- **VaFT fallback** `v1.0.16`: if `stitched-ad` survives stripping (new format), attempt clean stream `GQL PlaybackAccessToken embed` → `usher v2` → variant (5s timeout, fallback to stripping) (`VaftFallback`, dormant while `lastCut>0`)
- **Reproducible build**: canonicalized ZIP (timestamp + order), `SELFTEST 31/31`, `check-release.sh` 4/4

## What's new in v1.0.28 — October 25, 2026

- **The return key no longer hides the compose bar.** On phones, pressing return inside the player no longer hides the compose bar; the player stays open, the chat stays visible, and the message field keeps its draft when it is focused. A second return exits the player back to the original channel.
- **Two separate causes were fixed.** The onKeyDown guard was routing the key to the TV branch on phones (hiding the compose bar, consuming the key, no "return" log), and the message field had an upstream OnKeyListener that cleared the draft then called K1(false) with no guard — a NullPointerException when the player was not open. Both are fixed in the delivered bytecode: the key now returns to onKeyDown on phones, and K1 is no longer reached on return.
- **Watch points were already removed in v1.0.26.** This release only fixes the return-key defect.

## Installation

Download [`Twouich_v1.0.28.apk`](https://github.com/Endymi0n74/Twouich/releases/download/v1.0.28/Twouich_v1.0.28.apk) from the published release.

```bash
adb install -r Twouich_v1.0.28.apk
```



## Source project and credits

Twouich is based on the original [S0undTV](https://github.com/S0und/S0undTV) project. Thanks to its authors and contributors for the initial work and the libraries used.

This repository redistributes the patched binaries, the associated patches and the original upstream APK used as the build input (`patch/upstream/beta_144.apk`, required for a clone to rebuild byte-identical output); it does not redistribute the original source code. See [`CREDITS.md`](CREDITS.md) for details.



## Limitations

Filtering depends on the current format of Twitch ad markers. Sub-only VODs are only played if a token cached on the app side is still accepted by `usher` (server behaviour, observed on sub-only VODs). The VaFT fallback only kicks in when stripping fails, and falls back to local stripping on network errors.
