# Crédits, attribution et limites

## En amont

| Projet | Rôle | Attribution |
|---|---|---|
| **S0undTV** — https://github.com/S0und/S0undTV | application Twitch pour Android TV dont Twouich est un **build modifié**. Closed source : seul le binaire est publié par son auteur. | Toute l'application, son UI, son lecteur ExoPlayer, son intégration Twitch et ses fonctions (chat, emotes BTTV/FFZ/7TV, PiP, VOD, notifications) sont l'œuvre de **S0und** et de ses contributeurs. Les captures de `images/` proviennent de son dépôt. |
| **Streamlink** — https://github.com/streamlink/streamlink | l'implémentation de référence du nettoyage des plages publicitaires Twitch (`plugins/twitch.py`) a servi de base aux règles de `PlaylistSanitizer` (plages `stitched-ad`, titres `Amazon`, discontinuités). | Logique réimplémentée en smali pour Android ; merci aux mainteneurs de Streamlink. |
| **ExoPlayer** (Google) | lecteur utilisé par l'application ; Twouich ne fait que s'insérer dans sa chaîne de sources de données. | — |
| **apktool / uber-apk-signer / jadx** | outillage de désassemblage, de signature et d'analyse. | — |

## En aval (ce dépôt)

Ce qui est **nôtre** : le greffon anti-pub (`patch/smali/com/twouich/adblock/`), le repointage de la
mise à jour automatique vers ce dépôt, le script de patch rejouable (`patch/patch.py`), l'outillage
de build (`patch/build.sh`) et la documentation (`README.md`, `AUDIT.md`).

## Limites assumées

- **Closed source** : aucun code source de l'app d'origine n'est redistribué ici, seulement des
  binaires *patchés* et les patchs eux-mêmes. Aucun support n'est fourni, aucune garantie n'est
  donnée, et rien ne garantit que S0und approuve cette redistribution.
- **Usage personnel** : ce build n'est pas publié sur Google Play ni sur aucun magasin
  d'applications. Ne l'ajoute pas dans un dépôt public de binaires ni dans une boutique.
- **Aucune affiliation** avec Twitch Interactive, Inc. Twitch, l'icône Twitch et les marques
  associées appartiennent à Twitch Interactive, Inc.
- **Périmètre** : ce projet ne fait que retirer les publicités. Il ne contourne **aucun contenu
  payant** ni aucun abonnement — cette limite est volontaire et ne sera pas franchie.
- **Anti-pub** : le blocage repose sur le format actuel des marqueurs publicitaires de Twitch
  (SSAI `stitched-ad`). Twitch peut le changer à tout moment ; le point à ajuster est documenté
  dans `AUDIT.md`.
