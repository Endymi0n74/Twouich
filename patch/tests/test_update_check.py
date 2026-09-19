#!/usr/bin/env python3
"""
test_update_check.py — verrouille la logique de comparaison de version de
l'updater, notamment le scénario « annonce en retard ».

Pourquoi ce test existe
-----------------------
Le 2026-09-19, après la publication de la v1.0.6 (153), la question s'est posée :
que fait une app déjà à jour quand update.json annonce encore MOINS ? (fenêtre
historique entre la création d'une release et le push de son annonce). Réponse
vérifiée sur appareil : silence — mais rien ne verrouillait ce comportement.

Le code est `UpdateHelper.b()V` (patché une première fois en v1.0.0 : la
comparaison lit la version installée via PackageManager, plus le plancher figé
144 d'upstream). La logique exacte, extraite du smali décodé :

    g()I  -> canal       : 0 = stable, 1 = beta (autre = silence)
    i()I  -> versionCode installé, -1 si la lecture échoue
    b     -> AppRelease  : l'entrée candidate du canal courant
    c     -> AppRelease  : l'entrée candidate de l'autre canal

    canal stable : b == null -> silence
                   b.VersionCode > installée -> dialogue(b)
                   sinon                     -> silence   (c est IGNORÉE)
    canal beta   : c != null && c > installée && c > b -> dialogue(c)
                   sinon b != null && b > installée    -> dialogue(b)
                   sinon                               -> silence

Deux propriétés sont verrouillées ici :

  1. la TABLE DE VÉRITÉ (miroir Python de la logique extraite) : publiée <
     installée ou publiée == installée -> AUCUN dialogue, quel que soit le
     canal — c'est le « annonce en retard » ; et l'échec de lecture de la
     version installée (-1) déclenche au contraire le dialogue (fail-loud) ;
  2. l'ARBRE DÉCODÉ (work/decoded/, quand il existe) : le patch v1.0.0 y est
     bien posé (i()I lit getPackageInfo/versionCode, le plancher 144 est
     absent) et les branchements `if-le` qui portent le silence sont en place.

Sans arbre décodé (le décodage n'est pas versionné), la section 1 reste
exécutable : la table de vérité est la mémoire du comportement, l'arbre est sa
confrontation au code réel.
"""

import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Surcharge pour la mordance (test de mutation sur un a.smali copié) :
# TWOUICH_DECODED=/tmp/decoded python patch/tests/test_update_check.py
DECODED = Path(os.environ.get("TWOUICH_DECODED", HERE.parent.parent / "work" / "decoded"))
A_SMALI = DECODED / "smali_classes2" / "com" / "s0und" / "s0undtv" / "helpers" / "a.smali"
PATCHER = HERE.parent / "patch.py"

checks = []


def check(label, condition, detail=""):
    checks.append((label, bool(condition), detail))


# ── Miroir de la logique de UpdateHelper.b()V (voir docstring) ──────────────
def picked(channel, installed, b_code, c_code):
    """Retourne l'entrée dont le dialogue est ouvert, ou None (silence).

    channel   : 0 (stable), 1 (beta), autre = canal inconnu
    installed : versionCode installé (i()I, -1 = échec de lecture)
    b_code    : VersionCode de l'entrée du canal courant (None = absente)
    c_code    : VersionCode de l'entrée de l'autre canal (None = absente)
    """
    if channel not in (0, 1):
        return None
    if channel == 0:
        if b_code is None:
            return None
        return "b" if b_code > installed else None
    # canal beta : l'autre canal gagne si strictement plus récent que tout
    if c_code is not None and c_code > installed and (b_code is None or c_code > b_code):
        return "c"
    if b_code is not None and b_code > installed:
        return "b"
    return None


