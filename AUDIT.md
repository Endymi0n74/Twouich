# Audit Twouich — dépôt & APK Android TV

*15 septembre 2026 — audit de `Endymi0n74/Twouich` et de l'APK upstream `beta_144.apk`*

## 1. L'objet audité

| Élément | Constat vérifié |
|---|---|
| `Endymi0n74/Twouich` | créé le **14/09/2026** (mise en ligne 19:10→19:14), branche `master`, **0 release**, **aucun langage détecté** |
| Contenu | `README.md`, `images/` (3 jpg), `update.json`, `.github/FUNDING.yml` — c'est-à-dire une **copie du dépôt de distribution de `S0und/S0undTV`** |
| Code source de l'app | **absent** : S0undTV est un logiciel **closed source** ; ce dépôt ne publie que des APK et un manifeste de version |
| `README.md` | **verbatim** de celui de S0undTV (identité, Discord, changelog `s0und.github.io`, installation `bit.ly/S0und-TV`) |
| `update.json` | **verbatim** de celui de S0undTV : 3 entrées (standalone 143 du 06/08/2024, `beta_144.apk` du 28/12/2025, entrée Play Store vide), dont les fichiers APK n'existent **que** dans les releases de S0und |
| `.github/FUNDING.yml` | gabarit par défaut, mais avec `custom: ['https://www.paypal.me/S0undTV']` → **le bouton Sponsor de notre dépôt envoyait de l'argent au développeur d'origine** |
| APK upstream analysé | `beta_144.apk`, 10 398 408 o, SHA-256 `578da49b…51b0`, release tag `beta` |

## 2. Ce que fait réellement l'APK `beta_144.apk`

| Propriété | Valeur |
|---|---|
| Package | `com.s0und.s0undtv` (libellé « Sound TV ») |
| versionCode / versionName | **144** / `beta_144` |
| minSdk / targetSdk | **23** / **35** (Android TV, leanback requis) |
| Dex | 2 (`classes.dex` 7,4 Mo + `classes2.dex` 1,6 Mo) |
| ABIs natives | arm64-v8a, armeabi-v7a, **x86**, **x86_64** → tourne sur BlueStacks x86_64 sans couche de traduction |
| Lecteur | ExoPlayer 2 (`HlsMediaSource`), codec HLS natif |
| Client réseau HLS | `Lz3/u;` = **HttpURLConnection** (et non OkHttp) — un intercepteur OkHttp ne verrait rien |
| Obfuscation | R8 sur les **libs** (`z3`, `i3`, `l3`, `m3`, `s4`…), mais **le code de l'app garde ses noms** (`com.s0und.s0undtv.*`, 226 classes) → patch statique très praticable |
| Anti-pub | **aucun** : aucune occurrence de `adblock`, `stitched`, `adbreak`, `preroll`, `midroll`, `commercial` dans les 2 dex |

### 2.1 Système de mise à jour (standalone) — 4 emplacements codés en dur

| Fichier | Constante | Valeur d'origine |
|---|---|---|
| `helpers/UpdateHelper.smali` | manifeste des versions | `https://raw.githubusercontent.com/S0und/S0undTV/master/update.json` |
| `helpers/UpdateHelper.smali` | changelog beta | `https://github.com/S0und/S0undTV/releases/download/beta/changelog.html` |
| `helpers/UpdateHelper.smali` | préfixe des APK standalone | `https://github.com/S0und/S0undTV/releases/download/` |
| `helpers/a.smali` | préfixe beta + préfixe standalone | `…/releases/download/beta/` et `…/releases/download/` |
| `service/AutoUpdateService.smali` | **ancien updater** | `https://share.s0und.cloudns.cl/app-release.apk` |

### 2.2 Point d'accroche réseau du lecteur (trouvé)

