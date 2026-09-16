# Journal des modifications — Twouich

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
