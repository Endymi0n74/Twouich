# Twouich — mémoire projet

## Build

- `cd D:/Codex/Twouich && bash patch/build.sh`
- APK amont : `work/upstream/beta_144.apk` (SHA-256 `578da49bcab05b1bf0448bbf638f88af71ad7188052cd65c3319093ee5b151b0`)
- Fallback release si amont absent : télécharge `Twouich_v1.0.25.apk` depuis la release v1.0.25, SHA-256 verrouillé `23d23872acb51c7127abf2621f61595591d0f4eae0b58dddcbcfcc965c4b5e4c`
- Sortie : `dist/Twouich_v1.0.26.apk` — 24/10 au soir, **sans les points** : 11 323 517 octets, SHA-256 `ae82fbacc1a72331cd03def99ad46e8dcacb6e2b7d3a35f95e8b1705a7705c80`, signé v1+v2+v3 (versionCode 173). Deux builds successifs du même arbre donnent la même empreinte, y compris après les corrections de `patch.py` de cette passe.
- outils : `tools/apktool-3.0.3.jar`, `tools/uber-apk-signer.jar` (téléchargés par build.sh, ignorés par .gitignore)
- clé : `keys/twouich.keystore`, alias `twouich-dev`, mot de passe dans `KEY_PASS` (jamais écrit, ignoré par .gitignore)

## Version courante

- `v1.0.26` — versionCode 173 — 24 octobre 2026
- release : https://github.com/Endymi0n74/Twouich/releases/tag/v1.0.26
- APK publié : `Twouich_v1.0.26.apk`, 11 323 517 octets, SHA-256 `ae82fbacc1a72331cd03def99ad46e8dcacb6e2b7d3a35f95e8b1705a7705c80`
- `update.json` pointe vers v1.0.26 (versionCode 173, `hasChangeLog: true`)
- tags existants : `v1.0.26` et `v1.0.25` — le second est **conservé volontairement**, c'est la source du repli `BASELINE_URL` de `patch/build.sh` (un clone neuf n'a plus l'APK amont)

## Repli baseline (clone neuf / CI) — réparé le 24/10 au soir

`BASELINE_URL` télécharge l'APK de la v1.0.25 et le patche ; ce chemin échouait dès le premier bump, car un arbre issu de notre
propre release n'est pas un arbre amont. Cinq corrections dans `patch.py`, toutes des détections « déjà appliqué » (aucune ne
change le livrable produit depuis `beta_144`) :

