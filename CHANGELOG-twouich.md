# Journal des modifications — Twouich

## v1.0.19 — 5 octobre 2026

> **Publié le 5 octobre 2026** (versionCode 166) : tag `v1.0.19` poussé sur `4144054`, job CI « build signé + publication » **vert** (tests, secrets, keystore restauré, signature v1+v2+v3, release « Twouich v1.0.19 » avec l'APK et `changelog.html`, contrôle par la CI de ses propres octets servis), annonce `update.json` poussée **après** la release avec `ReleaseDate` = `publishedAt` exact `2026-10-05T12:39:02Z`. Livrable 11 260 648 o, SHA-256 `7edef794d155a64c1f8065ce01a05d00e3bf379a5b9619366200c09b2ad0e261` — **identique au digest de l'asset publié** (cinquième release reproductible de suite). `check-release.sh` **exit 0 sur les quatre étages**. Cette version corrige aussi une divergence introduite pendant la v1.0.18 : `dist/` contenait alors des octets différents de l'asset publié, ce que `check-release.sh` a correctement refusé.

- **Le parcours de mise à jour a été rejoué pour la première fois, de la 164 à la 165, sur un appareil réel.** La 164 est précisément l'APK cassé sur Android 14+ (service de premier plan sans type, tué dans `onCreate`), donc la route ne se joue qu'en API 33 ou moins. Les cinq points passent : dialogue automatique, `S0undTV_AutoUpdateSrv onStartCommand: …/v1.0.18/Twouich_v1.0.18.apk` après appui, pose de la 165, **octets installés = octets publiés** (`2d5a88e3…`, 11 260 648 o, relus sur l'appareil *et* localement), et relance muette sans boucle. Le contrôle le plus parlant : `firstInstallTime` n'a pas bougé quand `lastUpdateTime` a avancé de quatre minutes — **mise à jour en place, données survivantes**. Trois enseignements, tous consignés : **aucune session n'est requise** (le dialogue est apparu sans compte, 108 ms après le lancement) ; `onStartCommand` se lit **après** l'appui et non au lancement ; et **l'asset v1.0.18 publié ne contenait pas les quatre écrans ci-dessus** — vérifié sur l'octet installé, c'est ce qui rend cette publication nécessaire.
- **Quatre écrans trouvent enfin un chemin tactile.** L'audit avait relevé sept fonctions hors de portée du doigt ; la mesure en a infirmé une partie (Réglages était déjà atteignable, voir plus bas) et laissé quatre réellement orphelines. L'accueil n'exposait que **5 éléments cliquables** (`title_orb`, `title_text`, et les trois onglets de navigation basse) ; « Application info » des Réglages ne montrait que le build amont (`beta_144`) — ni À propos, ni mentions légales, ni changelog, ni déconnexion. Ces quatre écrans **existaient déjà** dans l'amont et ne sont pas *exportés* (un `am start` externe échoue) : un Intent explicite émis par l'application elle-même n'a pas cette contrainte, ce qui est exactement le mécanisme déjà employé par `twouichPhoneSearch`/`twouichPhoneSettings`. **Aucune logique d'authentification n'est réécrite.** Une seconde rangée de quatre actions à 120 × 48 dp (cible tactile conforme) porte `twouichPhoneAbout`, `twouichPhonePrivacy`, `twouichPhoneChangeLog`, `twouichPhoneLogout`. Mesuré sur BlueStacks (480 dp) : l'accueil passe à **9 éléments cliquables**, et chaque tap ouvre la bonne activité — `AboutActivity`, `PrivacyPolicyActivity`, `ChangeLogActivity`, `LogoutDialogActivity` — sans aucun `FATAL`.
- **La branche paysage du lecteur est mesurée pour la première fois** depuis le correctif d'empilement du 05/10. Contrôle préalable en portrait : la méthode reproduit exactement les bornes déjà publiées (720×405 / 720×763 / 720×112, somme 1280). En 1280×720 la vidéo est `0,0-1088,720`, le chat `1088,0-1280,608` et la saisie `1088,608-1280,720` ; en 1560×720 la vidéo fait `0,0-1280,720`, c'est-à-dire **16:9 exact**. La disposition est celle que le code écrit, au pixel près. Au passage, la mesure établit que le seuil réel du plafond de sûreté est `largeur/hauteur < (16/9)/0,85 = 2,092` : un écran **16:9 est concerné** (cadre de 1,51:1), comme le 16:10, le 4:3 des tablettes et les 3:2 des pliables ; le 19,5:9 et le 20:9 passent, ce qui explique que la mesure du 21/09 (2,22:1) n'ait jamais vu le phénomène. TV intacte : **0 nœud `twouich_*`** à 720 dp.
- **Aucun script ne peut plus dépendre du répertoire courant.** Un chemin résolu depuis le mauvais endroit écrivait là où personne n'attend le fichier, sans le moindre message d'erreur : le fichier visé était resté intact pendant qu'un jumeau hors sujet apparaissait à côté, et seul un test l'avait remarqué. `patch/tests/test_script_paths.py` (50 vérifications, branché dans les deux jobs CI) verrouille la propriété — racine morte, littéral de chemin non ancré, et rejeu de dix scripts depuis un répertoire étranger. **Mordance prouvée par quatre mutations.** Un vrai défaut a été corrigé au passage : `device-ui.sh` calculait une racine depuis `BASH_SOURCE` sans jamais s'en servir.
- **Deux détails d'outillage** consignés parce qu'ils ont coûté cher et qu'ils se reproduiront : sous Windows, le `bash` qu'un Python résout est le lanceur WSL (`/mnt/c`), dont l'espace de noms ignore `/d/…` ; Git Bash exporte `PWD` en forme Windows ; et un chemin Windows passé à bash via Python voit ses antislashs mangés par MSYS.

## v1.0.18 — 4 octobre 2026

> **Publié le 5 octobre 2026** (versionCode 165) : tag `v1.0.18`, release « Twouich v1.0.18 » (APK + `changelog.html`), annonce `update.json` poussée **après** la release avec `ReleaseDate` = `publishedAt` exact. La date de cette entrée reste le **4 octobre** : c'est elle qui est figée dans la page « Nouveautés » embarquée (`VERSION_RELEASE_DATE`), la corriger après coup ferait diverger le SHA du livrable de celui déjà publié.

- **Le crash de mise à jour qui tuait l'app sur Android 14+ est corrigé.** `AutoUpdateService` se plaçait en premier plan sans `android:foregroundServiceType` : depuis Android 14 (cible 35), la plateforme refuse et tue le processus — `android.app.MissingForegroundServiceTypeException: Starting FGS without a type`, **3 entrées `data_app_crash`** dans la DropBox du Xiaomi le 04/10 à 10 h 22 puis 10 h 23. Chaque service porte maintenant son usage réel : `AutoUpdateService` en **dataSync**, `NotificationService` (boucle d'alertes d'environ une minute, activée par l'utilisateur) en **specialUse** avec le sous-type `android.app.PROPERTY_SPECIAL_USE_FGS_SUBTYPE` exigé par la plateforme, `PlayerKeepAlive` restant en mediaPlayback (veille pendant la lecture). Les permissions `FOREGROUND_SERVICE_DATA_SYNC` et `FOREGROUND_SERVICE_SPECIAL_USE` sont déclarées ; le service WorkManager reste **sans type** (audit du dex : aucun Worker n'emploie `ForegroundInfo`/`setForeground`, et les deux ponts synthétiques qui appellent `startForeground` pour ce service sont injoignables), et le générateur refuse désormais tout nouvel appel oublié comme tout Worker foreground non audité.
- **La fenêtre vidéo n'empiète plus sur le chat en portrait.** Le test de mode TV `twouichTvInterface()` avait ses deux tests aboutissant à la même étiquette, étiquette posée sur la ligne suivante : l'exécution tombait donc dans la branche TV **pour tout appareil**, téléphone compris. Mesuré sur BlueStacks en portrait 480 dp : trace `interface : TV`, `ExoPlayer` en `match_parent` sur les 1280 px de l'écran et `ChatRecycleView` GONE. Depuis le 21/09, aucun téléphone n'a donc jamais eu d'empilement — la vidéo couvrait le chat. Le repli explicite vers la branche téléphone est reposé (sur les arbres neufs comme sur ceux déjà patchés), et la hauteur du chat se déduit désormais de la vidéo **après** son plafond au lieu de la hauteur entière moins la barre de saisie — il ancré sous la vidéo, il débordait d'autant. Résultat mesuré : `ExoPlayer` `0,0-720,405` (16:9 exact en haut), chat `0,405-720,1168`, saisie `0,1168-720,1280`, soit 1280 px exactement. **TV intacte** : en 720 dp, trace `interface : TV` et `ExoPlayer` en `0,0-1920,1080`, disposition d'origine.
- **Un `build.sh` quilausait sur un désassemblage neuf.** L'empreinte des greffes accompagne l'arbre ; `rm -rf work/decoded` laissait donc l'ancienne empreinte et le contrôle de `patch.py` refusait l'arbre neuf, pourtant légitime. Elle est maintenant emportée avec lui.
- **La connexion Twitch redevient atteignable au doigt.** Sans session, l'accueil téléphone affiche un bandeau « Login to use the app » purement décoratif : les entrées réelles — « Login (Preferred) », « Login (Web) », « Login with Turbo » — sont des actions d'un menu latéral que la télécommande ouvre et que le doigt n'atteint pas (mesuré le 05/10/2026 sur le Xiaomi 24095PCADG : tap, appui long et touche MENU ouvraient autre chose). Ni chat, ni « Abonnées », ni VOD réservées au compte n'étaient donc accessibles sur téléphone. Le bandeau devient un bouton qui appelle le chemin de connexion **déjà livré par l'amont** (`Login (Web)` → `LoginActivity`, OAuth officiel de Twitch dans un WebView) : aucun flux d'authentification n'est réécrit. Le « Login (Preferred) » de l'amont a été **écarté**, et c'est un choix mesuré : il ouvre `AltLoginV2Activity`, qui interroge un serveur HTTP du réseau local (`http://<ip>:13378/login`) — le port **refuse la connexion** sur le réseau du téléphone (Xiaomi en 192.168.1.22/24, Freebox en .24), donc une URL morte. L'endpoint de l'OAuth, lui, a été vérifié vivant (HTTP 302 de `id.twitch.tv/oauth2/authorize` vers `twitch.tv/login`).
- **Une mise à jour n'efface plus la session** : la recette d'installation imprimée en fin de build enchaînait `adb uninstall … || true` **puis** `adb install -r` — le `|| true` masquant l'échec sur une application déjà installée, chaque installation manuelle détruisait le jeton Twitch. Elle distingue maintenant la mise à jour (`adb install -r` seul, session conservée) de la première installation ou du changement de signature (avec le coût nommé). Mesure du 05/10 : `adb install -r` laisse `firstInstallTime` inchangé et `dataDir` identique, donc `/data/user/0` est conservé ; `uninstall` + `install` recrée le paquet et perd la session. L'updater intégré passe par le même `PackageInstaller`, et rien du greffon Twouich ne touche les préférences de session.
- **Un piège du générateur supprimé au passage** : le contrôle d'idempotence (copier l'arbre patché, repasser `patch.py` deux fois, comparer) a montré que le garde de veille insérait **une ligne vide de plus à chaque build** dans `PlayerActivity.smali`. Sans effet sur le dex — l'empreinte du livrable est restée identique —, mais c'est le mécanisme exact qui rend une cible de `patch.py` invisible quand `build.sh` réutilise `work/decoded`. Corrigé à la source, avec l'empreinte inchangée comme preuve de neutralité.
- **Aucune régression du mode TV**, garantie par construction et **mesurée** : le garde est `twouichPhoneHeadersState() == 3`, la décision déjà employée par le portage (mode déclaré par le système, ou ≥ 600 dp), et il est appliqué dans les **deux** méthodes (pose du listener et action) ; le listener n'est de plus posé que dans la branche qui affiche ce bandeau, donc jamais pour un utilisateur connecté. Mesure sur BlueStacks en 1920×1080 / 240 dpi (720 dp de largeur minimale) : le même bandeau est `clickable=false` et l'écran ne contient **aucun** nœud `twouich_*` — les en-têtes téléphone ne sont pas posés et le titre reste inerte.
- **Le chat du téléphone a un bouton « Envoyer ».** Jusque-là, le message ne pouvait partir qu'au clavier. Le compositeur téléphone gagne un bouton icône de 48 dp, branché sur **exactement** la même voie d'envoi que la touche ENTER (callback asynchrone `Ly6/i0`, donc les mêmes gardes d'authentification et followers-only) plutôt que sur une implémentation parallèle qui divergerait à la première évolution d'amont ; le réglage de taille de police existant est conservé.
- **Preuves hors appareil** : `test_apk` gagne des verrous sur le type dataSync de l'updater, le type specialUse **et** son sous-type, les permissions, le layout téléphone, la méthode d'envoi dans le dex — et sur la connexion au doigt (les deux méthodes et le listener présents dans le dex livré, activité de connexion déclarée) — avec des drapeaux **mesurés** sur l'AXML compilé (dataSync `1<<0`, mediaPlayback `1<<1` en témoin de calibrage, specialUse `1<<30`), jamais devinés. `test_smali_branches` **52/52** (dont l'invariant « source unique TV » : la méthode d'envoi passe désormais par `write_player` au lieu d'écrire le smali du lecteur en direct, les 5 verrous de la connexion au doigt, et les 3 du plafond vidéo — dont « `v7` reçoit un entier **avant** le test », sans quoi ART refuse la classe entière : `VerifyError: args to 'if' (Integer, Reference: android.util.DisplayMetrics) must be integral`), `test_sanitizer`, `test_update_check` 26/26, `test_brand`, `test_normalize_apk`, `test_radar` 10/10, `test_check_secrets`, `test_analyzer.sh`, `test_device_ui.sh` et `check-secrets` verts. Build reproductible : l'empreinte du livrable est **inchangée** après le refactoring du générateur.
- **Validé sur l'appareil (Xiaomi 24095PCADG, Android 16 / API 36)** : un candidat au versionCode volontairement inférieur (150, construit depuis le même arbre patché) a été installé pour rejouer le scénario ; la mise à jour proposée a donné `S0undTV_AutoUpdateSrv onStartCommand: …/v1.0.17/Twouich_v1.0.17.apk`, soit un `startForeground` **réussi** là où la version publiée mourait dans `onCreate`. L'updater installant ensuite v1.0.17 — non corrigée —, le redémarrage de celle-ci reproduit le crash attendu : démonstration en négatif du diagnostic. Le 165 final est ensuite installé : `SELFTEST 31/31`, aucun `FATAL EXCEPTION`, aucune boucle de mise à jour (annonce 164 < installée 165) et les trois permissions de type accordées par la plateforme.
- **Connexion au doigt, validé sur BlueStacks** (Android 13 / API 33, 720×1280 en 240 dpi, soit 480 dp — l'appareil de référence étant débranché) : `title_text` porte « Login to use the app » avec `clickable=true` en `[237,41][636,131]`, le tap ouvre `com.s0und.s0undtv/.activities.LoginActivity` (`topResumedActivity`) — **pas** `AltLoginV2Activity` —, le WebView rend la page (les couleurs relevées sont celles de Twitch, pas le thème de l'app `#130c1f`/`#7c22e8`), et le logcat ne contient ni `FATAL` ni erreur réseau. Aucune connexion Twitch n'a été tentée : il n'y a pas de compte à engager dans l'environnement de test.
- **Chaîne de publication vérifiée jusqu'aux octets.** Tag `v1.0.18` poussé sur `2207593` → job CI « build signé + publication » **vert** (tests, secrets, keystore restauré depuis les secrets chiffrés, signature v1+v2+v3, release créée avec l'APK et `changelog.html`, contrôle par la CI de ses propres octets servis). Livrable `dist/Twouich_v1.0.18.apk`, 11 260 648 o, SHA-256 `2d5a88e3a12d6b9779d1c3ef214e5cacc010d46d76eafe8eeead88b4f5c8082e` — **identique au digest de l'asset publié** (reproductibilité local↔CI tenue, comme v1.0.14/15/17). `check-release.sh` **exit 0 sur les quatre étages** : livrable conforme, `update.json` publié en 165/v1.0.18, release `latest` + assets en 200, **octets servis = livrable**. Reste à faire sur appareil : le parcours `165-1 → 165` (dialogue → téléchargement → `PackageInstaller`), la Freebox POP n'ayant pas été rebranchée.

