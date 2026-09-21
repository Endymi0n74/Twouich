#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
# test-chat-toggle.sh — acceptation du chat repliable, en une séquence
# ═══════════════════════════════════════════════════════════════════
# Vérifie les SIX états du lecteur téléphone dans l'arbre des vues
# réellement appliqué, et sort en 1 au PREMIER écart :
#
#   1. empilé   vidéo 16:9 en haut, chat juste dessous, saisie au bas de l'écran
#   2. replié   (tap sur le bouton du chat) vidéo plein écran, chat et saisie GONE
#   3. déplié   (re-tap) exactement l'état 1
#   4. reprise  (bureau puis relance) le chat replié le reste, même processus
#   5. persisté replié  (application fermée puis rouverte) le chat revient replié,
#      processus neuf et trace « chat restaure masque »
#   6. persisté affiché (application fermée puis rouverte) l'état 1 revient, avec
#      la trace « chat restaure affiche » — le repli n'est pas collé
#
# Pourquoi l'arbre du framework et pas `uiautomator dump` : ce dernier omet les
# vues GONE, donc « chat masqué » et « chat absent » s'y ressemblent trait pour
# trait (cf. § 8.8 de TEST-DEVICE.md — c'est ce qui a coûté une session entière).
#
# Usage :
#   ADB=/chemin/adb SERIAL=192.168.1.51:5555 bash patch/test-chat-toggle.sh
#     --apk dist/Twouich_v1.0.9.apk   installer ce livrable avant d'observer
#     --channel ddg                    direct à ouvrir (défaut : ddg)
#     --pause 4                        secondes d'attente après chaque tap
#
# Rejeu hors appareil — vérifie la logique d'assertion sans téléphone :
#   TREE_DIR=patch/tests/fixtures/chat-toggle bash patch/test-chat-toggle.sh
#   chaque lecture vient alors de $TREE_DIR/<etat>.txt (empile, replie, deplie,
#   reprise, persiste-replie, persiste-affiche), aucun adb n'est appelé. Un
#   arbre faux doit faire sortir en 1 :
#     mkdir /tmp/faux && cp $TREE_DIR/*.txt /tmp/faux/
#     cp <arbre d'avant le correctif> /tmp/faux/empile.txt
#     TREE_DIR=/tmp/faux bash patch/test-chat-toggle.sh     # → écart au point 1
# ═══════════════════════════════════════════════════════════════════
set -u

CHANNEL=ddg
APK=""
PAUSE="${PAUSE:-3}"
ADB="${ADB:-adb}"
SERIAL="${SERIAL:-}"
TREE_DIR="${TREE_DIR:-}"
REPLAY=0
[ -n "$TREE_DIR" ] && REPLAY=1

PKG=com.s0und.s0undtv

while [ $# -gt 0 ]; do
    case "$1" in
        --apk)     APK="$2"; shift 2 ;;
        --channel) CHANNEL="$2"; shift 2 ;;
        --pause)   PAUSE="$2"; shift 2 ;;
        -h|--help) sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "❌ option inconnue : $1"; exit 2 ;;
    esac
done

etape() { printf '\n▶ %s\n' "$*"; }
ok()    { printf '  ✅ %s\n' "$*"; }
info()  { printf '     %s\n' "$*"; }
ecart() {
    printf '  ❌ %s\n' "$*"
    printf '\n═══════════════════════════════════════════════════════════════\n'
    printf 'verdict : ÉCART — %s\n' "$*"
    exit 1
}

adb_shell() {
    if [ -n "$SERIAL" ]; then "$ADB" -s "$SERIAL" shell "$@"; else "$ADB" shell "$@"; fi
}

# ── lectures ──────────────────────────────────────────────────────────────────
# arbre <etat> : l'arbre des vues, du framework (ou du rejeu hors appareil).
arbre() {
    if [ "$REPLAY" = 1 ]; then
        cat "$TREE_DIR/$1.txt"
    else
        adb_shell "dumpsys activity top" | tr -d '\r'
    fi
}

TREE=""
charger() {
    TREE="$(arbre "$1")"
    [ -n "$TREE" ] || ecart "arbre des vues vide — « dumpsys activity top » n'a rien rendu"
    case "$TREE" in
        *app:id/container*) : ;;
        *) ecart "l'arbre ne contient pas le lecteur (app:id/container absent) : « $1 » n'est pas l'écran attendu" ;;
    esac
}