1. page Nouveautés : réécriture du titre `Twouich vX (date)` existant quand le bloc `beta_144` n'est plus là ;
2. cartes du lecteur : le couple rayon+clip est reconnu quel que soit l'ordre des attributs (aapt2 réordonne) ;
3. flag beta : le champ nu `.field … a:Z` (valeur par défaut false, apktool n'écrit pas `= false` au redécodage) est accepté puis canonisé ;
4. `AutoUpdateService` : l'URL `releases/latest/download/<autre>.apk` d'une release précédente est remplacée, pas seulement l'URL amont morte ;
5. `Application info` / écran debug / bandeau / prefs : les littéraux déjà greffés (nom et code de la release précédente, lus dans `apktool.yml` **avant** le bump) sont reconnus.

Plus trois contrôles de fin de chaîne rendus structurels (ils exigeaient des noms d'étiquettes que le compilateur renomme au
redécodage : `:restore_done` → `:cond_1`, `:restore_pip_layout`, `:twouich_tap_unhandled`), et un vrai piège : le `<dimen
name="twouich_phone_chat_height">` était détecté par la ligne littérale (`280dp`) alors qu'un arbre redécodé écrit `280.0dp` —
la seconde définition rendait `aapt2` muet sur un `duplicate value`, donc build impossible depuis le repli.

Deux autres défauts de la même famille, trouvés par le run CI de la release : la pastille de points restait dans
`activity_player.xml` (la vue y était écrite `@id` et non `@+id`, donc non reconnue) et son identifiant survivait dans
`ids.xml`/`public.xml` — le contrôle « pastille retirée du livrable » la retrouvait. `remove_phone_points()` nettoie
désormais les trois. Et `test_apk` ne peut plus échouer sur l'absence de l'APK amont (il **dit** qu'il saute, avec `⏭️`) :
ce contrôle comparait le layout TV à une capture de l'APK amont, disparu depuis le 24/10.

Mesure : décodage de l'asset v1.0.25 → `patch.py` **exit 0** (233 contrôles) → `apktool b` **exit 0** (11 112 086 o non signé),
puis `bash patch/build.sh` sur un clone sans amont (`SKIP_SIGNING=1`) : **exit 0**, hash non signé `07273a51…`,
identique à deux exécutions.
`classes2.dex` est **identique** au build `beta_144` ; `classes.dex` diffère de 128 octets (ordre des attributs/étiquettes revisité
par le redécodage) : les deux chemins ne produisent donc **pas** les mêmes octets. C'est pourquoi la release publie le build
`beta_144` (chaîne d'origine, testée sur appareil) et non celui de la CI.

## Fonctionnalités livrées en v1.0.25

- points de chaîne : **fonctionnalité retirée le 24/10**. Le compteur local (une minute = un point)
  n'a jamais été les points de chaîne de Twitch — l'app n'a ni GQL/Helix ni jeton, donc le nombre
  était inventé. Greffons (`WatchPoints`, `PointsTicker`, `PointsLongPress`), vue de la rangée
  de saisie, méthode du lecteur, champ `twouichPointsBound` et appui long : tout est parti.
  `remove_phone_points()` nettoie un arbre de travail réutilisé, et deux contrôles
  (`test_smali_branches`, `test_apk`) verrouillent l'absence de greffe.
- UI téléphone : panneau de chat (surface sombre, coins supérieurs arrondis, 8 dp sous la vidéo), bouton PiP circulaire, champ de saisie en pastille, fiche chaîne (surface sombre, avatar rond, boutons pilule)
- TV intact : vérifié ressource par ressource (`layout-sw600dp`, `layout-sw540dp`, `layout-television`) et à l'écran 1920×1080
- listes du lecteur : coins à 14 dp côté téléphone, 2 dp côté TV
- anti-pub : `PlaylistSanitizer` + `AdBlockDataSource`, fallback VaFT corrigé (ne sert plus la playlist brute)
- pause / reliquat : plus de sujet — la cadence qui portait `setPlaying`/`carry` est supprimée avec la pastille
- PiP : le rappel ne touche plus à la pastille ; il masque le chat et la saisie puis restaure l'empilement
- capture de chaîne : `twouichSetChannel` dans `onCreate` (deeplink) et dans `x3()` — inchangé, sert au secours anti-pub
- défaut trouvé le 24/10 (soir) sur la release publiée : `PointsTicker.run()` appelait une méthode absente du dex (`NoSuchMethodError` au premier tir). Il disparaît avec la fonctionnalité ; `test_apk` vérifie désormais qu'aucune classe de points n'est livrée

## Tests locaux

- `test_apk` : conforme (APK signé, version manifeste, accord update.json)
- `test_smali_branches` : 81/81 verifications passees
- `test_vaft` : 20/20
- `test_update_check` : 26/26
- `test_script_paths` : 51/51
- `test_sanitizer` : passe
- `test_brand` : passe (polices Windows requises, mainteneur uniquement)
- `test_radar` : 10/10
- `test_check_secrets` + `check-secrets` : 136 fichiers, aucun secret en clair
- `sync-readme --check` : passe
- `test_normalize_apk` : controles reels passes
- `phone_geometry` : passe
- `analyzer` : 11/11
- `device_ui` : 99/99 (harnais hors appareil, double adb)
- self-test : 31/31

## Vérification v1.0.26 sur BlueStacks (24/10, après publication)

- `adb install -r dist/Twouich_v1.0.26.apk` → `Success` ; `firstInstallTime` inchangé (2026-10-05 14:13:09), session conservée.
- **Octets installés = livrable** : `adb pull` de `base.apk` → SHA-256 `ae82fbacc1a72331cd03def99ad46e8dcacb6e2b7d3a35f95e8b1705a7705c80`, identique à `dist/`.
- Lancement à froid (`force-stop` + `am start MainActivity`) : `SELFTEST 31/31 verifications, flux filtre : 328 octets`,
  **0 FATAL / 0 ANR**, `topResumedActivity` = `MainActivity` puis `SettingsActivity`.
- Page « Application info » à l'écran : **Version name `v1.0.26`**, **Version code `173`**, Build type RELEASE, branche
  « Twouich master (fork de S0undTV) », Build time `24/10/2026 14:00` (date de release figée, 12:00 UTC).

## Parcours de mise à jour 1.0.25 → 1.0.26 rejoué (BlueStacks, 24/10)^

- Rétrogradation volontaire : `adb install -r -d dist/Twouich_v1.0.25.apk` (`23d23872…`, l'asset de la release v1.0.25)
  → `versionCode 172`, `firstInstallTime` toujours `2026-10-05 14:13:09`.
- Lancement froid : **UpdateActivity s'ouvre seule 10 s après** `MainActivity` (« New update available! », Version v1.0.26,
  code 173) — aucune navigation, aucun compte nécessaire.
- Appui « Install update » → `D/S0undTV_AutoUpdateSrv: onStartCommand:
  https://github.com/Endymi0n74/Twouich/releases/download/v1.0.26/Twouich_v1.0.26.apk`, puis
  `START … dat=content://com.s0und.s0undtv.provider/... typ=application/vnd.android.package-archive
  cmp=com.android.packageinstaller/.InstallStart` (uid 10093) et `PackageInstallerActivity` au premier plan.
- Appui « METTRE À JOUR » → `versionCode 173`, `lastUpdateTime 22:04:31`, **`firstInstallTime` inchangé** : mise à jour en
  place, session conservée.
- **Octets installés = octets servis** : `base.apk` relu (`adb pull`) → `ae82fbac…05c80` = asset téléchargé par curl =
  `dist/Twouich_v1.0.26.apk`.
- Relance après mise à jour : `MainActivity` (aucune `UpdateActivity`), `SELFTEST 31/31`, 0 FATAL/ANR — l'annonce ne boucle pas.

## Devices (deux devices Android TV attachés)

- TV : Android TV 11, 1920×1080, `RM-17325` (reste intact à chaque session de test téléphone)
- Cell : Android 14, 1080×2340, Pixel-ish (Tiramisu), 사용되며 smartcover 실험

## Ressources

- dépôt upstream amont : S0undTV (code source non redistribué, uniquement binaires patchés)
- APK amont `beta_144.apk` : l'amont a supprimé son asset `S0undTV/releases/download/beta/beta_144.apk` (404 mesurée 24/10) — le fallback release est indispensable pour les clones neufs
- CI : `.github/workflows/build.yml` — job `build` (sans signature, détection de rupture) + job `release` (signé, publication, vérification octets servis)
- CI secondaire : `.github/workflows/radar.yml` (radar-ads, scheduling, marche)

## Ce qui a été publié et vérifié

- v1.0.26 : release créée avec l'APK (11 323 517 o, `ae82fbac…`) et `changelog.html` ; `update.json` poussée après publication
(`ReleaseDate` = `publishedAt`, `2026-10-24T19:17:56Z`) ; `check-release.sh` vert sur les quatre étages, **octets servis
revérifiés après le run de tag** ; CI verte : `40126044259` (master, non signée) et `40126046782` (tag, signée + publication)
- v1.0.25 : release créée, APK + changelog uploadés, SHA-256 local = SHA-256 servi (vérifié par curl). **Asset remplacé depuis** : le rebuild sans points avait été poussé sur le dépôt, la release publiée garde `23d23872…` (source du repli baseline)
- v1.0.24 : supprimée (tag distant `v1.0.24` supprimé, release supprimée)
- anciennes releases v1.0.19–v1.0.23 : toutes supprimées (n'existaient pas sur GitHub à la date du nettoyage)
- tous les anciens runs CI échoués supprimés (14 runs, IDs 40035469810 à 40100358457)
- .gitignore créé : ignore keys/, tools/, __pycache__/, work/build/, work/decoded/, work/captures/, work/*.log, work/*.png, fichiers .pyc, fichiers OS
- build.sh corrigé : BASELINE_SHA256 passe de 517af65c... (faux) à 23d23872... (bon) — cette erreur était la cause racine des échecs CI

## Ce qu'il reste à faire / surveiller

- La CI reconstruit depuis le repli baseline et **écrase l'asset** au tag (étape `gh release upload --clobber`). Constaté le
24/10 sur la v1.0.26 : le run de tag (vert, `40126046782`) a publié son propre build (`f0e6aecd…`, même taille, `classes2.dex`
identique, `classes.dex` à 128 octets d'écart — ordre des attributs/étiquettes revisité par le redécodage). Le livrable
`beta_144` (`ae82fbac…`) a été re-poussé après le run, et `check-release.sh` confirme `servi = local`. **Après chaque release :
relancer `bash patch/check-release.sh` et re-poser `dist/` si la CI a substitué un build.**
- Le contrôle « layout TV confronté à la capture de l'amont » est **sauté** (`⏭️`) sur un clone sans APK amont : il dit qu'il
ne juge pas, les autres gardes TV restent actifs. Sur la machine du mainteneur (amont présent) il mord toujours.

## Preuves sur appareil (mesures du 24/10)

- première ouverture depuis l'accueil (lancement froid) : session ouverte 12:02:27.304, solde écrit 12:03:42.261, pastille 146→147 — sans HOME ni relance
- pause (raccourci Play/Pause) : pastille 147, après 2 min 37 d'arrêt toujours 147, 0 solde écrit — 0 pixel différent dans la zone vidéo pendant la pause
- reprise : 148 (reliquat des 75 s déjà courues avant la pause), puis 149 — 185 862 pixels différents après reprise
- PiP : sortie rend la pastille selon préférence (chemin jamais mesuré jusqu'ici)
- rotation : pas de pixel différent pendant la pause, capture confirmée

Preuves dans `work/proof-pause-*` et `work/coldpause-*` (captures, journaux complets, extraits).
Livrable local `dist/Twouich_v1.0.25.apk`, SHA-256 `23d23872...` (rebuild local, mis à jour, fait shRNAke256sum sur la release).
