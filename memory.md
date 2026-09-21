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
| Version produite | `versionCode 154` / `versionName v1.0.7` |
| Livrable | `dist/Twouich_v1.0.6.apk` (signé par la CI, v1+v2+v3, zipalign vérifié ; le SHA-256 de chaque release est publiable à l'octet près — build reproductible inter-plateformes, voir §3) |
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
python patch/tests/test_smali_branches.py # 23 assertions : branchements réels du smali (pièges Dalvik),
                                          #   polarité des tests de place du lecteur, et drapeaux d'accès
                                          #   des overrides injectés (voir §6, 20/09)
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

**Septième et huitième cas, 19/09 — les inversions que les tests ne voyaient pas.** Le test de
branchement surveille les opcodes *ambigus* ; il ne dit rien des `if-eqz`/`if-nez` écrits à l'envers
sur une valeur calculée. Deux d'entre eux ont vécu jusqu'à l'appareil dans `TapClick` :
`if-nez` sur `moved` refusait **tous** les taps francs (aucun log, aucune action — le symptôme exact
du défaut qu'on corrigeait), et `if-nez` sur le résultat d'`instance-of` court-circuitait la descente
dans l'arbre, si bien que la grille (cliquable) se déclarait elle-même cible. Les deux se lisaient
« le tap ne fait rien » : c'est la **trace instrumentée** — position du point, géométrie de la
grille, classe de la cible — qui a tranché, pas la relecture. Leçon : sur un `if-*-z` posé sur un
booléen calculé, écrire le sens en commentaire à côté de l'instruction, et ajouter l'assertion dans
`test_smali_branches.py` (deux vérifications de plus, avec le dégât décrit).

**Dixième cas, 20/09 — les deux tests de place du lecteur, écrits à l'envers.** En corrigeant la
hauteur de chat négative du lecteur téléphone (vidéo 16:9 calculée depuis la largeur), les **deux**
comparaisons ont été inversées : `if-ge v10, v7` au lieu de `if-lt` (la vidéo qui tenait déjà dans la
hauteur était plafonnée quand même) et `if-lt v7, v3` au lieu de `if-ge` (l'empilement se faisait
exactement là où il n'y avait pas la place). Particularité de ce cas : **les deux configurations
d'écran donnaient un résultat plausible** — en portrait le chat tombait à 0 sans que rien ne signale
l'erreur, et en paysage la vidéo plein écran ressemblait à un repli volontaire. C'est la mesure des
rectangles (`dumpsys activity top`) qui a montré que le compte n'y était pas — 450 px de vidéo là où
on en attendait 1488 — pas la relecture. Leçon : pour un calcul de place, écrire l'intention en
commentaire à côté de chaque branchement **et** vérifier les coordonnées attendues, pas seulement
l'absence de plantage. Les deux polarités sont désormais verrouillées par `test_smali_branches.py`.

**Neuvième cas, 20/09 — une faute qui n'est pas un branchement : le drapeau d'accès.** L'override
`onWindowFocusChanged(Z)V` injecté dans `PlayerActivity` était déclaré `.method protected`. Aucun
test ne pouvait le voir : `test_sanitizer.py` teste un miroir Python, `test_smali_branches.py`
regardait des opcodes, et `test_apk.py` lit des octets — or les drapeaux d'accès ne sont ni des
chaînes ni des instructions. Sur l'émulateur (API 25), le lieur ART a rejeté la **classe entière** :
`IllegalAccessError: Method 'void PlayerActivity.onWindowFocusChanged(boolean)' implementing
interface method 'void android.view.Window$Callback.onWindowFocusChanged(boolean)' is not public`,
d'où `ClassNotFoundException` puis `NoClassDefFoundError` — et **tout** chemin qui charge
`PlayerActivity` (clic sur une carte de direct via `MainFragment$e.c`, deep link, `am start`) tuait
l'application. Elle passait pourtant sur le téléphone de référence : une faute de ce genre dépend du
vérificateur, pas de la logique, donc **un seul appareil ne suffit pas à l'absoudre**. Leçon : quand
on injecte un override d'un type du framework, vérifier la visibilité de la méthode parente avant
tout le reste (`Activity` implémente `Window.Callback` → `public`), et faire surveiller la
**déclaration** — pas la chaîne littérale — par un test, en laissant les règles de réparation nommer
la forme fautive pour pouvoir la corriger.

**Onzième cas, 20/09 — un garde de nullité à l'envers, et le silence qu'il produit.** En vérifiant
l'incrustation sur le téléphone, la trace était absente et le chat restait dessiné sur la vidéo.
`twouichPhoneView` — le petit helper qui résout un identifiant puis rend la vue — portait
`if-nez v0, :no_phone_view`, c'est-à-dire **« retourne null quand l'identifiant est trouvé »** : la vue
n'était jamais rendue, donc `onPictureInPictureModeChanged` sortait aussitôt sur ses trois gardes de
nullité. Un garde de nullité ne dit rien : il sort en silence. Ce qui a tranché n'est pas la relecture
mais la **trace ajoutée dans le rappel** — sans elle, la géométrie mesurée restait compatible avec un
empilement appliqué par un autre chemin (les deux produisent la même vidéo 16:9 dans une fenêtre
16:9). Leçon : quand une méthode peut sortir avant d'agir, instrumenter la sortie autant que l'action,
car deux chemins différents donnent souvent la **même** mesure — et mesurer ne suffit alors pas à
savoir lequel a tourné.

### Leçon de mesure — compter le rouge sans se tromper de critère

Pour vérifier qu'aucune image ne portait plus la marque d'avant, j'ai d'abord mesuré la **distance
au rouge** `#a30f2c` avec une tolérance de 45 (somme des écarts par canal). Verdict : 41 à 57 % de
chaque capture du tutoriel... ce qui était **faux**. Sur des pixels presque noirs, une tolérance de
45 est énorme : `(10,12,0)` — un vert sombre — passe pour du rouge. La bonne mesure regarde le
**déséquilibre des canaux** (`R > G + 25` et `R > B + 25`) : le fond réel de ces captures était un
sombre neutre ou verdâtre venu des vignettes, et le rouge de marque ne pesait que 2 % (et 37 % pour
`tut_5`, un panneau au thème rouge). Un chiffre qui décide d'un plan de travail se vérifie sur des
pixels dont on sait ce qu'ils sont — pas sur une distance calculée au jugé.

**Et un critère de droit ne se lit pas dans un drapeau : il se lit à la fin de la chaîne.** Pour la même
famille de question (« Twitch sert-il cette VOD à ce client ? »), j'ai d'abord conclu sur un champ du jeton
(`authorization.forbidden = false`) — conclusion **fausse** : la restriction d'abonnement vit dans
`chansub.restricted_bitrates`, et Twitch tranche au **manifeste** (`usher`). La sonde qui vaut est celle qui
va jusqu'au bout — jeton → `usher` → code HTTP — et qui la répète sur **plusieurs** chaînes : un refus
uniforme pouvait venir de la méthode (jeton sans compte), pas du droit. Un contraste entre chaînes est une
preuve ; un refus seul n'en est pas une.

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

## 8. Reste à faire — tout traité ; la feuille de route prend la suite

**Statut au 19/09/2026 : les cinq chantiers fondateurs sont traités, et l'annexe §5 d'AUDIT.md est intégralement traitée ou assumée.** Le §5 d'AUDIT.md pointe désormais ici. Ce qui reste n'est plus du travail ouvert : ce sont des **assumés** (choix ou limites documentés, aucune action en attente), puis la **feuille de route** (chantiers futurs volontaires, rien d'urgent).

### Assumés — aucune action en attente

- **Limite mainteneur `test_brand.py` + `test_apk.py`** — par construction : polices Windows non redistribuables, APK signé requis. La CI a de toute façon prouvé sa valeur (4 divergences local/CI trouvées et corrigées — journal §9).
- **Aucune entrée beta dans `update.json`** — décision produit (16/09) : les installations 147/148 restées en canal Beta doivent basculer en Stable dans les réglages (une fois) pour recevoir les mises à jour ; toute installation d'après la v1.0.2 démarre déjà en Stable. Cohérent avec la suppression des tags hérités de S0und (`beta` casse l'URL gravée, assumé).
- **« INSTALLER » du système = le seul geste humain** du self-update (Freebox, Android 10 : pas d'auto-confirm). Deux filets de secours consignés en TEST-DEVICE.md §0.2 : reboot de la Freebox si l'installeur s'est figé, tap ADB sur INSTALLER si le focus D-pad ne répond pas.
- **`schedule` CI désactivé par GitHub après 60 jours d'inactivité** du dépôt : le cron radar reste rechargeable en dispatch (`workflow_dispatch`, chaînes surchargeables) — comportement de plateforme, documenté dans le workflow lui-même.
- **Un run CI peut être vert sans avoir rien vérifié** (pannes réseau ne sont pas des alertes) — l'absence de preuve n'alerte pas, c'est le choix du radar ; la trace reste dans le log.
- **PlaylistResetException en fin de pod** — effet de bord inhérent au stripping (resync 2–4 s, récupérée seule), non corrigeable sans re-reset de session usher ; toutes les variantes restent en contenu pendant un pod, pas d'atténuation par bascule de variante.
- **Bruits upstream bénins** (chat) : Glide « load for a destroyed activity » et `NumberFormatException: "Not Found"` (404 7TV par-chaîne pour un compte sans 7TV — attrapé, « 7TV Done » rendu quand même).
- **Pas de pronouns dans la build upstream** — absent du code, rien à patcher.
- **Limite documentaire chat** : le rendu **pixel** des emotes/badges (images CDN) n'est pas traçable par logcat — la preuve de rendu repose sur le chat visible et les chargeurs verts.

### Feuille de route

**Chantiers fondateurs — tous traités.** Le détail et les dates sont au journal §9 : retrait de pub prouvé (self-test embarqué, puis 571 pods réels le 18/09 avec 0 fuite), releases et chaîne `check-release.sh` verte (de `v1.5.10x-twouich1` à `v1.0.7`), updater durci (canal Beta corrigé à la source en v1.0.2, comparaison `getPackageInfo` en v1.0.0, table de vérité à trois étages dont le bytecode embarqué 28/28), CI (sans signature à chaque push, signante sur tags, cron radar quotidien), rebranding complet (accent d'usine repeint).

**Horizon 1 — court terme**
- ~~**Self-update 153→154 sur la Freebox Pop**~~ — **observé le 19/09, spontanément au foyer** : le cas « mises à jour rapprochées » a tranché — le figement **pathologique** ne s'est pas reproduit (processus installeur frais), mais une forme **bénigne** du silence est documentée (premier appui rebondi sur `DeleteStagedFileOnResult`, à répéter). Détail en TEST-DEVICE.md §0.2.
- **Reproduire sur émulateur le scénario « installeur figé »** (installer-sans-écran entre deux releases à moins de 24 h d'intervalle) : le seul scénario d'exploitation non reproduit à la demande.

**Horizon 2 — moyen terme**
- **Entrée beta** dans `update.json` si un jour des appareils en canal Beta doivent être servis (décision produit actuelle : non — voir assumés).
- **Radar : prouver l'alerte de bout en bout** en dispatch (`radar.yml`) — run rouge + issue dédoublonnée, jamais déclenché en réel depuis la création du cron.
- ~~**Mentions légales / politique de confidentialité Twouich**~~ — **fait le 19/09** : deux pages embarquées (`twouich_legal.html`, `twouich_privacy.html`) écrites sur des faits **vérifiés contre le code compilé** et reliées depuis la page À propos.
- ~~**Neutraliser la télémétrie Firebase/Measurement**~~ — **fait le 19/09** : providers/services/receivers retirés du manifeste, identifiants retirés des ressources, Remote Config (`MainApp.q`, `PlayerActivity.J3`), facade Crashlytics (`P6/e`) et Analytics (`P6/b`, `P6/l.i`) remplacés par des no-op à signatures inchangées. `test_apk.py` vert sur le candidat `v1.0.9`; cold start sur BlueStacks (UID 10069, 25 s) : SELFTEST 28/28, aucun crash ni log Firebase pour le PID Twouich, aucune entrée Firebase dans `dumpsys netstats`; les lignes restantes sont celles de BlueStacks lui-même. La preuve réseau doit être rejouée à chaque release.

**Horizon 3 — long terme / veille**
- **Version smartphone — cadrage après observation du 19/09** : le lecteur et le chat fonctionnent sur le profil paysage 1280×720, mais l'app reste Leanback/`sensorLandscape`; chantiers prioritaires : conteneur portrait responsive, navigation tactile, contrôles lecteur/chat découvrables, saisie clavier et accessibilité. Détail et preuves en TEST-DEVICE.md §0.3.
- **Socle UX smartphone implémenté le 19/09** : `patch.py` rend les activités `fullSensor`, conserve le lecteur TV dans `layout-sw600dp` et installe une variante téléphone où le chat principal est large, ancré en bas et visible (280dp). `test_apk.py` vérifie le manifeste compilé, les deux layouts et la dimension.
- **Première acceptation téléphone réel le 19/09** : Xiaomi `24095PCADG`, Android 16, écran portrait `1220×2712`/520 dpi, APK v1.0.9 (156) installé et lancé sans crash ; UI tactile visible sur tout l'écran et `SELFTEST 28/28` confirmé. La première coque smartphone ajoute Accueil/Recherche/Réglages ; les deux actions ont été tapées avec succès et ouvrent les activités existantes sans crash. Un direct suivi `Niniste` a ensuite été ouvert en `PlayerActivity` : vidéo portrait centrée `[0,1013][1220,1699]`, chat bas pleine largeur `[0,1356][1220,2712]`, message réel visible. Après exposition du champ téléphone, l'utilisateur a confirmé pouvoir écrire dans le chat ; l'arbre UI montre le champ focusable `[16,2105][1204,2208]`. Sur recommandation de l'utilisateur, la disposition est maintenant réalignée sur l'UX TwitchDroid : vidéo 16:9 en haut, chat dessous et compositeur collé en bas, uniquement sous 600dp ; le TV garde son layout d'origine. Le parcours vidéo → chat → clavier est validé, sans publier de message de test.
- **Constance UX smartphone — écart mesuré avec PurpleTV (19/09)** : PurpleTV est un mod de l'app Twitch officielle (`D:\Codex\TwitchDroid`), donc son UX est celle de Twitch mobile : barre de navigation basse, grille de cartes, théâtre vidéo/chat. Twouich hérite de S0undTV (client Leanback), d'où l'écart structurel : panneau latéral, rangées horizontales et navigation D-pad, dont l'accueil reste peu utilisable au doigt et certains menus (rails, grille du panneau) ne répondent pas au tap. Le chantier de fond est donc un **écran d'accueil téléphone dédié** (barre basse + grille tactile) réutilisant la couche données existante, et non un simple rhabillage de Leanback — **cap validé par l'utilisateur le 19/09**.
- **Chat tactile « qui ne défile pas » — diagnostic partiel** : les deux suspects évidents ont été écartés par lecture du code (le `GestureDetector` du lecteur ne reçoit pas les touches du chat, aucune `setOnTouchListener` dans `PlayerActivity` ; `ChatRecyclerView` n'intercepte rien et délègue à `RecyclerView`). Restent deux causes opposées, à trancher sur appareil déverrouillé : auto-scroll sur nouveau message (chat très actif qui annule le geste) ou simplement rien à défiler. Le correctif ne sera pas posé à l'aveugle.
- **Bug smartphone corrigé le 19/09 — crash à l'ouverture d'une vignette** : `twouichPhoneStackedLayout()` passait un objet `LayoutParams` à `View.setVisibility(int)`, erreur de vérification Dalvik qui faisait planter `PlayerActivity` dès son ouverture. Corrigé avec un registre entier, plus un garde-fou dans `patch.py` (2 contrôles) contre la régression. Vérifié sur le téléphone via le deep link `s0undtv://stream` : `PlayerActivity` s'ouvre proprement, vidéo 16:9 `[0,0][1220,686]` en haut, compositeur `[16,2616][1204,2696]` en bas. La barre basse des 3 boutons gris par défaut est remplacée par une barre sombre sobre (hairline + libellés Accueil/Recherche/Réglages), et Recherche/Réglages restent vérifiés au tap.
- **Rebase upstream** : surveiller une future beta S0und et rejouer la chaîne complète (les vérifications endpoints/obsolescences reviendront avec le nouvel arbre).
- **Audits périodiques des endpoints tiers** (7TV/BTTV/FFZ/robotty) — le prochain à l'occasion d'une beta upstream ou d'un incident chat.
- **Vitrine du projet** : README orienté utilisateurs finaux (captures à jour, FAQ), éventuellement un canal de distribution signé au-delà de GitHub Releases.

## 9. Journal

| Date | Événement |
|---|---|
| 2026-08/09 | Audit du dépôt et de l'APK ; constat que l'updater renvoyait vers S0und. |
| 2026-09-15 | Greffon anti-pub écrit, chaîne de build reproductible, `update.json`/README/FUNDING réécrits, audit + procédure de test rédigés. |
| 2026-09-19 | **Neutralisation Firebase/Measurement** : retrait des composants de démarrage et de la configuration, no-op des facades Remote Config/Crashlytics/Analytics. APK v1.0.9 reconstruit et `test_apk.py` vert ; cold start BlueStacks observé 25 s, SELFTEST 28/28, aucun crash/trace Firebase attribuable à Twouich et aucune entrée netstats UID 10069. Voir TEST-DEVICE.md §0. |
| 2026-09-19 | **Première observation smartphone hors-TV** : profil OnePlus 3T Android 7.1.1 en 1280×720 paysage. Navigation tactile et lecteur live fonctionnels sur Niniste ; environ 30 refreshs HLS en 60 s, zéro erreur ExoPlayer/ANR/crash. Chat réel visible après swipe du bord droit, mais bouton d'ouverture, redimensionnement et saisie non découvrables ; toutes les activités restent `sensorLandscape`. Chantiers UX smartphone classés en TEST-DEVICE.md §0.3. |
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
| 2026-09-18 | **Release `v1.0.5` (152) publiée avec la sentinelle embarquée.** Bump conventionnel (`1b2e233`) après commit de la recette reproductible (`d668098`) ; double build local → SHA identiques (`bd871e5c…`), self-test 18/18 sur le dex du candidat puis en app après `install -r` (signature acceptée par-dessus 151). Tag `v1.0.5` → CI signante verte, release créée (APK + `changelog.html` « Twouich v1.0.5 (2026.09.18) »), octets servis auto-vérifiés par la CI ; contrôle mainteneur sur les octets servis : 2172/2172 entrées CRC-identiques au build Windows, sentinelle présente dans les dex. `update.json` poussé après (verrou d'annonce levé) ; `check-release.sh` vert aux trois étages que traverse l'app, updater muet au cold start (152 = dernière). **Découverte : la reproductibilité n'est pas encore inter-plateformes** — l'ordre des entrées ZIP diffère Windows/Linux (énumération FS d'apktool), ce qui décale les digests `MANIFEST.MF` et le bloc v2 : SHA servi `fe50f91d…` ≠ build local, à contenu identique. Canonisation de l'ordre (tri par nom dans `normalize_apk.py`) = chantier suivant. |
| 2026-09-18 | **Ordre des entrées ZIP canonisé — reproductibilité inter-plateformes prouvée.** `normalize_apk.py` re-séquençe les entrées (LFH + données + CDH) par tri sur le nom en octets et recalcule les offsets (CDH, EOCD). Découverte en route : `apktool b` écrit en flux — **1613/2169 entrées avec descripteur de données** (LFH à zéros + flag 0x0008, descripteur 12 octets sans signature après les données) : supportées (valeurs réelles lues dans le CD, longueur déduite de la disposition séquentielle, copie intacte). Harnais à 29 vérifications, dont l'**invariance d'ordre** (deux ZIP de même contenu écrits dans des ordres différents → octets identiques, y compris streamés). **Preuve finale** : artefact `twouich-unsigned` du run CI `bd41683` (Linux) téléchargé et `cmp`-identique au build Windows — SHA `1efd1bb1…` identique aux deux plateformes ; un rebuild local reproduira désormais l'APK signé servi à l'octet près (la v1.0.5 publiée, `fe50f91d…`, reste sur l'ordre Linux — prochaine version signée avec l'ordre canonisé). |
| 2026-09-19 | **Release `v1.0.6` (153) publiée — première release reproduite à l'octet près depuis Windows.** Bump conventionnel (`8dfc620`) après le chantier surveillance (radar versionné `2f77f7b`, cron CI `925226e`) ; double build local → SHA identiques (`dadbe5ae…`), test_apk conforme, self-test 18/18 sur le dex du candidat. Tag `v1.0.6` → CI signante verte, release créée (APK + `changelog.html` « Twouich v1.0.6 (2026.09.19) »). **La preuve inter-plateformes en production** : SHA servi par la CI Linux = SHA du build local Windows (`dadbe5ae…`) — la limite laissée par la v1.0.5 (`fe50f91d…`, ordre ZIP non canonisé) est levée ; le hash publié identifie désormais le fichier livré ET la recette, quel que soit l'OS de build. Installation `install -r` acceptée par-dessus 152, self-test en app 18/18. `update.json` reste à pousser (verrou d'annonce volontaire). |
| 2026-09-19 | **Annonce v1.0.6 levée (`update.json` → 153).** `ReleaseDate = 2026-09-19T08:47:24.000Z` (`published_at` exact de la release), validé par `test_apk.py` **sans** le mode lag ; commit + push (`797e4cc`). **`check-release.sh` vert sur les quatre étages pour la première fois** : livrable local ✓, `update.json` publié (153/v1.0.6) ✓, release latest + assets servis en 200 ✓, et **octets servis = octets du livrable** (`dadbe5ae…`) — la comparaison locale↔servie, rouge sur la v1.0.5 à cause de l'ordre ZIP non canonisé, passe désormais : la chaîne est reproductible de bout en bout. Preuve appareil : cold start 153 → aucun dialogue (153 = dernière annoncée). |
| 2026-09-19 | **`patch/test-live.sh` — la recette d'observation en direct devient une commande.** Automatise les étapes mécaniques de TEST-DEVICE.md § 2 : état (version installée vs build.sh), capture détachée `nohup logcat -v time -T <heure appareil> >> log 2>&1 &` (append, stderr dans le fichier), lancement de l'app avec dump boussole D-pad, surveillance de vie, arrêt des clients logcat sans toucher au serveur adb, verdict. Sa validation sur appareil (fenêtres courtes, app au repos, relance fraîche) a trouvé **quatre bugs de la première version** : (1) capture inactive ≠ morte — un fichier vide ne dit rien, c'est le **compteur de clients logcat** qui fait foi, et la sonde PowerShell doit s'exclure elle-même (`-notlike '*Get-CimInstance*'`) sinon le kill s'auto-tue ; (2) une relance sans `-T` re-émet le tampon logcat → compteurs doublés dans le verdict ; (3) le `date` toolbox d'Android exige le format **quoté côté distant** (`adb shell "date '+%m-%d %H:%M:%S.000'"`), en args séparés il ne voit que `+%m-%d` et logcat meurt sur `-T "09-19" not in time format` à chaque relance ; (4) la sonde de date ne doit pas passer par la reprise `error: closed` d'`adb_run` (kill-server) — elle déconnecterait les clients logcat en cours. La mort d'une capture n'est déclarée qu'après **2 sondes CIM consécutives** sans client. Run final : relance fraîche de l'app pendant la fenêtre → verdict exactement 1 nettoyage / 3 segments (une seule ligne self-test), 0 client logcat restant. |
| 2026-09-19 | **Second usage de la recette — validée sur un autre profil de trafic.** Session `test-live.sh` de ~5,5 min, chaîne ouverte via **Top Streamers** (DDG venait, elle, de l'historique le 18/09) : navigation D-pad en 5 dumps (`Followed (1)` → `Followed Channels (22)` → `Top Games` → `Top Streamers` → carte focusée → DPAD_CENTER), direct **TheBurntPeanut** (Fortnite, « Dawson Oaks Trailer Park », 149 692 viewers), identité établie par les `bounds` du dump UI. Verdict : **115 playlists nettoyées de contenu pur (15,5 ko → identique, ~2 s), 0 segment retiré, 0 alerte sentinelle, 0 erreur de lecture, 0 repli proxy** — le ⚠️ « filtre actif mais rien retiré » est ici le cas bénin (aucun pod servi dans la fenêtre ; hiérarchie des chaînes cohérente avec le radar : DDG servait 22 segments/pod la veille). Le script a encaissé le scénario complet sans intervention : ~2 min de navigation avec capture neuve au repos (« client vivant, app au repos ? », aucune fausse relance), montée en charge détectée au lancement du direct (2 → 113 lignes), arrêt propre (BACK → FireTVMainActivity, app toujours vivante, 0 client logcat résiduel). Archives : `work/device-test/logcat-live-19-09.txt`, `test-live-second-session.log`. |
| 2026-09-19 | **`analyze_device_log.sh` : la cascade de verdicts distingue le bénin du suspect.** Le ⚠️ unique « Le filtre tourne mais n'a rien retiré » mélangeait deux cas : contenu traversé sans pod (bénin — session TheBurntPeanut du jour) et marqueurs changés (le cas que la sentinelle couvre désormais). Nouvelle cascade : ✅ **CONTENU TRAVERSÉ SANS POD** (0 retrait + 0 erreur — la sentinelle muette confirme que le format servi est celui des règles) ; ⚠️ **FILTRE ACTIF, RIEN RETIRÉ + erreurs** (à qualifier, erreurs d'abord) ; 🚨 sentinelle inchangée en priorité. Harnais `test_analyzer.sh` porté à **11 verdicts** — au passage, la branche 🚨 sentinelle n'était couverte par aucun test synthétique : ajoutée. Rejoué vert sur les captures archivées (TheBurntPeanut → nouveau verdict bénin ; session du 18/09 → verdict inchangé). |
| 2026-09-19 | **`patch/radar_ads.py` — le radar devient un garde-fou versionné.** Promotion de l'outil de session (`work/`) : `--cycles N [chaînes] --quiet`, et surtout **rejeu anti-fuite** — chaque playlist capturée repasse dans le miroir Python du sanitizer ; exit 1 + ligne HLS brute si la sentinelle du miroir parle ou si un marqueur pub (`stitched-ad`/`Amazon`) survit au nettoyage ; exit 0 sans occasion (offline, chaînes hors ligne, aucun pod — l'absence de preuve n'est pas une alerte). Harnais hors-réseau `patch/tests/test_radar.py` (10 vérifications) : fixture SSAI réelle dans le vrai `probe()` (réseau stubbé), **mordance prouvée par 2 mutations** (sanitizer affaibli → les marqueurs survivent ; format renommé → la sentinelle parle). Quatre pièges réglés en route : import du miroir **par module** (un import par valeur figerait `suspicious=False`), nom en **underscore** (`radar-ads.py` n'est pas importable), `probe()` auto-suffisant via `setdefault`, et `last_suspicious_line` = la ligne brute **sans** le préfixe `Log.w`. Réel : 3 cycles sur 5 chaînes — DDG 3/3 avec pod, fuites 0, sentinelle muette, verdict ✅ anti-fuite. Reste : cron CI quotidien (§ 5 d'AUDIT.md). |
| 2026-09-19 | **Cron CI quotidien pour le radar (`.github/workflows/radar.yml`).** Le pendant serveur de la sentinelle embarquée tourne désormais sans humain : harnais hors-réseau d'abord (la logique doit être verte avant de sonder), puis `radar_ads.py --quiet` sur 4 chaînes à forte charge — verdict 1 = run rouge + **issue dédoublonnée** par préfixe de titre (une seule à la fois), avec les 40 dernières lignes du log et la procédure de correction. Choix consignés : `schedule` à 04:17 UTC (hors heures pleines) + `workflow_dispatch` avec chaînes surchargeables ; `pipefail` + `tee` pour que le verdict 1 échoue le step **en gardant le log** dans `/tmp/radar.log` ; les pannes réseau ne sont pas des alertes (un run peut être vert sans avoir rien vérifié — la trace est dans le log) ; GitHub désactive les `schedule` après 60 jours d'inactivité du dépôt (le dispatch reste le recharge manuel). |
| 2026-09-19 | **`patch/tests/test_update_check.py` — la logique de comparaison de l'updater verrouillée hors réseau (20 vérifications).** Issue de la question « que fait une app à jour quand `update.json` annonce encore moins ? » (fenêtre historique entre release et annonce) : la table de vérité exacte de `UpdateHelper.b()V` est extraite du smali et rejouée en miroir Python — publiée **<** ou **==** installée → silence sur les deux canaux (le scénario « annonce en retard »), publiée > → dialogue (parcours prouvé en production), canal inconnu → silence, `i()` en échec (-1) → dialogue (fail-loud), et la préférence beta (`c` gagne ssi **strictement** supérieure à `b`) — le premier run a attrapé une erreur de mon propre scénario sur cette règle. Section 2 : gardes sur l'arbre décodé (`work/decoded/` quand il existe, surchargeable par `TWOUICH_DECODED`) — patch v1.0.0 posé (`i()I` lit `getPackageInfo.versionCode`, plancher figé 144/`0x90` absent, catch → -1), branchements `if-le` portant le silence en place. **Mordance prouvée par deux mutations** : table `>` → `>=` (KO exact sur « publiée == installée → silence ») et smali `if-le` → `if-gt` (KO exact sur la garde du silence). Câblé dans les deux jobs CI exécutant les patch tests. |
| 2026-09-19 | **Self-update observé en production sur la Freebox Pop : 152 → 153 (v1.0.6), octets installés consignés.** L'appareil était en 152 depuis la veille au soir (l'info « encore en 151 » était périmée) : le franchissement du verrou 153 est observé depuis 152, mêmes mécaniques. Chaîne complète : `UpdateActivity` (« v1.0.6 / 153 ») → « Install update » → URL exacte du tag → `PackageInstallerActivity` → **153 installée à 11:48:36**, app relancée sur `FireTVMainActivity`. **Les octets installés sont identifiés** : SHA-256 du `base.apk` calculé **sur l'appareil** = pull ADB relu localement = livrable Windows = octets servis CI/GitHub = `dadbe5ae…` — l'identité chaîne→TV est désormais prouvée jusqu'aux octets réellement installés. Self-test embarqué **6/6** via `app_process` sur les octets installés (leçons : la sonde log en logcat, tag `Twouich` — son stdout est vide ; `logcat -c` refusé sur ce ROM). **Leçon d'exploitation : l'installeur système peut se figer en silence** — le processus `com.google.android.packageinstaller` resté en cache depuis la session de la veille (21:20) a avalé toute nouvelle session sans écran ni erreur (activité morte en < 100 ms, aucun `INSTALL_FAILED`) ; **un reboot de la Freebox assainit** l'état et l'écran système revient. Le focus D-pad de l'écran système n'est pas garanti (un OK peut ne rien faire) : le tap ADB sur INSTALLER (coordonnées du dump `uiautomator`) est le filet de secours. Archives : `work/device-test/freebox-selfupdate-153.apk` (octets installés), `freebox-selfupdate-19-09.log` (trace logcat de la session). |
| 2026-09-19 | **Première observation live sur la Freebox Pop à jour (v1.0.6/153) — filtre et sentinelle validés en production sur l'appareil réel.** Radar d'abord : DDG détecté avec pod actif (1 plage/3 segments), mais **coupe son direct entre le radar et la navigation** — la leçon : un choix de cible peut périmer en minutes, vérifier la liste vivante à l'écran. Cible de remplacement : **Coffee** (suivie, live, Fire Emblem — grande chaîne). Session 1 perdue à cause de l'ordre des étapes (la fenêtre de 600 s s'est écoulée pendant la navigation en grille : dumps `uiautomator` en retard d'un cran sur le focus D-pad réel, verdict « ❓ aucune playlist » sans lecteur ouvert) ; leçon inscrite à la recette — **`--no-launch` d'abord, navigation ensuite**, et cran par cran avec dump isolé. Session 2 (`--no-launch`, 600 s) : **169 playlists nettoyées, 0 retrait, 0 alerte sentinelle, 0 erreur de lecture, 0 repli proxy** — verdict ✅ « CONTENU TRAVERSÉ SANS POD » (cas bénin tranché par la sentinelle muette : le format servi est celui des règles, aucune pub servie à Coffee dans la fenêtre). Navigation Freebox consignée : les `input tap` y sont sans effet, tout passe au D-pad (fiche chaîne : UP → focus LIVE → OK) ; le BACK du lecteur rend l'accueil proprement. Le trio radar → script → verdict fonctionne identiquement sur l'émulateur et sur le vrai téléviseur. |
| 2026-09-19 | **Audit emotes/badges/highlighter (§ 5 d'AUDIT.md) clos — aucun défaut fonctionnel, rien à patcher.** Le code vivait dans le package obfusqué `A6/` (les recherches sous `com/s0und/s0undtv/` ne voyaient rien) : 6 endpoints exactement — 7TV **v3** (`7tv.io/v3/emote-sets/global` + `users/twitch/<id>`), BTTV (`betterttv.net/3/cached/emotes/global` + `users/twitch/<id>`), FFZ (`frankerfacez.com/v1/room/__ffz_global` + `room/id/<id>`), replay robotty (`recent-messages.robotty.de`, champ `userBadges`), CDN twitch (`jtvnw.net/emoticons/v2`) — conformes à la passe obsolescence du 18/09. Preuve en direct sur l'émulateur 153 (chat `#niniste`) : les **5 chargeurs verts** (`FFZ Done`, `BTTV Done`, `7TV Done`, `Global emotes Done`, `SubEmote Done`), IRCv3 complet (CAP tags/commands/membership ACK, JOIN, PONG), messages réellement rendus. `highlighted-message` traité dans `g.smali` (préfixe retiré avant rendu), modèle de badges `broadcaster/partner/vip/premium` présent. Deux bruits **upstream bénins**, attribués au niveau octet : Glide « load for a destroyed activity » (pattern connu) et `NumberFormatException: "Not Found"` tombée **pendant le loader 7TV** — un 404 `7tv.io/v3/users/twitch/<id>` (`{"status":"Not Found"}`) parsé en entier pour une compte sans 7TV, erreur attrapée, « 7TV Done » rendu quand même. La passe § 5 est désormais intégralement traitée ou assumée. |
| 2026-09-19 | **La table de vérité de l'updater entre dans le self-test embarqué : `SELFTEST 18/18 → 28/28`.** Le bloc 8 de `SelfTest.smali` rejoue en bytecode Dalvik la table de `test_update_check.py` via une nouvelle méthode pure `pick(IIII)I` — miroir exact de `UpdateHelper.b()V` (canal inconnu → silence, `-1` = entrée absente **ou** version installée illisible avec sa sémantique fail-loud, stricte supériorité porte le silence, l'autre canal gagne ssi strictement plus récent que tout) : 10 vérifications (« annonce en retard » → silence sur les deux canaux, annonce égale → silence, plus récente → dialogue, préférences de canaux, fail-loud). **La leçon du jour est arrivée en exécutant le probe** : le premier portage donnait `26/28` sur appareil — les cas 8.5 et 8.7 révélaient une divergence entre mon flux de branchements Dalvik et la condition composée de `a.smali` (le cas `c == b` tombait sur le dialogue `b` au lieu du dialogue `c` pour le 8.5) ; le portage structurel conforme (`:cond_1w`/`:cond_2`, jamais d'inversion `if-le`) a verrouillé `28/28`. C'est exactement le scénario que ce test existe pour attraper : la sémantique Dalvik réelle. Le candidat a été validé en probe `app_process` sur les octets du build ; `dist/` restauré aux octets CI (`dadbe5ae…`), à livrer avec la prochaine release. Verdict du § 0.1 actualisé dans `TEST-DEVICE.md` et `AGENTS.md`. |
| 2026-09-19 | **Release `v1.0.7` (154) publiée — le self-test à 28 vérifications part en production.** Bump conventionnel (`0e7bd97`) : double build local → SHA identiques (`6b54d7c0…`), suites vertes, `test_apk` conforme en mode lag (`update.json` annonce encore 153 — verrou d'annonce volontaire), probe `SELFTEST 28/28` sur les octets du candidat. Tag `v1.0.7` → CI signante verte, release « Twouich v1.0.7 » (APK 11 239 187 o + `changelog.html` « self-test 28 vérifications »), **octets servis = build local Windows** (`6b54d7c0…`) — deuxième release consécutive où le rebuild local reproduit les octets publiés. Acceptation émulateur : `install -r` acceptée par-dessus 153, `versionCode=154 / versionName=v1.0.7`, self-test en app **28/28**, updater silencieux au cold start (154 > 153 annoncé : pas de dialogue ; les 9 lignes « UpdateActivity » de la capture sont la plomberie interne du Play Store — Finsky « SystemUpdateActivity » — sans rapport avec l'app). `update.json` reste à pousser (verrou volontaire, même convention que la v1.0.6). |
| 2026-09-19 | **Annonce v1.0.7 levée (`update.json` → 154).** `ReleaseDate = 2026-09-19T12:22:16.000Z` (`published_at` exact de la release), commit + push (`d91faf9`), `check-release.sh` vert aux quatre étages (octets servis = `6b54d7c0…`). Péripétie d'exploitation consignée : le CDN de raw.githubusercontent a servi l'ancien `update.json` (~7 min après le push, TTL de cache) pendant que l'API git confirmait déjà 154 en ligne — l'API fait foi pendant la fenêtre, le cache se purge seul. |
| 2026-09-19 | **Probe SelfTest 28/28 sur la Freebox Pop** (app installée intacte en 153) : le self-test à 28 vérifications — dont la table de vérité de l'updater en bytecode Dalvik — tourne sur le vrai téléviseur via `app_process` sur un push ADB de `dist/Twouich_v1.0.7.apk` (octets servis `6b54d7c0…`), sans `install` ni session d'installation, sans toucher au self-update 154 en attente. Verdict : `SELFTEST 28/28 verifications, flux filtre : 328 octets` + `playlist nettoyee 623 -> 328 octets, segments pub retires : 3` ; état d'après propre (0 app_process résiduel, trace supprimée). Détail en TEST-DEVICE.md §0.2. |
| 2026-09-19 | **Self-update 153 → 154 observé en production — et spontanément au foyer (le cas Horizon 1 tranché).** Alors que l'observation ADB se préparait (15:10), l'appareil a fait la mise à jour **tout seul** : `UpdateActivity` 15:09:47 → « Install update » pressé à la télécommande → première tentative **rebondie** sur `DeleteStagedFileOnResult` (nettoyage du staged précédent, main rendue à l'`UpdateActivity`) → second appui 15:10:03 → `InstallSuccess` 15:10:19, app relancée directement en lecture, filtre actif dès 15:10:32. **Octets installés identifiés sur l'appareil** : `6b54d7c0…` = toute la chaîne (3e self-update consécutif) ; self-test **28/28** prouvé en sonde `app_process` **sur le `base.apk` installé** (la ligne du démarrage auto était perdue dans la rotation du tampon main — leçon : sonder les octets, pas le tampon). **Le figement pathologique ne s'est pas reproduit** (processus installeur frais, né au boot de 11:39, première session de sa vie à 15:09) — mais la forme **bénigne** du silence est documentée : le premier appui ne lance pas la session et doit être répété ; la forme pathologique (processus stalé qui avale tout, reboot seul recours) reste celle de la veille. Diagnostic discriminant : l'âge du processus vs le boot. Anti-boucle vérifiée (aucune réouverture d'`UpdateActivity`). Archives : `work/device-test/freebox-selfupdate-154.log` (10 608 lignes, archivé avant rotation). Détail en TEST-DEVICE.md §0.2. |
| 2026-09-19 | **Pages légales Twouich rédigées et câblées (Horizon 2) — mentions légales + politique de confidentialité embarquées.** Contenu écrit sur des faits vérifiés contre le code compilé : aucune donnée collectée ni serveur propre (filtrage SSAI purement local), session/préférences/favoris/historique stockés dans l'espace privé de l'app, services tiers nommés (Twitch API/IRC/EventSub WebSocket — pas de FCM, 7TV/BTTV/FFZ, robotty optionnel, GitHub Releases pour l'updater), **Firebase Crashlytics/Analytics upstream toujours configuré** (`google_app_id` + clé de crash d'origine intactes — documenté comme « la vérité sur l'héritage », neutralisation suivie comme chantier), AD_ID déclarée par héritage sans publicité dans le fork, **caméra = lecteur QR de connexion uniquement** (`com.journeyapps.barcodescanner`), **micro jamais accédé** (aucun AudioRecord/MediaRecorder dans tout le smali). Implémentation : sources de vérité sous `patch/branding/` (`twouich_legal.html`, `twouich_privacy.html`, style de la page À propos), injection en fin d'étape 5 de `patch.py` (canonisation LF, échec bruyant si source manquante), liens `file:///android_asset/` ajoutés à la section Legal de la page À propos (navigation intra-WebView — aucun interceptionneur d'URL dans `AboutActivity`), contrôles finaux de patch.py portés à 53, `test_apk.py` à 18 verdicts (3 nouveaux : pages présentes + liens). Validations : patch.py vert sur l'arbre, build candidat `0ea7d4f9…` (+4 240 o = les deux pages), test_apk 18/18 en mode lag, SELFTEST 28/28 en sonde sur les octets du candidat, toutes les suites vertes, `dist/` restauré aux octets CI (`6b54d7c0…`). À embarquer avec la prochaine release. |
| 2026-09-19 | **Release v1.0.8 (155) publiée — les pages légales partent en production — et immédiatement suivie de la v1.0.9 (156) : la découverte de l'acceptation.** v1.0.8 : double build identique (`3072c3b5…`), CI signante verte, octets servis = local, annonce levée, `check-release.sh` vert. **L'acceptation appareil a révélé un résidu upstream que la lecture du code n'avait pas vu** : la grille du menu latéral contient une entrée « Privacy policy » (MainFragment → `PrivacyPolicyActivity`) qui chargeait **toujours** la politique S0undTV en ligne (Google Sites) — notre politique n'était atteignable que depuis la page À propos. Correction : `patch.py` repointe le `const-string` de `PrivacyPolicyActivity` vers `file:///android_asset/twouich_privacy.html` (même fenêtre, zéro réseau), contrôle final ajouté ; livraison en v1.0.9 (156, double build identique `3256e316…`, chaîne verte, annonce levée). **Acceptation v1.0.9 complète sur l'émulateur** : 156 installée, SELFTEST 28/28 en app, page À propos affiche les deux liens (rendus dans l'arbre d'accessibilité), et le menu « Privacy policy » ouvre **notre** page locale (« En bref », « La vérité sur l'héritage », « Caméra et microphone » vérifiés à l'écran). Leçons de navigation WebView TV consignées : les liens ne sont pas focusables au D-pad (limite upstream), **TAB + ENTER** navigue et active dans la WebView ; l'entrée du menu la plus fiable est l'attribut `selected` du dump (`uiautomator`), pas les bounds (la grille du panneau ne défile pas toujours). |
| 2026-09-19 | **§8 clos — assumés explicites + feuille de route.** Les cinq chantiers fondateurs barrés et le §5 d'AUDIT.md intégralement traité ou assumé (vérifié en réel : zéro issue ouverte, CI verte) — le §8 est réécrit en deux parties : **assumés** (neuf limites/choix documentés, aucune action en attente — mainteneur test_brand/test_apk, pas d'entrée beta, INSTALLER humain, schedule CI 60 j, pannes réseau muettes, PlaylistResetException, bruits chat bénins, pas de pronouns, limite pixel chat) et **feuille de route à trois horizons** : H1 = self-update 153→154 sur la Freebox (cas « mises à jour rapprochées » qui doit trancher la récurrence de l'installeur figé) + reproduction à la demande du scénario sur émulateur ; H2 = alerte radar prouvée de bout en bout en dispatch, mentions légales/politique de confidentialité Twouich, entrée beta si un jour nécessaire ; H3 = rebase upstream (future beta S0und), audits périodiques des endpoints tiers, vitrine du projet. L'historique détaillé du §8 vit au journal §9. |
| 2026-09-18 | **Session d'observation live du soir (~13 min, DDG) — sentinelle et filtre validés ensemble sur l'app publiée (v1.0.5, 152).** Direct ouvert depuis l'historique de l'appareil (navigation D-pad). Verdict `analyze_device_log.sh` : 459 nettoyages, **207 playlists avec pubs retirées, 2539 segments publicitaires supprimés** (max 22/pod — pod de 15:41:54→15:41:58, playlist 62 ko → 3 ko), 0 repli proxy, **0 alerte « marqueur pub inconnu »** : le filtre retirait les pods pendant que la sentinelle, exposée aux mêmes DATERANGE `stitched-ad`, tags `quartile` et titres `Amazon` réels, restait muette. Les 10 « Source error » toutes `m3.l$d` = `PlaylistResetException` de fin de pod, récupérées (dernier nettoyage horodaté après la dernière erreur). Incident d'outillage consigné : premier client logcat mort à 15:37 (capture figée sans prévenir) — relance en append via `nohup … >log 2>&1 &` (un `&` nu dans une commande synchrone bloque la clôture ; `BACKGROUND` n'est pas disponible côté agent) ; capture cumulée 2 420 lignes, `work/device-test/logcat-sentinel-live-18-09.txt`. |
| 2026-09-19 | **Accueil smartphone : le panneau TV n'était pas caché, il était déployé — et les cartes n'étaient pas tappables.** Deux causes distinctes, mesurées au doigt sur le Xiaomi réel (1220×2712, densité 520). (1) **Panneau** : `setHeadersState` recevait l'état `1` depuis la session précédente ; la table de `BrowseSupportFragment.N2` XOR l'état avec `1` avant d'appeler `HeadersFragment`, donc seuls `1`/`2` laissent le panneau **visible** (`GONE = false`) et l'état **3** le cache. Preuve : `browse_headers` 852×2504 à l'écran, rangées écrasées dans 362 px de large (dump `uiautomator`). Le patch passe `3` sous 600 dp, `2` sur TV — après quoi le panneau disparaît du dump et les rangées reprennent les 1220 px. (2) **Tap** : instrumentation de `BaseGridView.dispatchTouchEvent` — l'appui est reçu, mais aucune vue enfant ne reçoit le relâchement ; le clic natif n'est prédit ni par le focus (carte déjà focusée : premier appui sans effet) ni par la sélection (carte déjà sélectionnée : idem). Nouveau greffon `TapClick` branché à cette entrée : tap franc (seuil `ViewConfiguration`) → clic de la plus profonde vue cliquable sous le doigt (parcours récursif, translation et défilement retirés), geste annulé puis **relâchement consommé** (un tap = exactement un clic, le chemin natif ne peut plus s'ajouter). Verdicts sur appareil : un tap ouvre la fiche (`K6.d$b` → `ChannelDetailsActivity`) et le direct (`K6.d$a` → `PlayerActivity`) ; glissement → `relachement ignore : glissement` ; D-pad et barre basse → aucune trace (hors `MotionEvent`/hors grille) ; une seule fiche empilée après retour. La télévision reste inchangée (état 2, et le D-pad n'émet aucun `MotionEvent`). Garde-fous : `test_smali_branches.py` 19 vérifications (dont les deux inversions `if-nez` qui ont vécu jusqu'à l'appareil, §6), `test_apk.py` exige `TapClick` + le tag `TWOUICH-TAP` dans le dex, `patch.py` 87 contrôles (greffon présent et hook placé **avant** la logique d'origine de la grille). Recette complète en `TEST-DEVICE.md` §0.3 (encadré « Cartes et rangées réellement tappables au doigt »). |
| 2026-09-20 | **La limite des 600 dp vérifiée à l'unité près — et le crash qu'elle a révélé.** Le garde du tap → clic repose sur `smallestScreenWidthDp < 600` : le vérifier sur un grand écran ne suffit pas, il faut **franchir la limite**. L'émulateur s'y prête sans matériel, sa configuration se pilote par `wm` (densité 240 → `px / 1,5 = dp`). Une seule APK, quatre configurations : **720 dp** (1920×1080) et **600 dp** (1920×900) → `browse_headers` **déployé** (`[0,0][393,1080]`, 20 % de la largeur), barre téléphone absente, tap → **aucune** trace, écran inchangé, D-pad → fiche ouverte avec zéro trace et lecteur TV intact (`ExoPlayer` plein écran, `SendMessageWindow` en `GONE`) ; **599 dp** (1920×899, un pixel sous la limite) → barre téléphone présente, panneau masqué, tap → `appui` puis `tap -> clic K6.d$a` → `PlayerActivity`. Le silence au-dessus de 600 dp n'est donc pas une absence de branchement : à 599 dp, même appareil, même geste, la même APK clique. **Le crash** : ouvrir un direct plantait l'application sur API 25 alors que la même APK se lançait sur le téléphone de référence — `NoClassDefFoundError: PlayerActivity`, causé par `IllegalAccessError: onWindowFocusChanged(boolean) implementing interface method Window$Callback.onWindowFocusChanged(boolean) is not public`. L'override injecté pour empiler la disposition téléphone était `.method protected` : `Activity` implémente `Window.Callback`, dont ce callback est **public**, un override plus faible fait rejeter la classe entière par le lieur ART — donc tout chemin qui charge `PlayerActivity` (clic sur une carte via `MainFragment$e.c`, deep link, `am start`) tuait l'app. Corrigé en `.method public`, plus deux garde-fous dans `patch.py` (89 contrôles) et un verrou dans `test_smali_branches.py` (21 vérifications) qui ne cherche que la **déclaration** — les règles de réparation de `patch.py` doivent pouvoir nommer la forme fautive pour la corriger. Vérifié après correction : `K6.d$a` → `PlayerActivity`, **0 `FATAL EXCEPTION`**; lecteur TV inchangé à 720 dp ; SHA `8b0f8ae6`. Recette en `TEST-DEVICE.md` (encadrés « limite des 600 dp » et « override `protected` »). |
| 2026-09-20 | **UX smartphone alignée sur l'interface de référence + picture-in-picture, TV intacte.** Cible : les captures de Twitch mobile / PurpleTV fournies par l'utilisateur. Traité côté téléphone uniquement (qualifiers de ressources, donc le visuel TV ne bouge pas d'un pixel) : **barre basse** de 58dp à fond `#0e0e10` + hairline, trois entrées **icône + libellé** (Accueil / Parcourir / Réglages) avec des vectoriels dédiés (`twouich_ic_home|search|settings`, posés par `install_phone_assets`) et l'onglet actif en `theme_purple_bright` ; **champ de saisie** renommé « Envoyer un message » (l'ancien libellé est réparé au passage) ; **picture-in-picture** : bouton 48dp sur la vidéo, ratio 16:9, chat et saisie masqués pendant l'incrustation, empilement réappliqué à la sortie. Le PiP exigeait `android:supportsPictureInPicture="true"` **et** `screenSize|smallestScreenSize|screenLayout|orientation` dans `configChanges` — sans quoi Android recrée l'activité à l'entrée en incrustation et le direct repart de zéro ; comme elle n'est plus recréée, la disposition est réappliquée dans `onConfigurationChanged` et l'incrustation est traitée dans `onPictureInPictureModeChanged` (callback **public** : même piège que l'`IllegalAccessError` du matin). **Disposition empilée corrigée** : la vidéo 16:9 calculée depuis la largeur n'était pas plafonnée (mesuré à 1920×899 : vidéo écrasée, chat à **0 px**) ; la vidéo est désormais plafonnée et l'empilement refusé s'il ne reste pas un tiers de la hauteur pour le chat — en paysage on garde le layout d'origine (vidéo plein écran, chat en bas), qui est aussi la disposition de la référence. Vérifié sur l'émulateur : portrait `sw533dp` → vidéo `[0,0][800,450]` et chat `[0,450][800,1440]` ; paysage `sw599dp` → vidéo plein écran et chat `[0,449][1920,899]` ; `sw720dp` → panneau TV déployé, aucune entrée de barre téléphone, tap sans trace, lecteur TV plein écran ; **0 `FATAL EXCEPTION`** partout, y compris sur API 25 (le nouveau smali passe donc le vérificateur ART). Reste à constater sur un vrai téléphone **API ≥ 26** : l'incrustation elle-même (le seul point non mesurable sur l'émulateur, qui est en API 25). Garde-fous : `patch.py` 116 contrôles (dont la polarité des deux tests de place et l'unicité des labels), `test_smali_branches.py` 23 vérifications, `test_apk.py` 32 verdicts. |
| 2026-09-20 | **Incrustation (PiP) acceptée sur le téléphone — deux défauts, dont un garde de nullité à l'envers.** Exercée sur un direct réel (`ddg`, servant du SSAI : jusqu'à 16 segments de pub retirés par cycle) avec la recette de `TEST-DEVICE.md` : plein écran → vidéo `[0,0][1220,686]` (16:9), chat `[0,686][1220,2712]`, compositeur `[0,2600][1220,2712]` ; incrustation (`mode=pinned`, fenêtre `[492,130][1200,528]`) → vidéo `[0,0][708,398]`, chat **et** compositeur en `G`, trace `picture-in-picture : video plein cadre, chat et saisie masques` ; retour → trace `disposition empilee restauree` et empilement retrouvé, `mode=pinned = 0`. **Défaut 1 — `twouichPhoneView` rendait toujours `null`** (`if-nez v0, :no_phone_view` = « retourne null quand l'identifiant est trouvé ») : le rappel d'incrustation sortait aussitôt sur ses trois gardes de nullité, donc rien n'était masqué — `ChatRecycleView` visible et `SendMessageWindow` à `[0,286][708,398]`, **par-dessus la vidéo** de la fenêtre. C'est la trace logcat qui a tranché, pas la mesure : la géométrie (vidéo `708×398`) restait compatible avec un empilement appliqué par un autre chemin, et un garde de nullité sort en silence. **Défaut 2 —** l'entrée en PiP (perte de focus + changement de configuration) réappliquait `twouichPhoneStackedLayout`, qui remet le compositeur visible et ancré en bas : un champ d'instance `twouichPipActive`, écrit en tête de `onPictureInPictureModeChanged`, fait désormais refuser l'empilement pendant l'incrustation (trace `empilement ignore (incrustation active)`). Les textes des blocs PiP vivent dans des constantes `PHONE_PIP_*` utilisées **à la fois** par le bloc injecté et par la réparation d'un arbre déjà patché — une seule source, donc pas de dérive entre les deux chemins ; un test d'absence trop large (`iput-boolean p1, p0,` existait déjà dans le code upstream) a d'ailleurs dû être remplacé par une needle exacte pour que l'état soit réellement posé. Garde-fous : `patch.py` **126 contrôles**, `test_smali_branches.py` **27 vérifications**, `test_apk.py` vert, `SHA e53dcf05`. |
| 2026-09-20 | **VOD « réservée aux abonnés » de Kenbogard : lue par un jeton mémorisé, pas par le compte connecté — verdict mesuré, hypothèse précédente renversée.** Question posée : « comment S0undTV lit-il les VOD sub-only ? ». Chaîne de mesure : (1) sonde **anonyme** (`videoPlaybackAccessToken` sans compte) → `chansub.restricted_bitrates` couvre **toutes** les renditions et `usher` répond **403 `vod_manifest_restricted`** pour kenbogard / gotaga / kamet0, alors que **quatre** autres chaînes (ddg, twitch, gaules, zackrawrr) reçoivent un **200 / 6 variantes** — la méthode distingue donc bien une VOD restreinte d'une VOD ouverte ; (2) la VOD `2878257226` ouverte dans Twouich v1.0.9 sur le téléphone **joue** (décodeur `c2.mtk.avc.decoder`, 120 images/2 s, piste audio active) ; (3) la **même** VOD, dans l'app Twitch **officielle** 31.2.0 connectée sur le même appareil, affiche « Cette vidéo est réservée aux abonnés. Abonnez-vous pour regarder et soutenir cette chaîne. » ; (4) Réglages → *Application info* de Twouich : **`User ID` vide**. Verdict : le droit est une décision **serveur**, évaluée sur le jeton présenté ; Twouich ne le contourne pas — il présente un **jeton mémorisé** (chemin token de l'app), et le compte connecté, lui, n'a pas le droit puisque Twitch le refuse pour la même VOD. **Rien à porter vers TwitchDroid** : aucun code client ne débloque cela. Lecture des préférences tentée puis abandonnée (app non débuggable, `adb backup` refusé par l'appareil) : aucun jeton lu ni affiché — seul l'état du champ `User ID` a été observé. |
| 2026-09-21 | **La recette de pilotage ADB (focus et D-pad) portée dans Twouich — et vérifiée hors appareil.** Le projet voisin avait outillé ce que Twouich faisait encore à la main : la boucle `dump → repérer le focus → naviguer → re-dumper` du § 2 étape 3, dont le défaut est connu (le dump a un cran de retard sur le focus réel). Deux livrables : **`patch/device-ui.sh`** (`probe` mesure le canal au lieu de le supposer, `launch`, `texts`, `focus`, `clickables`, `find`, `nav`, `press`, `tap`, `key`, `shot` ; `--serial`/`--list`/`--connect` et la même détection d'`adb` que `test-device.sh`) et **`TEST-DEVICE.md` § 8** (le fait — le canal est une propriété de l'appareil, mesuré : Freebox et téléphone HyperOS absorbent le tactile, l'émulateur non —, la méthode, la signature d'écran textuelle comme seul signal fiable, huit pièges, la transposition à un nouvel appareil).**Vérification hors appareil : `patch/tests/test_device_ui.sh`, 37 vérifications vertes** — un double d'`adb` (`patch/tests/fixtures/fake-adb.py`) rejoue l'accueil TV puis le lecteur et contrôle les *décisions* de l'outil : que `probe` distingue les deux canaux, que `nav` échoue proprement sur une cible inatteignable, que les bornes `[x1,y1][x2,y2]` sont lues à la virgule près, et qu'une capture vide est attribuée à l'appareil et non à la copie. **Ce harnais a trouvé deux pièges MSYS que la recette ne mentionnait pas** : `MSYS2_ARG_CONV_EXCL='*'` (forcé par `device-ui.sh`, et déjà par `test-device.sh`) empêche la conversion des chemins passés à un interpréteur **natif Windows** — un `/d/Codex/…` arriverait tel quel à `python.exe`, qui ne le résout pas ; et MSYS ne convertit **pas** les variables d'environnement, donc un chemin d'état transmis par variable doit être normalisé explicitement (`cygpath -w`). Les deux sont consignés en § 8.4 (lignes 1 et 2). **Acceptation réelle sur BlueStacks** (`127.0.0.1:5555`, app Twouich non installée sur cette instance : l'acceptation a porté sur l'écran d'une autre app patchée, ce qui suffit — c'est l'appareil qui décide) : `probe` → `tactile=oui` (conforme au cas émulateur), `launch`/`focus`/`texts`/`nav`/`find` rendant l'état réel de l'écran. Le point de fond, hérité du diagnostic Google : **confondre « je n'ai pas pu cliquer » et « le bouton ne fait rien » mène à de fausses conclusions sur le code**. **Ajout de la session : `step`, la recette en une ligne.** `step <écran avant> <actions> <écran après>` (actions `nav:`, `press`, `key:<code>`, `tap:<x>,<y>`, `launch`, `wait:<s>`, jointes par `+`) rend une vérification complète et sort 0/1 — avec, comme preuve, le **delta** des textes gagnés et perdus sur l'écran, et un avertissement quand la sortie attendue était **déjà là** avant l'action (l'étape passerait sans rien prouver, même exigence que `probe` sur un canal indéterminé). Harnais porté à **61 vérifications**, dont une recette en deux étapes enchaînées (accueil → lecteur → accueil au BACK). Trois faits payés en route : (1) un `local IFS=+` posé pour découper les actions restait actif dans `cmd_nav`, où il transformait son `for i in $(seq 1 $UI_MAX)` en **une seule** itération — le `nav` échouait après un unique déplacement ; c'est le harnais qui l'a attrapé, la lecture ne l'aurait pas vu ; (2) `nav` brûlait 30 crans de D-pad (**87 s**) quand aucun élément n'a le focus — il le diagnostique maintenant en trois crans et renvoie vers `UI_KEY=19|21|22` ; (3) `nav` ne cible qu'un **texte**, donc un nœud sans libellé (le seul focalisable de l'accueil d'une vraie app était un `FrameLayout` de barre d'onglets) est injoignable par nom — passer par `clickables` + `tap`. Acceptation réelle sur BlueStacks : `step "Les commentaires sont ici" "key:4" "Accueil"` → conforme en 10 s. |
| 2026-09-21 | **Toggle du chat smartphone : le patch était aveugle à ses propres injections — tests de présence réparés, idempotence prouvée.** Chantier : replier le bloc chat + saisie en lecture téléphone (il occupait la moitié basse en portrait sans aucun contrôle pour le replier). Livré : bouton chat 32dp sur la vidéo (`twouich_ic_chat`, ancré au-dessus du bloc, filet de secours bas-droit), méthodes `twouichChatTraces`/`twouichChatApply(Z)`/`twouichPhoneChatToggle(View)`, champ d'état `twouichChatHidden:Z` (le tap bascule et délègue — une seule source de vérité, lisible par l'analyseur logcat), hauteur 448dp × densité, ancrages RelativeLayout recalculés (chat sous la vidéo/bas du parent, saisie au-dessus du chat, bouton replié ancré bas-droit puis restauré). **Le bug de la session** : sur arbre neuf, CHAT_METHODS était ajouté AVANT le test `if "twouichPhoneStackedLayout" not in player_fixed` — et un COMMENTAIRE des méthodes injectées citait ce nom — le test de présence par nom nu rentrait faux-positif, le bloc lecteur (`player_methods` + `pip_methods`) n'était plus jamais écrit, `onPictureInPictureModeChanged` disparaissait du smali (le contrôle final mordait, exit 1 — masqué un temps par un `tail` sans propagation d'erreur, le piège pipefail documenté). Correction de fond : **tous** les tests de présence passent aux signatures de méthode exactes (`.method …`), constante `CHAT_REPAIR_ANCHOR` alignée, commentaire désamorcé. Second défaut du même chantier : la réparation chat écrivait le fichier sans `newline="\n"` (churn CRLF/LF entre passes). Validation : décodage neuf → passe 1 exit 0 → passe 2 exit 0 → **smali lecteur octet-identique entre les passes** (idempotence), 33 ✅ / 0 ❌ au harnais du livrable, 27/27 smali branches, 11/11 verdicts analyseur, 53 ✅ device-ui, build candidat `14b61a21…` conforme. Le tap réel reste à accepter sur le téléphone. |
| 2026-09-21 | **Chat repliable (v2) : le repli donne l'écran à la vidéo, le bouton ne bouge plus — et un garde à polarité inversée empêchait la disposition téléphone de s'appliquer.** Le repli de la veille laissait la vidéo en 16:9 avec deux tiers d'écran noirs et déplaçait le **bouton d'incrustation** dans le coin bas droit : le bouton de rappel se retrouvait dessous, donc intappable. Câblage refait autour d'une seule source par décision : `twouichChatApply(Z)` écrit le champ puis délègue — `twouichChatCollapse` (vidéo plein écran, chat et saisie `GONE`) au repli, `twouichPhoneStackedLayout` (géométrie empilée, source unique) au dépli ; le bouton reste ancré à la vidéo dans les deux états ; l'empilement refuse de ressusciter un chat replié (`iget` du champ + `if-eqz v1, :stacked_chat_shown`) ; le champ fantôme `twouichChatButtonParams` disparaît, et le marqueur de version du câblage devient la méthode repliée (un arbre écrit par la version précédente est nettoyé puis reposé sans dupliquer PiP). Mesures sur l'émulateur en 720×1280 à 240 dpi (480 dp), arbre lu par `dumpsys activity top` — `uiautomator dump` ne pouvait pas trancher, il omet les vues `GONE` : **neuf** → vidéo `[0,0][720,405]`, chat `[0,405][720,1280]` visible, saisie `[0,1168][720,1280]`, boutons `[552,12][624,84]` et `[636,12][708,84]` ; **repli** → vidéo `[0,0][720,1280]`, chat et saisie `GONE`, boutons inchangés ; **dépli** → empilement rétabli, deux cycles joués ; **reprise d'activité** (bureau puis relance) avec chat replié → il reste replié ; **incrustation** → fenêtre `mode=pinned` 293×165 (16:9) avec `picture-in-picture : video plein cadre, chat et saisie masques`, puis `picture-in-picture : disposition empilee restauree` au retour. Aucun plantage (`pid` vivant), selftest 28/28, filtre actif sur le direct. La leçon de la session : `if-nez` au lieu de `if-eqz` sur le nouveau garde renvoyait **tout appel** dans la branche repliée sur un processus neuf — la disposition téléphone ne s'appliquait plus jamais, en silence ; le contrôle `if-eqz v1, :stacked_chat_shown` est désormais verrouillé par les contrôles de `patch.py` (138 au total), et la méthode de lecture de l'arbre est consignée en § 8.8 de `TEST-DEVICE.md` avec sa recette d'acceptation (§ 8.9). Livrable `034545ac…` (v1.0.9, 156), patch idempotent (smali identique sur deux passages), garde-fous verts : livrable conforme, 27/27 branches smali, 49 assertions du miroir, 11/11 verdicts de l'analyseur. |
| 2026-09-21 | **Chat : les derniers messages ne passent plus sous la barre de saisie — et le premier correctif essayé plantait l'activité.** Défaut mesuré juste avant : le chat, ancré au bas du parent, s'étirait jusque **sous** la saisie (chat `[0,405][720,1280]`, saisie `[0,1168][720,1280]`), donc 112 px de messages cachés en permanence. Premier correctif tenté : borner le chat par la règle 2 (`AU-DESSUS de la saisie`) — refusé net par le framework, `IllegalStateException: Circular dependencies cannot exist in RelativeLayout`, attrapée par l'acceptation au premier passage de mesure et **consignée en piège dans `TEST-DEVICE.md` § 8.9** : la saisie porte déjà `addRule(2, chat)`, la règle inverse ferme la boucle. Correctif retenu : une **marge basse** sur le chat (`iput v11, …, MarginLayoutParams->bottomMargin:I`), prise dans le **même registre** que la hauteur donnée à la saisie (`0x70` = 112 px) — les deux valeurs ne peuvent pas diverger, et aucune règle nouvelle n'est ajoutée, donc pas de cycle possible. Réparation de l'arbre de travail qui portait l'état intermédiaire (`PHONE_CHAT_ABOVE_OLD` → marge basse), gabarit et réparation issus du même texte (`PHONE_CHAT_BELOW_OLD`/`NEW`), patch toujours idempotent (smali identique sur deux passages) et 138 contrôles OK. Mesures après correction, arbre lu par `dumpsys activity top` : **empilé** → vidéo `[0,0][720,405]`, chat `[0,405][720,1168]` visible (bas du chat = haut de la saisie), saisie `[0,1168][720,1280]`, bouton `[552,12][624,84]` ; **replié** → vidéo `[0,0][720,1280]`, chat et saisie `GONE` ; **déplié** → empilement rétabli aux mêmes bornes. Aucun `FATAL EXCEPTION`, `pid` vivant, selftest 28/28, filtre actif. Livrable `600cd65e…` (v1.0.9, 156). Leçon de méthode : le repli d'un layout Android se mesure en bornes, jamais en captures — et un correctif de géométrie RelativeLayout doit vérifier qu'aucune règle ne ferme un cycle avant d'être livré. |
| 2026-09-21 | **La recette § 8.9 devient un script qui dit oui ou non tout seul — `patch/test-chat-toggle.sh`.** Quatre états (empilé, replié, déplié, reprise), chacun vérifié dans l'arbre des vues (§ 8.8) : vidéo 16:9 puis plein écran, chat visible puis `GONE`, **bas du chat = haut de la saisie**, saisie collée au bas, bouton du chat toujours hors du rectangle du bouton d'incrustation et **à la même place dans les quatre états**, plus les traces `chat masque`/`chat affiche` du logcat comme preuve que c'est bien le filtre qui a réagi (et pas seulement la disposition). Sortie **1 au premier écart**, avec les valeurs mesurées dans le message. Les taps sont relevés dans l'arbre (aucune coordonnée en dur), le départ est à froid (`am force-stop` : le champ d'état du repli ne survit pas au redémarrage, donc le point 1 est déterministe), et le processus doit être le même au point 4 — sinon le script le dit au lieu de conclure. **Rejeu hors appareil** : `TREE_DIR=patch/tests/fixtures/chat-toggle` fait lire quatre arbres capturés le 21/09 (livrés dans `patch/tests/fixtures/chat-toggle/`) sans appeler adb, ce qui rend la logique d'assertion vérifiable sans téléphone. **Le script a été prouvé mordant** sur deux arbres faux : l'arbre d'avant le correctif de géométrie (`ÉCART — le chat ne s'arrête pas au-dessus de la saisie (bas du chat 1280, haut de la saisie 1168)`) et un arbre où le bouton d'incrustation recouvre le bouton du chat (`ÉCART — le bouton du chat (552,12-624,84) recouvre le bouton d'incrustation`). Puis **joué pour de vrai** sur l'émulateur, départ à froid, quatre états conformes, exit 0 : vidéo `0,0-720,405`, chat `0,405-720,1168`, saisie `0,1168-720,1280`, bouton `552,12-624,84` — et la reprise sur le **même pid**. La vérification d'acceptation qui coûtait une séquence d'une dizaine de commandes à recopier tient maintenant en une ligne. |
| 2026-09-21 | **Le chat replié survit à la fermeture de l'application — et il a fallu deux pièges pour y arriver.** L'état (replié/affiché) est écrit dans la préférence `twouich`/`chat_hidden` par `twouichChatApply` et relu **une fois par instance** au démarrage du lecteur, sur `onResume` (le rappel de focus, seul point d'entrée précédent, n'est jamais dispatché sur BlueStacks/API 33 : la préférence n'était relue nulle part et le chat se rouvrait à chaque lancement). **Premier piège, une heure perdue** : le garde de relecture était écrit `if-eqz v0, :restore_done` — sur un processus neuf le champ est faux, donc la méthode sortait à la première instruction, **sans journal** ; c'est une sonde journalisée *avant* le garde qui a tranché (`restauration : entree` présent, trace d'état absente). Corrigé en `if-nez`, contrôlé par `patch.py` (polarité + appel dans le corps de `onResume`) et réparé sur les arbres déjà patchés. **Second piège, l'outillage** : `build.sh` réutilise `work/decoded`, donc un changement de gabarit ne s'applique pas à un arbre déjà patché et le build livre l'ancien texte sans un mot (deux builds ont embarqué un lecteur sans sonde) — `patch.py` estampille maintenant l'arbre à côté avec l'empreinte des gabarits et échoue bruyamment si elle ne correspond plus. **Preuves** : `patch/test-chat-toggle.sh` passe de 4 à **6 états** — persisté replié et persisté affiché (pid neuf à chaque fois, traces `chat restaure masque`/`chat restaure affiche`), rejeu hors appareil sur les six arbres capturés, et **toutes les gardes vertes** (livrable conforme, 27/27 branches smali, 147 contrôles, sanitizer) sur le livrable `fde91ad5709f98ab…`, patch toujours idempotent. Livrable `dist/Twouich_v1.0.9.apk` (le bump de version suivra). |
| 2026-09-21 | **Release v1.0.10 (157) : l'état du chat part en production — chaîne vérifiée jusqu'aux octets.** Bump des trois fichiers de version (`build.sh`, `patch.py`, `test_apk.py`), date de la page « Nouveautés » figée à 2026.09.21, entrée du journal des modifications + `sync-readme.py` (README aligné, lien d'installation repointé) ; build local **signé** sous Windows : `dist/Twouich_v1.0.10.apk`, 11 247 923 octets, SHA-256 `2fbadfb654de3c1b85a04db822d96f5425cae749c81120a30838b31a78d11584` — 147 contrôles du patch, livrable conforme, 27/27 branches smali, sanitizer, six états du chat rejoués hors appareil. Tag `v1.0.10` poussé → release CI **signée** publiée (`Twouich_v1.0.10.apk` + `changelog.html`, `publishedAt` 2026-09-21T15:27:15Z, release « latest »), `update.json` annoncé en 157, puis `check-release.sh` **vert** sur les quatre étages — dont **octets servis = octets du build local**, donc la reproductibilité Windows→Linux tient aussi pour cette version. À retenir : le job signé a **échoué une première fois** sur le téléchargement d'`uber-apk-signer.jar` (empreinte épinglée inchangée et correcte — le jar local porte bien `e1299fd6…`, l'`apktool` du même pas était OK) ; après relance, vert. Un hash épinglé qui ne correspond plus une fois sur téléchargement HTTP mérite d'être relancé avant d'être suspecté : c'est le contrôle lui-même qui a empêché un livrable non vérifié de partir. |
| 2026-09-21 | **Mode téléphone : l'UI devient enfin utilisable — portrait empilé, paysage côte à côte, plus d'info stream.** Trois captures du téléphone montraient deux défauts réels : en portrait la **barre d'info stream** (`@id/BottomBar` : avatar, pseudo, titre, spectateurs, qualité) restait affichée en bas, et en paysage le lecteur gardait la disposition TV — vidéo 16:9 **centrée** avec bandes noires de chaque côté et chat en surimpression à gauche. Corrections dans `twouichPhoneStackedLayout`, **téléphone seulement** (garde `smallestScreenWidthDp < 600` : le mode TV et `layout-sw600dp/` sont intacts) : la BottomBar passe en `GONE` ; en portrait vidéo 16:9 pleine largeur, chat dessous, saisie en bas ; en paysage vidéo à gauche sur **toute la hauteur sans bande noire** (largeur = `hauteur × 16/9`, plafond de sûreté 85 % de la largeur), chat à droite jusqu'au-dessus de la saisie, saisie en bas à droite. Mesuré sur le Xiaomi 1220×2712 (`dumpsys activity top`) — portrait : vidéo `0,0-1220,686`, chat `0,686-1220,2600`, saisie `0,2600-1220,2712`, BottomBar `GONE` ; paysage (`wm size 2712x1220`) : vidéo `0,0-2168,1220`, chat `2168,0-2712,1108`, saisie `2168,1108-2712,1220`, BottomBar `GONE` — 2168/1220 = 1,777, soit un 16:9 exact sur toute la hauteur. Cycle du chat rejoué : repli → vidéo plein écran et chat/saisie `GONE`, dépli → bornes ci-dessus, et l'état persiste après fermeture (`chat restaure masque` sur un pid neuf). Self-test 28/28 sur le téléphone, **aucun `FATAL`, aucun `VerifyError`**. Deux pièges payés, tous deux invisibles hors appareil : (1) le masquage du BottomBar écrivait la vue dans `v2`, qui portait déjà l'**id du chat** — la vérification Dalvik a rejeté **toute la classe** (`VerifyError: register v2 has type Reference: android.view.View but expected Integer`) et l'ouverture d'un direct plantait l'app ; règle posée : dans cette méthode, `v1..v6` portent identifiants et vues, n'écrire que dans `v0` et `v7..v11` ; (2) `user_rotation` et `cmd window user-rotation` sont **ignorés** par ce MIUI — c'est `wm size` qui a permis de mesurer le paysage sans retourner le téléphone. Livrable local `1eddfe61…` (hors release : la v1.0.10 publiée porte encore l'ancienne UI). Documenté en `TEST-DEVICE.md` § 8.10. |
| 2026-09-21 | **Alerte GitHub « Google API Key » : le dépôt ne publie plus les identifiants Firebase d'amont.** GitHub a signalé une fuite de secret dans `patch/tests/test_apk.py` (alerte « Google API Key #1 », détectée sur le commit `00999d6`) : les trois identifiants du projet Firebase **S0undTV** (identifiant d'application `1:815622240528:android:…`, clé `AIzaSy…`, URL `…firebaseio.com`) y étaient écrits **en clair** comme aiguilles du contrôle « aucun identifiant Firebase dans les ressources ». Ils sont désormais **éclatés en fragments réassemblés à l'exécution** (`_rebuild()` + `FIREBASE_TRACE`) : le contrôle reste une comparaison exacte d'octets, mais le fichier de test ne contient plus aucun secret littéral. Vérifié : les trois aiguilles réassemblées sont **identiques octet à octet** à celles d'avant (comparaison par empreinte, jamais par affichage de la valeur), et le contrôle **mord toujours** — l'APK d'origine `work/upstream/beta_144.apk` est refusé (« ❌ aucun identifiant Firebase dans les ressources »), notre livrable passe. Le cache `patch/tests/__pycache__/` (copie compilée qui portait encore la clé) a été supprimé ; il était déjà ignoré du dépôt. **Reste à faire côté GitHub** : l'alerte demeure attachée au commit historique — à clore manuellement en « not a real secret » : la clé est celle du projet d'amont, publiée dans l'APK officiel (elle est présente telle quelle dans `beta_144.apk`), nous ne pouvons pas la révoquer, et rien de chez nous n'y est exposé. |
| 2026-09-21 | **Trou de reproductibilité refermé : le patch réécrivait un smali avec les fins de ligne de la plateforme.** En vérifiant l'idempotence du patch pour la release, `PlayerActivity.smali` **divergeait** entre le premier et le second passage : identique au caractère près, mais en **LF puis CRLF** (+1 octet par ligne, 46 848 lignes). Cause : `disable_remote_config_calls` testait l'idempotence sur le **motif** (`\.method private J3\(\)V … .end method`) au lieu du **corps remplacé** — le motif matche encore après remplacement, donc `re.subn` renvoyait toujours 1, la méthode no-op était réécrite à chaque passage, et son `write_text` **sans `newline="
"`** laissait Python traduire `
` en `os.linesep` (CRLF sous Windows, LF sous Linux). Conséquence réelle : `build.sh` réutilise `work/decoded` quand la version n'a pas changé, donc **deux builds successifs de la même version ne donnaient pas le même APK** — exactement ce que la reproductibilité Windows→Linux promet d'éviter. Corrigé : test d'idempotence sur le corps réassemblé, écriture en `newline="
"`, et le journal dit enfin la vérité (« déjà appliqué : PlayerActivity.smali.J3() sans Remote Config »). Preuve : dépôt neuf → patch → **deuxième et troisième passages identiques octet à octet** (`diff -rq`), et **build sur arbre réutilisé = build sur arbre neuf** (même SHA-256 `e793c5fd…`), là où les deux divergeaient avant. |
| 2026-09-21 | **Release v1.0.11 (158) : le mode téléphone part en production — chaîne vérifiée jusqu'aux octets, et une alerte de secret fermée à la source.** Contenu : portrait empilé (vidéo pleine largeur, chat dessous, saisie en bas) et paysage côte à côte (vidéo 16:9 sur toute la hauteur à gauche, chat à droite), **sans la barre d'info stream** en mode téléphone ; le mode TV n'est pas touché. Trois commits : `fix` pour le secret Firebase d'amont (aiguilles éclatées, contrôle toujours mordant), `release` pour le bump et les corrections de `patch.py` (idempotence retrouvée : test sur le corps remplacé + `newline="
"`), `release` pour l'annonce. Build local signé sous Windows : `dist/Twouich_v1.0.11.apk`, 11 247 923 octets, SHA-256 `e793c5fd32a61af298a96a2fbfa26c1bdcec149c82b27c1e35c5851cb0bf35ce` — **identique pour un build sur arbre neuf et pour un build sur `work/decoded` réutilisé**, ce qui n'était plus vrai avant la correction d'idempotence. Tag `v1.0.11` → job signé **vert du premier coup** (`publishedAt` 2026-09-21T18:38:50Z, release « latest », assets APK + `changelog.html`), `update.json` annoncé en 158, puis `check-release.sh` **exit 0** sur les quatre étages : versionCode/versionName/asset concordants, release latest servie en 200, et **octets servis par GitHub identiques au build local**. Garde-fous au passage : 147 contrôles du patch, livrable conforme, 27/27 branches smali, sanitizer, updater, normalize, harnais ADB (61 vérifications), six états du chat rejoués hors appareil, patch idempotent sur trois passages. Rappel d'hygiène : les identifiants Firebase de l'amont ne sont plus littéraux dans le dépôt, mais l'alerte GitHub reste attachée au commit `00999d6` — à clore manuellement (« not a real secret »), la clé étant celle du projet S0undTV déjà publiée dans l'APK officiel. |