## v1.0.17 — 2 octobre 2026

- **Correctif de fuite midroll — la zone pub ne se ferme plus sur `#EXT-X-DISCONTINUITY`.** Dans un pod réel, ce tag arrive **dans le même bloc que les marqueurs, avant les segments** : l'ancienne fermeture ne protégeait que le bloc de balises, les segments ne restant protégés que par le titre « Amazon » du `#EXTINF`. Un second créatif sans ce titre partait alors au lecteur (fuite observée le 01/10/2026 en direct : compteur figé à 8 pendant 48 s, sortie +10 103 octets au-dessus de la baseline, ≈ 24 segments livrés). La zone se ferme désormais sur `#EXT-X-TWITCH-LIVE-SEQUENCE` **ou** la DATERANGE `X-TV-TWITCH-STREAM-SOURCE="live"` (doublon volontaire), un quartile en ligne la réarme par sécurité, et le `#EXT-X-DISCONTINUITY` reste émis pour le saut de timeline du lecteur.
- **Preuves** : `test_sanitizer` **69 assertions** (fixtures réelles `MIDROLL_DOUBLE_CREATIF_2026_10_01`, `QUARTILE_SEUL_2026_10_01`, `FIN_DE_POD_SANS_LIVE_SEQ_2026_10_01`), `test_smali_branches` **44 verrous**, **165 dumps réels** du 01/10 rejoués (0 fuite, 0 contenu mangé), mordance par **4 mutations**, et validation sur Freebox POP : 18 pods observés après installation, compteur 3 → 22 continu sur tout le pod, sortie jamais au-dessus de la baseline, aucune pub visible.