# noeud <id> → « VIS x1 y1 x2 y2 ». Le « } » fait partie du motif : app:id/ExoPlayer
# est un préfixe d'app:id/ExoPlayerMV, et app:id/ChatRecycleView de …View2.
noeud() {
    printf '%s\n' "$TREE" | awk -v motif="app:id/$1}" '
        index($0, motif) {
            split($4, b, "-"); split(b[1], p, ","); split(b[2], q, ",")
            print substr($2,1,1), p[1], p[2], q[1], q[2]
            exit
        }'
}

# lire <id> → VIS X1 Y1 X2 Y2 (et sort en 1 si la vue est absente de l'arbre).
lire() {
    local l
    l="$(noeud "$1")"
    [ -n "$l" ] || ecart "vue « $1 » absente de l'arbre des vues (identifiant non résolu ?)"
    # shellcheck disable=SC2086
    set -- $l
    VIS="$1"; X1="$2"; Y1="$3"; X2="$4"; Y2="$5"
}

vis_de() { noeud "$1" | awk '{print $1}'; }

pid_app() {
    if [ "$REPLAY" = 1 ]; then echo 99999; else adb_shell "pidof $PKG" | tr -d '\r' | tr -d '\n'; fi
}

attendre_vis() {  # <etat> <id> <visibilité> <secondes>
    local fin=$(( $(date +%s) + ${4:-8} ))
    while :; do
        charger "$1"
        [ "$(vis_de "$2")" = "$3" ] && return 0
        [ "$(date +%s)" -ge "$fin" ] && return 1
        sleep 1
    done
}

# ── invariants partagés ───────────────────────────────────────────────────────
RECT_BOUTON=""
BUTTONS_TXT=""

# Le bouton du chat ne doit jamais tomber dans le rectangle du bouton
# d'incrustation : c'est le défaut du 21/09, où le bouton de rappel se
# retrouvait SOUS le bouton PiP, donc intappable.
verifier_boutons() {  # <etat>
    local etat="$1" px1 py1 px2 py2
    lire twouich_phone_chat; local bx1=$X1 by1=$Y1 bx2=$X2 by2=$Y2 bvis=$VIS
    lire twouich_phone_pip
    px1=$X1; py1=$Y1; px2=$X2; py2=$Y2
    [ "$bvis" = V ] || ecart "[$etat] le bouton du chat n'est pas visible : le chat ne serait plus repliable"
    if [ "$bx2" -gt "$px1" ] && [ "$px2" -gt "$bx1" ] && [ "$by2" -gt "$py1" ] && [ "$py2" -gt "$by1" ]; then
        ecart "[$etat] le bouton du chat ($bx1,$by1-$bx2,$by2) recouvre le bouton d'incrustation ($px1,$py1-$px2,$py2)"
    fi
    if [ -z "$RECT_BOUTON" ]; then
        RECT_BOUTON="$bx1,$by1-$bx2,$by2"
    elif [ "$RECT_BOUTON" != "$bx1,$by1-$bx2,$by2" ]; then
        ecart "[$etat] le bouton du chat a bougé : $bx1,$by1-$bx2,$by2 (état empilé : $RECT_BOUTON)"
    fi
    BUTTONS_TXT="bouton chat $bx1,$by1-$bx2,$by2 (PiP $px1,$py1-$px2,$py2)"
}

