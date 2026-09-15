# Journal des modifications — Twouich

## v1.5.10x-twouich1 (versionCode 145) — 15 septembre 2026

Base : **S0undTV `beta_144`** (release tag `beta`, APK `beta_144.apk`,
SHA-256 `578da49bcab05b1bf0448bbf638f88af71ad7188052cd65c3319093ee5b151b0`).

### Ajouté

- **Blocage des publicités SSAI** — nouveau greffon `com.twouich.adblock` :
  - `AdBlockDataSource` : source de données ExoPlayer qui intercepte chaque lecture de playlist
    HLS, la relit intégralement puis la réécrit ; les segments vidéo passent sans copie.
  - `PlaylistSanitizer` : retrait des plages `#EXT-X-DATERANGE` publicitaires
    (`CLASS="twitch-stitched-ad"` / `ID="stitched-ad-…"`), des segments titrés `…Amazon…`, et des
    blocs `#EXT-X-CUE-OUT` / `#EXT-X-CUE-IN` ; les `#EXT-X-DISCONTINUITY` et
    `#EXT-X-TWITCH-LIVE-SEQUENCE` sont conservés pour que la timeline reste valide côté lecteur.
  - Injection au point unique `Lz3/u$b.a()` : *toutes* les lectures HLS de l'app (live, VOD,
    aperçus de l'accueil et de la recherche) passent par le filtre.
- **Option proxy** (`PROXY_HOST`, désactivée par défaut) : les requêtes de playlist maître partent
  d'abord par le proxy configuré, avec **repli automatique** sur la requête directe en cas d'échec.