## v1.0.16 — 22 septembre 2026

- **Intégration TwVodNoAdsJCed : VOD dé-mutée et fallback anti-pub VaFT.** Les playlists VOD `cloudfront` contenant `-unmuted` sont réécrites en `-muted` avant lecture (`PlaylistSanitizer`, 5 lignes, miroir `test_sanitizer.py` + 4 asserts) — les VODs mutées retrouvent leur son d'origine lorsque Twitch le conserve sous `-muted`. Le fallback VaFT (`VaftFallback`, `AdBlockDataSource`) capture le `channel` sur `usher.ttvnw.net/channel/hls` et, si `stitched-ad` survit au stripping (nouveau format), tente un flux propre via `GQL PlaybackAccessToken embed` (`kimne78kx3ncx6brgo4mv6wki5h1ko`) -> `usher v2` -> première variante `m3u8` (5 s timeout, `try/catch` -> repli stripping local, `ENABLED=true` dormant tant que `lastCut>0`). `test_smali_branches 40/40`, `test_apk 48/48`, `SELFTEST 31/31` verts sur `Freebox POP`.
- **Aucune régression** : `AdBlockDataSource.read()` `.locals 7`, `PlaylistSanitizer` hors machine à états, `VaftFallback` no-op quand `ENABLED=false` ou `lastChannel` vide.