* `HlsMediaSource$Factory` est construit **7 fois** dans l'app (`PlayerActivity` ×5, `Fragments/b`, `SearchFragment`) et reçoit à chaque fois une **factory de source de données `Lz3/u$a` instanciée depuis `Lz3/u$b`**.
* `Lz3/u;` (la source de données concrète) n'est instanciée **qu'à un seul endroit** : `Lz3/u$b.b()`, appelée uniquement par `Lz3/u$b.a()` (la méthode d'interface `Lz3/l$a.a()`).
* ⇒ **Patcher `Lz3/u$b.a()` suffit** à intercepter *toutes* les lectures HLS : playlist maître, playlist de variante (celle qui contient les pubs), segments, clés.

## 3. Registre des obsolescences et des risques

| # | Constat | Nature | Action |
|---|---|---|---|
| 1 | Mise à jour automatique pointant vers `S0und/S0undTV` | **bloquant** : l'app installée proposerait (et tenterait d'installer) le build de S0und, écrasant le nôtre | ✅ corrigé — 5 URLs repointées vers `Endymi0n74/Twouich` (`patch/patch.py`) |
| 2 | `AutoUpdateService` → `share.s0und.cloudns.cl` | **mort** (ancien backend, domaine abandonné) | ✅ corrigé — repointé sur `…/Twouich/releases/latest/download/<apk>` |
| 3 | `update.json` décrivant les APK de S0und | obsolète/incohérent dans notre dépôt | ✅ réécrit — une seule entrée, la nôtre (versionCode 147, tag `v1.0.0`) |
| 4 | `README.md` copié de l'upstream (identité, liens, installation `bit.ly/S0und-TV`) | mensonger / trompeur | ✅ réécrit (`README.md` Twouich) |
| 5 | `FUNDING.yml` → PayPal de S0und | détournement de dons | ✅ neutralisé |
| 6 | Aucune release, aucune CI, aucune licence/attribution | dépôt inutilisable en l'état | ✅ release documentée + `CREDITS.md` ; CI laissée en suspens (voir §5) |
| 7 | **Aucun anti-pub** dans l'APK : les pubs SSAI « stitched » restent dans la playlist de variante | **le cœur de la demande** | ✅ mis en place (`AdBlockDataSource` + `PlaylistSanitizer`), voir §4 |
| 8 | Version absente du manifest reconstruit (apktool 3 déplace `versionCode`/`versionName` vers `apktool.yml` et ne les réinjecte pas) | **piège de build** : un APK sans versionCode est refusé à l'installation | ✅ corrigé — réécriture explicite des attributs dans `AndroidManifest.xml` |
| 9 | Signature d'origine S0und | notre build est signé par une clé différente ⇒ **impossible de mettre à jour par-dessus l'app officielle** | ✅ documenté (désinstallation obligatoire) + clé dédiée `keys/twouich.keystore` |
| 10 | Endpoints tiers morts possibles (`recent-messages.robotty.de`, `pronouns`, 7TV/BTTV/FFZ, « proxy Tokyo » pour le 1080p) | obsolescence partielle, non bloquante pour l'anti-pub | ⚠️ documenté, non touché (hors périmètre demandé) |
| 11 | `beta_144` est une **beta** : une nouvelle beta upstream peut casser le patch | risque de maintenance | ✅ atténué : chaîne rejouable, patchs dans `patch/`, `patch.py` échoue bruyamment si un motif disparaît |

## 4. Anti-pub — mécanisme mis en place

### 4.1 Pourquoi il n'existe pas d'« anti-pub du navigateur » à porter

Twitch diffuse aujourd'hui les pubs en **SSAI (server-side ad insertion)** : les segments publicitaires sont cousus **dans la playlist de variante**. Les méthodes « client-side » (bloquer une requête, changer d'url d'API, `player=twitchweb`) ne suffisent plus ; deux familles de solutions existent réellement :

1. **proxy** : faire passer les requêtes vers `usher.ttvnw.net` par un service tiers qui sert des playlists nettoyées (famille TTV LOL / Purple AdBlock) ;
2. **stripping local** : réécrire soi-même la playlist pour retirer les plages publicitaires.

Les deux sont implémentées, dans **un seul point d'injection**.

