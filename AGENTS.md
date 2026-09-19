# AGENTS.md — Twouich

Instructions pour tout agent (IA ou humain) qui travaille dans **ce dépôt**.
Contexte détaillé du projet : [`memory.md`](memory.md). Audit : [`AUDIT.md`](AUDIT.md).

---

## 1. Portée

Tu travailles **uniquement** dans `D:\Codex\Twouich`.

- **Ne touche pas** aux projets voisins de `D:\Codex` — en particulier `TwVodNoAdsJCed` (userscript
  VOD, projet distinct) et `TwitchDroid` (patching d'un autre APK). Aucune de leurs conventions ne
  s'applique ici.
- Le dépôt est le **fork Android TV de S0undTV** avec greffon anti-pub. Ce n'est pas un projet
  JavaScript, ni un userscript.

## 2. Règles d'or

1. **Aucun commit, aucun push, aucune release, aucun tag** sans demande explicite de l'utilisateur.
   Le travail reste sur disque, non commité.
2. **`patch/` est la source de vérité.** `work/` (décodage, builds, captures) est **jetable** :
   on ne l'édite jamais à la main, il est régénéré par `patch/build.sh`.
3. **Ne versionne jamais** `keys/`, `dist/`, `tools/`, `work/` (voir `.gitignore`). La clé de
   signature `keys/twouich.keystore` est **irremplaçable** : sans elle, plus aucune mise à jour ne
   s'installe par-dessus la version déjà déployée.
4. **Ne change jamais** :
   - le nom de paquet `com.s0und.s0undtv` (casserait les mises à jour par-dessus) ;
   - la clé de signature (mêmes conséquences) ;
   - le `versionCode` à la baisse (l'updater et Android refusent).
5. Les valeurs figées (SHA-256 de l'APK upstream, `versionCode`, `versionName`, nom du livrable)
   vivent **dans `patch/build.sh`** — jamais dupliquées ailleurs, sauf dans `update.json` où le
   schéma l'exige.

## 3. Smali — la partie qui casse tout si on la bâcle

Le greffon est écrit **à la main en smali** (`patch/smali/com/twouich/adblock/`). Les erreurs y sont
silencieuses : le build passe, l'APK s'installe, et la lecture casse. Quatre bugs de ce type ont déjà
été payés (voir `memory.md` §6).

### Sémantique des branchements contre zéro (Dalvik) — à ne pas se raconter

| Opcode | Sens réel |
|---|---|
| `if-eqz` | `v == 0` |
| `if-nez` | `v != 0` |
| `if-ltz` | `v < 0` |
| **`if-gez`** | **`v >= 0`** ← se lit naturellement à l'envers |
| **`if-gtz`** | **`v > 0`** ← 0 ne branche pas |
| `if-lez` | `v <= 0` |

Les formes à deux registres (`if-le v4, v3`, `if-ge v2, v3`) sont littérales.

### Règles imposées

- **Interdit** : `if-gez` et `if-gtz`. Utiliser `if-ltz` (`v < 0`) ou `if-lez` (`v <= 0`), avec un
  commentaire au-dessus quand l'intention n'est pas évidente.
- Après **toute** édition de smali : `python patch/tests/test_smali_branches.py` (11 vérifications).
  Ce test refuse les opcodes ambigus et l'inversion des branchements critiques ; il balaie **tout**
  `patch/smali/**/*.smali`, donc un nouveau fichier est surveillé sans rien changer.
- **Sens des branchements sur un test de forme.** `if-eqz` branche quand le résultat est faux,
  `if-nez` quand il est vrai : sur `startsWith("#")`, c'est `if-nez` qui veut dire « la ligne
  commence par # ». Un `if-eqz` à cette place a fait compter les balises et ignorer les URI, donc
  annoncer 4 segments publicitaires là où il y en avait 3 (trouvé le 15/09/2026 par le self-test).
- Un test qui n'a jamais échoué ne prouve rien : quand tu ajoutes un garde-fou, **vérifie qu'il
  mord** en réintroduisant la faute sur une copie (`/tmp`) avant de le déclarer bon.
- Toute la logique de nettoyage doit rester **testable dans le code compilé** : si tu touches au
  nettoyeur, à la source de données ou à leur instrumentation, étends `SelfTest.smali` plutôt que de
  te contenter du miroir Python. C'est ce self-test qui a trouvé le compteur fautif, invisible
  partout ailleurs.
- Les journaux doivent rester **parcimonieux** : une ligne par playlist nettoyée, pas une par
  lecture de segment (une instrumentation bavarde a déjà produit 9 000 lignes en quelques minutes).

## 4. Construire

```bash
cd Twouich
bash patch/build.sh          # APK upstream → apktool d → patch.py → apktool b → zipalign → signature v1+v2+v3
```

- Outils requis dans `tools/` : `apktool-3.0.3.jar`, `uber-apk-signer.jar`.
- `patch.py` pose **deux** points d'accroche : `z3/u$b.a()` (toutes les sources de données du
  lecteur passent par le filtre) et `MainApp.onCreate()` (une ligne qui lance le self-test au
  démarrage). Si l'un des deux disparaît d'une beta, le script le dit et s'arrête.
- L'**identité visuelle** (écran de démarrage, icônes, bannière, nom, thème, pages embarquées,
  captures du tutoriel) est produite par `patch/branding/make_brand.py` et posée par l'étape 2 de
  `patch.py`. On ne retouche **jamais** un visuel à la main dans `work/decoded/res/` : on change
  `make_brand.py`, on réémet les assets (`python patch/branding/make_brand.py emit`) et `patch.py`
  les recopie.
- Les **six captures du tutoriel** ne se recadrent ni ne s'éditent : ce sont des captures d'écran de
  l'app, remappées d'une palette à l'autre par `recolor_tutorial()` (rouge S0und → violet Twouich),
  sources versionnées dans `patch/branding/tutorial/`. L'émulateur de test plafonne à 1280×720 : les
  recapturer dégraderait des images 1920×1080 pour une mise en page qui n'a pas changé.
- Les **identifiants de signature ne sont pas versionnés** : `patch/build.sh` lit `keys/keystore.properties` (ignoré par git) ou `KEY_PASS`, et s'arrête avant de construire s'il ne les trouve pas. Le dépôt est public : une clé dont le mot de passe circule permet à n'importe qui de signer un APK qu'Android acceptera comme une mise à jour.
- La chaîne est **idempotente** : relancer ne casse rien.
- `patch/patch.py` **échoue bruyamment** si un motif upstream a changé. Ne « répare » jamais ce
  message en assouplissant le motif : c'est le signal qu'une nouvelle beta upstream demande
  d'adapter le patch.
- Piège connu : apktool 3 ne réinjecte pas `versionCode`/`versionName` au build — ils sont réécrits
  explicitement dans le manifest par `patch.py`. Ne pas retirer ce patch.

## 5. Vérifier (obligatoire avant de dire « c'est bon »)

```bash
python patch/tests/test_sanitizer.py       # 48 assertions : règles de nettoyage (miroir Python) + fixture SSAI réelle du 18/09/2026 + sentinelle marqueur inconnu
python patch/tests/test_smali_branches.py  # 11 assertions : branchements réels du smali
python patch/tests/test_brand.py           # 14 assertions : identité visuelle (voir plus bas)
python patch/tests/test_apk.py             # 13 verdicts sur l'APK LIVRÉ (pas sur l'arbre de travail),
                                           #   dont l'accord avec update.json
python patch/tests/test_normalize_apk.py   # 29 vérifications : le normaliseur canonise horodatage
                                           #   et ordre des entrées ZIP sans rien toucher d'autre
bash   patch/tests/test_analyzer.sh        # 8 verdicts sur captures synthétiques
bash   patch/test-selftest.sh              # self-test embarqué, sur appareil (voir plus bas)
bash   patch/test-live.sh                  # observation live longue : capture détachée + verdict (TEST-DEVICE.md § 2)
bash   patch/check-release.sh              # chaîne update.json → tag → asset → octets servis
```

Le self-test embarqué (`patch/smali/com/twouich/adblock/SelfTest.smali`, exécuté par
`MainApp.onCreate`) rejoue des playlists publicitaires Twitch dans le **vrai code compilé** et fait
traverser `AdBlockDataSource` : c'est la seule preuve qui ne dépend pas d'une coupure réelle, et la
seule qui parle la sémantique Dalvik (elle a déjà trouvé deux défauts que rien d'autre ne voyait).
Verdict attendu, une ligne : `I/Twouich: SELFTEST 18/18 verifications, flux filtre : 328 octets`.
Toute nouvelle vérification ajoutée là doit passer sur l'appareil avant d'être déclarée bonne.

**Et si tu touches à l'identité visuelle** : `test_brand.py` couvre le générateur et les assets
versionnés, `test_apk.py` ce qui a réellement été empaqueté (lance-le **après** `build.sh`), mais ni
l'un ni l'autre ne voit ce que l'appareil affiche. Il faut **aussi** installer et capturer l'écran de
démarrage — un splash se regarde, il ne se déduit pas d'un XML. La liste des visuels attendus est
figée dans les deux : c'est elle qui rattrape un asset oublié. Et pour la marque d'avant, c'est le
**déséquilibre des canaux** qui la caractérise, pas une distance au rouge : une tolérance large
classe les pixels presque noirs comme rouges (erreur commise, voir `memory.md` §6).

**Et si tu touches au chemin de lecture** (source de données, nettoyeur, injection) : il faut
**aussi** passer par l'appareil. La lecture doit fonctionner réellement, sans quoi tu ne sais rien.

```bash
ADB="/c/Users/<vous>/AppData/Local/ScrcpyGUI/scrcpy-bin/adb.exe" \
  bash patch/test-device.sh --serial <serial> --no-install
bash patch/analyze_device_log.sh work/device-test/logcat-<date>.txt
```

Pour une observation **longue** en direct (prouver qu'un pod est retiré pendant que la sentinelle
reste muette, sans terminal occupé), `bash patch/test-live.sh --duration 600` enchaîne les étapes
mécaniques — état, capture détachée surveillée, arrêt + verdict `analyze_device_log.sh` ; seules la
navigation D-pad et l'observation de l'écran restent à la main (détails et pièges : `TEST-DEVICE.md` § 2).

Indices à surveiller dans le logcat (tag `Twouich`) :
`playlist nettoyee <avant> -> <après> octets, segments pub retires : <n>`.

### Règles adb (chacune a déjà coûté une heure)

- **Un seul binaire `adb`.** BlueStacks embarque `HD-Adb.exe`, scrcpy des platform-tools : deux
  serveurs qui se tuent mutuellement → `error: closed` en plein transfert. Exporter `ADB=…` et s'y
  tenir.
- **Aucun `timeout` autour de `adb install`.** Un timeout tue l'installation en plein transfert et
  **fige `adbd`** de l'émulateur ; il faut alors le redémarrer.
- **Git Bash réécrit les chemins absolus** : exporter `MSYS_NO_PATHCONV=1` et
  `MSYS2_ARG_CONV_EXCL='*'`.
- **`logcat -v time` change le format** (`I/Twouich (23733): …`) : un `grep 'Twouich : '` ne matche
  plus rien et fait croire à une panne inexistante. Grepper sur `Twouich` seul.
- Pas de mode arrière-plan : une capture = **une seule commande synchrone** (ouverture du flux +
  `logcat` enchaînés).
- L'app de test **ne cohabite pas** avec la S0undTV officielle (signatures différentes).

## 6. Documentation à tenir à jour

| Fichier | Quand le mettre à jour |
|---|---|
| `CHANGELOG-twouich.md` | à chaque changement visible pour l'utilisateur |
| `AUDIT.md` | nouvelle obsolescence, nouveau risque, nouvelle règle de nettoyage |
| `TEST-DEVICE.md` | nouveau pas de procédure, nouveau piège de terrain |
| `memory.md` | état de validation, leçons, journal — à chaque session qui change l'état du projet |
| `README.md` | commandes, activation du proxy, passage à une nouvelle beta |

Les documents sont **en français**, comme le reste du projet.

## 7. Définition de « terminé »

- [ ] `bash patch/build.sh` passe jusqu'à `signature verified [v1, v2, v3]` ;
- [ ] les tests locaux passent (4 suites + `bash patch/check-release.sh` s'il y a une publication) ;
- [ ] `python patch/sync-readme.py --check` passe (README et CHANGELOG synchronisés) ;
- [ ] le self-test embarqué passe sur appareil (`bash patch/test-selftest.sh` → `SELFTEST n/n`) ;
- [ ] si le chemin de lecture est touché : lecture réelle vérifiée sur appareil (flux qui tourne,
      `0 erreur de lecture`), pas seulement « l'app se lance » ;
- [ ] `CHANGELOG-twouich.md` et `memory.md` à jour ;
- [ ] rien n'est commité, poussé ou taggé sans demande explicite.

## 8. Release (sur demande uniquement)

1. Incrémenter `VERSION_CODE` / `VERSION_NAME` dans `patch/build.sh`, puis ajouter l'entrée
   correspondante en tête de `CHANGELOG-twouich.md` ; `python patch/sync-readme.py` aligne alors
   le README (lien d'installation vers l'APK du tag + section de version manquante) — la CI
   vérifie cet alignement à chaque push (`sync-readme.py --check`) ;
2. reconstruire, puis `update.json` doit décrire **exactement** le livrable
   (`APK`, `ReleaseDate`, `ReleaseType`, `VersionCode`, `VersionName`, `hasChangeLog`) ;
3. le **tag Git doit être identique au `VersionName`** — l'updater de l'app s'appuie dessus ;
4. joindre l'APK `dist/Twouich_v1.0.1.apk` à la release ;
5. joindre **aussi** `changelog.html` — copie de `work/decoded/assets/S0undTV_changelog.html` :
   l'updater pointe le bouton « changelog » sur cet asset **au tag**, donc sans ce fichier la page
   « Nouveautés » de l'app est vide pour tout utilisateur à jour ;
6. annoncer le **SHA-256** de l'APK — le build est **reproductible au sens strict** depuis le 18/09/2026 :
   deux builds du même arbre produisent les **mêmes octets**, quelle que soit la plateforme (horodatage
   ZIP et ordre des entrées canonisés par `patch/normalize_apk.py` avant signature, date du changelog
   figée par version dans `build.sh`, pages embarquées canonisées LF). Le SHA publié identifie donc
   désormais aussi la **recette** : un rebuild conforme doit reproduire le hash exact ;
7. vérifier la chaîne entière d'une commande — `bash patch/check-release.sh` couvre `update.json`,
   le tag, les deux assets et les **octets réellement servis** (comparés au livrable local). Il fait
   aussi contrôle négatif : lancé sur une version inexistante, il doit sortir en 1 ;
8. rappeler à l'utilisateur de sauvegarder `keys/twouich.keystore` hors du dossier.

### ⚠️ Valider le parcours de mise à jour : la release intermédiaire

L'updater ne s'exécute **jamais** tant qu'il n'y a rien de plus récent à installer. Une release qui
n'est que la première publication laisse donc tout le chemin (dialogue → téléchargement → passage à
l'installeur) non prouvé. Pour le fermer :

1. publier une version N (releases ci-dessus) et **installer cet APK sur un appareil** ;
2. incrémenter à N+1 (`build.sh` — le désassemblage se refait seul quand la version change) et
   publier N+1 ;
3. **pousser `update.json` après la release**, jamais avant : l'URL est construite avec le
   `VersionName` publié, donc un `update.json` en avance fait annoncer une mise à jour pour un
   asset qui n'existe pas ;
4. lancer l'app : elle doit ouvrir **son** écran de mise à jour sans qu'on lui demande. Le vérifier
   par l'activité, pas à l'œil — `dumpsys activity activities | grep mResumedActivity` doit dire
   `com.s0und.s0undtv/.activities.UpdateActivity` ;
5. « Install update » → l'app télécharge puis passe l'APK au système :
   `logcat -s S0undTV_AutoUpdateSrv` montre l'URL exacte, et l'ActivityManager l'intent
   `content://com.s0und.s0undtv.provider/cache_files/update.apk` vers `PackageInstallerActivity`.
   Seul geste humain : le « INSTALLER » du système, qu'Android impose ;
6. comparer les octets **installés** au livrable, pas seulement le numéro de version :
   `adb shell pm path com.s0und.s0undtv` puis `adb pull` de `base.apk` → `sha256sum` doit égaler
   celui de `dist/` (et celui de `check-release.sh`). C'est la seule preuve que c'est bien notre
   fichier qui a atterri sur l'appareil.

**Piège du canal** : `helpers/a.b()` filtre d'abord par canal (`pref_update_channel`). En canal
**Beta**, seule une entrée `ReleaseType: 1` est acceptée — une `update.json` qui ne publie qu'une
entrée **stable** n'y produit aucun dialogue, sans erreur nulle part. Les installations héritées de
S0undTV sont souvent en Beta (même paquet Android, préférence conservée) : si l'app ne dit rien sur
un appareil, **vérifier le canal** (Réglages → General settings → « Update channel ») avant de
soupçonner la publication.
