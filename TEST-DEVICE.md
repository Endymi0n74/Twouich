# Procédure de test anti-pub sur un appareil réel

Objectif : prouver, avec les traces de l'appareil lui-même, que les plages publicitaires sont
retirées **pendant** une coupure réelle — et pas seulement que l'app « a l'air de marcher ».

Trois scripts font tout le travail :

| Script | Rôle |
|---|---|
| `patch/test-selftest.sh` | **verdict déterministe** : rejoue des playlists publicitaires Dans le code compilé, sur l'appareil, sans attendre une coupure (§ 0.1) |
| `patch/test-device.sh` | trouve `adb`, choisit l'appareil, installe l'APK, lance la capture `logcat` filtrée, puis analyse |
| `patch/test-live.sh` | **observation longue en direct** : enchaîne les étapes mécaniques de la recette du § 2 (capture détachée surveillée + verdict) ; la navigation et l'observation restent à la main |
| `patch/device-ui.sh` | **pilotage de l'interface** : mesure le canal d'entrée (tactile ou touches), lit le focus, navigue au D-pad et active un bouton (§ 8) |
| `patch/analyze_device_log.sh` | verdict d'une capture existante (utilisable seul) |
| `patch/check-release.sh` | la release publiée correspond-elle au livrable et à `update.json` (§ 0.2) |

---

## 0. État de validation

Vérifié sur un appareil réel (émulateur BlueStacks, `emulator-5554`, Android 7.1.1 / API 25), avec
un compte Twitch connecté — session de 4 minutes sur une chaîne en direct :

- installation réussie → `versionName=v1.0.0` lu sur l'appareil (versionCode 147) ;
- **la lecture fonctionne** : 131 nettoyages de playlist média (une toutes les 2 s, c'est le
  rafraîchissement HLS normal), des milliers de lectures de segments, **0 erreur de lecture**,
  aucun `Playback error`, aucun `FATAL EXCEPTION` ;
- le filtre est bien traversé par *toutes* les lectures HLS de l'app, sous le tag `Twouich` ;
- les 4 verdicts de `analyze_device_log.sh` sont testés (pubs retirées / rien retiré / erreurs de
  lecture / aucune playlist).

### Validation fraîche v1.0.0 (16/09/2026, même émulateur)

- désinstallation complète puis installation de `dist/Twouich_v1.0.0.apk` → `versionCode=147
  versionName=v1.0.0` ;
- `SELFTEST 18/18` dès le premier lancement (`bash patch/test-selftest.sh --in-app`) ;
- **updater sans boucle** : 4 lancements consécutifs — l'activité au premier plan reste
  `FireTVMainActivity` à chaque fois, `UpdateActivity` n'apparaît jamais et
  `S0undTV_AutoUpdateSrv` ne loggue rien (147 = version publiée, rien de plus récent à proposer) ;
  le seul « update » du logcat est la télémétrie Firebase (`update_required:false`, sans rapport).

### Anti-boucle revérifiée (19/09/2026, émulateur v1.0.6 = annonce v1.0.6)

Rejeu du même protocole des 4 lancements sur le cas limite où **l'annonce égale la version
installée** (émulateur en 153 / v1.0.6, `update.json` publié annonçant 153) :

- 4 cold starts consécutifs (force-stop → relance launcher, ~18 s chacun, capture `logcat`
  en continu) → à chaque fois `mCurrentFocus` reste
  `com.s0und.s0undtv/.activities.FireTVMainActivity`, `UpdateActivity` n'apparaît jamais,
  et `S0undTV_AutoUpdateSrv` ne loggue **aucune ligne** (son silence est le verdict :
  rien de plus récent à proposer) ;