- **Identité visuelle Twouich** — l'app ne porte plus la marque d'origine à l'écran :
  - **écran de démarrage** : dégradé violet Twitch (`#9146ff` → `#150826`) et mot-symbole
    « TWOUICH » avec sa tagline, à la place du fond rouge et du logo S0und ;
  - **icônes de lancement** (5 densités, carrée et ronde) et **icône adaptative** (fond violet au
    lieu du rouge) ;
  - **bannière Android TV** 320×180 et son double 1280×720 ;
  - **nom affiché** : « Twouich » (le paquet reste `com.s0und.s0undtv`, sinon plus aucune mise à
    jour ne s'installerait par-dessus) ;
  - **thème par défaut** violet, pages **À propos** et **Nouveautés** réécrites (fond sombre, en-tête
    et entrée Twouich) ;
  - trois visuels internes portant encore le logo (`header_logo`, `app_icon`, `channel_logo`),
    retrouvés en balayant les pixels de l'APK — aucune référence de code ne les signalait ;
  - les **six images du tutoriel** (onboarding à la première lecture), dont les cadres d'annotation
    et un panneau entier étaient au rouge du thème d'origine — remappées vers la palette Twouich
    (même transformation qu'un changement de thème), composition et vignettes inchangées.
  - Tout est **calculé** par `patch/branding/make_brand.py` (3 pistes au choix, assets versionnés) et
    posé par l'étape 2 de `patch.py` : rien n'est retouché à la main dans les ressources.

### Corrigé

- **Mise à jour automatique** : les 5 URLs de l'updater pointaient vers `S0und/S0undTV` et auraient
  fait télécharger le build d'origine par-dessus le nôtre → repointées vers `Endymi0n74/Twouich`.
- **`AutoUpdateService`** : endpoint mort `https://share.s0und.cloudns.cl/app-release.apk` (ancien
  backend abandonné) → remplacé par l'asset de notre dernière release.
- **Version de l'APK** : apktool 3 sort `versionCode`/`versionName` du manifest et ne les réinjecte
  pas au build, ce qui produisait un APK **sans version** (installation refusée) → les attributs
  sont désormais réécrits explicitement dans `AndroidManifest.xml`.
- **`update.json`** : décrivait les APK de S0und (dont des fichiers inexistants ici) → remplacé par
  une entrée unique décrivant notre build.
- **`README.md`** : était la copie conforme de celui de S0undTV (identité, Discord, liens
  d'installation `bit.ly/S0und-TV`) → réécrit pour Twouich.
- **`.github/FUNDING.yml`** : le bouton Sponsor renvoyait vers le PayPal du développeur de S0und →
  neutralisé.

- **Blocage des publicités — deux erreurs de branchement** trouvées seulement en testant sur un
  appareil réel (`if-eqz`/`if-nez` inversés dans `PlaylistSanitizer.a` et dans
  `AdBlockDataSource.read`, puis `if-gez`/`if-gtz` employés avec leur sens naturel alors que Dalvik
  définit `if-gez` = « `>= 0` » et `if-gtz` = « `> 0` »). Symptômes : plantage `NullPointerException`
  au premier appel de lecture, puis flux vide (« `Underlying input stream returned zero bytes` ») et
  lecture impossible. Corrigé, vérifié en direct sur l'appareil, et verrouillé par
  `patch/tests/test_smali_branches.py`.
- **Compteur de publicités retirées** : dans le journal, `segments pub retires : n` comptait les
  balises HLS jetées (`#EXTINF`, `#EXT-X-DATERANGE`…) au lieu des URI de segments publicitaires —
  il annonçait par exemple 4 segments pour une coupure de 3. Le blocage lui-même n'était pas
  affecté. Trouvé et vérifié par le self-test embarqué, puis verrouillé par
  `patch/tests/test_smali_branches.py`.

### Technique

- **Génération de l'identité** (`patch/branding/make_brand.py`) : une seule source de vérité pour le
  mot-symbole, la tagline, la palette et la composition — déclinée en arborescence `res/` prête à
  recopier, en aperçu HTML des trois pistes, et en rendu ASCII pour vérifier la composition sans
  ouvrir d'image. L'écran de démarrage est un `layer-list` (dégradé XML + composition PNG posée au
  centre, sans mise à l'échelle) : aucune ressource nouvelle, aucun risque de collision d'`id`.
- **Garde-fou d'identité** (`patch/tests/test_brand.py`, 14 assertions) : les assets versionnés sont
  octet pour octet ce que le générateur produit, la **famille rouge d'origine** est absente de tous
  les visuels (tutoriel compris), la composition tient dans un écran 720p, les icônes existent aux
  cinq densités, les six captures du tutoriel restent en 1920×1080. Vérifié en le cassant
  (5 mutations, chacune fait passer la sortie en code 1 — recolor désactivé : 31,96 % de rouge
  détecté sur `tut_5`). `patch.py` verrouille de son côté les
  25 assets posés dans l'arbre patché et l'absence de `#a30f2c` hors palette.
- **Self-test embarqué** (`SelfTest`, `SelfTest$Fake`) exécuté au démarrage de l'app : il rejoue des
  playlists publicitaires aux formats Twitch réels (plage SSAI, bloc `CUE-OUT`/`CUE-IN`, segment
  titré `Amazon`) dans le code compilé et fait traverser la vraie source de données du lecteur, puis
  publie son verdict sur logcat — une ligne en cas de succès :
  `SELFTEST 18/18 verifications, flux filtre : 328 octets`. Il rend le retrait d'une publicité
  **reproductible à volonté**, sans attendre une vraie coupure. Lancement à la demande :
  `bash patch/test-selftest.sh` (l'APK n'est même pas installé) ou `--in-app`.

### Notes d'installation

- **Signature différente** de l'app officielle : désinstaller `com.s0und.s0undtv` avant d'installer
  Twouich, sinon Android refuse la mise à jour. Les mises à jour *suivantes* de Twouich s'installent
  normalement (même clé).
- L'application s'appelle désormais **Twouich** (launcher, réglages, pages embarquées).
- Restent à valider sur un appareil : comportement réel pendant une coupure publicitaire (voir
  `AUDIT.md` § 4.4). Le reste de l'application est inchangé par rapport à `beta_144`.