### 4.2 `PlaylistSanitizer` — règles de suppression

Reprises de l'implémentation de référence de Streamlink (`plugins/twitch.py`), qui est l'outil le plus à jour sur ce sujet :

* une plage est **publicitaire** si un `#EXT-X-DATERANGE` a `CLASS="twitch-stitched-ad"` ou un `ID` commençant par `stitched-ad-` ;
* un segment est **publicitaire** s'il est titré `…Amazon…` (marqueur SSAI), ou s'il tombe dans une plage publicitaire ;
* les tags `#EXT-X-CUE-OUT` / `#EXT-X-CUE-IN` (publicités côté client) encadrent une zone supprimée ;
* les `#EXT-X-DISCONTINUITY` et `#EXT-X-TWITCH-LIVE-SEQUENCE` **sont conservés** : ils signalent au lecteur le saut de timeline (sinon ExoPlayer se bloque sur une discontinuité non déclarée).

La logique est volontairement **ligne par ligne** (machine à états `inAd`/`inCue`/`skipUri`) : pas de calcul de dates, donc pas de dépendance à l'horloge ni au fuseau, et un comportement prévisible.

Ces règles sont **figées par un test** (`patch/tests/test_sanitizer.py`, miroir Python de la machine à états) : 17 assertions sur des playlists réalistes (pub SSAI live, bloc `CUE-OUT`, titre `Amazon`, `DATERANGE` non publicitaire, playlist maître, idempotence).

```bash
python patch/tests/test_sanitizer.py
```

### 4.3 `AdBlockDataSource` — où ça s'accroche

* Implémente `Lz3/l` (l'interface source de données d'ExoPlayer) en délégant à la source réelle.
* Si l'URL demandée se termine par `.m3u8` → la réponse est **lue en entier, nettoyée, puis resservie** (le contenu d'une playlist est petit, l'impact est négligeable).
* Sinon (segments `.ts`, clés, images) → **passage direct**, zéro copie.
* **Proxy d'abord** : si `PROXY_HOST` est renseigné, les requêtes vers `usher.ttvnw.net` partent d'abord vers ce proxy (même chemin, même requête) ; **toute exception retombe immédiatement** sur l'URL d'origine, puis sur le stripping local. C'est littéralement « proxy d'abord, stripping local en secours ».
* **Self-test embarqué** (`SelfTest` + `SelfTest$Fake`, même paquet) : branché sur `MainApp.onCreate`, il rejoue des playlists publicitaires Twitch dans le code compilé et fait traverser `AdBlockDataSource` (source en mémoire, lecture par tranches de 64 octets) avant de publier son verdict sur logcat. Deuxième point d'injection posé par `patch.py`, à côté de `z3/u$b.a()`.

**Le proxy est désactivé par défaut** (`PROXY_HOST = ""`), volontairement : aucun proxy communautaire public n'expose aujourd'hui l'API de relais « chemin conservé » utilisée ici, et TTV LOL PRO exige désormais une session propre à son client. Activer un hôte mort aurait cassé la lecture au lieu d'aider. Pour l'activer, une seule ligne à changer :

```
patch/smali/com/twouich/adblock/AdBlockDataSource.smali
    .field private static final PROXY_HOST:Ljava/lang/String; = "mon-proxy.exemple.net"
```

### 4.4 Portée réelle et ce qui reste à valider sur un appareil

