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

## What's new in v1.0.26 — October 24, 2026

- **Watch points are removed.** The v1.0.25 counter invented its numbers: one minute watched counted as one point, while Twitch channel points are not earned that way and the app embeds neither GQL/Helix nor a token to read them. The badge, the counter, its ticker and the long-press go away, together with the composer row view and the player methods. The composer row is back to exactly the message field, the send arrow and the player options.
- **The defect shipped in v1.0.25 goes with it.** The APK published as `v1.0.25` embedded `PointsTicker.run()` calling `PlayerActivity.twouichPhonePointsTick()`, a method **missing from the dex**: a `NoSuchMethodError` fifteen seconds into playback. Two checks now lock the feature out of the delivered dex and layout.
- **Everything else in v1.0.25 is unchanged**: phone player (dark chat, circular PiP, pill composer), channel page, portrait and landscape geometry, branding and ad filtering. TV mode stays as it was.

## Installation

Download [`Twouich_v1.0.26.apk`](https://github.com/Endymi0n74/Twouich/releases/download/v1.0.26/Twouich_v1.0.26.apk) from the published release.

```bash
adb install -r Twouich_v1.0.26.apk
```



## Source project and credits

Twouich is based on the original [S0undTV](https://github.com/S0und/S0undTV) project. Thanks to its authors and contributors for the initial work and the libraries used.

This repository redistributes the patched binaries, the associated patches and the original upstream APK used as the build input (`patch/upstream/beta_144.apk`, required for a clone to rebuild byte-identical output); it does not redistribute the original source code. See [`CREDITS.md`](CREDITS.md) for details.



## Limitations

Filtering depends on the current format of Twitch ad markers. Sub-only VODs are only played if a token cached on the app side is still accepted by `usher` (server behaviour, observed on sub-only VODs). The VaFT fallback only kicks in when stripping fails, and falls back to local stripping on network errors.
