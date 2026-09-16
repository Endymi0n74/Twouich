# Twouich

Client Android TV pour Twitch, avec filtrage local des marqueurs publicitaires SSAI.

> Projet indépendant, sans affiliation avec Twitch Interactive, Inc.

![Splash Twouich](images/splash-twouich.jpg)

## v1.0.1

- accent par défaut recoloré aux couleurs Twouich : plus de rouge d'origine dans l'interface ;
- l'accent par défaut s'appelle « Twouich » dans les réglages.

## v1.0.0

- identité visuelle Twouich violette avec monogramme `T`, mot-symbole volumétrique et tagline TV ;
- splash, icônes, bannière TV et captures du tutoriel régénérés avec la même identité ;
- filtrage des plages publicitaires HLS `stitched-ad`, `CUE-OUT`/`CUE-IN` et segments publicitaires ;
- self-test du filtre dans le code compilé ;
- updater limité aux releases Twouich, avec comparaison à la version réellement installée : une version déjà à jour ne redemande pas la même mise à jour ;
- changelog embarqué neuf, avec lien vers le projet source et crédits.

## Installation

Télécharger [`Twouich_v1.0.1.apk`](https://github.com/Endymi0n74/Twouich/releases) depuis la release publiée.

```bash
adb install -r Twouich_v1.0.1.apk
```

Le paquet Android technique est conservé pour permettre les mises à jour par-dessus une installation Twouich existante. La signature doit rester la même pour les versions suivantes ; la clé de signature n'est jamais versionnée.

## Vérification locale

Depuis la racine du dépôt :

```bash
python patch/tests/test_sanitizer.py
python patch/tests/test_smali_branches.py
python patch/tests/test_brand.py
python patch/tests/test_apk.py
bash patch/tests/test_analyzer.sh
```

Le résultat attendu est :

- règles de nettoyage conformes ;
- 10 vérifications smali ;
- identité visuelle conforme ;
- APK signé conforme à `update.json`.

Pour vérifier le comportement sur un appareil :

```bash
bash patch/test-selftest.sh --in-app
bash patch/test-device.sh --fresh
```

Le self-test attendu est `SELFTEST 18/18`.

## Construire

La chaîne complète vérifie l'APK source, désassemble, applique les patchs, régénère l'identité, reconstruit et signe l'APK :

```bash
bash patch/build.sh
```

Les outils locaux sont ignorés par Git. Le mot de passe de la clé doit être fourni via `keys/keystore.properties` ou `KEY_PASS` ; il n'est pas stocké dans le dépôt.

## Identité visuelle

Les assets versionnés sont générés par une seule source de vérité :

```bash
python patch/branding/make_brand.py preview
python patch/branding/make_brand.py emit
```

La piste livrée est un dégradé violet profond avec badge `T`, texte arrondi en relief, ombres douces et tagline `an Android TV client for Twitch`.

## Projet source et crédits

Twouich est basé sur le projet d'origine [S0undTV](https://github.com/S0und/S0undTV). Merci à ses auteurs et contributeurs pour le travail initial et les bibliothèques utilisées.

Ce dépôt redistribue uniquement des binaires patchés et les patchs associés ; il ne redistribue pas le code source original. Voir [`CREDITS.md`](CREDITS.md) pour les détails.

## Fichiers importants

| Fichier | Rôle |
|---|---|
| `patch/build.sh` | version, APK source et chaîne de build |
| `patch/patch.py` | patchs smali, updater, pages embarquées et version |
| `patch/branding/make_brand.py` | génération du splash, des icônes et de la bannière |
| `patch/smali/com/twouich/adblock/` | filtre HLS et self-test embarqué |
| `update.json` | release annoncée à l'application |
| `CHANGELOG-twouich.md` | journal public |
| `TEST-DEVICE.md` | procédure de validation appareil |
| `AUDIT.md` | audit technique et limites connues |

## Limites

Le filtrage dépend du format actuel des marqueurs publicitaires Twitch. Il ne contourne aucun abonnement ni contenu payant.
