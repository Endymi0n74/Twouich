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

## What's new in v1.0.23 — October 6, 2026

- **Phone-player rotation no longer breaks the layout mid-playback.** Switching portrait → landscape keeps the video at an exact 16:9 frame (`1845×1038` in a simulated 2712×1220 screen) and ranks chat and the compose bar in a column to its right — the landscape branch is replayed with **re-measured** geometry, instead of the stale configuration `onConfigurationChanged` still found in place.
- **The "Send a message" bar rises above the keyboard.** Measured glued to the IME top edge (`y=1687` with the keyboard open up to 2712) while the chat shrinks accordingly; keyboard closed, the original portrait stacking is unchanged. With the window edge-to-edge (target 35), `adjustResize` is not enough — and **IME insets report nothing on this MIUI**: the keyboard height is read via `getWindowVisibleDisplayFrame`, the only reliable source measured on the device. A layout watch (`PhoneLayoutWatch`) replays the geometry on every visible-frame change, with an anti-loop guard.
- No message was sent during validation; no session was lost (`adb install -r`, `firstInstallTime` preserved). Measurement details and recipes: `TEST-DEVICE.md` § 8.26.

## Installation

Download [`Twouich_v1.0.23.apk`](https://github.com/Endymi0n74/Twouich/releases/download/v1.0.23/Twouich_v1.0.23.apk) from the published release.

```bash
adb install -r Twouich_v1.0.23.apk
```



## Source project and credits

Twouich is based on the original [S0undTV](https://github.com/S0und/S0undTV) project. Thanks to its authors and contributors for the initial work and the libraries used.

This repository only redistributes patched binaries and the associated patches; it does not redistribute the original source code. See [`CREDITS.md`](CREDITS.md) for details.



## Limitations

Filtering depends on the current format of Twitch ad markers. Sub-only VODs are only played if a token cached on the app side is still accepted by `usher` (server behaviour, observed on sub-only VODs). The VaFT fallback only kicks in when stripping fails, and falls back to local stripping on network errors.