def main():
    # ── Section 1 : table de vérité (hors réseau, hors appareil) ────────────

    # Le scénario visé : annonce EN RETARD ou ÉGALE -> silence, les deux canaux.
    for label, published in (("publiée < installée", 152), ("publiée == installée", 153)):
        check(
            f"stable + {label} -> silence",
            picked(0, 153, published, None) is None,
            "un dialogue ici proposerai de (ré)installer une version plus ancienne",
        )
        check(
            f"beta   + {label} -> silence",
            picked(1, 153, published, None) is None,
            "l'entrée de l'autre canal (absente ici) ne doit pas créer de dialogue",
        )

    # Le cas nominal du self-update : l'annonce plus récente déclenche le dialogue.
    check(
        "stable + publiée > installée -> dialogue",
        picked(0, 152, 153, None) == "b",
        "c'est le parcours prouvé en production (Freebox 152 -> 153)",
    )
    check(
        "beta   + publiée stable > installée -> dialogue (autre canal)",
        picked(1, 152, 152, 153) == "c",
        "l'entrée de l'autre canal gagne si strictement plus récente que tout",
    )
    check(
        "beta   + égalité des entrées (toutes > installée) -> dialogue(b)",
        picked(1, 152, 153, 153) == "b",
        "c doit être STRICTEMENT supérieure à b pour prendre la main : à égalité, l'entrée du canal gagne",
    )
    check(
        "beta   + les deux entrées en retard -> silence",
        picked(1, 153, 152, 151) is None,
        "aucune entrée ne dépasse la version installée",
    )
    check(
        "beta   + entrée du canal plus récente que l'autre -> dialogue(b)",
        picked(1, 150, 153, 152) == "b",
        "l'ordre de préférence ne doit pas inverser le choix",
    )
    check(
        "canal inconnu -> silence même si l'annonce est plus récente",
        picked(2, 152, 153, None) is None,
        "g()I ne rend 0 que pour '0' ; tout le reste est un canal non géré",
    )
    check(
        "aucune entrée candidate -> silence",
        picked(0, 150, None, None) is None and picked(1, 150, None, None) is None,
        "b == null (ou c sans b sur beta) ne doit pas déclencher de dialogue",
    )
    check(
        "i() en échec (-1) -> dialogue (fail-loud, direction sûre)",
        picked(0, -1, 153, None) == "b" and picked(1, -1, 152, 153) == "c",
        "une version illisible doit proposer la mise à jour, jamais se taire",
    )

    # ── Section 2 : confrontation au code réel (si l'arbre décodé existe) ───
    if not A_SMALI.is_file():
        print(
            f"[--] arbre décodé absent ({DECODED}) : gardes smali sautées —\n"
            "     la table de vérité ci-dessus reste la référence du comportement.\n"
            "     Relance après `bash patch/build.sh` pour la confrontation complète."
        )
    else:
        text = A_SMALI.read_text(encoding="utf-8")

        # Le patch v1.0.0 est posé : la version installée est lue, le plancher
        # figé 144 (const/16 v1, 0x90) ne doit plus exister nulle part.
        check(
            "patch v1.0.0 posé : i()I est appelée dans la comparaison",
            "invoke-direct {p0}, Lcom/s0und/s0undtv/helpers/a;->i()I" in text
            and "move-result v1" in text,
            "l'appel à i()I (version installée) a disparu de a.smali",
        )
        check(
            "plancher figé 144 (0x90) absent du comparateur",
            "const/16 v1, 0x90" not in text,
            "la comparaison upstream figée à 144 est réapparue",
        )
        check(
            "i()I lit PackageManager.getPackageInfo(...).versionCode",
            "getPackageInfo" in text and "versionCode:I" in text,
            "i()I ne lit plus la version installée",
        )
        check(
            "i()I échoue vers -1 (catch -> const/4 v0, -0x1)",
            ".catch Ljava/lang/Exception;" in text and "const/4 v0, -0x1" in text,
            "l'échec de lecture doit retourner -1 (fail-loud), pas 0 ni une exception",
        )
        # Les branchements qui portent le silence (extraits de b()V) :
        check(
            "b()V : publiée <= installée sur le canal courant -> silence",
            "if-le v3, v1, :cond_2" in text,
            "attendu 'if-le v3, v1, :cond_2' (v3 = VersionCode de b, v1 = installée)",
        )
        check(
            "b()V : publiée <= installée sur l'entrée stable -> silence",
            "if-le v2, v1, :cond_5" in text,
            "attendu 'if-le v2, v1, :cond_5' (v2 = VersionCode de l'entrée stable)",
        )
        check(
            "b()V : le canal (g()I) est lu avant la version (i()I)",
            text.find("->g()I") < text.find("->i()I") != -1,
            "l'ordre du dispatch canal/versions a changé : relire la table de vérité",
        )
        if PATCHER.is_file():
            patcher = PATCHER.read_text(encoding="utf-8")
            check(
                "patch.py garde la recette du patch v1.0.0",
                "UPDATE_VERSION_CALL" in patcher and "UPDATE_VERSION_METHOD" in patcher,
                "la recette de comparaison a disparu de patch.py",
            )

    # ── rapport ──────────────────────────────────────────────────────────────
    width = max(len(label) for label, _, _ in checks)
    failed = 0
    for label, ok, detail in checks:
        print(f"[{'OK ' if ok else 'KO '}] {label.ljust(width)}")
        if not ok:
            failed += 1
            if detail:
                print(f"        -> {detail}")

    print(f"\n{len(checks) - failed}/{len(checks)} verifications passees")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