## v1.0.15 — 22 septembre 2026

- **La table de vérité de la mise à jour automatique dit enfin ce que fait l'application.** Le
  canal Beta exige **les deux entrées** du fichier d'annonce (`ReleaseType: 0` **et** `1`) : une
  annonce qui n'en publie qu'une — c'est notre cas, nous ne publions qu'une entrée stable — ne
  réveille donc pas une installation restée en Beta. Les deux miroirs de cette logique (le test
  hors appareil et le self-test embarqué) annonçaient au contraire un dialogue dans ce cas :
  corrigés sur le bytecode réellement livré, et **deux vérifications nouvelles** verrouillent la
  précondition, dans le test comme dans le code compilé.
- **Le self-test embarqué passe à 31 vérifications** (18 du filtre anti-pub + 13 de la table de
  vérité de l'updater) : c'est lui qui empêchera la même dérive de revenir.

## v1.0.14 — 22 septembre 2026

- **Le mode TV est réparé** : l'interface TV se décidait sur le seuil de 600 dp — or la Freebox Pop
  (1920×1080 en 320 dpi) déclare 540 dp et recevait donc la disposition téléphone (barre de
  navigation tactile à l'accueil, panneau Leanback replié, géométrie empilée dans le lecteur). La
  décision passe par le **mode déclaré par le système** (`uiMode`), et les layouts d'origine sont
  posés dans `layout-television/` (+ `layout-sw600dp/`, `layout-sw540dp/`) depuis la capture
  versionnée `patch/res-tv/` : une TV ne peut plus recevoir un layout téléphone, quel que soit son
  nombre de dp. Mesuré sur la Freebox : plus aucun id `twouich_phone_*` à l'accueil, **panneau
  latéral de nouveau déployé** (`browse_headers 0,0-540,1080`), lecteur dans la géométrie de
  l'amont (vidéo plein écran, chat 225 dp en bas à droite).
- **Trois gardes lisaient la polarité à l'envers** (`if-ne` au lieu de `if-eq` sur `uiMode`) : le
  téléviseur était traité en TV *par accident*, par le seul seuil de dp, et tout appareil non-TV
  sautait vers la branche TV. Conséquence mesurée : le **service de premier plan démarrait sur le
  téléviseur** (notification comprise), et un téléphone aurait reçu la disposition TV. Corrigé et
  rejoué sur la Freebox (aucun service, trace `interface : TV`), verrous de test alignés.
- **La lecture en veille** : le service de premier plan `mediaPlayback` crée son canal de
  notification dès l'API 26 et ses branchements sont corrigés (deux polarités inversées qui
  faisaient planter le service au démarrage). Il est **réservé au téléphone** (`startIfPhone`), et
  le démontage d'`onStop()` est sauté écran éteint. Le CPU reste à régler pour la veille — détail en
  `TEST-DEVICE.md` § 8.13.
## v1.0.13 — 21 septembre 2026

- **La lecture survit vraiment à l'écran éteint** : un service de premier plan `mediaPlayback` (avec sa description de lecture) garde l'application du bon côté du système quand l'écran s'éteint. Mesure du 21/09 sur le téléphone : sans lui, le système **détruisait les sockets TCP** de l'app passée en arrière-plan et HyperOS annonçait sa mise en sourdine — le flux mourait au bout de 10 s sur `UnknownHostException`. Démarrage avec le lecteur, arrêt avec lui, et **téléphone seulement** : le mode TV ne change pas.
- **La page « Application info » ne montre plus de build obsolète** : la variante `standalone` de l'amont disparaît.

## v1.0.12 — 21 septembre 2026

- **La barre « Envoyer un message » se place au-dessus du clavier** : la fenêtre se réduit quand le clavier s'ouvre, au lieu de laisser la barre au bas de l'écran, cachée derrière les touches.
- **Les lecteurs ne sont plus libérés à l'extinction de l'écran** : le passage en veille ne libère plus ExoPlayer (garde sur `onStop`). Insuffisant à lui seul — mesuré le 21/09 —, voir la v1.0.13.
- **La page « Informations sur l'application » dit la vérité** : elle affichait encore les métadonnées de compilation du projet d'origine (« beta_144 », code 144, branche STV-64, date de build de décembre 2025) ; elle montre la version livrée et la date de publication.
- **Le bouton de repli du chat est retiré** : depuis que le chat vit sous la vidéo, il ne changeait plus la taille de l'image ; le chat reste toujours visible.

## v1.0.11 — 21 septembre 2026

- **En paysage, le direct occupe tout le bord gauche jusqu'en bas** : la vidéo est calée en 16:9 plein écran (plus aucune bande noire) et le chat tient une colonne à droite, avec la saisie sous lui — au lieu de l'image centrée avec le chat en surimpression.
- **La barre d'informations du direct disparaît sur téléphone** : avatar, pseudo, titre, spectateurs et qualité ne prennent plus le bas de l'écran en double du chat ; en portrait la vidéo garde la pleine largeur et le chat la hauteur restante.
- **Rien ne change sur TV** : les deux corrections sont réservées aux écrans de moins de 600 dp, la disposition télévision et son panneau restent tels quels.

## v1.0.10 — 21 septembre 2026

- **Le chat du lecteur garde l'état choisi sur téléphone** : replié ou affiché, le choix survit à la fermeture de l'application et est relu au démarrage du lecteur — un chat replié ne se rouvre plus tout seul au lancement suivant (le choix vit dans les préférences de l'app, une seule relecture par instance).
- **Les derniers messages du chat ne passent plus sous la barre de saisie** : le chat s'arrête désormais au-dessus de la saisie, qui reste collée au bas de l'écran (112 px de messages étaient cachés en permanence) ; les dispositions empilée, repliée et en incrustation restent inchangées.
- **La recette d'acceptation du chat par téléphone devient un script** (`patch/test-chat-toggle.sh`) : six états vérifiés dans l'arbre des vues réellement appliqué, sortie 1 au premier écart, rejouable hors appareil sur des arbres capturés.

## v1.0.9 — 19 septembre 2026

- **La « Politique de confidentialité » du menu affiche désormais la politique Twouich embarquée** (elle chargeait encore la page en ligne du projet d'origine) ; la page « Mentions légales » embarquée est accessible depuis « À propos ».

## v1.0.8 — 19 septembre 2026

- **Mentions légales et politique de confidentialité embarquées** : deux nouvelles pages accessibles depuis « À propos », écrites sur ce que l'application fait réellement — aucune donnée collectée, aucun serveur propre, et la vérité documentée sur l'héritage d'origine (composants Firebase toujours configurés, permission micro déclarée mais jamais accédée).

## v1.0.7 — 19 septembre 2026

- Le self-test embarqué passe à **28 vérifications** : la table de vérité de la mise à jour automatique est désormais rejouée dans le bytecode réel à chaque démarrage (annonce en retard → silence, pas de boucle d'update, sécurité sur version illisible) — le miroir machine de la logique vérifiée hors réseau.

## v1.0.6 — 19 septembre 2026

- Build reproductible inter-plateformes : l'ordre des entrées ZIP est canonisé (tri par nom) — le SHA-256 du livrable est désormais identique quel que soit l'OS de build (Windows ou Linux) ; le hash publié identifie le fichier livré **et** la recette.
- Surveillance continue du format publicitaire : un radar quotidien en CI rejoue le nettoyage sur des playlists Twitch réelles et ouvre une issue si un marqueur n'était pas reconnu — le pendant serveur de la sentinelle embarquée depuis la v1.0.5.
- Outillage de test enrichi : observation live automatisée (`test-live.sh`), verdicts d'analyse affinés (contenu traversé sans pod ≠ cas suspect).

## v1.0.5 — 18 septembre 2026

- Sentinelle intégrée au filtre : toute balise publicitaire non reconnue est consignée en logcat (`marqueur pub inconnu`), pour détecter automatiquement un futur changement de format côté Twitch.
- Build reproductible au sens strict : horodatage ZIP normalisé, date de la page « Nouveautés » figée, fins de ligne canonisées — deux builds du même arbre produisent des octets identiques.

## v1.0.4 — 16 septembre 2026

- Version de maintenance, publiée pour valider la chaîne de publication automatique (tag poussé → build signé par la CI) ; aucun changement fonctionnel par rapport à la v1.0.3.

## v1.0.3 — 16 septembre 2026

- Version de maintenance, publiée pour valider le parcours de mise à jour automatique (aucun changement fonctionnel par rapport à la v1.0.2).

## v1.0.2 — 16 septembre 2026

- Les nouvelles installations démarrent désormais sur le canal de mise à jour **Stable** (le socle d'origine était un build beta et forçait le canal Beta au premier lancement, ce qui rendait la mise à jour automatique muette tant qu'aucune entrée beta n'était publiée).

## v1.0.1 — 16 septembre 2026

- Accent par défaut recoloré aux couleurs Twouich : plus de rouge d'origine dans l'interface (cartes focalisées, bouton de recherche, commutateurs).
- Dans les réglages, l'accent par défaut s'appelle désormais « Twouich ».
- Corrections de documentation et gardes-fous supplémentaires sur le livrable.

## v1.0.0 — 15 septembre 2026

Première release publique de [Twouich](https://github.com/Endymi0n74/Twouich), un client Android TV pour Twitch.

### Nouveautés

- Filtrage des marqueurs publicitaires SSAI dans les playlists HLS avant leur lecture.
- Nouvelle identité Twouich : écran de démarrage, icônes, bannière TV et interface violette.
- Captures du tutoriel adaptées à la nouvelle palette.
- Mise à jour automatique depuis les releases Twouich, sans proposition répétée lorsque la version installée est déjà la plus récente.
- Self-test embarqué du filtre et chaîne de build vérifiable.

### Projet d'origine et crédits

Twouich est basé sur le projet d'origine [S0undTV](https://github.com/S0und/S0undTV). Merci à ses auteurs et à ses contributeurs pour le travail initial et les bibliothèques utilisées.

Ce dépôt redistribue uniquement des binaires patchés et les patchs associés ; il ne redistribue pas le code source original.

### Limites

- Le filtrage dépend du format actuel des marqueurs publicitaires Twitch et peut nécessiter une adaptation si ce format change.
- L'application n'est pas affiliée à Twitch Interactive, Inc.
- Aucun contenu payant ni abonnement n'est contourné.