# ── état 1/3 : empilé ─────────────────────────────────────────────────────────
verifier_empile() {  # <etat>
    local etat="$1" PW PH vvis vy2 cx1 cy1 cy2 cvis iy1 iy2 ivil
    lire container; PW=$((X2-X1)); PH=$((Y2-Y1))
    lire ExoPlayer
    vvis=$VIS; vy2=$Y2
    [ "$vvis" = V ] || ecart "[$etat] la vidéo n'est pas visible"
    [ "$X1" -eq 0 ] && [ "$Y1" -eq 0 ] || ecart "[$etat] la vidéo ne part pas du coin haut gauche ($X1,$Y1)"
    [ "$X2" -eq "$PW" ] || ecart "[$etat] la vidéo n'occupe pas toute la largeur ($X2 au lieu de $PW)"
    # 16:9 calculé depuis la largeur, tolérance 2 % (les arrondis de disposition
    # varient d'un appareil à l'autre) : c'est la place laissée au chat.
    local attendu=$(( PW * 9 / 16 )) tol=$(( PW / 50 ))
    if [ "$vy2" -lt $(( attendu - tol )) ] || [ "$vy2" -gt $(( attendu + tol )) ]; then
        ecart "[$etat] la vidéo n'est pas en 16:9 : bas à $vy2, attendu ≈ $attendu (± $tol)"
    fi
    cx1=$X1
    lire ChatRecycleView
    cvis=$VIS; cy1=$Y1; cy2=$Y2
    [ "$cvis" = V ] || ecart "[$etat] le chat n'est pas visible (vis=$cvis)"
    [ "$X1" -eq "$cx1" ] || ecart "[$etat] le chat ne part pas du bord gauche ($X1)"
    [ "$cy1" -eq "$vy2" ] || ecart "[$etat] le chat ne commence pas sous la vidéo (chat $cy1, bas de vidéo $vy2)"
    lire SendMessageWindow
    ivil=$VIS; iy1=$Y1; iy2=$Y2
    [ "$ivil" = V ] || ecart "[$etat] la barre de saisie n'est pas visible (vis=$ivil)"
    # Le point du chantier : le chat s'arrête AU-DESSUS de la saisie, sinon les
    # derniers messages restent cachés sous la barre (112 px perdus avant le
    # correctif du 21/09).
    [ "$cy2" -eq "$iy1" ] || ecart "[$etat] le chat ne s'arrête pas au-dessus de la saisie (bas du chat $cy2, haut de la saisie $iy1)"
    [ "$iy2" -eq "$PH" ] || ecart "[$etat] la saisie n'est pas collée au bas de l'écran ($iy2 au lieu de $PH)"
    verifier_boutons "$etat"
    ok "[$etat] vidéo 0,0-$PW,$vy2 · chat 0,$cy1-$PW,$cy2 · saisie 0,$iy1-$PW,$iy2"
    info "$BUTTONS_TXT"
    PREUVE="${PREUVE}  $etat : vidéo 0,0-$PW,$vy2 | chat $cy1→$cy2 | saisie $iy1→$iy2 | $RECT_BOUTON
"
}

# ── état 2/4 : replié ─────────────────────────────────────────────────────────
verifier_replie() {  # <etat>
    local etat="$1" PW PH vvis vy2 cvis ivil
    lire container; PW=$((X2-X1)); PH=$((Y2-Y1))
    lire ExoPlayer
    vvis=$VIS; vy2=$Y2
    [ "$vvis" = V ] || ecart "[$etat] la vidéo n'est pas visible"
    [ "$X1" -eq 0 ] && [ "$Y1" -eq 0 ] || ecart "[$etat] la vidéo ne part pas du coin haut gauche ($X1,$Y1)"
    [ "$X2" -eq "$PW" ] && [ "$vy2" -eq "$PH" ] || ecart "[$etat] le repli ne donne pas l'écran à la vidéo ($X2×$vy2 au lieu de $PW×$PH)"
    lire ChatRecycleView; cvis=$VIS
    [ "$cvis" = G ] || ecart "[$etat] le chat n'est pas GONE (vis=$cvis) : il reste affiché alors qu'il est replié"
    lire SendMessageWindow; ivil=$VIS
    [ "$ivil" = G ] || ecart "[$etat] la barre de saisie n'est pas GONE (vis=$ivil)"
    verifier_boutons "$etat"
    ok "[$etat] vidéo 0,0-$PW,$PH plein écran · chat GONE · saisie GONE"
    info "$BUTTONS_TXT"
    PREUVE="${PREUVE}  $etat : vidéo 0,0-$PW,$PH (plein écran) | chat GONE | saisie GONE | $RECT_BOUTON
"
}

# ── préparation ───────────────────────────────────────────────────────────────
PREUVE=""
etape "0. Préparation"
if [ "$REPLAY" = 1 ]; then
    ok "rejeu hors appareil : arbres lus dans $TREE_DIR, aucun adb appelé"
    for e in empile replie deplie reprise persiste-replie persiste-affiche; do
        [ -f "$TREE_DIR/$e.txt" ] || ecart "arbre de rejeu manquant : $TREE_DIR/$e.txt"
    done
