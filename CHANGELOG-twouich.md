# Journal des modifications — Twouich

## v1.0.0 — 15 septembre 2026

C'est la première release publique renommée, prête pour un projet qui commence à être partagé\
(installation sur un appareil, mise à jour automatique depuis ce dépôt, build rejouable sans appareil).

### Ce qui entre dans ce première release

- **Blocage des publicités SSAI** — nouveau greffon `com.twouich.adblock` :
  - `AdBlockDataSource` : source de données ExoPlayer qui intercepte chaque lecture de playlist
    HLS, la relit intégralement puis la réécrit ; les segments vidéo passent sans copie.
  - `PlaylistSanitizer` : retrait des plages `#EXT-X-DATERANGE` publicitaires
    (`CLASS="twitch-stitched-ad"`, `ID="stitched-ad-…"`), des segments titrés `…Amazon…`,
    et des blocs `#EXT-X-CUE-OUT` / `#EXT-X-CUE-IN` ; les `#EXT-X-DISCONTINUITY` et
    `#EXT-X-TWITCH-LIVE-SEQUENCE` sont conservés pour que la timeline reste valide côté lecteur.
  - Injection au point unique `Lz3/u$b.a()` : *toute* lecture HLS de l'app (live, VOD, aperçus
    de l'accueil et de la recherche) passe par le filtre.
  - Preuve embarquée à chaque démarrage : le greffon contient un self-test qui rejoue des playlists
    Twitch réelles dans le **vrai code compilé** et fait traverser `AdBlockDataSource`. Verdict dans
    `logcat` (tag `Twouich`).
- **Identité Twouich** : nom affiché, écran de démarrage, icônes de lancement, bannière TV,
  icône adaptative, thème par défaut et pages embarquées (À propos / Nouveautés) portent
  l'identité Twouich — jamais le rouge S0und.
- **Mise à jour automatique** : l'updater pointe désormais sur **ce dépôt** (il ne tentera plus
  jamais d'installer un build de S0und par-dessus le nôtre).
- **Replayable, tér​mable, vérifiable** : build reproductible, tests locaux, self-test embarqué,
  harnais de test sur appareil, contrôle de la cohérence de la release (`check-release.sh`).

### Ce qu'a déjà prouvé ce build

- anti-pub : self-test embarqué vert sur l'appareil (`SELFTEST 18/18`, `playlist nettoyee 623 -> 328
  octets, segments pub retires : 3`), donc le retrait d'une publicité est reproduit à volonté, sur
  l'appareil, dans le code compilé — pas seulement vérifié par lecture statique.
- mise à jour automatique : release intermédiaire publiée, app installée en version précédente mise à
  jour par elle-même (dialogue ouvert seul → téléchargement → passage à l'installeur système),
  et les octets installés ont le SHA-256 du livrable publié.

### Ce qui est assumé

- Closed source : aucun code source de l'app d'origine n'est redistribué ici, seulement des binaires
  *patchés* et les patchs eux-mêmes. Aucun support n'est fourni, aucune garantie n'est donnée.
- Usage personnel : ce build n'est pas publié sur Google Play ni sur aucun magasin d'applications.
  Ne l'ajoute pas dans un dépôt public de binaires ni dans une boutique.
- Anti-pub : le blocage repose sur le format actuel des marqueurs publicitaires de Twitch (SSAI
  `stitched-ad`). Twitch peut le changer à tout moment — le point à surveiller est documenté dans
  `AUDIT.md`.
- Ce build ne contourne **aucun contenu payant** ni aucun abonnement. Cette limite est volontaire
  et ne sera pas franchie.
