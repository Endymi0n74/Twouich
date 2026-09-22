#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# install-hooks.sh — brancher les garde-fous locaux de .githooks/
# ═══════════════════════════════════════════════════════════════════════
# Les hooks sont versionnés dans `.githooks/` et non dans `.git/hooks/` :
# un hook non versionné n'existe que sur la machine qui l'a écrit, et il ne
# survit ni à un clone ni à la CI — donc il ne protège personne d'autre que
# son auteur, le jour où il y a pensé.
#
# Usage :  bash patch/install-hooks.sh
# Effet :  `git config core.hooksPath .githooks` (dépôt courant seulement :
#          rien n'est écrit dans la configuration globale de la machine).
# Sortie : 0 si le hook est branché et exécutable, 1 sinon.
# ═══════════════════════════════════════════════════════════════════════
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

HOOK=".githooks/pre-commit"
if [ ! -f "$HOOK" ]; then
    echo "❌ $HOOK introuvable — rien n'a été branché"
    exit 1
fi

git config core.hooksPath .githooks || exit 1
chmod +x "$HOOK" 2>/dev/null || true

BRANCHED="$(git config core.hooksPath)"
if [ "$BRANCHED" != ".githooks" ]; then
    echo "❌ core.hooksPath = « $BRANCHED » (attendu « .githooks »)"
    exit 1
fi
if [ ! -x "$HOOK" ]; then
    echo "❌ $HOOK n'est pas exécutable (git l'ignorerait)"
    exit 1
fi

echo "✅ hooks branchés : core.hooksPath = .githooks"
echo "   $HOOK refuse un secret AVANT qu'il n'entre dans l'historique."
echo "   Passer outre pour un commit : git commit --no-verify"
exit 0