- c'est le bras « publiée == installée » de la comparaison corrigée en v1.0.0 (la version
  installée est lue via `PackageManager.getPackageInfo`, plus le plancher figé 144
  d'upstream) ; le bras « publiée < installée » — l'« annonce en retard », fenêtre historique
  entre une release et le push de son annonce — donne le même silence par construction :
  verrouillé hors réseau par `patch/tests/test_update_check.py` (table de vérité + gardes
  sur l'arbre décodé, 20 vérifications) ;
- la preuve complémentaire en production est en § 0.2 : la Freebox en 152 a ouvert le
  dialogue au cold start suivant l'annonce 153, pendant que l'émulateur en 153 ne rouvrait
  rien — même logique, observée des deux côtés du seuil.

### Réglage d'accent vérifié en conditions réelles (16/09/2026, v1.0.1)

Pilotage `uiautomator` sur `emulator-5554` : Réglages → General settings → Accent color —

- le réglage affiche **« Twouich »** (l'ancien « Red (default) » n'existe plus, ni en libellé ni
  dans le dialogue de choix, où « Twouich » est passé en première position) ;
- choisir **« Blue »** est accepté et persiste (relançant l'app, comme annoncé par le dialogue) :
  les zones de focus passent au bleu `#004db3` (mesuré au pixel), plus aucun violet ni rouge ;
- revenir à **« Twouich »** fonctionne de même et persiste après redémarrage complet de l'app —
  l'appareil est laissé dans cet état.

**Ce que cette session a coûté — et pourquoi elle valait la peine.** Le premier passage sur
appareil a cassé la lecture : deux erreurs de branchement dans le smali (`if-eqz`/`if-nez` inversés
et la sémantique Dalvik de `if-gez`/`if-gtz`, qui se lit *à l'envers* de son nom : `if-gez` teste
`>= 0`). Le miroir Python de `test_sanitizer.py` ne pouvait pas les voir — seul l'appareil pouvait.
Elles sont corrigées et verrouillées par `patch/tests/test_smali_branches.py`.

Ce que cette session ne pouvait pas montrer — parce que la chaîne testée n'a servi aucune pub —
est **le retrait effectif de segments publicitaires**. Il est désormais prouvé autrement : par le
**self-test embarqué** (§ 0.1), qui fait passer des playlists publicitaires Twitch réelles dans le
code compilé, sur l'appareil, et vérifie le résultat. La capture live reste utile en complément
(elle prouve que ça tient pendant tout un direct), mais elle n'est plus la seule preuve possible.

---

### Neutralisation Firebase/Measurement (19/09/2026, candidat v1.0.9)

Le candidat `dist/Twouich_v1.0.9.apk` a été installé sur l'émulateur BlueStacks `127.0.0.1:5555`
(Android 7.1.1, UID applicatif 10069), puis lancé après `am force-stop` et remise à zéro de `logcat`.
Pendant 25 secondes de cold start :

- `SELFTEST 28/28` et nettoyage `623 → 328` sont apparus ; aucun `FATAL EXCEPTION`,
  `Default FirebaseApp`, `FirebaseCrashlytics` ou `RemoteConfig` n'est apparu pour le processus
  Twouich (PID observé 14794) ;
- aucune ligne d'initialisation Firebase/Measurement ne porte le processus Twouich : les lignes
  Firebase restantes proviennent exclusivement des processus BlueStacks (`com.bluestacks.home`,
  `com.bluestacks.gamecenter`) et sont séparées par PID/package ;
- le manifeste signé ne contient plus de provider/service/receiver Firebase ou Measurement, les
  identifiants Firebase sont absents de `resources.arsc`, et `test_apk.py` est vert ;
- `dumpsys netstats` ne présente aucune entrée Firebase pour l'UID Twouich. Cette observation est
  une preuve de non-départ sur l'appareil dans cette fenêtre ; elle est conservée avec la capture
  `/tmp/twouich-device-firebase-final2.log` et doit être rejouée à chaque release.

Le correctif couvre les trois chemins qui restaient actifs après le retrait du manifeste : Remote
Config (`MainApp.q()` / `PlayerActivity.J3()`), facade Crashlytics (`P6/e`) et événements Analytics
(`P6/b` / `P6/l.i()`), remplacés par des no-op à signatures inchangées. Les bibliothèques Google
peuvent encore être présentes dans le dex upstream, mais aucun point d'entrée applicatif ne les
initialise ni ne leur fournit de configuration.

---

## 0.3 Observation smartphone — candidat v1.0.9 (19/09/2026)

Le téléphone connecté apparaît comme `ONEPLUS_A3010` / Android 7.1.1, mais son profil d'émulation
reste **1280×720 paysage** : cette session valide donc le tactile et le lecteur hors-TV, pas encore
un vrai écran portrait 1080×2400.

Parcours observé sur un direct réel (`Niniste`, catégorie Just Chatting) :

- **Navigation** : le lancement arrive directement sur `FireTVMainActivity`, avec une UI très TV
  (panneau latéral large, rangées horizontales, grandes cartes et navigation D-pad implicite). Le
  tactile fonctionne pour ouvrir « Followed Channels », puis un direct ; les noms des chaînes
  suivies et les cartes live sont accessibles, mais l'espace vide et la hiérarchie sont mauvais pour
  un téléphone. L'application et toutes les activités restent forcées en `sensorLandscape`.
- **Lecteur** : `PlayerActivity` s'ouvre, affiche la chaîne, le titre, la qualité `720p60` et le
  compteur de spectateurs. Soixante secondes de lecture stable ont produit environ une requête de
  playlist toutes les deux secondes, sans `Playback error`, `FATAL EXCEPTION`, `ANR` ni erreur
  ExoPlayer. Le filtre a traversé le trafic réel ; les playlists observées étaient du contenu pur
  (`~16,7 Ko → ~16,7 Ko`, `segments pub retirés : 0`), aucune coupure publicitaire n'a eu lieu.
- **Chat** : il n'est pas visible à l'ouverture du lecteur. Un geste horizontal du bord droit vers
  le centre le révèle dans une colonne de **338 px** (`ChatRecycleView`, bornes `[942,360][1280,720]`)
  et les messages live défilent correctement. En revanche, le contrôle qui affiche/masque le chat,
  son redimensionnement et la saisie ne sont pas découvrables par le tactile ni exposés dans l'arbre
  d'accessibilité ; le clavier et l'envoi n'ont donc pas pu être validés comme parcours smartphone.

**Chantiers UX réels, par priorité** :

1. créer un vrai conteneur smartphone (portrait + paysage) et remplacer la navigation Leanback/rangées
   par une navigation tactile avec barre/bottom navigation et cartes adaptatives ;
2. rendre le lecteur responsive (vidéo au-dessus, chat dessous ou panneau redimensionnable) et exposer
   des contrôles tactiles explicites pour pause, qualité, chat et changement de disposition ;
3. ajouter un bouton chat visible à l'ouverture, une zone de saisie/clavier Android et des états
   d'accessibilité/content-description ;
4. tester les densités, rotations et tailles de texte sur un vrai profil portrait avant toute promesse
   de support smartphone.

### Première acceptation sur téléphone réel — Xiaomi 24095PCADG (19/09/2026)

Le téléphone USB `QOGQ694DEE5PLBGI` est un appareil réel Android 16, écran physique
`1220×2712` en densité 520. Installation de `v1.0.9` (versionCode 156) réussie après
acceptation de l'autorisation « Installer via USB », puis lancement sans crash :

- `FireTVMainActivity` reste le composant de premier plan, mais Android affiche bien l'UI dans
  le profil portrait réel ; l'arbre UI couvre `[0,0][1220,2712]` et le champ de recherche est
  tactile/focusable dans la zone supérieure ;
- `SELFTEST 28/28 verifications, flux filtre : 328 octets` est confirmé dans le logcat du
  téléphone ;
- la coque tactile smartphone est visible avec trois actions en bas : **Accueil**, **Recherche** et
  **Réglages** ; les deux dernières ont été activées par tap et ouvrent respectivement
  `SearchActivity` et `SettingsActivity`, sans crash ;
- le parcours vers un direct suivi a ensuite été rejoué sur `Niniste` : `PlayerActivity` s'ouvre
  en portrait, la vidéo occupe `[0,1013][1220,1699]` (format 16:9 centré) et le chat occupe
  `[0,1356][1220,2712]`, soit une vraie colonne basse de 1 356 px ; le message de bienvenue est
  présent dans l'arbre UI. Le direct et le chat sont donc bien rendus dans la variante téléphone ;
- en suivant l'UX de TwitchDroid, le patch suivant force maintenant une disposition verticale
  dédiée au téléphone : vidéo 16:9 en haut, chat immédiatement dessous, puis barre de saisie
  collée en bas ; la disposition TV reste inchangée. Le panneau d'envoi contient un `EditText`
  identifié `ET_SendMessage`, le hint « Écrire dans le chat » et `imeOptions=actionSend`. Le
  garde-fou APK vérifie cette ressource. **Bug corrigé le 19/09** : la première version de
  `twouichPhoneStackedLayout()` passait un `LayoutParams` (objet) à `View.setVisibility(int)` —
  erreur de vérification Dalvik qui faisait **planter l'app à l'ouverture d'une vignette/du
  lecteur**. Le registre entier est désormais utilisé, et `patch.py` refuse la régression
  (2 contrôles). Vérification sur le téléphone : `am start -a android.intent.action.VIEW -d
  s0undtv://stream` ouvre `PlayerActivity` sans `FATAL EXCEPTION` ni `VerifyError`, et la
  géométrie mesurée au dump confirme l'empilement — vidéo `[0,0][1220,686]` (1220×686 = 16:9)
  en haut, compositeur `[16,2616][1204,2696]` en bas. La barre basse est aussi passée de trois
  `Button` Android par défaut (grises, hors thème) à une barre sombre opaque avec hairline et
  trois libellés : Accueil / Recherche / Réglages, tous deux derniers vérifiés au tap
  (`SearchActivity`, `SettingsActivity`).

  **Acceptation réussie après
  déverrouillage** : le champ est focusable/tactile dans l'arbre UI (`[16,2105][1204,2208]`),
  le clavier s'ouvre et un message peut être écrit dans le chat réel. Le parcours smartphone
  vidéo → chat → saisie est donc validé ; il reste seulement à consigner un envoi publié si
  l'utilisateur souhaite éviter tout message de test.

### Diagnostic en cours — chat tactile qui « ne défile pas » (19/09)

Symptôme rapporté sur téléphone : le chat s'affiche mais ne répond pas au doigt.

Deux hypothèses ont été **écartées par lecture du code**, pas par supposition :

- le `GestureDetector` du lecteur (`PlayerActivity.e4`, construit sur `p0` + un
  `OnGestureListener`) n'intercepte pas le chat : aucune `setOnTouchListener` n'existe dans
  `PlayerActivity`, et la distribution Android donne la priorité aux enfants — un drag sur le
  `ChatRecyclerView` ne remonte donc jamais jusqu'à `onTouchEvent` de l'activité ;
- `ChatRecyclerView` n'intercepte rien lui-même : la classe n'ajoute que deux champs privés et
  délègue à `RecyclerView` (aucun `onTouchEvent`/`onInterceptTouchEvent` dans le smali).

Restent deux causes plausibles, **à trancher sur appareil déverrouillé** :

1. **auto-scroll sur nouveau message** — un chat très actif (ddg) repousse la liste en bas à
   chaque arrivée, ce qui annule visuellement le geste (le drag « revient » en place) ; c'est
   l'hypothèse la plus probable et elle demande d'ajouter un verrou « l'utilisateur a touché » ;
2. **rien à faire défiler** — hauteur insuffisante ou liste vide au moment du test, auquel cas
   le problème n'est pas le défilement du tout.

Le correctif ne doit pas être posé à l'aveugle : les deux causes appellent des changements
opposés (respectivement un garde sur le scroll programmatique, ou un ajustement de hauteur).

### Ouvrir le lecteur directement, sans naviguer (recette de test)

`PlayerActivity` n'est pas lançable par `am start -n …` sur tous les ROM, mais elle porte un
**deep link** : `s0undtv://stream` avec l'extra string **`user_login`** (clé = ressource
`R.string.user_login`, valeur `0x7f130236`). C'est la façon déterministe d'ouvrir le lecteur
— donc de tester la disposition téléphone, le chat et la saisie sans dépendre des rails Leanback :

```bash
"$ADB" -s "$S" shell am start -a android.intent.action.VIEW \
    -d "s0undtv://stream" --es user_login ddg
```

Résultat mesuré le 19/09 sur le téléphone (Xiaomi, Android 16) : `PlayerActivity` au premier plan,
`SELFTEST 28/28` dans le logcat de l'app, **aucun `FATAL EXCEPTION`**, et la géométrie empilée
(vidéo `[0,0][1220,686]`, compositeur `[16,2616][1204,2696]`).

### Variante UX smartphone livrée dans le patch

Le patch prépare désormais une variante réellement sélectionnée par Android :

- les `uses-feature` restent présentes mais sont toutes `android:required="false"`, et les activités
  passent de `sensorLandscape` à `fullSensor` : un téléphone peut rester en portrait, tandis qu'un
  téléviseur conserve son orientation capteur habituelle ;
- `res/layout/activity_player.xml` devient la variante téléphone ; le layout TV original est conservé
  dans `res/layout-sw600dp/activity_player.xml`, donc le parcours Leanback n'est pas écrasé ;
- sur téléphone, le chat principal occupe la largeur et est ancré en bas avec une hauteur dédiée de
  280dp : il est visible dès l'ouverture du lecteur, sans dépendre du swipe du bord droit observé
  sur le profil paysage ;
- le garde-fou `test_apk.py` lit le manifeste compilé, exige l'enum `fullSensor`, les deux variantes
  de layout et la ressource de dimension. Cette étape ne prétend pas encore valider une vraie saisie
  clavier ni une disposition portrait vidéo/chat idéale : elle constitue le socle UX à tester sur
  un téléphone 1080×2400.

### UX smartphone alignée sur l'interface de référence — barre basse, saisie, picture-in-picture (20/09/2026)

L'interface de référence (Twitch mobile / PurpleTV, captures du 20/09) a servi de cible : les écarts
qui restaient tenables dans ce pipeline (smali + qualifiers de ressources) ont été traités, **sans
toucher au visuel TV**.

| Élément de la référence | Ce qui est fait, côté téléphone seulement |
|---|---|
| Barre basse à icônes, onglet actif coloré | 58dp, fond `#0e0e10` + hairline, trois entrées **icône + libellé** (`Accueil` / `Parcourir` / `Réglages`), icônes vectorielles dédiées et teinte `theme_purple_bright` sur l'onglet actif |
| Champ « Envoyer un message » | libellé du `ET_SendMessage` remplacé (l'ancien « Écrire dans le chat » est réparé au passage), `imeOptions=actionSend` conservé |
| Fenêtre d'incrustation | **picture-in-picture** : bouton sur la vidéo, ratio 16:9, chat et saisie masqués pendant l'incrustation, empilement réappliqué à la sortie |

Le PiP demande trois choses que le manifeste n'avait pas : `android:supportsPictureInPicture="true"`
sur l'activité lecteur, et `screenSize|smallestScreenSize|screenLayout|orientation` dans ses
`configChanges` — sans eux Android **recrée** l'activité à l'entrée en incrustation, donc le direct
repart de zéro. Comme l'activité n'est désormais plus recréée, la disposition est réappliquée dans
`onConfigurationChanged`, et l'entrée/sortie d'incrustation est traitée dans
`onPictureInPictureModeChanged` (le préfixe de callback public est celui de `Activity`, comme pour
`onWindowFocusChanged` — l'erreur du même jour).

Recette sur un téléphone réel (Android ≥ 8, sinon le PiP n'existe pas) :

```bash
ADB="<chemin>/adb.exe"; S=<série>; A=com.s0und.s0undtv
"$ADB" -s "$S" shell am force-stop $A; "$ADB" -s "$S" logcat -c
"$ADB" -s "$S" shell am start -a android.intent.action.VIEW \
    -d "s0undtv://stream" --es user_login ddg
sleep 8
# bouton d'incrustation, en haut à droite de la vidéo (48dp)
"$ADB" -s "$S" shell input tap <droite> <haut>
sleep 3
"$ADB" -s "$S" shell dumpsys activity activities | grep -i picture
"$ADB" -s "$S" shell dumpsys activity top | grep -E 'ChatRecycleView|ExoPlayer'   # chat masqué, vidéo pleine
```

Vérifié le 20/09 sur l'émulateur (API 25, donc **sous** l'API 26 du PiP) : le bouton est bien posé sur
la vidéo (`[1836,12][1908,84]` en 1920×899 = 48dp), l'appui est **inerte sans planter** — le garde
`sget v0, Landroid/os/Build$VERSION;->SDK_INT:I` / `if-lt v0, 0x1a` fait sortir la méthode avant toute
référence à `PictureInPictureParams`, classe qui n'existe pas avant l'API 26. L'acceptation réelle du
PiP (fenêtre d'incrustation, retour au plein écran, chat restauré) demande un téléphone **API ≥ 26** :
l'acceptation réelle a été faite le **20/09** sur un téléphone API ≥ 26 — voir ci-dessous, elle a mis au jour deux défauts que l'émulateur ne pouvait pas montrer.

#### Acceptation de l'incrustation sur le téléphone (20/09/2026) — et les deux défauts qu'elle a mis au jour

Exercée sur un direct réel (`ddg`, qui servait du SSAI : jusqu'à **16 segments de pub retirés** par
cycle pendant la session), avec la commande ci-dessus et les deux mesures systématiques —
`dumpsys activity top` pour les rectangles **et** la trace logcat pour l'état.

| État | Vidéo | Chat | Compositeur | Trace `Twouich` |
|---|---|---|---|---|
| Plein écran (portrait 1220×2712, `sw392dp`) | `[0,0][1220,686]` (16:9 exact) | `[0,686][1220,2712]` | `[0,2600][1220,2712]` | — |
| Incrustation (`mode=pinned`, fenêtre `[492,130][1200,528]`) | `[0,0][708,398]` (16:9 exact) | **`G`** | **`G`** | `picture-in-picture : video plein cadre, chat et saisie masques` |
| Retour plein écran (`am start -n …/PlayerActivity`) | `[0,0][1220,686]` | `[0,686][1220,2712]` | `[0,2600][1220,2712]` | `picture-in-picture : disposition empilee restauree` |

`G` = `setVisibility(8)` ; `mode=pinned` retombe à 0 à la sortie (l'activité est `singleTask`, donc
`am start` ramène l'instance au premier plan au lieu d'en créer une seconde). La capture d'écran
recadrée sur la fenêtre (`screencap`, puis recadrage `[492,130][1200,528]`) confirme le reste à l'œil :
la vidéo remplit le cadre, **aucune barre de saisie**.

Ce que cette acceptation a révélé — deux causes distinctes, dont la première expliquait tout :

1. **`twouichPhoneView` rendait toujours `null`.** Son garde était écrit `if-nez v0, :no_phone_view`,
   c'est-à-dire « retourne null quand l'identifiant **est trouvé** » : la vue n'était jamais rendue, le
   rappel d'incrustation sortait aussitôt sur ses trois tests de nullité, et **rien n'était masqué** —
   `ChatRecycleView` restait visible et `SendMessageWindow` se dessinait à `[0,286][708,398]`,
   c'est-à-dire **par-dessus la vidéo de la fenêtre d'incrustation** (le défaut visible sur la capture).
   Sans la trace logcat ajoutée dans le même mouvement, la géométrie mesurée (vidéo `708×398`)
   restait compatible avec un empilement appliqué par un autre chemin : la sortie anticipée de la
   méthode était **silencieuse, comme tous les gardes de nullité**.
2. **L'empilement se réappliquait pendant l'incrustation.** Entrer en PiP fait perdre le focus et
   change la configuration ; chacun de ces rappels appelle `twouichPhoneStackedLayout`, qui **remet le
   compositeur visible** et ancré en bas — donc par-dessus la vidéo. Un champ d'instance
   (`twouichPipActive`, écrit en tête de `onPictureInPictureModeChanged`) est désormais lu par ce garde
   (`if-eqz v11, :twouich_phone_layout_ok`), avec la trace
   `picture-in-picture : empilement ignore (incrustation active)` qui rend le refus visible.

Les deux corrections sont verrouillées à la source : la polarité de `twouichPhoneView` et le garde
d'incrustation sont contrôlés par `patch.py` (126 contrôles) et `test_smali_branches.py` (27
vérifications, dont l'assertion « le garde n'est pas inversé »). Vérifié après correction : trace
émise, les deux vues en `G`, empilement restauré à la sortie, **0 `FATAL EXCEPTION`**.

### Disposition empilée : portrait empilé, paysage en repli (20/09/2026)

La vidéo 16:9 était calculée depuis la **largeur**, sans plafond : sur un écran plus large que haut,
elle dépasse la hauteur et le chat recevait une hauteur négative. Mesuré à 1920×899 avant correction :
vidéo écrasée par son parent, chat à **0 px**, disposition inutilisable. Deux règles désormais :

1. la vidéo est **plafonnée** à la place disponible au-dessus du compositeur ;
2. l'empilement n'est appliqué que s'il reste **au moins un tiers** de la hauteur pour le chat —
   sinon on garde le layout d'origine (vidéo plein écran, chat ancré en bas en surimpression), qui est
   aussi la disposition de l'interface de référence en paysage.

Mesures du 20/09 sur l'émulateur (densité 240) :

| Configuration | Vidéo | Chat | Verdict |
|---|---|---|---|
| 800×1600 portrait (`sw533dp`) | `[0,0][800,450]` = 16:9 exact | `[0,450][800,1440]` | empilé, compositeur ancré en bas |
| 1920×899 paysage (`sw599dp`) | `[0,0][1920,899]` plein écran | `[0,449][1920,899]` | repli : vidéo plein écran, chat en bas |

Les deux polarités de ces tests (`if-lt` pour sauter le plafond, `if-ge` pour empiler) sont verrouillées
par `test_smali_branches.py` : elles avaient été écrites à l'envers une fois — la dixième faute de
branchement de ce projet, et la plus coûteuse à diagnostiquer, puisque *les deux* cas d'écran donnaient
un résultat plausible.

### Cartes et rangées réellement tappables au doigt — tap → clic Leanback (19/09/2026)

Symptôme mesuré au doigt (Xiaomi 24095PCADG, Android 16, 1220×2712, densité 520) : **le premier
appui sur une carte ne fait que déplacer la sélection**, l'élément ne s'ouvre qu'au **second**
appui. Deux causes distinctes ont été tracées puis corrigées.

**1. Le panneau TV occupait 70 % de l'écran.** `setHeadersState` recevait l'état `1`, qui laisse le
panneau **visible** — la table de branchement de `BrowseSupportFragment.N2` XOR l'état avec `1`
avant d'appeler `HeadersFragment` : seuls les états `1`/`2` donnent `GONE = false`, l'état `3` met le
panneau en `GONE`. Mesuré auparavant : panneau `browse_headers` de 852×2504 à l'écran, rangées
écrasées dans une bande de 362 px — « les menus sont inutilisables ». Le patch passe donc l'état
**3** (`HEADERS_HIDDEN`) sous 600 dp et **2** (`HEADERS_ENABLED`) sur TV.

**2. Le geste était consommé par la grille.** Instrumentation à l'entrée de
`BaseGridView.dispatchTouchEvent` : l'appui est bien reçu, mais aucune vue enfant ne reçoit le
relâchement — ni le focus préalable de la carte, ni sa sélection ne prédisent le clic natif (les deux
ont été mesurés, puis invalidés). Le patch branche `TapClick` (greffon) à cette entrée : sur un tap
franc (appui + relâchement sans glissement au-delà du seuil `ViewConfiguration`), il clique la plus
profonde vue cliquable sous le doigt — parcours récursif des enfants, positions de mise en page,
translation et défilement retirés — annule d'abord le geste (la carte ne reste pas « appuyée »), puis
**consomme le relâchement** : le chemin natif ne peut donc pas s'ajouter, un tap = exactement un clic.

**Recette reproductible** (téléphone réel, APK du dépôt installé) :

```bash
ADB="<chemin>/adb.exe"; S=<série>; A=com.s0und.s0undtv
"$ADB" -s "$S" install -r dist/Twouich_v1.0.9.apk
"$ADB" -s "$S" shell am force-stop $A
"$ADB" -s "$S" logcat -c
"$ADB" -s "$S" shell am start -n $A/com.s0und.s0undtv.activities.FireTVMainActivity
sleep 9
"$ADB" -s "$S" shell input tap 264 613          # une carte de « Followed Channels »
"$ADB" -s "$S" shell dumpsys activity activities | grep topResumedActivity
"$ADB" -s "$S" logcat -d -s TWOUICH-TAP | tail -3
```

Verdicts obtenus (build final de `TapClick`, en une passe) :

| Geste | Attendu | Mesuré |
|---|---|---|
| Un tap sur une carte de chaîne | la fiche s'ouvre | `ChannelDetailsActivity`, trace `tap -> clic K6.d$b` |
| Un tap sur une carte de direct | le lecteur s'ouvre | `PlayerActivity`, trace `tap -> clic K6.d$a` |
| Retour arrière après l'ouverture | revenir à l'accueil | `FireTVMainActivity` (une seule fiche empilée) |
| Glissement horizontal sur une rangée | défiler, ne rien ouvrir | `relachement ignore : glissement`, accueil inchangé |
| D-pad (→ puis OK) | ouvrir comme avant | `ChannelDetailsActivity`, **aucune** trace (aucun `MotionEvent`) |
| Barre basse (Recherche) | ouvrir la recherche | `SearchActivity`, **aucune** trace (hors grille) |
| Zone sans vue cliquable | rien | `relachement ignore : rien de cliquable sous le doigt` |

La télévision est hors de portée par construction : l'état du panneau n'y change pas (≥ 600 dp) et le
D-pad n'émet aucun `MotionEvent` — la navigation TV reste exactement la même (avant-dernière ligne).

### La limite des 600 dp vérifiée à l'unité près, sur écran large (20/09/2026, BlueStacks/API 25)

Le garde du tap → clic repose sur `Configuration.smallestScreenWidthDp < 600`. Le vérifier « sur un
grand écran » ne suffit pas : il faut **franchir la limite** et montrer que le changement se produit
exactement là. Un émulateur le permet sans matériel supplémentaire — sa configuration se pilote par
`wm` :

```bash
ADB="<chemin>/HD-Adb.exe"; S=<série>; A=com.s0und.s0undtv
"$ADB" -s "$S" shell wm density 240          # densité d'origine, à connaître pour convertir
"$ADB" -s "$S" shell wm size 1920x900        # 900 px / 1,5 = smallestScreenWidthDp = 600
"$ADB" -s "$S" shell dumpsys activity | grep -m1 -oE 'sw[0-9]+dp'   # confirmer la configuration lue
"$ADB" -s "$S" shell am force-stop $A; "$ADB" -s "$S" logcat -c
"$ADB" -s "$S" shell am start -n $A/com.s0und.s0undtv.activities.FireTVMainActivity
sleep 9 && "$ADB" -s "$S" shell input tap <centre d'une carte>
"$ADB" -s "$S" logcat -d -s TWOUICH-TAP        # doit rester VIDE au-dessus de 600 dp
"$ADB" -s "$S" shell wm size reset              # rendre l'émulateur à sa configuration d'origine
```

Une seule APK, quatre configurations mesurées (densité 240, donc `px / 1,5 = dp`) :

| Configuration | `smallestScreenWidthDp` lu | Barre téléphone | Panneau `browse_headers` | Trace après un tap sur une carte |
|---|---|---|---|---|
| 1920×1080 | **720** | absente | `[0,0][393,1080]` **déployé** | **aucune** (écran inchangé) |
| 1920×900 | **600** (exactement la limite) | absente | `[0,0][393,900]` **déployé** | **aucune** (écran inchangé) |
| 1920×899 | **599** (un pixel sous la limite) | présente | absent (masqué) | `appui` puis `tap -> clic K6.d$a` → `PlayerActivity` |

Trois choses sont donc prouvées par ce tableau, et pas seulement le silence :

- **le silence au-dessus de 600 dp n'est pas une absence de branchement** — à 599 dp la même APK,
  sur le même appareil et le même geste, trace et clique : c'est bien le garde qui refuse, pas le
  hook qui manque ;
- **le panneau TV reste déployé comme avant** — `browse_headers` occupe 393 px de large (20 % de
  1920) et le panneau est `GONE` uniquement sous 600 dp ; la géométrie TV est intacte ;
- **le D-pad est intact** : → puis OK à 720 dp ouvre la fiche, avec **zéro** trace (aucun
  `MotionEvent` ne naît d'une touche) ; le lecteur TV garde sa disposition d'origine
  (`ExoPlayer` plein écran `0,0-1920,1080`, `SendMessageWindow` en `GONE`).

### Le crash que cette vérification a révélé — override `protected` (20/09/2026)

Ouvrir un direct sur l'émulateur (API 25) **plantait l'application**, alors que la même APK se
lançait sur le téléphone de référence :

```text
java.lang.NoClassDefFoundError: Failed resolution of: Lcom/s0und/s0undtv/activities/PlayerActivity;
  at com.s0und.s0undtv.fragments.MainFragment$e.c(...)      # clic sur une carte de direct
  at com.android.trace.androidx.leanback.widget.P$c$a.onClick(...)
Caused by: java.lang.ClassNotFoundException: com.s0und.s0undtv.activities.PlayerActivity
Caused by: java.lang.IllegalAccessError: Method 'void ...PlayerActivity.onWindowFocusChanged(boolean)'
            implementing interface method 'void android.view.Window$Callback.onWindowFocusChanged(boolean)'
            is not public
```

L'override injecté pour appliquer la disposition empilée était déclaré `.method protected`. `Activity`
implémente `Window.Callback`, dont `onWindowFocusChanged(boolean)` est **public** : un override plus
faible fait rejeter la **classe entière** par le lieur ART, donc `PlayerActivity` devient introuvable
et tout chemin qui la charge (clic sur une carte, deep link, `am start`) tue l'application. Corrigé en
`.method public`, avec deux garde-fous dans `patch.py` et un verrou dans `test_smali_branches.py`
(le test ne cherche que la **déclaration** — les règles de réparation de `patch.py` doivent pouvoir
nommer la forme fautive pour la corriger). Vérifié après correction : `K6.d$a` → `PlayerActivity`
ouverte, `FATAL EXCEPTION` = 0, et à 720 dp la même carte mène au lecteur TV inchangé.

---

## 0.1 Self-test embarqué — la preuve déterministe

Le greffon contient un self-test (`patch/smali/com/twouich/adblock/SelfTest.smali`) qui ne dépend
d'aucun direct, d'aucun compte et d'aucune coupure : il rejoue quatre playlists aux formats Twitch
réels (plage SSAI `stitched-ad`, bloc `#EXT-X-CUE-OUT`/`CUE-IN`, segment titré `Amazon`, daterange
non publicitaire) dans le **vrai code compilé**, plus un passage complet par `AdBlockDataSource`
(ouverture puis lecture par tranches de 64 octets, avec une source en mémoire).

```bash
cd /d/Codex/Twouich
bash patch/test-selftest.sh             # dex frais, exécuté via app_process, RIEN n'est installé
bash patch/test-selftest.sh --in-app    # ou : redémarre l'app installée et lit son verdict
bash patch/test-selftest.sh --serial emulator-5554
```

Le script rend un verdict et un code de sortie (0 = vert). Deux lignes attendues :

```
I/Twouich: playlist nettoyee 623 -> 328 octets, segments pub retires : 3
I/Twouich: SELFTEST 28/28 verifications, flux filtre : 328 octets
```

| Ligne | Signification |
|---|---|
| `SELFTEST 28/28 …` | les 28 vérifications passent : le filtre agit, sur l'appareil, dans le bytecode réel |
| `SELFTEST KO : <vérification>` | une vérification précise a échoué — c'est la ligne à recopier pour corriger |
| `SELFTEST ECHEC n/28 …` | verdict global en échec (sortie Log.e, donc bien visible dans les captures) |
| `VerifyError` | le smali assemble mais ne passe pas le vérificateur Dalvik : à corriger avant tout test live |

**Validé le 15/09/2026** (`emulator-5554`, BlueStacks, API 25) : `SELFTEST 18/18`, flux filtré de
328 octets — et, dans l'app, `playlist nettoyee 623 -> 328 octets, segments pub retires : 3`. Le
retrait d'une plage publicitaire n'est donc plus une hypothèse à attendre : il est reproduit à
volonté.

Le self-test s'exécute aussi **une fois par démarrage** de l'app (injecté dans `MainApp.onCreate`) :
une seule ligne si tout va bien, le détail des échecs sinon. Il ne dépend d'aucun réseau.

---

## 0.2 Mise à jour automatique — le parcours réel

Un updater ne se prouve qu'avec quelque chose de plus récent à installer : il faut **publier une
version N+1** et regarder une app installée en N se mettre à jour elle-même. C'est la seule preuve
possible : ni les tests locaux, ni la lecture du smali ne l'apportent. La recette complète est au
§ 8 d'`AGENTS.md` ; voici ce qui a été observé, et à quoi ça doit ressembler.

**Validé le 15/09/2026** (`emulator-5554`, API 25). App installée en **145**
(`v1.5.10x-twouich1`), release intermédiaire **`v1.5.10x-twouich2`** (146) publiée + `update.json`
poussé après elle.

| Ce qu'on regarde | Trace attendue |
|---|---|
| l'app ouvre **seule** son écran de mise à jour | `dumpsys activity activities` → `mResumedActivity: …/.activities.UpdateActivity` ; à l'écran « New update available! » + `Version: … / Version code: …` |
| elle télécharge la bonne URL | `adb logcat -s S0undTV_AutoUpdateSrv` → `onStartCommand: https://github.com/<repo>/releases/download/<VersionName>/<APK>` |
| elle passe son APK au système | ActivityManager → `START … dat=content://com.s0und.s0undtv.provider/cache_files/update.apk typ=application/vnd.android.package-archive … cmp=com.android.packageinstaller/.PackageInstallerActivity from uid <uid de l'app>` |
| l'installation aboutit | écran système « Voulez-vous installer une mise à jour pour cette application ? Vos données ne seront pas perdues. » puis « Application installée. » |
| la version installée a changé | `dumpsys package com.s0und.s0undtv` → `versionCode=146 versionName=v1.5.10x-twouich2` |
| **ce sont nos octets** | `pm path` + `pull` de `base.apk` → SHA-256 égal à `dist/` **et** à celui servi par la release |
| l'app fonctionne encore | `bash patch/test-selftest.sh --in-app` → `SELFTEST 18/18` |

Le seul geste humain est le « INSTALLER » du système — Android l'impose, l'app ne peut pas
l'éviter. Choisir l'URL, télécharger, et lancer l'installeur : tout est fait par l'app.

### Revalidé le 16/09/2026 sur la chaîne v1.0.0 → v1.0.1 (147 → 148)

Même protocole, conditions plus dures cette fois : **installation neuve** de la v1.0.0 (octets de
la release GitHub, pas un `install -r` qui aurait conservé la session), puis self-update vers la
v1.0.1 publiée.

- **Sans session Twitch, pas de vérification de mise à jour.** Le helper n'est construit qu'une
  fois l'utilisateur connecté (callbacks d'auth/RESUME) ; sur une installation fraîche, la
  connexion du compte fait partie du test. Diagnostic posé par observation `/proc/net/tcp` :
  aucune connexion vers `raw.githubusercontent.com` tant que la session est absente.
- **Le canal Beta a de nouveau muetté l'updater — cause racine trouvée.** L'appareil neuvement
  installé est reparti en Beta (voir piège 1 ci-dessous) : le fetch part bien (connexion TCP
  observée), le JSON est servi correctement (200 sur `master/update.json`, entrée 148 stable), et
  pourtant aucun dialogue — l'entrée stable est filtrée avant la comparaison. Bascule **Stable**
  via Réglages → Updates, comme au 15/09.
- **Parcours complet observé en 147** : cold start → `UpdateActivity` ouverte seule (« New update
  available! — Version: v1.0.1 (148) ») → « Install update » → téléchargement depuis la release →
  installeur système → « Application installée » → `versionCode=148 versionName=v1.0.1`,
  **session Twitch conservée** (22 chaînes suivies), self-test 18/18.
- **La comparaison corrigée est prouvée** (piège 2) : en 147, l'app propose exactement 148 — ni
  147 en boucle, ni rien ; une fois en 148, plus aucune proposition.
- **État final propre** : le build instrumenté utilisé pour le diagnostic a été remplacé par la
  v1.0.1 publiée (`install -r`) ; SHA-256 du `base.apk` installé = `469db927…` = release = `dist/`.

### Validé sur le vrai téléviseur du foyer (Freebox Pop, Android 10) : 153 → 154 (v1.0.7), le 19/09/2026 — self-update **spontané**, le cas « mises à jour rapprochées »

Le self-update s'est déclenché **tout seul au foyer** (aucun pilotage ADB de l'installeur) — la
meilleure condition d'observation possible, et précisément le scénario Horizon 1 : 153 installée
la veille (11:48), annonce 154 levée le jour même (12:37), mise à jour à 15:10.

- **parcours complet dans le tampon logcat de l'appareil** : `UpdateActivity` ouverte par l'app
  (15:09:47) → « Install update » pressé à la télécommande (15:09:52) → **première tentative
  rebondie** (voir leçon) → second `InstallStart` (15:10:03) → `InstallStaging` →
  `PackageInstallerActivity` → `InstallInstalling` → `InstallSuccess` (15:10:19) →
  `lastUpdateTime=2026-09-19 15:10:12`, app relancée directement en lecture
  (`PlayerActivity` au focus, filtre actif dès 15:10:32 — playlists nettoyées en production) ;
- **octets installés identifiés sur l'appareil** : `sha256sum` du `base.apk` installé
  (`/data/app/com.s0und.s0undtv-…/base.apk`) = `6b54d7c0…` = livrable local Windows = octets
  servis CI/GitHub — troisième self-update consécutif dont les octets installés sont prouvés
  identiques à toute la chaîne ;
- **self-test 28/28 sur les octets installés** : la ligne du démarrage auto a été perdue dans la
  rotation du tampon main (borne basse 15:10:22 — le flux de lecture fait tourner le journal),
  remplacée par la sonde `app_process` **directement sur le `base.apk` installé**
  (`CLASSPATH=/data/app/…/base.apk app_process … SelfTest`) → `SELFTEST 28/28 verifications,
  flux filtre : 328 octets` à 15:18 — preuve équivalente et plus forte : ce qui tourne au
  quotidien embarque le self-test complet vert ;
- **anti-boucle vérifiée** : aucune réouverture d'`UpdateActivity` après l'installation
  (154 = dernière annoncée) ;
- **leçon du jour — le « silence » de l'installeur a deux formes** : (a) la **bénigne**, observée
  ici : le premier appui est routé vers `DeleteStagedFileOnResult` (nettoyage du fichier staged
  précédent), qui rend la main à l'`UpdateActivity` sans rien installer — l'utilisateur voit
  « rien ne se passe » et doit **re-presser** (~9 s plus tard ici) ; le second appui passe quand
  le processus installeur est **frais** (né au boot de 11:39, première session à 15:09) ;
  (b) la **pathologique** (la veille, 152→153) : un processus installeur **stalé** (en cache
  depuis la session de la veille au soir) avale **toutes** les tentatives — seul un reboot
  assainit. Diagnostic discriminant : l'âge du processus (`ps -A -o PID,STIME,NAME | grep
  packageinstaller`) face au moment du boot.

### Acceptation des pages légales embarquées (v1.0.8 → v1.0.9, émulateur, le 19/09/2026)

Procédure d'acceptation d'une page embarquée (À propos / politique), utile à toute future page :

1. **Ouvrir la page À propos** : `AboutActivity` n'est **pas exportée** (`am start` direct →
   SecurityException) — passer par l'UI : tap sur « Settings » du dock latéral (ou D-pad),
   puis grille du panneau → « About » (se fier à l'attribut `selected` du dump
   `uiautomator`, pas aux bounds : la grille ne défile pas toujours) → `DPAD_CENTER`/tap ;
2. **La WebView d'À propos** : le contenu se défile au `input swipe` ; les liens ne sont
   **pas focusables au D-pad** (limite upstream du WebView TV) — la navigation utile est
   **TAB + ENTER** (`input keyevent 61` puis `66`) : le focus traverse le DOM, ENTER active ;
3. **Marqueurs de vérification** dans le dump : page À propos (en-tête Twouich, liens
   « Mentions légales » / « Politique de confidentialité » rendus), page légale (« Éditeur »,
   « Nature du logiciel », « Garantie »), politique (« En bref », « La vérité sur
   l'héritage », « Caméra et microphone »). ATTENTION en v1.0.8 : l'entrée « Privacy policy »
   du menu ouvrait encore la page upstream — corrigé en v1.0.9 (repointage
   `PrivacyPolicyActivity` vers l'asset local, cf. journal).

### Probe SelfTest 28/28 sur le vrai téléviseur (Freebox Pop, app installée 153/v1.0.6), le 19/09/2026

Le self-test à **28 vérifications** (table de vérité de l'updater en bytecode Dalvik, bloc 8 de
`SelfTest.smali`) est validé sur le vrai téléviseur **sans toucher à l'app installée** — sonde
`app_process` sur un push ADB, aucun `install`, aucune session d'installation :

- **candidat** : `dist/Twouich_v1.0.7.apk` (SHA-256 `6b54d7c0…` — les octets exacts servis en
  release v1.0.7), poussé sur `/data/local/tmp/twouich-selftest.apk` ;
- **sonde** : `CLASSPATH=/data/local/tmp/twouich-selftest.apk app_process /system/bin
  com.twouich.adblock.SelfTest` — exit 0, stdout muet (protocole connu : la sonde log en
  logcat, tag `Twouich`) ; capture par `logcat -v time -T "<date locale de l'appareil>"
  > /data/local/tmp/probe-154.log` lancée sur l'appareil pendant la sonde, puis filtrage ;
- **verdict** : `SELFTEST 28/28 verifications, flux filtre : 328 octets` +
  `playlist nettoyee 623 -> 328 octets, segments pub retires : 3` (le flux e2e est inclus dans
  les 28) — les 10 vérifications updater (dont « annonce en retard » → silence et fail-loud
  `i()`) passent en bytecode réel sur Android 10/Freebox, comme sur l'émulateur au 12:07 ;
- **état d'après** : app intacte en `versionCode=153 versionName=v1.0.6`, 0 processus
  `app_process` résiduel, 0 session d'installation, trace de sonde supprimée — la sonde ne
  déclenche pas le self-update 154 en attente (celui-ci n'arrive qu'à l'exécution de l'app).

### Validé sur le vrai téléviseur du foyer (Freebox Pop, Android 10) : 152 → 153 (v1.0.6), le 19/09/2026

Premier self-update à installer des octets **reproductibles inter-plateformes** (recette canonisée v1.0.6) — et une leçon d'exploitation sur l'installeur :

- **l'appareil était déjà en 152** (installée la veille au soir) — le franchissement du verrou
  153 est donc observé depuis 152, mêmes mécaniques que depuis 151 ;
- parcours complet observé : `UpdateActivity` (« New update available! — Version: v1.0.6 /
  Version code: 153 ») → « Install update » → `S0undTV_AutoUpdateSrv` :
  `releases/download/v1.0.6/Twouich_v1.0.6.apk` (téléchargement en ~1,4 s) →
  `PackageInstallerActivity` (« Voulez-vous mettre à jour cette application ? Vos données
  actuelles ne seront pas perdues. ») → installation → `versionCode=153 versionName=v1.0.6`,
  app relancée directement sur `FireTVMainActivity` ;
- **octets installés = octets servis = livrable local, à l'octet près** : `sha256sum` calculé
  **sur l'appareil** sur le `base.apk` installé + `pull` ADB relu localement → SHA-256
  `dadbe5ae…` identique au build local Windows, donc aux octets servis par la CI et par GitHub
  Releases — première fois que le SHA identifie à la fois le fichier publié, la recette et ce
  qui est réellement installé sur le téléviseur du foyer ;
- self-test embarqué **6/6** via `app_process` sur les octets installés — attention, la sonde
  log en logcat (tag `Twouich`), son stdout est vide : lire le journal (cf. § 0.1) ;
- **session Twitch conservée**, vérifiée par navigation ADB le jour même : rails authentifiés
  peuplés (« Followed (5) », « Followed Channels (22) » — compte identique aux validations
  précédentes), grille des chaînes suivies rendue avec noms/titres live/catégories réels et
  navigable au D-pad (le scroll révèle des chaînes hors écran), retour accueil propre ;
- **piège du jour — l'installeur peut se figer en silence** : un processus
  `com.google.android.packageinstaller` resté en cache depuis la veille (la session 151→152 de
  21:20) **avale toute nouvelle session sans écran, sans erreur, sans crash** — l'activité
  naît et meurt en < 100 ms (« no activity for token »), aucun `INSTALL_FAILED`, l'app reprend
  le focus comme si l'utilisateur avait annulé. **Un reboot de la Freebox assainit** (l'écran
  système apparaît alors normalement). Diagnostics : `ps -A | grep packageinstaller` (processus
  ancien ≠ frais, `starttime`), fenêtre logcat autour du `START` de l'installeur. Seconde
  leçon : le **focus D-pad** de l'écran système n'est pas garanti (un OK peut ne rien faire) —
  le tap ADB sur INSTALLER (coordonnées lues dans le dump `uiautomator`) est le filet de secours.

### Validé sur le vrai téléviseur du foyer (Freebox Pop, Android 10) : 150 → 151 (v1.0.4, APK signé par la CI), le 16/09/2026

Même protocole, et cette fois l'APK proposé n'a jamais été construit localement : c'est le
**build signé par la CI** au push du tag `v1.0.4` (SHA-256 `dcaa1efd…`) — premier self-update
à installer les octets produits par la chaîne tag → build signé → publication automatique :

- parcours complet : `UpdateActivity` ouverte seule (« New update available! — Version: v1.0.4 /
  Version code: 151 ») → « Install update » → `AutoUpdateSrv` : `releases/download/v1.0.4/`
  → `PackageInstallerActivity` (« Voulez-vous mettre à jour cette application ? » — l'écran
  « INSTALLER » système a été piloté par ADB) → `versionCode=151 versionName=v1.0.4` ;
- **octets installés = octets servis** (`pm path` + `pull` → SHA-256 `dcaa1efd…` = livrable CI) ;
- **session Twitch conservée** (« Followed Channels (22) »), self-test **18/18**, relance sans
  dialogue. Transport ADB instable pendant la session (TV passée hors réseau un temps) : les
  étapes courtes avec reconnexion ont suffi.

### Validé sur le vrai téléviseur du foyer (Freebox Pop, Android 10) : 149 → 150, le 16/09/2026

Même protocole sur matériel réel cette fois, et double preuve au passage :

- **la Freebox était en 149 (v1.0.2), installation fraîche de la veille** — donc démarrée en canal
  **Stable** grâce au correctif `b.a = false` : c'est ce canal qui lui a fait voir l'entrée stable
  de `update.json`. Le correctif v1.0.2 est donc prouvé **en production** : aucune bascule manuelle
  de canal n'a eu lieu, et le dialogue est arrivé au cold start suivant la publication ;
- parcours complet observé : `UpdateActivity` ouverte seule (« New update available! — Version:
  v1.0.3 / Version code: 150 ») → « Install update » → `S0undTV_AutoUpdateSrv` :
  `releases/download/v1.0.3/Twouich_v1.0.3.apk` (URL exacte du tag) → `PackageInstallerActivity`
  → « Application installée » → `versionCode=150 versionName=v1.0.3` ;
- **octets installés = livrable** (`pm path` + `pull` → SHA-256 `147562df…` = `dist/` = octets
  servis, cf. `check-release.sh`) ;
- **session Twitch conservée** (22 chaînes suivies affichées à l'accueil), self-test **18/18**,
  relance sans dialogue (`FireTVMainActivity` reste au premier plan).

### Deux pièges qui font échouer ce test sans rien casser

1. **Le canal de mise à jour.** `helpers/a.b()` filtre par canal *avant* de regarder la version
   (`pref_update_channel`). Sur le canal **Beta**, seule une entrée `ReleaseType: 1` est acceptée :
   une `update.json` qui ne publie qu'une entrée **stable** n'y produit **aucun dialogue**, sans
   aucune erreur. L'appareil du test était en Beta (cas normal d'une installation héritée de
   S0undTV : même paquet, donc même préférences) — deux lancements muets, puis dialogue immédiat
   après passage en Stable (Réglages → General settings → *Update channel*). **Avant de suspecter la
   publication, lire ce canal.**

   **Cause racine (16/09).** Le socle upstream est un build **beta** : le flag `MainApp.b.a = true`
   est gravé dans le smali d'origine, et `MainApp.p()` écrit `pref_update_channel = "1"` au premier
   lancement quand la préférence est absente. **Toute installation neuve de Twouich démarre donc en
   canal Beta** — ce n'est pas un réglage hérité, c'est l'état d'usine du paquet. **Corrigé depuis la
   v1.0.2 (149)** : `patch.py` (étape 3b) force `b.a = false`, `p()` n'écrit plus rien et le défaut
   de lecture de `g()` (« 0 » = Stable) s'applique. Vérifié sur les octets installés : le `base.apk`
   relu de l'appareil décode `a:Z` sans initialisateur (false) là où l'upstream `beta_144` décode
   `a:Z = true` (contrôle négatif) ; garde-fou ajouté à `test_smali_branches.py`. Les installations
   existantes gardent leur canal sauvegardé — pour elles, publier aussi une entrée `ReleaseType: 1`
   ou basculer le canal à la main reste la solution.
2. **La comparaison de version est fausse en amont.** `b()` compare la version publiée à un plancher
   figé (144), jamais à la version installée : l'app propose d'installer… la version qu'elle exécute
   déjà. Une fois en 146, elle redemande 146 au démarrage suivant. C'est un défaut d'origine ; il
   n'empêche pas le parcours ci-dessus, mais il rend le résultat bruyant. (**Corrigé depuis la
   v1.0.0** : la comparaison lit la version installée via `PackageManager.getPackageInfo()`.)

### Le piège d'ordre, à ne pas inverser

`update.json` doit être poussé **après** la création de la release : l'URL est construite avec le
`VersionName` publié, donc un `update.json` en avance annonce une mise à jour pour un asset qui
n'existe pas (404 silencieux côté app). `bash patch/check-release.sh` vérifie l'ensemble après coup,
y compris les **octets réellement servis** comparés au livrable local.

---

## 1. Brancher la machine

**Android TV / Fire TV** — activer le débogage : *Paramètres → À propos → Réseau* (ou taper 7 fois sur
*Build*), puis :

```bash
adb connect <ip-de-la-tv>:5555     # l'IP est dans Paramètres → Réseau
adb devices                        # doit afficher une ligne « ... device »
```

**BlueStacks** — *Paramètres → Avancé → Android Debug Bridge* (activer), le port est indiqué juste à
côté :

```bash
adb connect 127.0.0.1:5555
```

### ⚠️ Un seul binaire `adb`, et le bon transport

BlueStacks expose **deux** transports pour la même machine : `emulator-5554` et `127.0.0.1:5555`.
Le second accepte `push`/`install` mais ne rend **aucun verdict** `app_process` — le script
concluait « aucun verdict SELFTEST » alors que rien n'avait été testé. `patch/test-selftest.sh`
choisit maintenant `emulator-*` par défaut (et affiche les transports quand il y en a plusieurs).
En cas de doute : `--serial emulator-5554`.

### ⚠️ Un seul binaire `adb` à la fois

C'est le piège n°1, rencontré en vrai : BlueStacks embarque `HD-Adb.exe` (**1.0.36**) et les
platform-tools / scrcpy embarquent un **1.0.41**. Si les deux sont utilisés, chaque appel tue le
serveur de l'autre → le serveur redémarre **au milieu** d'une commande et `adb` répond
`error: closed`. L'installation reste alors à moitié faite.

Le script choisit un binaire et s'y tient. Pour le forcer explicitement :

```bash
ADB="/c/Users/<vous>/AppData/Local/ScrcpyGUI/scrcpy-bin/adb.exe" \
  bash patch/test-device.sh --install-only
adb kill-server          # une seule fois, puis on ne mélange plus les deux clients
```

`bash patch/test-device.sh --list` affiche l'appareil retenu, l'état brut, et le `adb` utilisé.

---

## 2. Lancer le test

```bash
cd /d/Codex/Twouich

bash patch/test-device.sh --list                        # qui est branché ?
bash patch/test-device.sh --install-only                # installe sans capturer
bash patch/test-device.sh --fresh                       # désinstalle d'abord (signature différente)
bash patch/test-device.sh --serial emulator-5554        # plusieurs appareils : choisir
bash patch/test-device.sh --connect 192.168.1.42:5555   # Android TV distante
bash patch/test-device.sh --no-install --duration 420   # capture seule, 7 min, sans Ctrl+C
```

| Option | Effet |
|---|---|
| `--fresh` | désinstalle avant (obligatoire la 1ʳᵉ fois : notre clé de signature ≠ celle de S0und) |
| `--install-only` | installe, vérifie la version, s'arrête |
| `--no-install` | capture seulement |
| `--serial <serial>` | appareil visé (nécessaire si plusieurs) |
| `--connect <host:port>` | connexion réseau (TV ou émulateur) |
| `--duration <s>` | capture minutée au lieu d'un `Ctrl+C` |
| `--analyze <fichier>` | analyse une capture déjà faite |
| `--apk <chemin>` | tester un autre APK |

Le script : installe `dist/Twouich_v1.0.0.apk`, vérifie que la version installée est bien
`v1.0.0` (et **avertit si ce n'est pas notre build**), vide le tampon `logcat`, puis
capture avec le filtre :

```
Twouich:V ExoPlayerImpl:W ExoPlayerImplInternal:W HlsMediaSource:W Loader:W MediaCodec:W MediaDrm:W AndroidRuntime:E *:S
```

Ensuite : **lancer un stream sur la TV**, laisser passer **au moins une coupure publicitaire
complète**, noter l'heure de la coupure, puis `Ctrl+C`.

Si `adb install` échoue en flux direct, le script bascule tout seul sur `push` + `pm install`
(même résultat, transport différent — c'est ce repli qui a fait passer l'installation sur BlueStacks).

### Observation en direct longue — capture détachée, navigation D-pad, sentinelle comprise

`test-device.sh` capture en **synchrone** (`Ctrl+C` ou `--duration`) : la session tient le terminal
et suppose que quelqu'un lance le direct à la main. Pour une **observation longue sans terminal
occupé** — typiquement prouver sur un même trafic réel que le filtre retire les pods *et* que la
sentinelle « marqueur pub inconnu » reste muette —, la séquence suivante fait tout en commandes
indépendantes. Recette éprouvée le 18/09/2026 (~13 min de direct : 459 nettoyages, 2539 segments
retirés, 0 alerte sentinelle — consigné en `AUDIT.md` § 4.4). Pour maximiser les chances de voir
un pod, choisir une chaîne à forte charge publicitaire (méthode radar de `AUDIT.md` § 4.4 —
désormais une commande : `python patch/radar_ads.py`, avec rejeu anti-fuite intégré).

> **Automatisation** : `bash patch/test-live.sh --duration 600` exécute les étapes 1, 2, 4 et 5
> (état, capture détachée surveillée avec relance en append, arrêt + verdict) — il ne reste à la main
> que l'étape 3 (la navigation) et l'observation. Les pièges ci-dessous expliquent *pourquoi* le
> script fait chaque chose. Options : `--serial`, `--connect`, `--list`, `--no-launch`, `--no-quit`,
> `--analyze <fichier>` (verdict seul).
>
> **Ordre des étapes à l'usage** (leçon du 19/09, Freebox) : lancer le script **après** la
> navigation, pas avant — la fenêtre de 10 min s'est écoulée pendant que le focus D-pad de la
> grille « Followed Channels » était géré (dumps `uiautomator` en retard d'un cran sur le focus
> réel : naviguer cran par cran **avec dump isolé entre chaque**, viser l'étiquette, puis ouvrir).
> `--no-launch` est fait pour ça : capture fraîche pendant l'ouverture du direct, observation
> complète ensuite. Sur la Freebox, les boutons de la fiche chaîne se pressent au **D-pad**
> (UP → focus sur LIVE → OK) — l'injection tactile (`input tap`) y est sans effet.

**1. État** — un seul binaire `adb` pour toute la session (piège § 1 : BlueStacks → `HD-Adb.exe`),
transport `emulator-*` (le TCP ne rend pas les verdicts `app_process`), et la version installée :

```bash
export MSYS_NO_PATHCONV=1
ADB="/c/Program Files/BlueStacks_nxt/HD-Adb.exe"
"$ADB" connect 127.0.0.1:5555 && "$ADB" devices
"$ADB" -s emulator-5554 shell dumpsys package com.s0und.s0undtv | grep -E 'versionCode|versionName'
```

**2. Capture détachée** — même filtre que `test-device.sh`, plus `-v time` pour les horodatages.
Le `nohup … &` se lance **dans sa propre commande** : un `&` en fin de commande synchrone en bloque
la clôture, et il n'y a pas de mode arrière-plan d'agent. Rediriger stderr **dans le fichier** :
une ligne `adb: error: closed` explique une capture morte, au lieu de la laisser deviner.

```bash
L=work/device-test/logcat-live-$(date +%d-%m).txt
nohup "$ADB" -s emulator-5554 logcat -v time \
    Twouich:V ExoPlayerImpl:W ExoPlayerImplInternal:W HlsMediaSource:W Loader:W \
    MediaCodec:W MediaDrm:W AndroidRuntime:E *:S >> "$L" 2>&1 &
sleep 3 && wc -l "$L"        # la capture vit-elle ?
```

⚠️ **Une capture logcat peut mourir sans prévenir** (le 18/09 : morte à 15:37, la moitié de la
session perdue avant le constat). Vérifier à chaque fenêtre d'observation que `$L` grossit ; s'il
est figé, **relancer la même commande en append (`>>`)** — jamais un fichier neuf : le verdict doit
couvrir d'un seul tenant les deux fenêtres.

**3. Ouvrir un direct à la télécommande** — l'UI TV se pilote au **D-pad** : les libellés ne
répondent pas à `input tap`, seul compte l'élément **focusé**. Boucle : dumper, repérer le focus et
la cible, naviguer, re-dumper, valider. (Les deep-links `twitch://` n'existent pas dans l'app.)

```bash
"$ADB" -s emulator-5554 shell monkey -p com.s0und.s0undtv -c android.intent.category.LAUNCHER 1
sleep 6
"$ADB" -s emulator-5554 shell uiautomator dump /sdcard/ui.xml
"$ADB" -s emulator-5554 pull /sdcard/ui.xml work/device-test/ui-live.xml
grep -o '<node[^>]*focused="true"[^>]*>' work/device-test/ui-live.xml
grep -c 'Live Stream History' work/device-test/ui-live.xml
"$ADB" -s emulator-5554 shell input keyevent 23     # DPAD_CENTER sur l'entrée focusée
```

Naviguer (19 haut, 20 bas, 21 gauche, 22 droite, 23 valider) jusqu'à la carte de la chaîne, en
vérifiant **à chaque dump** que la carte est bien dans le conteneur focusé avant d'appuyer sur 23.

> Cette boucle est outillée (§ 8) : `bash patch/device-ui.sh nav "<texte de la carte>"` relit le focus
> après **chaque** déplacement (donc sans le retard d'un cran du dump) puis `bash patch/device-ui.sh
> press` active l'élément focalisé. Sur la Freebox **et** sur le téléphone, c'est le seul canal qui
> passe — vérifier au `probe` plutôt que de le supposer (§ 8.1).
Le direct est lancé quand :

```bash
"$ADB" -s emulator-5554 shell dumpsys activity activities | grep mResumedActivity   # → PlayerActivity
sleep 10 && grep -c 'playlist nettoyee' "$L"        # les nettoyages affluent
```

**4. Observer** — des fenêtres de quelques minutes (`sleep 240`), en re-vérifiant que `$L` grossit
(piège du point 2). La checklist de § 4 s'applique sur l'écran pendant ce temps.

**5. Arrêter et rendre le verdict** — tuer **le client logcat, pas le serveur adb** (tuer le
serveur casse tout adb pour la suite, piège § 1), sortir du direct, puis analyser :

```bash
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.CommandLine -like '*logcat*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }"
"$ADB" -s emulator-5554 shell input keyevent 4      # BACK : retour à l'accueil
bash patch/analyze_device_log.sh "$L"
```

Les compteurs de § 3 et le verdict de § 5 s'appliquent tels quels, plus deux lignes propres à la
sentinelle :

| Ligne du verdict | Lecture |
|---|---|
| `marqueurs pub inconnus : 0` | **la sentinelle est muette sur le vrai trafic** — l'objectif du test est atteint |
| `marqueurs pub inconnus : n > 0` | le verdict 🚨 s'affiche **en tête** avec la ligne HLS brute : ajouter la règle + un cas figé au miroir (`test_sanitizer.py`), cf. `AUDIT.md` § 4.2 |
| `Source error` ×n | attendu **en fin de pod uniquement**, chaque occurrence suivie de `Caused by: m3.l$d` = `PlaylistResetException` (resync de 2–4 s, `AUDIT.md` § 4.4) — toute autre cause passe en § 7 |
| `replis proxy → direct` | 0 attendu (proxy désactivé par défaut) |

---

## 3. Ce que la capture doit montrer

L'app trace elle-même chaque playlist nettoyée :

```
09-15 09:40:12.345 I/Twouich ( 3120): playlist nettoyee 8412 -> 7103 octets, segments pub retires : 3
```

| Signal | Signification |
|---|---|
| `playlist nettoyee …` | le filtre est bien dans le chemin du lecteur (toutes les playlists passent par lui) |
| `segments pub retires : 0` | playlist de contenu normal — **c'est le cas attendu la plupart du temps** |
| `segments pub retires : n > 0` | **coupure publicitaire détectée et retirée** au moment de la coupure |
| `proxy indisponible : repli sur la requete directe` | le mode proxy (si activé) a échoué et le repli a fonctionné |

---

## 4. Checklist pendant la coupure publicitaire

À cocher au moment exact où la coupure devrait survenir :

- [ ] **Aucune pub n'apparaît** (ni vidéo publicitaire, ni bandeau « Publicité »).
- [ ] **Aucun écran noir prolongé** (< 2 s), pas de gel d'image.
- [ ] **Aucun compteur** « l'annonce se termine dans … ».
- [ ] le **son reste synchronisé** avec l'image juste après la coupure.
- [ ] la lecture **reprend le direct** (pas de retour en arrière, pas de saut dans la VOD).
- [ ] dans la capture : une ligne `segments pub retires : n` avec `n > 0` à l'heure de la coupure.
- [ ] dans la capture : aucune erreur `Discontinuity`, `BehindLiveWindow`, `ParserException`.

---

## 5. Lire le verdict

```bash
bash patch/analyze_device_log.sh work/device-test/logcat-<date>.txt
```

Le script affiche le nombre de playlists nettoyées, le total de segments publicitaires retirés, les
horodatages des retraits, les replis proxy et les erreurs de lecture, puis conclut :

| Conclusion | Suite à donner |
|---|---|
| ✅ **ANTI-PUB FONCTIONNEL** | rien à faire ; archiver la capture |
| ✅ **CONTENU TRAVERSÉ SANS POD** (0 retrait, 0 erreur, sentinelle muette) | cas bénin : le contenu passe par le filtre et aucune pub n'a été servie pendant la capture — pour voir des retraits, cibler une chaîne à forte charge (radar multi-chaînes, `AUDIT.md` § 4.4) |
| ⚠️ **FILTRE ACTIF, RIEN RETIRÉ + erreurs de lecture** | cas suspect : commencer par les erreurs (§ 7) ; si elles révèlent un format non reconnu, suivre `AUDIT.md` § 4.2 (constante `stitched-ad` de `PlaylistSanitizer`) — la sentinelle (🚨) reste le premier signal d'un format renommé |
| ⚠️ **pubs retirées mais erreurs de lecture** | garder la capture : les erreurs indiquent quel tag doit être conservé/ajouté |
| ❓ **aucune playlist nettoyée** | l'APK installé n'est pas le nôtre, ou la capture a démarré avant le lancement du stream |

---

## 6. Dépannage

| Symptôme | Cause | Solution |
|---|---|---|
| `error: closed` sur presque toutes les commandes | deux `adb` en conflit, ou `adbd` bloqué après un transfert interrompu | `ADB=<un seul binaire>` ; `adb kill-server` ; **ne jamais** tuer `adb install` par un `timeout` court (le script n'en met aucun) |
| `device` listé mais `offline` / `unauthorized` | invite non acceptée, ou transport fantôme | accepter le message sur l'écran de la TV ; sinon `adb disconnect` puis `adb connect` |
| appareil listé **deux fois** | transport TCP + transport console | `--serial` pour en choisir un, `adb disconnect` l'autre |
| `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | l'app officielle S0undTV est installée | `--fresh` (les deux signatures ne cohabitent pas) |
| `INSTALL_FAILED_VERSION_DOWNGRADE` | version installée plus récente | `--fresh` |
| rien dans la capture | app pas encore lancée, ou mauvaise build | `adb logcat -c` puis relancer la lecture ; vérifier `versionName` |
| `push`/`pm install` introuvable alors que l'APK existe | Git Bash réécrit `/data/local/tmp/…` en chemin Windows | le script force déjà `MSYS_NO_PATHCONV=1` ; à la main : `MSYS_NO_PATHCONV=1 adb push … /data/local/tmp/…` |
| émulateur figé après un échec | `adbd` de BlueStacks bloqué | *Paramètres → Avancé → ADB* hors/marche, ou redémarrer l'instance |

---

## 7. Ce qu'il faut me renvoyer pour que je corrige

1. la sortie complète de `analyze_device_log.sh` ;
2. la capture brute (`work/device-test/logcat-*.txt`) ou au moins :
   ```bash
   grep -E 'Twouich|Discontinuity|Exception|BehindLiveWindow' work/device-test/logcat-*.txt | head -40
   ```
3. l'heure approximative de la coupure, pour recouper avec les horodatages.

Avec ces trois éléments, un ajustement des règles se fait sans appareil : le miroir Python des règles
(`patch/tests/test_sanitizer.py`) permet de rejouer une playlist fautive en local avant de reconstruire
l'APK.

---

## 8. Piloter l'interface à la main — focus et D-pad (`patch/device-ui.sh`)

*Comment ouvrir un direct, se déplacer dans l'interface et vérifier qu'une action a réellement agi,
quand l'injection tactile ne passe pas. Mesuré le 21/09/2026 sur trois appareils.*

L'étape 3 du § 2 se fait aujourd'hui à la main, par une boucle `dump → repérer le focus → naviguer →
re-dumper`, dont le principal défaut est connu : `uiautomator` a **un cran de retard** sur le focus
réel. `patch/device-ui.sh` exécute cette boucle, mais en relisant le focus **après chaque
déplacement** — ce qui supprime le piège au lieu de le documenter.

### 8.0 En une minute

```bash
export ADB="/d/android-sdk/platform-tools/adb.exe"     # un seul binaire adb (règle du § 1)
bash patch/device-ui.sh --list                         # appareils utilisables
bash patch/device-ui.sh probe                          # quel canal agit sur CET appareil ?
bash patch/device-ui.sh launch                         # lance l'app et relève le focus
bash patch/device-ui.sh nav "<texte du bouton>" && bash patch/device-ui.sh press
bash patch/device-ui.sh step "<écran avant>" "nav:<cible>+press" "<écran après>"   # § 8.7
```

Si `probe` conclut `tactile=oui` (le cas de l'émulateur), `bash patch/device-ui.sh tap <x> <y>` suffit
et le D-pad ne sert plus que pour les éléments hors champ. S'il conclut `tactile=non touches=oui`
(le cas de la Freebox et du téléphone), **tout passe par `nav` + `press`**.

### 8.1 Le fait à connaître : le canal dépend de l'appareil, pas d'Android

Un même `adb shell input tap` **agit** sur un appareil et **ne fait rien** sur un autre :

| Appareil | `input tap` | `input keyevent` |
|---|---|---|
| Freebox Pop (Android 10) — boutons de la fiche chaîne (19/09) | **absorbé** | agit |
| Téléphone HyperOS / MIUI | **absorbé** | agit |
| Émulateur BlueStacks (21/09) | **agit** | agit |

Sur les appareils où il est absorbé, l'événement est pourtant bien injecté côté système :

```
D InputManager: injectMotionEvent: … {action=ACTION_DOWN, x[0]=318.0, y[0]=2530.0, …}
W MIUIInput: Input motion event injection from package: null action ACTION_DOWN
```

…mais l'application n'y réagit **jamais** : ni sur un bouton, ni au milieu de l'écran, ni même sur
`BACK`. Les touches, elles, arrivent au `ViewRootImpl` de l'application :

```
I MIUIInput: [KeyEvent] ViewRootImpl windowName '…LoginActivity',
             KeyEvent { action=ACTION_DOWN, keyCode=KEYCODE_DPAD_DOWN, … }
```

**Règle qui en découle** : ne jamais supposer le canal. Le mesurer — c'est le rôle de `probe`, et
c'est ce qui évite de conclure à tort « l'app est figée » ou « l'écran est inatteignable » (le piège
qui a coûté une session entière sur le projet voisin, cf. § 8.6).

### 8.2 La méthode : le focus, puis le D-pad

`uiautomator dump` produit l'arbre d'accessibilité — la même vision qu'un outil d'assistance. Il dit
qui a le focus, qui est cliquable, et où (`bounds`). C'est la source de vérité de toute la méthode :

```bash
bash patch/device-ui.sh focus          # élément focalisé + classe + bornes
bash patch/device-ui.sh texts          # tous les textes de l'écran
export UI_KEY=20                       # 20 bas, 19 haut, 21 gauche, 22 droite (défaut : 20)
bash patch/device-ui.sh nav "Suivre"   # déplace le focus jusqu'à cet élément
bash patch/device-ui.sh press          # DPAD_CENTER (23) — l'équivalent du clic
```

| Touche | Code | Usage |
|---|---|---|
| DPAD_UP / DOWN / LEFT / RIGHT | 19 / 20 / 21 / 22 | déplacer le focus |
| DPAD_CENTER | 23 | activer (équivalent du clic) |
| ENTER | 66 | activer, variante clavier |
| BACK / HOME | 4 / 3 | navigation système (`bash patch/device-ui.sh key 4`) |

Quand la grille se déplace dans un autre sens que le D-pad par défaut, `UI_KEY=22` (droite) est
souvent le bon axe : c'est un paramètre, pas une reconstruction à faire dans le terminal.

### 8.3 Vérifier qu'une action a réellement agi

Aucune des deux méthodes ci-dessous n'est fiable seule ; ensemble, elles le sont.

- **Signature d'écran textuelle (préférée)** : relever l'ensemble des textes de l'arbre, agir,
  relever de nouveau, comparer. C'est ce que fait `tap`, et ce que fait `probe` pour trancher entre
  les deux canaux. Objectif, portable, indépendant du rendu.
- **Capture d'écran (secondaire)** : utile à l'œil humain, à **ne pas** utiliser comme signal de test.
  Sur BlueStacks, `screencap` a écrit un fichier **vide sur l'appareil lui-même** (0 octet — ce n'est
  pas la copie qui échoue) ; un hash vide (`d41d8cd98f…` est le md5 de la chaîne vide) ressemble alors
  exactement à « l'écran n'a pas changé ».

C'est ce qui distingue « l'action n'a pas été prise en compte » de « l'action a été prise en compte
mais a échoué » — deux diagnostics opposés qu'un même silence recouvre.

### 8.4 Les pièges, chacun vérifié à ses dépens

| Piège | Symptôme | Correctif |
|---|---|---|
| **MSYS réécrit les chemins** | `uiautomator dump` réussit mais l'arbre est **vide** : `/sdcard/…` devient `C:/Program Files/Git/sdcard/…` | `MSYS_NO_PATHCONV=1` (déjà forcé par le script, comme `test-device.sh`) |
| **MSYS ne convertit pas les variables d'environnement** | un chemin MSYS passé à un outil natif Windows n'est pas résolu (rencontré en écrivant le test hors appareil) | le convertir explicitement (`cygpath -w`), ou `cd` puis passer un nom simple |
| **Bornes séparées par des virgules** | coordonnées absurdes, sans message d'erreur : `[174,60][237,120]` donnait `(60,120)` | lire `^\[x1,y1\]\[x2,y2\]$` — et non `cut -dx`, qui vaut pour `wm size` (`1220x2712`) |
| **Une seule cible testée** | faux négatif : `tactile=non` alors que le tap marche, parce que le premier élément cliquable était inerte | essayer 2-3 cibles distinctes avant de conclure (`probe` le fait) |
| **Taper le centre de l'écran** | « aucun effet » sur tout écran dont le milieu est vide | viser le centre d'un élément **cliquable** de l'arbre |
| **Conclure « l'app est figée »** | `BACK` sans effet + aucun tap pris en compte | c'est le tactile qui est absorbé : les touches passent |
| **Croire qu'un `focused="true"` suffit** | l'activation par `23` peut être ignorée si l'élément est recouvert | vérifier le changement d'écran (§ 8.3) après chaque activation |
| **Un dump par anticipation** | on navigue « un cran de trop » : l'arbre est en retard sur le focus réel | relire le focus **après** chaque déplacement (ce que fait `nav`) |

### 8.5 Transposer à un nouvel appareil

1. `bash patch/device-ui.sh probe` sur un écran contenant au moins un bouton.
2. `tactile=oui touches=oui` → tap direct, D-pad en secours.
3. `tactile=non touches=oui` → **D-pad uniquement** : `nav` puis `press`.
4. `tactile=non touches=non` → l'appareil n'accepte aucune injection : lire l'état par `texts`, et
   confier l'action à un humain.
5. `?` → écran sans élément cliquable **ou** sans élément focusable : refaire le probe sur un écran
   plus riche avant de conclure. C'est le cas fréquent après un `tap` qui a ouvert une WebView
   (l'écran de connexion, par exemple) : `probe` n'y a plus de focus à déplacer.

### 8.6 Provenance, et ce que la méthode a coûté

La recette vient du projet voisin (`TwitchDroid`), où une session avait conclu que l'écran de
connexion Google était **inatteignable** — parce qu'elle essayait de cliquer, sur un appareil qui
absorbait le tactile. Le bouton était vivant ; il a suffi de `nav` + `press` pour l'activer et pour
faire apparaître la vraie réponse du service, qui n'avait rien à voir avec le bouton.

**Le piège à retenir** : confondre « je n'ai pas pu cliquer » et « le bouton ne fait rien » mène à de
fausses conclusions sur le code — ici, à accuser le filtre anti-pub ou l'updater d'un défaut qui
n'existait pas. C'est pour cette raison que l'outil *mesure* le canal au lieu de le supposer.

**Acceptation du 21/09/2026 (BlueStacks, `127.0.0.1:5555`)** : `probe` → `tactile=oui`, `launch`,
`focus`, `texts`, `nav` et `find` ont rendu l'état réel de l'écran. L'app Twouich n'était pas
installée sur cette instance ; l'acceptation a été faite sur l'écran d'une autre application patchée,
ce qui suffit pour juger le canal et la navigation (c'est l'appareil qui décide, pas l'app).

**Vérification hors appareil** — `bash patch/tests/test_device_ui.sh` (61 vérifications) : un double
d'`adb` rejoue l'accueil TV puis le lecteur, et contrôle les *décisions* de l'outil — que `probe`
distingue bien les deux canaux, que `nav` échoue proprement sur une cible inatteignable, que les
bornes sont lues à la virgule près, et qu'une capture vide est attribuée à l'appareil et non à la
copie. Les deux causes d'échec ci-dessus (§ 8.4, lignes 1 et 2) ont été trouvées par ce test, pas par
une lecture attentive — et il a aussi attrapé une **faute d'implémentation** que la lecture ne voyait
pas : un `local IFS=+` posé pour découper les actions restait actif dans `cmd_nav`, où il transformait
le `for i in $(seq 1 $UI_MAX)` en une seule itération (la nouvelle ligne n'étant plus un séparateur),
donc en un `nav` qui échouait après un unique déplacement.

### 8.7 Scripter une recette : `step`, une vérification par ligne

`step` réunit les trois éléments d'une vérification — **l'écran attendu, l'action, l'écran obtenu** —
dans une seule commande, et sort en 1 si l'un des trois ne colle pas. C'est ce qui permet de scripter
une recette de bout en bout dans un bête fichier bash.

```bash
bash patch/device-ui.sh step "<texte présent au départ>" "<actions>" "<texte attendu après>"
```

Les actions sont des verbes séparés par `+`, chacun `verbe[:argument]` :

| Action | Effet |
|---|---|
| `nav:<texte>` | amener le focus sur cet élément (relu après chaque déplacement) |
| `press` | activer l'élément focalisé (DPAD_CENTER) |
| `key:<code>` | touche brute — `4` = BACK, `61` = TAB, `66` = ENTER |
| `tap:<x>,<y>` | tap par coordonnées (repli D-pad signalé s'il est absorbé) |
| `launch` | lancer l'app |
| `wait:<s>` | attendre avant la suite (décimales acceptées) |

Exemple **réellement joué** le 21/09/2026 sur l'émulateur (Clips → accueil, au BACK) :

```
$ bash patch/device-ui.sh step "Les commentaires sont ici" "key:4" "Accueil"
▶ « Les commentaires sont ici » → [key:4] → « Accueil »
  avant  : ✓ « Les commentaires sont ici » présent
  action : key:4 → ✓ touche 4 envoyée
  delta  : +[Accueil, Activité, Bytell2, CabriDIY] −[Ajouter un commentaire, Les commentaires sont ici !, …]
  après  : ✓ « Accueil » présent
✓ ÉTAPE CONFORME (10 s)
```

La ligne `delta` n'est pas décorative : elle donne la **preuve** du changement (les textes gagnés et
perdus), là où deux captures se contenteraient de dire « ça a l'air différent ». C'est la même
exigence que la signature d'écran du § 8.3, appliquée à l'étape entière.

Une recette, dès lors, s'écrit ainsi — chaque étape repart de l'état où la précédente a laissé
l'appareil, et `set -e` interrompt au premier écart :

```bash
#!/bin/bash
set -e
export ADB=/chemin/vers/adb
D="bash patch/device-ui.sh"
$D launch
$D step "Accueil"            "nav:<carte d'une chaîne>+press" "<texte du lecteur>"
$D step "<texte du lecteur>" "nav:<menu>+press+wait:3"        "À propos"
$D step "À propos"           "key:61+key:66"                 "En bref"     # TAB puis ENTER : les liens d'une WebView ne sont pas focusables au D-pad
$D step "En bref"            "key:4"                         "À propos"
```

Trois précautions, chacune payée :

- **Le libellé attendu doit être absent au départ.** Sinon l'étape passerait sans rien prouver ;
  `step` le signale (`⚠ la sortie attendue est DÉJÀ présente avant l'action`) et le dit au lieu de
  rendre un succès trompeur. Mesuré : la pastille du compteur anti-pub reste dans l'arbre sur
  plusieurs écrans, elle ne peut donc pas servir à prouver « on a ouvert le lecteur ».
- **`nav` ne cible qu'un texte.** Un élément sans `text` — le conteneur de rangée d'une grille
  Leanback, un `FrameLayout` de barre d'onglets — est **injoignable par nom** : le cible par
  `clickables` + `tap`, ou par une touche. Sur l'accueil d'une vraie app, le seul nœud focalisable
  était un `FrameLayout` sans texte.
- **Aucun élément focalisé au départ → mauvais axe, ou écran qui ne focalise rien.** `nav` le
  diagnostique au bout de **trois** crans ; sans cela il brûlait 30 crans de D-pad pendant 87 s sur un
  direct en cours avant de rendre le même verdict, sans la cause. Essayer `UI_KEY=19|21|22` : une
  grille se parcourt dans l'axe de ses rangées, pas toujours verticalement.

### 8.8 Lire l'arbre des vues réellement appliqué — `dumpsys activity top`

`uiautomator dump` ne dit pas tout : il **omet les vues `GONE`** et il arrive qu'il
escamote une vue entièrement recouverte par une voisine. Deux conséquences vécues le
21/09/2026 : un chat masqué et un chat **absent** se ressemblaient trait pour trait, et
un bouton déclaré mort (introuvable dans le dump) était en fait présent, simplement
sous le bouton d'incrustation. L'arbre du framework, lui, ne cache rien :

```bash
ADB=/chemin/vers/adb ; S=127.0.0.1:5555
"$ADB" -s $S shell "dumpsys activity top" > etat.txt
grep -E "app:id/(ExoPlayer|ChatRecycleView|SendMessageWindow|twouich_phone_chat|twouich_phone_pip)\}" etat.txt
```

Lecture d'une ligne :

```
com.s0und.s0undtv.chat.ChatRecyclerView{b99dd8 VFED..... ........ 0,405-720,1280 #7f0b0023 app:id/ChatRecycleView}
                                          └─ drapeaux                    └─ bornes        └─ identifiant résolu
```

- **drapeaux** : `V` visible, `I` invisible, `G` *gone* (`GFED.....` = `GONE`) ;
- **bornes** : `x1,y1-x2,y2` — c'est la géométrie **après** disposition, donc la preuve
  qu'une disposition a réellement été appliquée (et pas seulement appelée) ;
- **identifiant** : `#7f0b0023 app:id/ChatRecycleView` — le nom résolu, celui que
  `Resources.getIdentifier` doit trouver (un nom nu qui n'apparaît pas ici n'existera pas
  au moment de l'exécution).

**Ce que l'outil a tranché, et qu'aucun `uiautomator dump` ne pouvait dire** : un repli du
chat qui donnait l'écran entier à la vidéo (`[0,0][720,1280]`) au lieu de garder le 16:9,
un chat `GONE` là où la disposition empilée le voulait visible — donc une disposition
téléphone qui ne s'appliquait plus du tout. La cause était un garde à polarité inversée
(`if-nez` au lieu de `if-eqz`), silencieux par construction.

### 8.9 Recette d'acceptation du chat repliable (téléphone ou émulateur < 600 dp)

Cinq vérifications, chacune avec sa preuve dans l'arbre des vues (§ 8.8) : l'état empilé,
le repli, le dépli, la reprise d'activité et l'incrustation.

```bash
S=127.0.0.1:5555                       # ou l'IP du téléphone
"$ADB" -s $S install -r dist/Twouich_v1.0.9.apk
"$ADB" -s $S shell "am start -a android.intent.action.VIEW -d 's0undtv://stream/ddg'"
sleep 12 ; "$ADB" -s $S shell "dumpsys activity top" > e1.txt      # 1. empilé
"$ADB" -s $S shell "input tap 588 48"
sleep 3  ; "$ADB" -s $S shell "dumpsys activity top" > e2.txt      # 2. replié
"$ADB" -s $S shell "input tap 588 48"
sleep 3  ; "$ADB" -s $S shell "dumpsys activity top" > e3.txt      # 3. déplié
"$ADB" -s $S shell "input keyevent 3" ; sleep 3
"$ADB" -s $S shell "am start -a android.intent.action.VIEW -d 's0undtv://stream/ddg'"
sleep 8  ; "$ADB" -s $S shell "dumpsys activity top" > e4.txt      # 4. reprise
```

Mesures obtenues sur l'émulateur (720×1280, 240 dpi = 480 dp), le 21/09/2026 :

| Étape | Vidéo | Chat | Saisie | Bouton chat |
|---|---|---|---|---|
| 1. empilé | `[0,0][720,405]` | `0,405-720,1280` **V** | `0,1168-720,1280` **V** | `552,12-624,84` **V** |
| 2. replié | `[0,0][720,1280]` | `0,405-720,1280` **G** | `0,1168-720,1280` **G** | `552,12-624,84` **V** |
| 3. déplié | `[0,0][720,405]` | `0,405-720,1280` **V** | `0,1168-720,1280` **V** | `552,12-624,84` **V** |
| 4. reprise (replié au départ) | `[0,0][720,1280]` | **G** | **G** | `552,12-624,84` **V** |

Trois invariants à vérifier sur chaque ligne : **le bouton ne bouge jamais** (mêmes bornes
dans les quatre états — il doit rester hors du rectangle `636,12-708,84` du bouton
d'incrustation), **la vidéo prend l'écran au repli** (`720,1280`, pas un 16:9 qui laisse un
tiers noir), et **la reprise ne ressuscite pas le chat** replié.

Cinquième vérification, l'incrustation : `input tap 672 48` (bouton PiP) puis
`dumpsys activity activities | grep mode=pinned` — la fenêtre doit être en 16:9
(`mBounds=Rect(403, 1091 - 696, 1256)` sur cet écran, soit 293×165) et `logcat` doit porter
`picture-in-picture : video plein cadre, chat et saisie masques`, puis, au retour,
`picture-in-picture : disposition empilee restauree`.
