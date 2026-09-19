# Journal des modifications — Twouich

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
