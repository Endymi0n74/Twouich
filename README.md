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

## Nouveautés v1.0.28 — 25 octobre 2026

- **Le retour dans le lecteur ne masque plus la saisie.** Sur téléphone, un appui sur RETOUR dans le lecteur ne cache plus la barre « Envoyer un message » ; le lecteur reste ouvert, le chat reste visible, et le champ garde son brouillon quand il est focalisé. Un second RETOUR sort du lecteur vers la chaîne d'origine.
- **Derrière ce correctif, deux causes distinctes.** Le garde `onKeyDown` donnait la touche à la branche TV sur téléphone (donc `setVisibility(8)` sur la saisie, consommation de la touche, plus de journal « RETOUR »), et le champ avait un `OnKeyListener` amont qui vidait le brouillon puis appelait `K1(false)` sans garde — plantage `NullPointerException` quand le lecteur n'est pas ouvert. Les deux sont corrigés sur le bytecode livré : la touche revient à `onKeyDown` téléphone (et nulle part ailleurs), et `K1` n'est plus atteint sur RETOUR.
- **Preuves hors appareil** : `test_smali_branches.py` **84/84** verrous (dont les deux sommets `if-eqz v0, :twouich_back_phone` dans `onKeyDown` — inverse du bon sens — et les branches `if-eqz v1, :invoke` / `if-eqz v0, :invoke` dans `twouichPhoneBack` — inverse de la porte dérobée), le sélecteur de méthode de retour `twouichPhoneBack` présent dans le dex livré, et l'invariant « source unique TV » : le patch n'écrit jamais `OnKeyListener` sur `SendMessageWindow` (appui de test : substituer un garde `if-nez` sur la méthode montée fausse le test).
- **Validé sur BlueStacks (v1.0.28, `install -r`)**. Clavier ouvert, champ focalisé : journal `RETOUR : clavier ferme, barre de saisie conservee`, clavier refermé, `topResumedActivity` reste `PlayerActivity`, `SendMessageWindow [0,1184][720,1280]` et champ `[12,1198][558,1265]` inchangés, texte `brouillonRETOUR` conservé, **0 FATAL**. Sans clavier : `RETOUR : rendu a la chaine d'origine (touche non consommee)` et sortie du lecteur vers `MainActivity`. Réouverture de la chaîne : barre de nouveau présente avec son texte d'invite. `ALLOW_UPDATE_JSON_LAG=1 python patch/tests/test_apk.py` → **livrable conforme**.

## Installation

Télécharger [`Twouich_v1.0.28.apk`](https://github.com/Endymi0n74/Twouich/releases/download/v1.0.28/Twouich_v1.0.28.apk) depuis la release publiée.

```bash
adb install -r Twouich_v1.0.28.apk
```



## Projet source et crédits

Twouich est basé sur le projet d'origine [S0undTV](https://github.com/S0und/S0undTV). Merci à ses auteurs et contributeurs pour le travail initial et les bibliothèques utilisées.

Ce dépôt redistribue les binaires patchés, les patchs associés et l'APK amont d'origine qui sert d'entrée de build (`patch/upstream/beta_144.apk`, nécessaire pour qu'un clone reconstruise à l'identique) ; il ne redistribue pas le code source original. Voir [`CREDITS.md`](CREDITS.md) pour les détails.



## Limites

Le filtrage dépend du format actuel des marqueurs publicitaires Twitch. Les VODs sub-only ne sont lues que si un jeton mémorisé côté app reste accepté par `usher` (comportement serveur, observé sur VOD sub-only). Le fallback VaFT ne s'active que si le stripping échoue et reste replié sur le stripping local en cas d'erreur réseau.
