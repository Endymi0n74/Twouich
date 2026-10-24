# Twouich — mémoire projet

## Build

- `cd D:/Codex/Twouich && bash patch/build.sh`
- APK amont : `work/upstream/beta_144.apk` (SHA-256 `578da49bcab05b1bf0448bbf638f88af71ad7188052cd65c3319093ee5b151b0`)
- Fallback si amont absent : télécharge `beta_144.apk` — l'APK **amont d'origine**, archivé sur la release v1.0.25 — SHA-256 verrouillé `578da49bcab05b1bf0448bbf638f88af71ad7188052cd65c3319093ee5b151b0` (même source que le mainteneur, donc mêmes octets ; cf. « Source du repli » plus bas)
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

Première version du repli (soirée du 24/10) : `BASELINE_URL` téléchargeait l'APK de **notre** release v1.0.25 et le patchait.
Ce chemin échouait dès le premier bump, car un arbre issu de notre propre release n'est pas un arbre amont. Cinq corrections
dans `patch.py`, toutes des détections « déjà appliqué » (aucune ne change le livrable produit depuis `beta_144`) :

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

### Source du repli : l'amont archivé (24/10, fin de soirée)

Rebâtir depuis notre propre release ne redonnait **pas** les octets du livrable : `classes2.dex` identique, `classes.dex` à
128 octets d'écart (ordre des attributs/étiquettes revisité par le redécodage). D'où le run de tag qui remplaçait l'APK publié,
et donc le garde `published_guard`. La source du repli est maintenant l'APK **amont d'origine** (`beta_144.apk`, SHA-256
`578da49b…`), archivé comme asset de la release v1.0.25 :

- `BASELINE_URL` = `…/releases/download/v1.0.25/beta_144.apk`, `BASELINE_APK` = `work/upstream/baseline_beta_144.apk`,
  `BASELINE_SHA256` = `578da49b…` (épinglé, identique à `UPSTREAM_SHA256`) ;
- vérifié à la main avant de pousser : amont local masqué + arbre décodé supprimé → `bash patch/build.sh` télécharge
  l'archive, recompile et sort `ae82fbac…` à l'octet près ;
- **prouvé en CI** (run `40132794711`, tag `v1.0.26` sur `3ceb9e2`, Ubuntu, clone neuf) : le build signé sort
  `ae82fbac…05c80`, 11 323 517 octets, identique à `dist/` et à l'asset publié ;
- conséquence : le garde répond « octets identiques », la publication est **sautée** et le run est vert — les mêmes octets
  circulent du build local à la CI et à la release.

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

## Parcours de mise à jour 1.0.25 → 1.0.26 rejoué (BlueStacks, 24/10)

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
- APK amont `beta_144.apk` : l'amont a supprimé son asset `S0undTV/releases/download/beta/beta_144.apk` (404 mesurée 24/10). Il est donc archivé sur la release v1.0.25 (`beta_144.apk`, `578da49b…`) : c'est la source du repli pour un clone neuf et pour la CI, et c'est ce qui garantit les mêmes octets à la sortie
- CI : `.github/workflows/build.yml` — job `build` (sans signature, détection de rupture) + job `release` (signé, publication, vérification octets servis)
- CI secondaire : `.github/workflows/radar.yml` (radar-ads, scheduling, marche)

## Ce qui a été publié et vérifié

