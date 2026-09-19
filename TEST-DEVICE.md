# Procédure de test anti-pub sur un appareil réel

Objectif : prouver, avec les traces de l'appareil lui-même, que les plages publicitaires sont
retirées **pendant** une coupure réelle — et pas seulement que l'app « a l'air de marcher ».

Trois scripts font tout le travail :

| Script | Rôle |
|---|---|
| `patch/test-selftest.sh` | **verdict déterministe** : rejoue des playlists publicitaires Dans le code compilé, sur l'appareil, sans attendre une coupure (§ 0.1) |
| `patch/test-device.sh` | trouve `adb`, choisit l'appareil, installe l'APK, lance la capture `logcat` filtrée, puis analyse |
| `patch/test-live.sh` | **observation longue en direct** : enchaîne les étapes mécaniques de la recette du § 2 (capture détachée surveillée + verdict), la navigation restant à la main |
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
I/Twouich: SELFTEST 18/18 verifications, flux filtre : 328 octets
```

| Ligne | Signification |
|---|---|
| `SELFTEST 18/18 …` | les 18 vérifications passent : le filtre agit, sur l'appareil, dans le bytecode réel |
| `SELFTEST KO : <vérification>` | une vérification précise a échoué — c'est la ligne à recopier pour corriger |
| `SELFTEST ECHEC n/18 …` | verdict global en échec (sortie Log.e, donc bien visible dans les captures) |
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
