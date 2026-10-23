# Twouich

[![CI](https://github.com/Endymi0n74/Twouich/actions/workflows/build.yml/badge.svg)](https://github.com/Endymi0n74/Twouich/actions/workflows/build.yml)
[![Dernière release](https://img.shields.io/github/v/release/Endymi0n74/Twouich)](https://github.com/Endymi0n74/Twouich/releases/latest)

**🇫🇷 Français** · [🇬🇧 English](README.en.md)

Client Android TV pour Twitch, avec filtrage local des marqueurs publicitaires SSAI, dé-mute VOD et fallback anti-pub VaFT.

> Projet indépendant, sans affiliation avec Twitch Interactive, Inc.

![Splash Twouich](images/splash-twouich.jpg)

![Accueil Twouich](images/accueil-twouich.jpg)

## Fonctionnalités

- **SSAI local** : retrait `stitched-ad` / `Amazon` / `CUE-OUT` avant lecture ExoPlayer (`PlaylistSanitizer`, `AdBlockDataSource`)
- **VOD dé-mutée** `v1.0.16` : `-unmuted` → `-muted` sur playlists `cloudfront` (son d'origine, issu de `TwVodNoAdsJCed`)
- **Fallback VaFT** `v1.0.16` : si `stitched-ad` survit au stripping (nouveau format), tentative flux propre `GQL PlaybackAccessToken embed` → `usher v2` → variante (5s timeout, repli stripping) (`VaftFallback`, dormant tant que `lastCut>0`)
- **Build reproductible** : ZIP canonisé (horodatage + ordre), `SELFTEST 31/31`, `check-release.sh` 4/4

## Nouveautés v1.0.24 — 24 octobre 2026

- **Les points de visionnage arrivent sur téléphone.** Une minute regardée vaut un point, par chaîne, et la pastille s'affiche en haut à gauche de la vidéo (`0 pt`, `12 pts`). Tout reste sur l'appareil, dans les préférences privées de l'application : aucune session Twitch n'est nécessaire et rien n'est envoyé nulle part. Le compteur suit la lecture (rafraîchi toutes les 15 s) et reprend là où il s'était arrêté après une mise à jour.
- **Le lecteur et la fiche chaîne prennent les codes de Twitch mobile.** Sur téléphone uniquement : panneau de chat en surface sombre à coins supérieurs arrondis avec 8 dp de respiration sous la vidéo, bouton picture-in-picture circulaire, champ de saisie en pastille, fiche chaîne en surface sombre avec avatar rond et boutons pilule. La télévision garde son rendu d'origine, vérifié ressource par ressource (`layout-sw600dp`, `layout-sw540dp`, `layout-television`) et à l'écran en 1920×1080.
- **Les listes du lecteur perdent leurs coins droits.** Hauteur, qualité, vitesse de lecture et chapitres de VOD passent de 2 dp — invisibles à l'œil — à 14 dp : les panneaux qui s'ouvrent sur le chat se lisent enfin comme des cartes. Le rayon est posé côté téléphone seulement ; la TV retrouve les 2 dp d'origine.
- **Le secours anti-pub ne sert plus la playlist brute.** Sept conditions étaient inversées dans le repli : quand le filtre principal échouait, l'app rendait la playlist publicitaire telle quelle. Mesuré sur un pod réel : 2 578 octets remplacés par 15 674 octets de contenu propre, `ads_out=false`. La chaîne est désormais connue dès l'ouverture du lecteur — deep link compris — pour que le repli n'ait pas à la deviner.
- Aucun message n'a été envoyé et aucune session n'a été perdue pendant la validation (`adb install -r`).

## Installation

Télécharger [`Twouich_v1.0.24.apk`](https://github.com/Endymi0n74/Twouich/releases/download/v1.0.24/Twouich_v1.0.24.apk) depuis la release publiée.

```bash
adb install -r Twouich_v1.0.24.apk
```



## Projet source et crédits

Twouich est basé sur le projet d'origine [S0undTV](https://github.com/S0und/S0undTV). Merci à ses auteurs et contributeurs pour le travail initial et les bibliothèques utilisées.

Ce dépôt redistribue uniquement des binaires patchés et les patchs associés ; il ne redistribue pas le code source original. Voir [`CREDITS.md`](CREDITS.md) pour les détails.



## Limites

Le filtrage dépend du format actuel des marqueurs publicitaires Twitch. Les VODs sub-only ne sont lues que si un jeton mémorisé côté app reste accepté par `usher` (comportement serveur, observé sur VOD sub-only). Le fallback VaFT ne s'active que si le stripping échoue et reste replié sur le stripping local en cas d'erreur réseau.