- v1.0.26 : release créée avec l'APK (11 323 517 o, `ae82fbac…`) et `changelog.html` ; `update.json` poussée après publication
(`ReleaseDate` = `publishedAt`, `2026-10-24T19:17:56Z`) ; `check-release.sh` vert sur les quatre étages, **octets servis
revérifiés après le run de tag** ; CI verte : `40126044259` (master, non signée) et `40126046782` (tag, signée + publication)
- v1.0.25 : release créée, APK + changelog uploadés, SHA-256 local = SHA-256 servi (vérifié par curl). L'asset a été remplacé depuis (rebuild sans points), puis **complété le 24/10 au soir avec `beta_144.apk`** (l'APK amont d'origine, 10 398 408 o, `578da49b…`) : c'est la source du repli de `build.sh` pour les clones neufs et la CI
- v1.0.24 : supprimée (tag distant `v1.0.24` supprimé, release supprimée)
- anciennes releases v1.0.19–v1.0.23 : toutes supprimées (n'existaient pas sur GitHub à la date du nettoyage)
- tous les anciens runs CI échoués supprimés (14 runs, IDs 40035469810 à 40100358457)
- .gitignore créé : ignore keys/, tools/, __pycache__/, work/build/, work/decoded/, work/captures/, work/*.log, work/*.png, fichiers .pyc, fichiers OS
- build.sh corrigé : BASELINE_SHA256 passe de 517af65c... (faux) à 23d23872... (bon) — cette erreur était la cause racine des échecs CI

## Ce qu'il reste à faire / surveiller

- **La CI n'écrase plus l'asset publié** (garde `published_guard`, 24/10 au soir). Constaté sur la v1.0.26 : le run de tag
(`40126046782`, vert) avait publié son propre build (`f0e6aecd…`, même taille, `classes2.dex` identique, `classes.dex` à
128 octets d'écart) à la place du build `beta_144` testé sur appareil (`ae82fbac…`). Désormais, avant tout upload, le workflow
télécharge l'APK déjà présent sur la release et le compare :
  - identique → `upload=false`, rien n'est téléversé (run vert, résumé dans le job summary) ;
  - différent → **échec du job sans aucun upload**, avec les deux empreintes dans le résumé et la commande
    `gh release delete-asset <tag> <apk>` à lancer volontairement pour publier un rebuild ;
  - aucun asset → upload normal (première publication).
  Éprouvé hors CI avec un faux `gh` sur cinq cas : asset identique → `upload=false` ; release sans APK → `upload=true` ;
  aucune release → `upload=true` ; assets illisibles (502) → échec sans upload ; octets différents → échec sans upload.
  Le garde refuse aussi de publier quand la release existe mais que sa lecture échoue : jamais de repli silencieux
  sur `--clobber`. Le job signé reste donc vert sur une première publication et sur un rebuild identique, rouge sinon.
- **Prouvé en CI le 24/10 au soir**, deux fois :
  - run `40131704996` (tag `v1.0.26` sur `20ea27e`) — le garde **refuse** : `❌ l'APK publié (ae82fbac…) diffère du rebuild CI
    (f0e6aecd…)`, « Publier » et « Vérifier les octets servis » sautées, release intacte (`updatedAt` `19:40:39Z`, taille
    inchangée, octets servis retéléchargés = `ae82fbac…` = `dist/`).
  - run `40132794711` (tag `v1.0.26` sur `3ceb9e2`, source du repli = amont archivé) — le garde **laisse passer** :
    `✅ octets identiques : le rebuild n'apporte rien, aucun upload`, publication sautée, `✅ octets servis = livrable`.
  Le run vert est le régime normal ; le rouge reste la preuve que le garde mord si les octets divergent. `check-release.sh`
  vert sur les quatre étages dans les deux cas.
- Le contrôle « layout TV confronté à la capture de l'amont » est **sauté** (`⏭️`) sur un clone sans APK amont : il dit qu'il
ne juge pas, les autres gardes TV restent actifs. Sur la machine du mainteneur (amont présent) il mord toujours.

## Smoke test du lecteur en conditions réelles (BlueStacks, v1.0.26, 24/10 au soir)

- Ouverture depuis l'accueil (chaîne Recalbox, en direct) : `PlayerActivity` au premier plan en ~15 s, sans HOME ni relance.
  Journal : `chaine pre-capture : recalbox`, `chaine captee : recalbox`, `chat affiche`, `chat restaure affiche`.
- Lecture continue 22:24:08 → 22:33 (≈9 min) : `playlist nettoyee` toutes les ~2 s, **206 playlists** filtrées, aucun
  `E Twouich`, aucun FATAL, aucun ANR ; `dumpsys media_session` = `state=3` (PLAYING) à chaque contrôle ; les images vidéo
  diffèrent d'une capture à l'autre (le direct avance).
- Chat : messages, follows et réponses de l'utilisateur (`endymi0n`) défilent sans interruption, y compris pendant la saisie.
- Saisie : tap sur la pastille → `InputMethodManager showSoftInput view=… app:id/ET_SendMessage`, `inputType=1` ; texte visible
  à l'écran avec curseur. **Rien n'a été envoyé** (pas de message publié dans le chat d'autrui) ; champ vidé ensuite.
- Anti-pub : le sanitizer tourne sur **chaque** rafraîchissement de playlist (206 fois), **0 segment pub retiré** — aucun pod
  SSAI servi pendant la fenêtre : c'est le branchement qui est prouvé, pas le retrait d'un pod.
- **Défaut trouvé, non corrigé** : un appui sur RETOUR dans le lecteur masque `SendMessageWindow` (`dumpsys activity top` :
  `V.E` → `G.E`) alors que le joueur reste ouvert et le chat visible ; la barre ne revient pas (tap inopérant) et un second
  RETOUR sort du lecteur. Reproductible clavier ouvert comme fermé, à chaque ouverture ; il faut quitter puis rouvrir la
  chaîne pour recomposer. Le RETOUR upstream masque la saisie (comportement TV) sans que notre empilement la rétablisse.

Captures et journaux : `work/smoke_*`, `work/rep_*`, `work/smoke_2min.log`.
