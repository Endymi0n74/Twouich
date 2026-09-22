# Journal des modifications — Twouich

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