else
    command -v "$ADB" >/dev/null 2>&1 || [ -x "$ADB" ] || ecart "adb introuvable : $ADB (passer ADB=/chemin/adb)"
    [ -n "$(adb_shell true 2>/dev/null)" ] || adb_shell "true" || ecart "aucun appareil ne répond (SERIAL=$SERIAL)"
    info "appareil : $(adb_shell "getprop ro.product.model" | tr -d '\r')"
    if [ -n "$APK" ]; then
        [ -f "$APK" ] || ecart "APK introuvable : $APK"
        info "installation de $APK"
        if [ -n "$SERIAL" ]; then "$ADB" -s "$SERIAL" install -r "$APK" 2>&1 | tail -1;
        else "$ADB" install -r "$APK" 2>&1 | tail -1; fi | grep -q Success || ecart "installation refusée ($APK)"
        ok "livrable installé"
    fi
    # Départ à froid. Depuis le 21/09 le repli est MÉMORISÉ : un démarrage peut
    # donc restituer un chat replié, selon ce qu'un run précédent a laissé. On
    # rend l'état de départ déterministe (empilé) avant de mesurer — sinon le
    # point 1 mesurerait l'état d'un autre run.
    adb_shell "am force-stop $PKG" >/dev/null 2>&1
    sleep 1
    adb_shell "logcat -c" >/dev/null 2>&1
    info "ouverture du direct « $CHANNEL » (départ à froid)"
    adb_shell "am start -a android.intent.action.VIEW -d 's0undtv://stream/$CHANNEL'" >/dev/null 2>&1
    sleep 12
    TOP="$(adb_shell "dumpsys activity activities" | tr -d '\r' | grep -m1 ResumedActivity)"
    case "$TOP" in
        *PlayerActivity*) ok "le lecteur est au premier plan" ;;
        *) ecart "le lecteur n'est pas au premier plan : $TOP" ;;
    esac
    charger depart
    if [ "$(vis_de ChatRecycleView)" = G ]; then
        # La préférence a restitué un chat replié : c'est l'objet du point 5,
        # mesuré plus bas avec sa trace. Ici on repart de l'état 1.
        lire twouich_phone_chat
        info "chat replié restitué au démarrage (préférence) — déplié pour partir de l'état 1"
        adb_shell "input tap $(( (X1 + X2) / 2 )) $(( (Y1 + Y2) / 2 ))"
        sleep "$PAUSE"
        attendre_vis depart ChatRecycleView V 8 || ecart "le chat ne s'est pas déplié au démarrage"
    fi
fi

charger empile
PID="$(pid_app)"
[ -n "$PID" ] || ecart "processus $PKG introuvable — l'application n'est pas lancée"
info "processus $PKG : pid $PID"
lire twouich_phone_chat
ok "layout téléphone actif (bouton du chat présent)"

# ── 1. empilé ─────────────────────────────────────────────────────────────────
etape "1. Empilé — vidéo 16:9 en haut, chat dessous, saisie au bas"
verifier_empile "1. empilé"

# ── 2. replié ─────────────────────────────────────────────────────────────────
etape "2. Replié — tap sur le bouton du chat"
lire twouich_phone_chat
TAX=$(( (X1 + X2) / 2 )); TAY=$(( (Y1 + Y2) / 2 ))
info "tap à $TAX,$TAY (centre du bouton, relevé dans l'arbre)"
if [ "$REPLAY" = 0 ]; then
    adb_shell "input tap $TAX $TAY"
    sleep "$PAUSE"
    attendre_vis replie ChatRecycleView G 8 || ecart "le chat n'est pas masqué 8 s après le tap"
fi
charger replie
verifier_replie "2. replié"
if [ "$REPLAY" = 0 ]; then
    adb_shell "logcat -d -s Twouich:I" | tr -d '\r' | grep -q "chat masque" \
        && ok "trace du filtre : « chat masque »" \
        || ecart "la trace « chat masque » est absente du logcat : le tap n'a pas atteint le filtre"
fi

# ── 3. déplié ─────────────────────────────────────────────────────────────────
etape "3. Déplié — second tap sur le même bouton"
if [ "$REPLAY" = 0 ]; then
    adb_shell "input tap $TAX $TAY"
    sleep "$PAUSE"
    attendre_vis deplie ChatRecycleView V 8 || ecart "le chat n'est pas revenu 8 s après le second tap"