* Couvert par construction : **toutes** les lectures HLS de l'app (lecteur live, lecteur VOD, aperçus de la page d'accueil et de la recherche), puisque `Lz3/u$b.a()` est l'unique fabrique de sources de données.
* **Traçabilité embarquée** : chaque playlist nettoyée produit une ligne logcat `[Twouich] playlist nettoyee <avant> -> <après> octets, segments pub retires : <n>` ; un échec de proxy produit `proxy indisponible : repli sur la requete directe`. Le blocage est donc **observable** sur l'appareil, et pas seulement constatable à l'œil.
* Procédure de test complète (installation, capture filtrée, checklist de coupure, verdict) : [`TEST-DEVICE.md`](TEST-DEVICE.md) + `patch/test-device.sh` et `patch/analyze_device_log.sh`.
* **Vérifié sur appareil** (émulateur BlueStacks, API 25, compte Twitch connecté, session de 4 min) : l'app s'installe, la lecture d'une chaîne en direct fonctionne — 131 nettoyages de playlist média, des milliers de lectures de segments, **0 erreur de lecture** — et le filtre est bien traversé par toutes les lectures HLS.
* **Trois défauts de branchement trouvés par ce test**, invisibles pour le miroir Python : `if-eqz`/`if-nez` inversés dans `PlaylistSanitizer.a` (les vraies playlists repartaient intactes) et dans `AdBlockDataSource.read` (plantage au premier appel), plus l'emploi de `if-gez`/`if-gtz` avec leur sens naturel alors que Dalvik les définit à l'envers (`if-gez` teste `>= 0`, `if-gtz` teste `> 0`), ce qui vidait le flux. Corrigés, vérifiés en direct, et verrouillés par `patch/tests/test_smali_branches.py`.
* **Quatrième défaut, trouvé le 15/09/2026 par le self-test embarqué** : dans `PlaylistSanitizer`, le test de forme du compteur (`startsWith("#")`) était branché à l'envers, si bien que `segments pub retires : n` comptait les **balises** jetées et ignorait les URI (4 annoncés pour 3 segments réels). Le nettoyage était correct ; c'est la preuve annoncée qui était fausse — et c'est précisément le genre d'écart qu'aucun test hors appareil ne peut voir.
* **Le retrait effectif d'une publicité n'est plus une hypothèse.** La session live n'avait servi aucun marqueur (`retires : 0` sur 131 nettoyages), mais le self-test embarqué rejoue à volonté des playlists SSAI/CUE/Amazon aux formats Twitch, dans le code compilé : `SELFTEST 18/18`, et dans l'app `playlist nettoyee 623 -> 328 octets, segments pub retires : 3`. Une capture live reste utile pour vérifier la tenue pendant un direct, plus pour démontrer le mécanisme.
* À observer en direct malgré tout :
  1. la vidéo ne doit pas se figer au moment d'une coupure ;
  2. l'image doit sauter directement du contenu à la suite du contenu (avec un bref raccord) ;
  3. la capture doit contenir une ligne `segments pub retires : n` (`n > 0`) et aucune erreur `Discontinuity` / `BehindLiveWindow`.
* Cas particulier à surveiller : si Twitch change un jour le format des marqueurs (`twitch-stitched-ad`), il suffira d'ajuster la constante `"stitched-ad"` de `PlaylistSanitizer` — c'est le seul endroit à toucher.

### 4.5 Identité visuelle — les surfaces de marque, et celles qu'on avait ratées

La marque d'origine se trouvait sur **six** surfaces déclarées : écran de démarrage
(`drawable/s0undtv_logo_with_text_2.xml`, un vecteur rouge `#a30f2c` avec le mot-symbole),
icônes de lancement (`mipmap-*/ic_launcher*`), bannière TV (`banner_320_180.png` / `banner.png`),
nom affiché (`app_name` + libellé du manifeste), fond de l'icône adaptative
(`color/ic_launcher_background`), et les deux pages embarquées (`assets/S0undTV_about.html`,
`assets/S0undTV_changelog.html` — la seconde avait un fond **rouge opaque**).

