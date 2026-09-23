# Twouich

[![CI](https://github.com/Endymi0n74/Twouich/actions/workflows/build.yml/badge.svg)](https://github.com/Endymi0n74/Twouich/actions/workflows/build.yml)
[![Dernière release](https://img.shields.io/github/v/release/Endymi0n74/Twouich)](https://github.com/Endymi0n74/Twouich/releases/latest)

Client Android TV pour Twitch, avec filtrage local des marqueurs publicitaires SSAI, dé-mute VOD et fallback anti-pub VaFT.

> Projet indépendant, sans affiliation avec Twitch Interactive, Inc.

![Splash Twouich](images/splash-twouich.jpg)

![Accueil Twouich](images/accueil-twouich.jpg)

## Fonctionnalités

- **SSAI local** : retrait `stitched-ad` / `Amazon` / `CUE-OUT` avant lecture ExoPlayer (`PlaylistSanitizer`, `AdBlockDataSource`)
- **VOD dé-mutée** `v1.0.16` : `-unmuted` → `-muted` sur playlists `cloudfront` (son d'origine, issu de `TwVodNoAdsJCed`)
- **Fallback VaFT** `v1.0.16` : si `stitched-ad` survit au stripping (nouveau format), tentative flux propre `GQL PlaybackAccessToken embed` → `usher v2` → variante (5s timeout, repli stripping) (`VaftFallback`, dormant tant que `lastCut>0`)
- **Build reproductible** : ZIP canonisé (horodatage + ordre), `SELFTEST 31/31`, `check-release.sh` 4/4

## Nouveautés v1.0.16 — 22 septembre 2026

Intégration `TwVodNoAdsJCed` : dé-mute VOD + fallback VaFT dormant, purge code mort (`twouich_ic_chat`, `res-tv/activity_main`, `import datetime`). Voir [`CHANGELOG-twouich.md`](CHANGELOG-twouich.md) et [`memory.md`](memory.md).


## Installation

Télécharger [`Twouich_v1.0.16.apk`](https://github.com/Endymi0n74/Twouich/releases/download/v1.0.16/Twouich_v1.0.16.apk) depuis la release publiée.

```bash
adb install -r Twouich_v1.0.16.apk
```



## Projet source et crédits

Twouich est basé sur le projet d'origine [S0undTV](https://github.com/S0und/S0undTV). Merci à ses auteurs et contributeurs pour le travail initial et les bibliothèques utilisées.

Ce dépôt redistribue uniquement des binaires patchés et les patchs associés ; il ne redistribue pas le code source original. Voir [`CREDITS.md`](CREDITS.md) pour les détails.



## Limites

Le filtrage dépend du format actuel des marqueurs publicitaires Twitch. Les VODs sub-only ne sont lues que si un jeton mémorisé côté app reste accepté par `usher` (comportement serveur, observé sur VOD sub-only). Le fallback VaFT ne s'active que si le stripping échoue et reste replié sur le stripping local en cas d'erreur réseau.