fi
charger deplie
verifier_empile "3. déplié"
if [ "$REPLAY" = 0 ]; then
    adb_shell "logcat -d -s Twouich:I" | tr -d '\r' | grep -q "chat affiche" \
        && ok "trace du filtre : « chat affiche »" \
        || ecart "la trace « chat affiche » est absente du logcat"
fi

# ── 4. reprise d'activité, chat replié ────────────────────────────────────────
etape "4. Reprise — chat replié, puis bureau et relance"
if [ "$REPLAY" = 0 ]; then
    adb_shell "input tap $TAX $TAY"
    sleep "$PAUSE"
    attendre_vis reprise ChatRecycleView G 8 || ecart "le chat n'est pas masqué avant la reprise"
    adb_shell "input keyevent 3"            # bureau
    sleep 3
    adb_shell "am start -a android.intent.action.VIEW -d 's0undtv://stream/$CHANNEL'" >/dev/null 2>&1
    sleep 8
fi
charger reprise
verifier_replie "4. reprise"
PID2="$(pid_app)"
[ "$PID2" = "$PID" ] \
    && ok "même processus (pid $PID) : c'est bien la reprise d'activité qui a été mesurée" \
    || info "⚠️ processus relancé (pid $PID2 au lieu de $PID) : si le téléphone a tué l'app, relancer la recette"

# ── 5. persistance du repli ───────────────────────────────────────────────
etape "5. Persisté replié — application fermée puis rouverte"
if [ "$REPLAY" = 0 ]; then
    adb_shell "am force-stop $PKG" >/dev/null 2>&1
    sleep 2
    adb_shell "logcat -c" >/dev/null 2>&1
    info "processus tué, relance à froid du même direct"
    adb_shell "am start -a android.intent.action.VIEW -d 's0undtv://stream/$CHANNEL'" >/dev/null 2>&1
    sleep 12
fi
charger persiste-replie
verifier_replie "5. persisté replié"
PID3="$(pid_app)"
if [ "$REPLAY" = 0 ]; then
    [ "$PID3" != "$PID" ] \
        && ok "processus neuf (pid $PID3, l'ancien était $PID) : c'est bien la fermeture qui a été mesurée" \
        || ecart "le processus n'a pas changé (pid $PID3) : l'état vient du champ d'instance, pas de la préférence"
    adb_shell "logcat -d -s Twouich:I" | tr -d '\r' | grep -q "chat restaure masque" \
        && ok "trace de relecture : « chat restaure masque »" \
        || ecart "aucune trace « chat restaure masque » : la préférence n'est pas relue au démarrage"
fi

# ── 6. persistance de l'affichage ─────────────────────────────────────────
etape "6. Persisté affiché — re-tap, fermeture, relance"
if [ "$REPLAY" = 0 ]; then
    adb_shell "input tap $TAX $TAY"
    sleep "$PAUSE"
    attendre_vis persiste-affiche ChatRecycleView V 8 || ecart "le chat ne s'est pas déplié après la relance"
    adb_shell "am force-stop $PKG" >/dev/null 2>&1
    sleep 2
    adb_shell "logcat -c" >/dev/null 2>&1
    adb_shell "am start -a android.intent.action.VIEW -d 's0undtv://stream/$CHANNEL'" >/dev/null 2>&1
    sleep 12
fi
charger persiste-affiche
verifier_empile "6. persisté affiché"
if [ "$REPLAY" = 0 ]; then
    adb_shell "logcat -d -s Twouich:I" | tr -d '\r' | grep -q "chat restaure affiche" \
        && ok "trace de relecture : « chat restaure affiche »" \
        || ecart "aucune trace « chat restaure affiche » : l'état n'est pas relu, ou reste collé"
fi

# ── verdict ───────────────────────────────────────────────────────────────────
printf '\n═══════════════════════════════════════════════════════════════\n'
printf 'bornes mesurées (arbre des vues, %s)\n' "$([ "$REPLAY" = 1 ] && echo 'rejeu hors appareil' || echo 'appareil')"
printf '%s' "$PREUVE"
printf '═══════════════════════════════════════════════════════════════\n'
printf '✅ verdict : 6 états conformes — chat repliable et mémorisé, saisie au bas, bouton inamovible\n'
exit 0