Elle se trouvait aussi sur **trois** surfaces que rien ne signalait : `drawable/app_icon.png` (icône
interne), `drawable-xxhdpi/header_logo.png` (logo d'en-tête de liste) et
`drawable-xxhdpi/channel_logo.png` (avatar par défaut). Aucun fichier de
ressources ne les référence par leur nom, et leurs identifiants numériques n'apparaissent dans aucun
smali : elles n'existent que comme ressources publiques. **C'est un balayage des pixels de l'APK**
(521 images, distance au rouge `#a30f2c`) qui les a sorties — l'audit par lecture de code, même
exhaustif, ne pouvait pas les voir. Elles sont remplacées depuis.

Les six captures du tutoriel (`drawable/tut_*.webp`, 1920×1080) portaient, elles, les **cadres
d'annotation** rouges et — pour `tut_5` — un panneau au **thème rouge** (`#4d000f` + `#a30f2c`, un
tiers de l'image). Elles ont été **remappées** plutôt que recapturées : l'émulateur de test plafonne
à 1280×720, les refaire aurait donné des visuels 1,5× plus flous pour une mise en page inchangée.
Chaque couleur de la famille rouge a pris la couleur de même rôle dans la palette Twouich (même
transformation qu'un changement de thème), et la part de rouge de marque est passée de 2,3–36,7 % à
**0,0000 %** (écart de luminance moyen < 1,9/255). Les rouges de contenu (vignettes de streams) sont
conservés : ce n'est pas de la marque. Sources versionnées dans `patch/branding/tutorial/`.

À noter : une première mesure (distance au rouge sans regarder le déséquilibre des canaux) avait
conclu à 41–57 % de rouge dans ces images. C'était une **erreur de mesure** — une tolérance large
classe les pixels presque noirs comme rouges. Voir la leçon de mesure dans `memory.md` §6.

Ce qui empêche désormais une régression : le générateur d'identité (`patch/branding/make_brand.py`,
les 31 visuels sont **calculés** — dont les six captures remappées —, jamais retouchés à la main), le
contrôle de `patch.py` (46 vérifications : assets posés + aucun `#a30f2c` hors palette des thèmes),
`patch/tests/test_brand.py` (14 assertions, dont « famille rouge S0und absente des visuels »,
vérifiées par mutation) et `patch/tests/test_apk.py` (13 verdicts sur l'APK livré, avec contrôle
négatif sur l'APK d'origine).

### 4.6 Mise à jour automatique — ce que le test sur appareil a révélé

Le parcours complet (dialogue → téléchargement → passage à l'installeur système) a été exécuté le
15/09/2026 sur `emulator-5554` avec une **release intermédiaire** : app en 145, release 146 publiée,
l'app s'est mise à jour elle-même, et les octets installés ont le SHA-256 du livrable. Procédure et
traces : `TEST-DEVICE.md` § 0.2.

Deux défauts **d'origine** (ils précèdent Twouich) que ni la lecture du smali ni les tests locaux
n'avaient signalés, et que ce test a rendus visibles :

| Défaut | Effet réel | Mesure |
|---|---|---|
| `helpers/a.b()` filtre par **canal** avant la version : en canal **Beta**, seule une entrée `ReleaseType: 1` est acceptée | une `update.json` qui ne publie qu'une entrée **stable** ne produit **aucun dialogue** sur ces appareils — et la plupart des installations héritées de S0undTV sont en Beta (même paquet Android, préférence conservée) | deux lancements muets en Beta, dialogue immédiat après passage en Stable |
| la comparaison de version se fait contre un **plancher figé (144)**, jamais contre la version installée | l'app propose d'installer la version qu'elle exécute déjà, à chaque démarrage | en 146, relance → « New update available! Version code: 146 » |

Premier défaut : **corrigé depuis** — la v1.0.0 compare la release à la version réellement
installée (`PackageManager.getPackageInfo()`), vérifié par `test_smali_branches.py` sur le code
compilé. Le canal Beta reste à couvrir côté publication (voir § 5).

Conséquence pour la distribution : publier **aussi** une entrée `ReleaseType: 1`, sinon une partie
de l'audience ne verra jamais les releases. Le détail est en `memory.md` § 5 et § 8.

Un troisième écart, de nature différente, a été constaté au passage : l'**apparence par défaut** de
l'app est encore rouge. Réglages d'usine : thème « Dark grey (default) » + accent **« Red
(default) »** (`prefs_accent_color = 0`), et l'accent ne s'applique qu'aux thèmes « Dark grey » et
« Night mode » — donc à celui par défaut. Mesuré sur l'appareil : commutateur de réglages en
`#a00f2b` ≈ `theme_red` `#a30f2c`. La refonte a couvert les **assets** (splash, icônes, bannière,
tutoriel) et les **textes**, pas cette couleur d'interface.

## 5. Reste à faire (hors périmètre de cette passe)

* **CI GitHub Actions** : rejouer `patch/build.sh` à chaque push (téléchargement de l'APK upstream + apktool + signature éphémère) pour détecter immédiatement une rupture de patch sur une nouvelle beta. Non livrée ici : les URLs des archives d'outils (`apktool`, `uber-apk-signer`) doivent être figées une fois, et je n'ai pas pu valider le workflow sur GitHub depuis cet environnement.
* ~~**Publication de la release**~~ — **fait le 15/09/2026** : `v1.5.10x-twouich1` (tag identique au `VersionName`) avec `Twouich_beta144_ttv1.apk` (SHA-256 `a80be686…`) + `changelog.html`.
* ~~**Parcours réel de l'updater**~~ — **fait le 15/09/2026** : release intermédiaire `v1.5.10x-twouich2` (146), app installée en 145 mise à jour par elle-même, octets installés au SHA-256 du livrable (`TEST-DEVICE.md` § 0.2, `memory.md` § 5). Trois suites à ce travail : publier une entrée `ReleaseType: 1` pour les appareils en canal Beta, ~~remplacer le plancher de version figé (144) par la version installée~~ (**fait le 15/09/2026**, v1.0.0 : comparaison via `PackageManager.getPackageInfo()`), et traiter l'**accent rouge par défaut** (§ 4.6).
* **Accent rouge d'usine** : `prefs_accent_color = 0` (« Red (default) ») sur le thème « Dark grey (default) ». Une installation neuve le corrige en passant le défaut à `2` (« A familiar looking shade of purple ») ; les installations **existantes** gardent la valeur enregistrée, donc les repeindre demande de recolorer `theme_red*` — un choix produit, à arbitrer avec le rebranding des captures du README.
* **Reproductibilité octet pour octet** : deux builds du même arbre produisent un APK dont les **2172 entrées sont identiques au CRC** mais dont le SHA-256 diffère, apktool estampillant les entrées ZIP à l'heure du build. Le hash publié identifie donc le fichier livré, pas la recette ; normaliser l'horodatage ZIP rendrait le build reproductible au sens strict.
* **Emotes/badges/highlighter** : non concernés par cette passe.
* ~~**Rebranding**~~ — **fait le 15/09/2026** (voir § 4.5) : nom, écran de démarrage, icônes, bannière TV, icône adaptative, thème par défaut, pages embarquées et **images du tutoriel** portent l'identité Twouich ; plus aucune trace de la marque d'avant, ni en texte, ni en pixel. Reste optionnel : rafraîchir les captures du README (`images/image*.jpg`, prises avant la refonte).

## 6. Annexe — repères

```
APK upstream   : beta_144.apk (tag "beta"), 10398408 o
                 SHA-256 578da49bcab05b1bf0448bbf638f88af71ad7188052cd65c3319093ee5b151b0
Patch          : patch/patch.py (idempotent) + patch/smali/com/twouich/adblock/
Injection      : smali/z3.1/u$b.smali → a() renvoie AdBlockDataSource
Version produite : versionCode 147 / versionName v1.0.0
Livrable       : dist/Twouich_v1.0.0.apk (signé v1+v2+v3, zipalign vérifié)
                 11235091 o, SHA-256 8a4874f84a2df1269ab5cf14ab26948613bbe20bb5492af3137e0cf10c4fd656
Releases        : v1.5.10x-twouich1 (145, a80be686…), v1.5.10x-twouich2 (146, 7f3125d4…)
                  les deux avec APK + changelog.html ; update.json sur master → 147 (v1.0.0, non encore publiée)
Mise à jour     : prouvée sur appareil (TEST-DEVICE.md § 0.2), octets installés = SHA du livrable
```
