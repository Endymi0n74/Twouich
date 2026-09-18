# Twouich — mémoire projet

> APK Android TV **sans publicité** pour Twitch, construit par patch reproductible sur le build
> upstream **S0undTV**. Dépôt : `https://github.com/Endymi0n74/Twouich` — atelier local :
> `D:\Codex\Twouich`.

Dernière mise à jour : **18 septembre 2026**.

---

## 1. Identité

| Élément | Valeur |
|---|---|
| Nom du produit | **Twouich** (`update.json` → `v1.0.0`) |
| Paquet Android | `com.s0und.s0undtv` — **inchangé volontairement** (sinon les mises à jour ne s'installent plus par-dessus) |
| Identité visuelle | piste **C** « dégradé + monogramme », générée par `patch/branding/make_brand.py` |
| Palette | violet profond `#7c22e8` → `#210849` (dégradé 315°), mot-symbole puffy `#ffffff`, tagline `#e6d8ff` |
| Base upstream | S0undTV `beta_144.apk`, SHA-256 `578da49bcab05b1bf0448bbf638f88af71ad7188052cd65c3319093ee5b151b0` |
| Version produite | `versionCode 151` / `versionName v1.0.4` |
| Livrable | `dist/Twouich_v1.0.4.apk` (signé par la CI, v1+v2+v3, zipalign vérifié, SHA-256 `dcaa1efd…`) |
| Clé de signature | `keys/twouich.keystore`, alias `twouich-dev` — **non versionnée, à sauvegarder hors du dossier** ; mot de passe **hors du dépôt** (`keys/keystore.properties`, ignoré, ou `KEY_PASS`) |
| Modèle Android minimum | API 23 (Android 6), cible 35 |

`patch/build.sh` contient la **source unique** de ces valeurs (SHA upstream, version, nom d'APK).

## 2. Ce que fait le produit

S0undTV est un lecteur Twitch pour Android TV. Twitch insère les publicités **côté serveur**
(SSAI) : elles apparaissent dans la playlist HLS sous forme de plages `#EXT-X-DATERANGE` marquées
`stitched-ad`, avec des segments dont le titre contient `Amazon`. Twouich intercepte la lecture des
playlists et retire ces plages **avant** qu'ExoPlayer ne les voie.

### Architecture du greffon — `patch/smali/com/twouich/adblock/`

- **`AdBlockDataSource`** — implémentation de l'interface `Lz3/l;` (la `DataSource` d'ExoPlayer de
  l'app) qui décore la source réelle :
  - `c(Lz3/p;)` (open) : détecte si l'URL se termine par `.m3u8` → `e` = « c'est une playlist » ;
    réinitialise le cache ; transmet l'ouverture à la source réelle ;
  - `read([BII)` : pour une playlist, vide la source réelle **entièrement** dans un tampon, passe le
    texte au nettoyeur, met le résultat en cache et le sert par tranches ; pour tout le reste
    (segments `.ts`, clés, VOD binaires), simple passe-plat sans copie ;
  - la trace logcat `Twouich` est émise à chaque nettoyage (voir §5).
- **`PlaylistSanitizer`** — fonction pure `a(String) -> String`, règles alignées sur Streamlink
  (`plugins/twitch.py`) :
  - retrait des `#EXT-X-DATERANGE` contenant `stitched-ad` ;
  - retrait des `#EXTINF` contenant `Amazon` **et** de l'URI du segment qui suit ;
  - retrait des blocs `#EXT-X-CUE-OUT` … `#EXT-X-CUE-IN` ;
  - **conservation** de `#EXT-X-DISCONTINUITY` et `#EXT-X-TWITCH-LIVE-SEQUENCE` (ils signalent le
    saut de timeline au lecteur — les retirer casse la lecture) ;
  - un corps sans `#EXTM3U` est rendu tel quel.

**Injection** : un seul point, `Lz3/u$b.a()` — l'unique fabrique de sources de données de l'app
(vérifié : `Lz3/u;` n'est instanciée nulle part ailleurs). Conséquence : *toutes* les lectures HLS
(live, VOD, aperçus de l'accueil et de la recherche) passent par le filtre, sans patcher d'appelant.

- **`SelfTest`** (+ `SelfTest$Fake`) — self-test embarqué, lancé une fois par démarrage depuis
  `MainApp.onCreate` (deuxième point d'accroche de `patch.py`). Il rejoue des playlists
  publicitaires réelles dans le code compilé et fait traverser `AdBlockDataSource` ; verdict sur
  logcat, détail dans §5.

**Option proxy** : `PROXY_HOST` (dans `AdBlockDataSource`) est **vide par défaut**. S'il est
renseigné, les requêtes `usher.ttvnw.net` partent d'abord par le proxy, avec repli automatique sur
l'URL d'origine. Désactivé volontairement : aucun proxy public n'expose l'API de relais « chemin
conservé » utilisée ici.

### Identité visuelle — `patch/branding/make_brand.py`

L'app portait la marque S0und à **six endroits**, tous invisibles depuis le code : l'écran de
démarrage (vecteur rouge `#a30f2c` avec le mot-symbole), les icônes de lancement et la bannière TV,
le nom affiché (« S0undTV »), le fond de l'icône adaptative, et deux pages HTML embarquées (À propos,
Nouveautés) dont la seconde avait un fond rouge. Trois visuels de plus (« `header_logo` », « `app_icon` », « `channel_logo` ») portaient
le logo **dans l'interface** ; aucun n'était référencé par son nom, seuls les pixels les ont
signalés (voir §5).

Un seul fichier produit tout le visuel, et rien n'est retouché à la main :

- `make_brand.py` calcule la composition (mot-symbole Bahnschrift, tagline Segoe UI, monogramme),
  la décline en **arborescence `res/` prête à recopier** (`patch/branding/assets/res/`) et publie sa
  palette dans `brand.json` (lue par `patch.py` pour `colors.xml`) ;
- l'écran de démarrage est un **`layer-list`** : dégradé XML (aucune ressource nouvelle, donc aucun
  risque de collision d'`id` aapt2) et composition PNG transparente posée **au centre, sans mise à
  l'échelle** (1920×1080 en `nodpi`) — le texte garde donc le dessin validé, et le contenu reste
  entier même sur un écran 720p qui rogne les bords ;
- **trois pistes** existent (`A` violet plein, `B` noir Twitch, `C` dégradé + monogramme) ; la piste
  livrée est la constante `SHIPPING`. Changer d'identité = `python patch/branding/make_brand.py emit
  --variant B`, puis relancer `patch.py` : aucun autre fichier à toucher.
- Le **nom** change aussi côté ressources (`app_name`, libellé du manifeste) mais **pas** le paquet
  Android : c'est lui qui permet de mettre l'app à jour par-dessus l'installée.

### Captures du tutoriel — remappées, pas recapturées

Les six visuels de l'onboarding (`drawable/tut_*.webp`, 1920×1080) sont des captures d'écran réelles
prises par l'upstream, et ils portaient deux choses de la marque d'avant : les **cadres
d'annotation** dessinés en rouge (`#a30f2c`), et pour `tut_5` un **panneau au thème rouge**
(`#4d000f` + `#a30f2c`, un tiers de l'image).

Elles n'ont **pas** été recapturées, et c'est un choix : l'émulateur de test plafonne à 1280×720
alors que ces images sont en 1920×1080 — les refaire aurait donné des visuels 1,5× plus flous pour
une mise en page qui n'a pas changé (la refonte ne touche ni la disposition ni les écrans, seulement
la marque et le thème). `make_brand.py` applique donc **le même remappage qu'un changement de
thème** : chaque couleur de la famille rouge prend la couleur de même rôle dans la palette Twouich
(`theme_red_dark`→`theme_purple_dark`, `theme_red`→`theme_purple`, `theme_red_bright`→
`theme_purple_bright`), avec un fondu qui laisse intact tout ce qui n'est pas franchement rouge.

Résultat mesuré : la famille rouge passe de 2,3–36,7 % à **0,0000 %** sur les six images, et
l'écart de luminance moyen reste sous 1,9/255 (7,4 sur `tut_5`, dont le grand panneau rouge devient
violet). Les rouges de **contenu** (vignettes de streams) sont laissés tels quels : ce ne sont pas
des éléments de marque. Les sources sont versionnées dans `patch/branding/tutorial/`, donc le
remappage est rejouable et vérifiable sans appareil.

## 3. Chaîne de build (rejouable, idempotente)

```bash
cd Twouich
bash patch/build.sh
```

```
APK upstream vérifié par SHA-256 → apktool d → patch/patch.py → apktool b → zipalign → signature v1+v2+v3 → dist/
```

- `patch/patch.py` applique **tous** les patchs en un endroit, en cinq étapes numérotées : greffon
  anti-pub (1), **identité visuelle (2)**, repointage de l'updater (3), bump de version (4),
  contrôles (5). Il **échoue bruyamment** si un motif attendu a changé côté upstream — c'est la
  détection de rupture sur une nouvelle beta.
- `build.sh` régénère les assets de marque avant de patcher. Si Pillow ou les polices manquent, il
  utilise les assets **versionnés** et le dit — l'APK ne part jamais avec l'identité d'avant.
- Outils attendus dans `tools/` (non versionné) : `apktool-3.0.3.jar`, `uber-apk-signer.jar`.
- `work/` (décodage, builds, captures) et `dist/` sont **non versionnés**.
- Reproductibilité : **octet pour octet depuis le 18/09/2026** (voir journal). Avant : deux builds du
  même arbre ne coïncidaient qu'au CRC des 2172 entrées, apktool estampillant le ZIP à l'heure du build.
  La chaîne normalise désormais l'horodatage vers 1980-01-01 **avant** signature, fige la date du
  changelog par version et canonise les pages embarquées en LF — le SHA-256 publié identifie donc le
  fichier **et** la recette : un rebuild conforme doit reproduire le hash exact.

## 4. Ce qui a été corrigé côté obsolescences

- **Updater** : 5 URLs pointaient vers `S0und/S0undTV` → l'app aurait **téléchargé le build
  d'origine par-dessus le nôtre**. Repointées vers Twouich.
- **`AutoUpdateService`** : endpoint mort `https://share.s0und.cloudns.cl/app-release.apk` (ancien
  backend abandonné) → remplacé par l'asset de notre dernière release.
- **Manifest** : apktool 3 sort `versionCode`/`versionName` et ne les réinjecte pas au build → APK
  **sans version**, installation refusée. Réécriture explicite ajoutée.
- **`update.json` / `README.md` / `.github/FUNDING.yml`** : décrivaient S0und (dont des APK
  inexistants ici, et un bouton Sponsor vers le PayPal du développeur d'origine) → réécrits.

Détail complet : [`AUDIT.md`](AUDIT.md).

## 5. Vérifications

### En local, sans appareil

```bash
python patch/tests/test_sanitizer.py      # 48 assertions : règles de nettoyage (miroir Python) + fixture SSAI réelle du 18/09/2026 + sentinelle marqueur inconnu
python patch/tests/test_smali_branches.py # 11 assertions : branchements réels du smali (pièges Dalvik)
python patch/tests/test_brand.py          # 14 assertions : identité visuelle (assets, rouge mort, zone sûre,
                                          #   captures du tutoriel remappées)
python patch/tests/test_apk.py            # 13 verdicts sur l'APK livré (et non sur l'arbre de travail),
                                          #   dont l'accord avec update.json
bash   patch/tests/test_analyzer.sh       # 8 verdicts, sur des captures synthétiques
bash   patch/check-release.sh             # chaîne update.json → tag → asset → octets servis
```

### Identité visuelle — la preuve, à trois niveaux

Un asset oublié ne se plaint jamais : il s'installe, démarre, et affiche encore la marque d'avant.
La refonte est donc vérifiée jusqu'à l'écran :

1. **Générateur** — `test_brand.py` : les assets versionnés sont octet pour octet ce qu'`emit`
   produit (aucune dérive code/images), aucun pixel du rouge S0und dans les visuels, la composition
   reste entière en 720p et **centrée**, les icônes existent dans les cinq densités aux bonnes
   tailles, le mot-symbole est bien encré (pas de génération vide), et `brand.json` décrit la même
   palette que les XML.
2. **Arbre patché** — les 40 contrôles de `patch.py` (25 assets + 1 balayage) : chaque asset émis
   est présent dans l'arbre décodé, `app_name`/libellé du manifeste sont bien « Twouich », et
   **aucun `#a30f2c` ne subsiste** hors de la palette des thèmes (le rouge y reste un choix
   d'utilisateur, pas la marque).
3. **APK livré** — `test_apk.py` : c'est l'artefact qui part chez l'utilisateur, pas l'arbre de
   travail (aapt2 compile les XML en binaire, ré-encode des PNG, fusionne les ressources : un asset
   perdu à cette étape ne se plaint jamais). 25/25 visuels présents, identiques octet pour octet aux
   3 re-encodages près, composition du splash à sa taille de dessin, **zéro « S0undTV »** dans
   `resources.arsc` comme dans le manifeste, pages embarquées réécrites, signature v1 présente.
   Contrôle négatif : lancé sur l'APK **d'origine** de S0undTV, il échoue sur les 8 contrôles de
   marque — c'est ce qui montre qu'il discrimine.
4. **Appareil** — écran de démarrage capturé pendant un lancement réel sur BlueStacks
   (`work/branding/shots/splash-device.png`) : dégradé violet, pastille « T », mot-symbole
   « TWOUICH » et tagline, plus aucune trace de l'écran rouge. Le self-test anti-pub reste **vert**
   après la refonte (`SELFTEST 18/18`, dex frais **et** app installée).

Le contrôle « famille rouge S0und absente des visuels » couvre **tous** les visuels livrés,
captures du tutoriel comprises — c'est précisément ce qui manquait quand ces six images portaient
encore la marque. Vérifié en le cassant : recolor désactivé → `tut_5` remonte à **31,96 %** et la
sortie passe en code 1 (seuil calibré sur le bruit WebP, qui laisse 3 pixels dans l'angle arrondi
d'une icône, soit 0,014 %).

Le garde-fou a été **vérifié en le cassant** : piste livrée changée sans réémettre (§ « assets
versionnés »), mot-symbole repassé en rouge (balayage des pixels : 9,8 % sur la bannière), dégradé
repassé en rouge (contrôle des XML) et un visuel retiré du générateur (liste attendue : c'est
précisément la faute qui avait échappé à la relecture) — chaque fois la sortie passe en code 1.

### Self-test embarqué — la preuve qui ne dépend pas d'une coupure publicitaire

`SelfTest` (+ `SelfTest$Fake`) est **dans l'APK** et s'exécute une fois par démarrage (injecté par
`patch.py` dans `MainApp.onCreate`). Il rejoue quatre playlists aux formats Twitch réels dans le
**vrai code compilé** (plage SSAI `stitched-ad`, bloc `CUE-OUT`/`CUE-IN`, segment titré `Amazon`,
daterange non publicitaire) et fait traverser `AdBlockDataSource` (source en mémoire, lecture par
tranches de 64 octets), puis publie un verdict : une seule ligne si tout va bien.

```bash
bash patch/test-selftest.sh             # dex frais exécuté via app_process, RIEN n'est installé
bash patch/test-selftest.sh --in-app    # ou redémarre l'app installée et lit son verdict
```

**Validé le 15/09/2026** (BlueStacks, API 25 / `emulator-5554`) :

```
I/Twouich: playlist nettoyee 623 -> 328 octets, segments pub retires : 3
I/Twouich: SELFTEST 18/18 verifications, flux filtre : 328 octets
```

À retenir : un smali peut assembler proprement et être rejeté par le vérificateur Dalvik
(`VerifyError` au chargement de la classe) — une liste d'invoke est limitée à 5 registres, et deux
paramètres `long` imposent la forme `/range`. C'est la même famille de pièges que §6.

### Mise à jour automatique — la preuve, sur un appareil

L'updater était la dernière chose « vraie sur le papier » : il lit `update.json` sur `master`, en
tire un tag, télécharge l'asset. Mais rien de ce chemin ne s'exécute tant qu'une version **plus
récente** n'existe pas en ligne — d'où l'étape « release intermédiaire » du §8 d'`AGENTS.md`.

Rejoué de bout en bout le 15/09/2026 (`emulator-5554`, API 25), app installée en **145** :

| Étape | Preuve relevée |
|---|---|
| point de départ | `dumpsys package …` → `versionName=v1.5.10x-twouich1` |
| release `v1.5.10x-twouich2` (146) publiée + `update.json` à jour | `bash patch/check-release.sh` → chaîne cohérente |
| l'app ouvre **son** écran de mise à jour, seule, au lancement | `mResumedActivity: com.s0und.s0undtv/.activities.UpdateActivity` ; écran « New update available! Version: v1.5.10x-twouich2 / Version code: 146 » |
| « Install update » | `S0undTV_AutoUpdateSrv: onStartCommand: …/releases/download/v1.5.10x-twouich2/Twouich_beta144_ttv1.apk` |
| l'app passe son APK au système | `START … dat=content://com.s0und.s0undtv.provider/cache_files/update.apk typ=application/vnd.android.package-archive … from uid 10066` |
| installation | `versionCode=146 versionName=v1.5.10x-twouich2`, « Application installée. » |
| **octets installés** | `pm path` + `pull` → SHA-256 `7f3125d4…` = livrable local = octets servis par la release |
| l'app tourne sur ces octets | `bash patch/test-selftest.sh --in-app` → `SELFTEST 18/18` |

Le seul geste humain du parcours est le « INSTALLER » du système (Android l'impose) : le
téléchargement, le choix de l'URL et le lancement de l'installeur sont faits par l'app.

#### Deux comportements que la lecture de code n'a pas montrés

1. **Le canal pèse plus que la version.** `helpers/a.b()` filtre d'abord par **canal**
   (`pref_update_channel`, « Stable » par défaut). Sur le canal **Beta**, seule une entrée
   `ReleaseType: 1` est acceptée : une `update.json` qui ne publie qu'une entrée **stable** n'y
   produit **aucun** dialogue. Cet appareil était sur **Beta** — et c'est le cas attendu de toute
   installation héritée de S0undTV, puisque le paquet Android est le même et que la préférence
   survit. Mesuré : deux lancements sans dialogue en Beta, dialogue immédiat après bascule en
   Stable. **Conséquence produit** : publier aussi une entrée `ReleaseType: 1`, sinon les appareils
   en Beta ne verront jamais nos releases.
2. **La comparaison de version est fausse.** `b()` compare la version publiée à un **plancher figé
   (144)**, jamais à la version installée : l'app propose donc d'installer la version qu'elle
   exécute déjà. Mesuré : en 146, relance → « New update available! Version code: 146 » de nouveau.

Les deux viennent de l'upstream (ils précèdent Twouich) : consignés ici, pas corrigés en silence.
La **comparaison de version a été corrigée depuis** (v1.0.0 : lecture de la version installée via
`PackageManager.getPackageInfo()`). Le **canal Beta est corrigé structurellement depuis la v1.0.2** :
le flag gravé `b.a` est forcé à `false` par `patch.py` (étape 3b), donc une installation neuve
démarre en Stable — voir § 8, point 3.

#### Un piège que ce parcours a révélé

L'updater lit `update.json` sur `master` et construit son URL avec le `VersionName` publié. Si
`update.json` est poussé **avant** que la release existe, l'app annonce une mise à jour et
n'installe rien (404 silencieux). L'ordre correct est : construire → publier la release → pousser
`update.json`. `patch/check-release.sh` vérifie les quatre étages après coup.

### Sur appareil — `patch/test-device.sh` + `patch/analyze_device_log.sh`

Trace embarquée à chercher dans `logcat` (tag `Twouich`) :

```
[Twouich] playlist nettoyee <octets avant> -> <après> octets, segments pub retires : <n>
[Twouich] proxy indisponible : repli sur la requete directe
```

**Validé le 15/09/2026** sur émulateur BlueStacks (`emulator-5554`, Android 7.1.1 / API 25), compte
Twitch gratuit connecté, session de 4 minutes sur une chaîne en direct :

- installation OK (`versionName` relu sur l'appareil), app stable, aucun `FATAL EXCEPTION` ;
- **131 nettoyages** de playlist média (rafraîchissement HLS toutes les 2 s), des milliers de
  lectures de segments, **0 erreur de lecture**, aucun `Playback error` ;
- le filtre est donc prouvé **traversé** par toutes les lectures HLS, et — depuis le self-test
  ci-dessus — **efficace** : le retrait d'une plage publicitaire est reproduit à volonté dans le
  code compilé (623 → 328 octets, 3 segments retirés). La capture live reste utile pour vérifier la
tenne pendant un direct, mais elle n'est plus la seule preuve possible.

**Validé le 18/09/2026** (même émulateur, v1.0.4, compte Twitch reconnecté) — la première coupure
publicitaire **réelle** servie à l'app, avec recoupage PC ↔ appareil :

- **radar multi-chaînes côté PC** (refetch token GQL anonyme → `usher.ttvnw.net` → playlist
  variante toutes les ~8 s) pour trouver une chaîne avec pod publicitaire en cours, puis lecture
  de cette chaîne sur l'appareil pendant la session ;
- **1782 nettoyages, 571 playlists avec pubs retirées, 5974 segments pub supprimés** — pod
  maximum : 22 segments d'un coup (playlist 58 ko → 2,8 ko), 0 repli proxy ;
- le marqueur servi ce jour-là est **exactement celui des 3 règles** (`twitch-stitched-ad`,
  titres `Amazon|<id>`, `DISCONTINUITY`) plus une classe nouvelle sans effet
  (`twitch-ad-quartile`) : **34 playlists brutes capturées, 0 fuite** au rejouage dans le miroir
  Python, dont une figée comme fixture de régression (`patch/tests/fixtures/ssai-2026-09-18.m3u8`,
  session et tracking neutralisés) — l'hypothèse d'un format non reconnu est invalidée ;
- les **24 « Source error »** de la session sont des `PlaylistResetException` d'ExoPlayer en
  **fin de pod** (la playlist pub est un flux de substitution `MEDIA-SEQUENCE:0` ; au retour du
  contenu, la renumérotation force une resync en 2–4 s, récupérée automatiquement) — effet de
  bord attendu du stripping, pas des fuites ;
- l'insertion SSAI est **par session de token** : le PC et l'app peuvent être simultanément dans
  des états pub différents — un écart entre les deux flux n'est pas une preuve de fuite.

## 6. Leçons — les cinq bugs de branchement

Quatre cassaient la lecture, le cinquième faussait la preuve. Tous invisibles pour le miroir Python
(`test_sanitizer.py` passait 17/17) : **seul un appareil pouvait les révéler**. Ils sont documentés
ici parce qu'ils sont la raison d'être de `test_smali_branches.py` et du self-test embarqué.

1. `PlaylistSanitizer` : `if-eqz v1, :is_playlist` au lieu de `if-nez` → **les vraies playlists
   repartaient intactes, pubs comprises** (le filtre ne servait à rien sur les flux réels) et les
   corps non-playlist étaient nettoyés pour rien.
2. `AdBlockDataSource.read` : `if-nez v0, :fill` au lieu de `if-eqz` → le premier appel de lecture
   tombait directement sur `array-length(null)` → `NullPointerException`.
3. et 4. `if-gez v3, :drained` alors que `v3` valait **622** : piège de la sémantique Dalvik (table
   ci-dessous). La boucle de remplissage sortait avant d'écrire le moindre octet → playlist vide →
   `Underlying input stream returned zero bytes` → lecture impossible.

5. `PlaylistSanitizer`, compteur (trouvé le 15/09/2026 par le self-test, sur l'appareil) :
   `if-eqz v5, :drop_nocount` après `startsWith("#")`. Branche à l'envers : le compteur
   incrémentait les **balises** jetées (`#EXTINF`, `#EXT-X-DATERANGE`…) et ignorait les URI. Le
   nettoyage était correct, mais la trace annonçait `segments pub retires : 4` pour 3 segments — et
   c'est cette trace qui sert de preuve dans `TEST-DEVICE.md`. La sonde posée dans la boucle a
   montré la faute en trois minutes ; aucune analyse du fichier ne l'aurait donnée, puisque la
   source *se lit* comme correcte (`if-eqz` après un test de forme se lit naturellement comme
   « si c'est faux, on saute »).

### Table à connaître par cœur : les tests contre zéro en smali

| Opcode | Sens réel | Piège |
|---|---|---|
| `if-eqz` | `v == 0` | — |
| `if-nez` | `v != 0` | — |
| `if-ltz` | `v < 0` | — |
| `if-gez` | **`v >= 0`** | se lit comme « moins que zéro » alors que c'est l'inverse |
| `if-gtz` | **`v > 0`** | 0 ne branche pas |
| `if-lez` | `v <= 0` | — |

Les formes **à deux registres** (`if-le v4, v3`, `if-ge v2, v3`) sont, elles, littérales.

### Leçon de mesure — compter le rouge sans se tromper de critère

Pour vérifier qu'aucune image ne portait plus la marque d'avant, j'ai d'abord mesuré la **distance
au rouge** `#a30f2c` avec une tolérance de 45 (somme des écarts par canal). Verdict : 41 à 57 % de
chaque capture du tutoriel... ce qui était **faux**. Sur des pixels presque noirs, une tolérance de
45 est énorme : `(10,12,0)` — un vert sombre — passe pour du rouge. La bonne mesure regarde le
**déséquilibre des canaux** (`R > G + 25` et `R > B + 25`) : le fond réel de ces captures était un
sombre neutre ou verdâtre venu des vignettes, et le rouge de marque ne pesait que 2 % (et 37 % pour
`tut_5`, un panneau au thème rouge). Un chiffre qui décide d'un plan de travail se vérifie sur des
pixels dont on sait ce qu'ils sont — pas sur une distance calculée au jugé.

## 7. Pièges d'environnement (payés comptant)

- **Deux `adb` se battent.** BlueStacks embarque `HD-Adb.exe` (1.0.36), scrcpy des platform-tools
  (1.0.41). Chaque appel tue le serveur de l'autre → `error: closed` **en plein transfert**. Le
  script choisit un binaire et s'y tient ; il redémarre le serveur une fois en cas de coupure.
- **Aucun timeout sur `adb install`.** Un `timeout 20` a tué une installation en plein transfert et
  figé l'`adbd` de l'émulateur. Le script ne met aucun timeout sur l'installation et bascule sur
  `push` + `pm install` si le flux direct est refusé.
- **Git Bash réécrit les chemins absolus** passés aux binaires natifs : `/data/local/tmp/x.apk`
  devient `C:/Program Files/Git/data/local/tmp/x.apk`. D'où `MSYS_NO_PATHCONV=1` et
  `MSYS2_ARG_CONV_EXCL='*'` dans les scripts.
- **`adb devices` peut revenir vide** quand le serveur redémarre → relance + parsing explicite.
- **Deux transports pour le même émulateur** : BlueStacks répond sur `emulator-5554` **et** sur
  `127.0.0.1:5555`. Le second accepte `push` et `install` mais ne rend aucun verdict `app_process`
  (« aucun verdict SELFTEST dans la capture ») — panne silencieuse, le script croyait avoir testé.
  `test-selftest.sh` choisit donc explicitement `emulator-*` quand `--serial` n'est pas donné, et
  affiche les transports disponibles quand ils sont plusieurs.
- **`logcat -v time` change le format** : `I/Twouich (23733): …`. Un `grep 'Twouich : '` ne matche
  alors **rien** — erreur commise, et elle fait croire à une panne qui n'existe pas.
- **Aucun mode arrière-plan** dans cet environnement : une capture se fait dans une seule commande
  synchrone (enchaîner ouverture du flux + `logcat`).

## 8. Reste à faire

1. ~~Prouver le retrait effectif d'une pub~~ — **fait le 15/09/2026** : self-test embarqué vert sur
   l'appareil (`SELFTEST 18/18`, `623 -> 328 octets, segments pub retires : 3`), donc plus besoin
   d'attendre une coupure. **Capturé en réel le 18/09/2026** : session live sur une chaîne à forte
   charge publicitaire, 571 pods retirés / 5974 segments, 0 fuite au rejouage des playlists brutes
   capturées (détail en §5).
2. ~~**Publication de la release** `v1.5.10x-twouich1`~~ — **fait le 15/09/2026** : tag exactement
   égal au `VersionName`, APK `Twouich_beta144_ttv1.apk` (SHA-256 `a80be686…`) + `changelog.html`
   joints.
3. ~~**Parcours réel de l'updater**~~ — **fait le 15/09/2026** : release intermédiaire
   `v1.5.10x-twouich2` (versionCode 146) publiée, app installée en 145 mise à jour **par elle-même**
   (dialogue ouvert seule, téléchargement, passage à l'installeur système), octets installés
   identiques au livrable au SHA-256 près (voir §5). Reste, côté produit :
   - **canal Beta, installation neuve** — ~~toute installation neuve démarrait en Beta~~
     **corrigé structurellement le 16/09/2026 (v1.0.2, 149)** : `patch.py` étape 3b force
     `b.a = false`, donc `p()` n'écrit plus `pref_update_channel = "1"` et le défaut de `g()`
     (« 0 » = Stable) s'applique. Preuve par les octets installés : `base.apk` relu de l'appareil
     décodé → `a:Z` sans initialisateur (false), upstream `beta_144` → `a:Z = true` (contrôle
     négatif discriminant) ; garde-fou dans `test_smali_branches.py` (mordance vérifiée).
   - **canal Beta, installations existantes** — publier aussi une entrée `ReleaseType: 1` dans
     `update.json`, sinon les appareils hérités de S0undTV restés en Beta (comme celui du test)
     ne voient aucune de nos releases.
     **Décision produit (16/09) : pas d'entrée beta sur ce fork** — les installations 147/148
     restées en canal Beta doivent basculer en Stable dans les réglages (une fois) pour recevoir
     les mises à jour ; toute installation d'après la v1.0.2 démarre déjà en Stable.
     **Publication v1.0.2 faite le 16/09 au soir** : release `v1.0.2` (APK + `changelog.html`,
     tag = VersionName), `update.json` poussé APRÈS la release, README à jour (section + liens),
     `check-release.sh` vert de bout en bout (assets 200, octets servis = livrable).
     **Nettoyage GitHub le même soir** : releases de test `v1.5.10x-twouich1/2` supprimées et
     tags hérités de S0und (`beta`, `v1.4` … `v1.5.10x`) supprimés — ne restent que les
     `v1.0.0/1/2`. Le tag `beta` supprimé casse l'URL beta gravée dans l'app, cohérent avec
     l'absence d'entrée beta.
   - ~~**comparaison de version** — remplacer le plancher figé (144) par la version installée~~ —
     **fait le 15/09/2026** : la comparaison lit désormais `PackageManager.getPackageInfo()` et ne
     propose une mise à jour que si la release est plus récente que la version installée
     (`test_smali_branches.py` le vérifie sur le code compilé) ;
   - ~~**accent rouge par défaut**~~ — **fait le 16/09/2026** : la famille `theme_red*` est
     **repeinte aux couleurs de marque** (`patch.py` étape 4b) plutôt que de déplacer l'index par
     défaut — l'accent 0 reste celui des installations existantes (préférence sauvegardée), il
     affiche désormais le violet Twouich, et son libellé de réglages devient « Twouich ». Mesuré
     sur l'appareil : plus aucun pixel des anciens accents (`#a30f2c`/`#db002c`), le violet
     `#7c22e8` occupe les zones de focus ; le rouge restant à l'écran est du **contenu** des
     chaînes (miniatures, pochettes), pas de l'interface.
4. ~~**CI GitHub Actions** : rejouer `patch/build.sh` à chaque push~~ — **fait le 16/09/2026** :
   `.github/workflows/build.yml` (run vert) rejoue la chaîne **sans signature** (`SKIP_SIGNING=1`
   sur `build.sh`) : tests sanitizer + branches, `apktool d` → `patch.py` → `apktool b`, contrôle
   des pages embarquées, APK non signé en artefact de diagnostic. Empreinte du jar apktool figée
   (vérifiée égale au jar local). Limites assumées : `test_brand.py` (polices Windows non
   redistribuables) et `test_apk.py` (APK signé requis) restent des contrôles du mainteneur.
   La CI a d'emblée prouvé sa valeur : 4 divergences local/CI trouvées et corrigées (numpy/Pillow
   manquants, garde-mot-de-passe avant la définition de SKIP_SIGNING, sonde de version tuée par
   `pipefail` sans arbre décodé, et surtout **chemin de fabrique `z3.1` vs `z3` selon la
   plateforme** — `find_factory()` localise désormais au lieu de supposer). Livrable v1.0.3
   régénéré après refactor : 2 173 entrées identiques au CRC, `dist/` restauré aux octets publiés.
   **Extension du 16/09 (soir) — CI signante** : le workflow a maintenant deux jobs. Sur branche,
   le job sans signature (comme avant) ; sur **push de tag `v*`**, un job signé publie l'APK +
   `changelog.html` sur la release du tag. La clé vit dans 4 secrets GitHub chiffrés
   (`KEYSTORE_B64`/`KEYSTORE_SHA256`/`KEYSTORE_PASS`/`KEY_ALIAS`), l'empreinte du keystore est
   vérifiée après restauration, `KEY_PASS` ne transite que par l'env de step, et `update.json`
   reste **manuel** (poussé après la release — piège 404 documenté) ; `test_apk.py` en CI tourne
   avec `ALLOW_UPDATE_JSON_LAG=1` pour tolérer ce décalage par design. `build.sh` corrige au
   passage un vrai bug : `KEY_PASS=""` écrasait la variable d'env (invisible en local,
   `keystore.properties` masquait le chemin env) — désormais `${KEY_PASS:-}`/`${KEY_ALIAS:-...}`.
   Garde-fou de publication : le tag poussé doit égaler le `VERSION_NAME` de `build.sh`.
   Validé par **répétition signée** (`workflow_dispatch` : keystore restauré + vérifié, v1+v2+v3,
   signature contrôlée, empreinte relevée, publication et contrôle d'octets ignorés, release
   v1.0.3 intacte). Le dispatch ne publie jamais : c'est le mode répétition.
5. ~~Rebranding~~ — **fait le 15/09/2026** : nom, écran de démarrage, icônes, bannière TV, icône
   adaptative, thème par défaut et pages embarquées sont passés à l'identité Twouich (voir §2 et
   §5). Les **images du tutoriel** (`tut_*.webp`) ont été remappées au lieu d'être recapturées (voir
   §2) : plus aucune marque d'avant ne subsiste dans l'APK, ni en texte ni en pixel.
   **Réserve levée le 16/09/2026** : l'**apparence par défaut** est couverte — la famille
   `theme_red*` (l'accent d'usine) est repeinte aux couleurs de marque (voir §8 point 3).

## 9. Journal

| Date | Événement |
|---|---|
| 2026-08/09 | Audit du dépôt et de l'APK ; constat que l'updater renvoyait vers S0und. |
| 2026-09-15 | Greffon anti-pub écrit, chaîne de build reproductible, `update.json`/README/FUNDING réécrits, audit + procédure de test rédigés. |
| 2026-09-15 | Premier test sur appareil : **lecture cassée** par 4 erreurs de branchement (voir §6). |
| 2026-09-15 | Correction + `test_smali_branches.py` (vérifié en réintroduisant les fautes : 4/7 et code de sortie 1). |
| 2026-09-15 | Session de 4 min sur BlueStacks : lecture OK, 131 nettoyages, 0 erreur, aucune pub servie par la chaîne. |
| 2026-09-15 | **Self-test embarqué** écrit et branché sur `MainApp.onCreate` ; deux pièges Dalvik payés en route (paire de registres *wide* → `VerifyError`, corrigé en `/range` ; `min()` calculé à l'envers dans la source factice). |
| 2026-09-15 | Self-test vert sur l'appareil : **18/18**, `playlist nettoyee 623 -> 328 octets, segments pub retires : 3` — le retrait d'une pub est enfin reproductible à volonté. |
| 2026-09-15 | Mesure de reproductibilité : 2172/2172 entrées identiques au CRC entre deux builds du même arbre, SHA-256 **différents** (horodatage ZIP d'apktool) → le hash publié identifie le fichier, pas la recette. |
| 2026-09-15 | **Release `v1.5.10x-twouich1` publiée** (tag = `VersionName`) avec l'APK refondu, `changelog.html` et ses notes ; l'APK installé a été relu depuis l'appareil (`pm path` + `pull`) — SHA-256 **identique** à celui publié, self-test **18/18** sur ces octets. |
| 2026-09-15 | Ce self-test a trouvé un **cinquième bug** (compteur qui comptait les balises) ; corrigé, garde-fou ajouté à `test_smali_branches.py` (9 vérifications) et script `patch/test-selftest.sh` livré. |
| 2026-09-15 | **Refonte d'identité** : l'app devient visuellement Twouich (écran de démarrage, icônes, bannière, nom, thème violet, pages embarquées). Générateur `patch/branding/make_brand.py` (3 pistes, arborescence `res/` prête à recopier) et étape 2 de `patch.py`. |
| 2026-09-15 | Le balayage des pixels a trouvé **trois visuels portant le logo S0und dans l'interface** (`header_logo`, `app_icon`, `channel_logo`) qu'aucune référence de code ne signalait — remplacés, et le balayage est devenu un test (`test_brand.py`, 12 assertions, garde-fou vérifié par 4 mutations). |
| 2026-09-15 | Écran de démarrage Twouich **capturé sur l'appareil** pendant un lancement réel ; self-test anti-pub toujours vert sur l'APK reconstruit (18/18, dex frais et app installée). 40 contrôles dans `patch.py`. |
| 2026-09-15 | **Captures du tutoriel remappées** (6 images, 1920×1080) : les cadres d'annotation et le panneau du thème rouge passent à la palette Twouich — 2,3–36,7 % de rouge → **0,0000 %**, écart de luminance moyen < 1,9/255. Choix explicite : l'émulateur plafonne à 720p, les recapturer aurait flouté des images 1080p pour une mise en page inchangée. 31 assets, 46 contrôles, `test_brand.py` 14 assertions. |
| 2026-09-15 | Erreur de mesure corrigée en route : ma première quantification du rouge (distance euclidienne, tolérance 45) comptait les pixels presque noirs comme rouges et annonçait 41–57 % — la bonne mesure est le déséquilibre des canaux. Leçon consignée en §6. |
| 2026-09-15 | **Updater durci** : la comparaison ne repose plus sur le plancher figé 144 ; le code compilé lit désormais `PackageManager.getPackageInfo()` et ne propose une mise à jour que si la release est plus récente que la version installée. |
| 2026-09-15 | **v1.0.0** : changelog neuf limité aux nouveautés Twouich, lien vers le projet source et crédits ; identité puffy 3D violette générée et livrable `dist/Twouich_v1.0.0.apk` vérifié. |
| 2026-09-15 | **Deux défauts de l'updater trouvés par ce test**, invisibles en lecture de code : le **canal Beta** n'accepte que les entrées `ReleaseType: 1` (donc notre entrée stable ne produisait aucun dialogue — la plupart des installations héritées sont en Beta), et la comparaison se fait contre un **plancher figé à 144** au lieu de la version installée (l'app propose d'installer la version qu'elle exécute). Consignés, non corrigés en silence. |
| 2026-09-16 | **Release `v1.0.0` publiée** (tag = VersionName, APK + `changelog.html`) ; `check-release.sh` vert : `update.json` → tag → assets → octets servis identiques au livrable. Installation **fraîche** sur l'émulateur : 147/v1.0.0, self-test **18/18** d'emblée, et 4 relances **sans aucun dialogue de mise à jour** — l'updater ne propose plus la version qu'il exécute (procédure : `TEST-DEVICE.md` § 0). |
| 2026-09-15 | `test_apk.py` ne confrontait pas le livrable à `update.json` : il lit maintenant le `versionCode`/`versionName` dans le manifeste **binaire** (ni aapt2 ni apktool requis pour vérifier) et exige l'accord avec `update.json` — le trou par lequel un décalage de version passait sans bruit. 13 verdicts. |
| 2026-09-15 | `patch/check-release.sh` : la vérification de publication (encore manuelle) devient une commande — `update.json` → tag → assets → **octets réellement servis** comparés au livrable local. Contrôle négatif joué (version inexistante → 404 + sortie 1). |
| 2026-09-15 | Constaté sur l'appareil en passant par ses réglages : thème « Dark grey (default) » + accent **« Red (default) »** → l'app, réglages d'origine, **s'affiche encore rouge** (mesuré `#a00f2b` sur le commutateur). La refonte a couvert les assets et les textes, pas l'accent par défaut. Consigné en §8 (deux correctifs possibles, dont un choix). |
| 2026-09-16 | **Accent d'usine repeint** : la famille `theme_red*` passe aux couleurs de marque et le libellé « Red (default) » devient « Twouich » (`patch.py` étape 4b, contrôle `test_apk.py` sur `resources.arsc`). Mesuré sur l'appareil après mise à jour (`install -r`) : **0 pixel** des anciens accents UI, violet de marque `#7c22e8` sur les zones de focus, self-test toujours **18/18** — le rouge restant à l'écran appartient aux miniatures des chaînes (contenu), pas à l'interface. |
| 2026-09-16 | **Canal Beta corrigé à la source (v1.0.2, 149)** : `patch.py` étape 3b force `b.a = false` — le flag beta gravé upstream faisait démarrer toute installation neuve en canal Beta, muet pour une publication stable (cause racine documentée le matin même dans `TEST-DEVICE.md`). Preuve : installation fraîche 149/v1.0.2 sur l'émulateur, `base.apk` relu (`pm path` + `pull`) → SHA-256 = livrable, re-décodage → `a:Z` sans initialisateur (false) là où l'upstream décode `a:Z = true` ; self-test **18/18** d'emblée ; rail de réglages focus en violet `#7c22e8`. Garde-fou `test_smali_branches.py` porté à 11 vérifications (mordance vérifiée par mutation). Limite de terrain : lecture directe des préférences impossible sur cet émulateur (pas de root, pas de `run-as`, `adb backup` bloqué) et réglages verrouillés derrière la connexion Twitch — la preuve du canal effectif sur appareil connecté reste à faire (§ 8). |
| 2026-09-16 | **v1.0.2 installée sur la Freebox Pop du foyer (192.168.1.24, Android 10)** : l'ADB réseau n'était pas appairé (dialogue d'autorisation validé à la télécommande) ; la S0undTV officielle beta_144 qui y était a été désinstallée (signature différente) puis Twouich installée — session Twitch à reconnecter une fois. Self-test **18/18** dès le premier lancement, aucune erreur, updater silencieux (149 = dernière). |
| 2026-09-16 | **Release `v1.0.2` publiée** (tag = VersionName, APK + `changelog.html`), `update.json` poussé après la release, README mis à jour ; `check-release.sh` vert de bout en bout (assets servis 200, SHA-256 servi = livrable). **Décision produit : aucune entrée beta** — releases de test `v1.5.10x-twouich1/2` supprimées et **tous les tags hérités de S0und supprimés** (`beta`, `v1.4`…`v1.5.10x`) : le dépôt GitHub ne montre plus que `v1.0.0/1/2`, aucun vieux numéro de version nulle part. Les installations 147/148 restées en Beta doivent basculer en Stable dans les réglages pour recevoir les mises à jour. |
| 2026-09-16 | **Release `v1.0.3` (150) publiée** — version de maintenance sans changement fonctionnel, destinée à valider le self-update de l'app 149 installée sur la Freebox. Piège d'asset évité de justesse : le `changelog.html` uploadé d'abord était la copie v1.0.2 d'avant build (remplacé via `gh release upload --clobber`, et un second asset créé à tort par le suffixe `#label` supprimé) ; le `curl` peut ensuite servir un cache CDN périmé — l'API des assets (taille + `updated_at`) fait foi, et `check-release.sh` (« octets servis ») est vert. Observation du self-update **en attente** : la Freebox est repassée `unauthorized` (dialogue ADB à ré-accepter sur l'écran) et la session Twitch y est absente depuis l'installation fraîche — l'updater ne s'exécute qu'après connexion. |
| 2026-09-16 | **Self-update validé sur le vrai téléviseur (Freebox Pop, Android 10) : 149 → 150.** Cold start → `UpdateActivity` ouverte seule (« v1.0.3 / 150 ») → « Install update » → URL exacte du tag → `PackageInstallerActivity` → installation → octets installés = livrable (`147562df…`), session Twitch conservée (22 chaînes), self-test **18/18**, relance sans dialogue. **Le correctif canal Stable (v1.0.2) est prouvé en production** : la Freebox, installée fraîche en 149, a vu le dialogue sans aucune bascule manuelle. Reste la même limite qu'en § 0.2 : le « INSTALLER » du système est le seul geste humain du parcours. |
| 2026-09-16 | **CI GitHub Actions verte** (`.github/workflows/build.yml` + mode `SKIP_SIGNING=1` de `build.sh`) : la chaîne est rejouée sans clé à chaque push. Quatre divergences local/CI corrigées en route — dépendances numpy/Pillow du test de marque, ordre garde-mot-de-passe/définition SKIP_SIGNING, sensibilité `pipefail` de la sonde de version sans arbre décodé, et le chemin de fabrique `z3.1`/`z3` propre au décodage Windows (`find_factory()` localise, échoue bruyamment si absent). Le livrable v1.0.3 reconstruit après refactor reste **identique au CRC** (2 173 entrées) aux octets publiés — la recette est redevenue portable sans changer un seul octet du produit. |
| 2026-09-16 | **CI signante** : secrets keystore chiffrés, job de publication automatique sur tags `v*` (APK + changelog.html), `update.json` resté manuel, répétition signée validée par dispatch. Bug réel corrigé au passage : `KEY_PASS=""` écrasait l'environnement dans `build.sh`. |
| 2026-09-16 | **Synchronisation README/CHANGELOG automatisée** : `patch/sync-readme.py` (mode `sync` correcteur, `--check` pour la CI) pointe le bloc d'installation vers l'APK de la version la plus récente et insère les sections de version manquantes — sans jamais réécrire les sections existantes. Contrôle câblé dans le job CI `build` ; garde prouvé par mutations (exit 1) et autoréparation vérifiée. |
| 2026-09-16 | **Chemin tag → publication validé en réel** : bump 151/v1.0.4 → tag poussé → CI signante a construit, signé, **créé la release** et publié APK + changelog.html, puis vérifié ses octets servis (SHA CI `dcaa1efd…`). `dist/` aligné sur les octets CI (horodatages ZIP apktool), `update.json` poussé après (verdict check-release rouge ~5 min le temps du CDN raw — attendu), chaîne verte ensuite. Au passage : édition web du README intégrée sans l'écraser, et `sync-readme.py` durci (opt-out sections + bloc remanié toléré). |
| 2026-09-16 | **Self-update 150 → 151 validé sur la Freebox, avec APK signé par la CI** : dialogue v1.0.4/151 ouvert seul au cold start, URL du tag en logcat, « INSTALLER » système piloté par ADB, octets installés = octets servis CI (`dcaa1efd…`), session Twitch conservée (22 chaînes), self-test 18/18. La chaîne complète push → CI signante → self-update sur TV réelle est désormais prouvée de bout en bout. |
| 2026-09-18 | **Endpoints tiers : tous vivants, point clos.** Lecture statique du smali décompilé (`work/decoded/`) : 7TV appelle **déjà l'API v3** (`7tv.io/v3/emote-sets/global` + `users/twitch/<login>` — l'hypothèse d'un ancien endpoint cassé est invalidée), BTTV/FFZ/robotty répondent 200 (robotty = opt-in via réglage), le chat charge réellement sur l'appareil (`FFZ Done`/`BTTV Done`/`7TV Done`, 45 emotes globales 7TV). Le « proxy Tokyo » n'existe pas : le seul `"Tokyo"` du smali est une table de fuseaux horaires (`tyo`/`Tokyo`, `P6/d.smali`). Aucun service de pronouns dans la build. Rien à patcher. |
| 2026-09-18 | **Première coupure pub réelle capturée et retirée** : radar multi-chaînes côté PC (token GQL anonyme → usher → variante, dumps bruts au moment d'une pub) pour cibler une chaîne avec pod en cours, puis session sur l'appareil — 1782 nettoyages, 571 pods retirés, 5974 segments, max 22/pod. Les 34 playlists brutes rejouées dans le miroir : **0 fuite** ; une fixture de régression figée (`patch/tests/fixtures/ssai-2026-09-18.m3u8`, session/tracking neutralisés). Le marqueur servi est exactement celui des 3 règles existantes — l'hypothèse d'un format non reconnu est invalidée, aucune règle à ajouter. `test_sanitizer.py` porté à 33 assertions (compteurs synchronisés dans AGENTS.md/AUDIT.md). |
| 2026-09-18 | **Build reproductible au sens strict.** Trois sources de non-déterminisme éliminées : (1) horodatage ZIP d'apktool — `patch/normalize_apk.py` réécrit les 4 octets date+time de chaque entrée (LFH + CD) vers 1980-01-01 au niveau octet, **avant** signature (les blocs v2/v3 couvrent le CD), idempotent, harnais `test_normalize_apk.py` (9 assertions : CRC/contenu intacts, faux EOCD dans une entrée stockée ignoré via recoupement de l'EOCD, seuls octets touchés = horodatage, idempotence, --check) ; câblé en étape 4b de `build.sh` avec double contrôle + garde `--check`. (2) Date du changelog embarqué — `patch.py` utilisait `datetime.date.today()` : remplacée par `--release-date` (constante `VERSION_RELEASE_DATE` dans `build.sh`, comme `APK_NAME`). (3) Fins de ligne des pages embarquées — Python traduisait CRLF (Windows) / LF (Linux) au `write_text` : canonicalisation LF explicite (stockage brut dans l'APK). Prouvé : deux builds successifs → SHA-256 identiques (`d5889b87…`) ; rebuild Windows vs APK publié par la CI Linux → 2168/2172 entrées CRC-identiques, les 4 écarts s'expliquant sans ambiguïté (3 entrées de signature META-INF + `classes2.dex` contenant la sentinelle du 18/09, absente du build CI du 16/09). Le livrable normalisé installé sur appareil : self-test 18/18, filtre actif, sentinelle muette. `dist/` restauré aux octets CI (`dcaa1efd…`). |
| 2026-09-18 | **Sentinelle « marqueur pub inconnu » implantée** : détection automatique si Twitch sert un jour un format hors des 3 règles. `PlaylistSanitizer.b(String)` émet `Log.w("Twouich", "marqueur pub inconnu : …")` (1 ligne max/playlist, drapeau reseté par playlist, appelé uniquement hors zones déjà reconnues) sur deux familles : `#EXT-X-CUE*` inconnu, et DATERANGE avec attributs `X-TV-TWITCH-AD-*` sans `stitched-ad` ni `quartile`. Logique prouvée dans le miroir d'abord (leçon des 5 bugs de branchement — le portage smali a de nouveau révélé un branchement inversé dans la sonde, attrapé avant le build), sonde `SentinelProbe` (`SENTINEL 6/6` sur appareil via app_process), verdict 🚨 branché dans `analyze_device_log.sh` **avant** les autres (un format renommé masquerait les compteurs), et silence vérifié en live réel (>20 min, 0 alerte). `test_sanitizer.py` à 48 assertions. Sémantique de nettoyage inchangée — observation pure. |
| 2026-09-18 | **Les « Source error » de fin de pod expliquées** : `m3.l$d` = `PlaylistResetException` d'ExoPlayer — la playlist pub est un flux de substitution (`MEDIA-SEQUENCE:0`, `EXT-X-START`) et la renumérotation au retour du contenu force une resync de 2–4 s, récupérée seule. Effet de bord inhérent au stripping, non corrigeable sans re-reset de session usher ; toutes les variantes restent en contenu pendant un pod (vérifié), donc pas d'atténuation possible par bascule de variante. |
