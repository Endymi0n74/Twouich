# Procédure de test anti-pub sur un appareil réel

Objectif : prouver, avec les traces de l'appareil lui-même, que les plages publicitaires sont
retirées **pendant** une coupure réelle — et pas seulement que l'app « a l'air de marcher ».

Trois scripts font tout le travail :

| Script | Rôle |
|---|---|
| `patch/test-selftest.sh` | **verdict déterministe** : rejoue des playlists publicitaires Dans le code compilé, sur l'appareil, sans attendre une coupure (§ 0.1) |
| `patch/test-device.sh` | trouve `adb`, choisit l'appareil, installe l'APK, lance la capture `logcat` filtrée, puis analyse |
| `patch/analyze_device_log.sh` | verdict d'une capture existante (utilisable seul) |
| `patch/check-release.sh` | la release publiée correspond-elle au livrable et à `update.json` (§ 0.2) |

---

## 0. État de validation

Vérifié sur un appareil réel (émulateur BlueStacks, `emulator-5554`, Android 7.1.1 / API 25), avec
un compte Twitch connecté — session de 4 minutes sur une chaîne en direct :

- installation réussie → `versionName=v1.5.10x-twouich1` lu sur l'appareil ;
- **la lecture fonctionne** : 131 nettoyages de playlist média (une toutes les 2 s, c'est le
  rafraîchissement HLS normal), des milliers de lectures de segments, **0 erreur de lecture**,
  aucun `Playback error`, aucun `FATAL EXCEPTION` ;
- le filtre est bien traversé par *toutes* les lectures HLS de l'app, sous le tag `Twouich` ;
- les 4 verdicts de `analyze_device_log.sh` sont testés (pubs retirées / rien retiré / erreurs de
  lecture / aucune playlist).

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

### Deux pièges qui font échouer ce test sans rien casser

1. **Le canal de mise à jour.** `helpers/a.b()` filtre par canal *avant* de regarder la version
   (`pref_update_channel`). Sur le canal **Beta**, seule une entrée `ReleaseType: 1` est acceptée :
   une `update.json` qui ne publie qu'une entrée **stable** n'y produit **aucun dialogue**, sans
   aucune erreur. L'appareil du test était en Beta (cas normal d'une installation héritée de
   S0undTV : même paquet, donc même préférences) — deux lancements muets, puis dialogue immédiat
   après passage en Stable (Réglages → General settings → *Update channel*). **Avant de suspecter la
   publication, lire ce canal.**
2. **La comparaison de version est fausse en amont.** `b()` compare la version publiée à un plancher
   figé (144), jamais à la version installée : l'app propose d'installer… la version qu'elle exécute
   déjà. Une fois en 146, elle redemande 146 au démarrage suivant. C'est un défaut d'origine ; il
   n'empêche pas le parcours ci-dessus, mais il rend le résultat bruyant.

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

Le script : installe `dist/Twouich_beta144_ttv1.apk`, vérifie que la version installée est bien
`v1.5.10x-twouich1` (et **avertit si ce n'est pas notre build**), vide le tampon `logcat`, puis
capture avec le filtre :

```
Twouich:V ExoPlayerImpl:W ExoPlayerImplInternal:W HlsMediaSource:W Loader:W MediaCodec:W MediaDrm:W AndroidRuntime:E *:S
```

Ensuite : **lancer un stream sur la TV**, laisser passer **au moins une coupure publicitaire
complète**, noter l'heure de la coupure, puis `Ctrl+C`.

Si `adb install` échoue en flux direct, le script bascule tout seul sur `push` + `pm install`
(même résultat, transport différent — c'est ce repli qui a fait passer l'installation sur BlueStacks).

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
| ⚠️ **filtre actif mais rien retiré** | aucune coupure pendant la capture, **ou** les marqueurs Twitch ont changé → voir `AUDIT.md` § 4.2 (constante `stitched-ad` de `PlaylistSanitizer`) |
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
