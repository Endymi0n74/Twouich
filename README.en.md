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

## What's new in v1.0.16 — September 22, 2026

Integration of `TwVodNoAdsJCed`: VOD un-mute + dormant VaFT fallback, dead code removal (`twouich_ic_chat`, `res-tv/activity_main`, `import datetime`). See [`CHANGELOG-twouich.md`](CHANGELOG-twouich.md) and [`memory.md`](memory.md).


## Installation

Download [`Twouich_v1.0.16.apk`](https://github.com/Endymi0n74/Twouich/releases/download/v1.0.16/Twouich_v1.0.16.apk) from the published release.

```bash
adb install -r Twouich_v1.0.16.apk
```



## Source project and credits

Twouich is based on the original [S0undTV](https://github.com/S0und/S0undTV) project. Thanks to its authors and contributors for the initial work and the libraries used.

This repository only redistributes patched binaries and the associated patches; it does not redistribute the original source code. See [`CREDITS.md`](CREDITS.md) for details.



## Limitations

Filtering depends on the current format of Twitch ad markers. Sub-only VODs are only played if a token cached on the app side is still accepted by `usher` (server behaviour, observed on sub-only VODs). The VaFT fallback only kicks in when stripping fails, and falls back to local stripping on network errors.
