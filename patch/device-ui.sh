#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
# device-ui.sh — piloter l'interface de l'appareil par ADB : focus + D-pad
# ═══════════════════════════════════════════════════════════════════════
# Usage :
#   bash patch/device-ui.sh                          # aide
#   bash patch/device-ui.sh --list                   # appareils utilisables
#   bash patch/device-ui.sh --serial 192.168.1.24:5555 probe
#   bash patch/device-ui.sh --connect 127.0.0.1:5555 texts
#
#   probe           quel canal agit réellement sur CET appareil ? (à lancer en premier)
#   launch          lance l'app et relève le focus (repris de test-device.sh étape 1)
#   texts           textes présents à l'écran — la « signature d'écran »
#   focus           élément qui a le focus, sa classe et ses bornes
#   clickables      éléments cliquables de l'écran + bornes
#   find <texte>    localiser un élément par son texte (cliquable ? focusable ?)
#   nav <texte>     amener le focus sur cet élément (D-pad)
#   press           activer l'élément focalisé (DPAD_CENTER)
#   tap <x> <y>     tap par coordonnées, avec repli D-pad si le tactile est absorbé
#   key <code>      touche brute (4 = BACK, 3 = HOME, 19/20/21/22 = flèches)
#   shot <f.png>    capture d'écran (signal humain, pas signal de test)
#   step <avant> <actions> <apres>
#                   UNE vérification complète en une ligne : l'écran attendu, les
#                   actions, l'écran obtenu. Sort 0 si conforme, 1 sinon — de quoi
#                   écrire une recette de bout en bout dans un script bash.
#                   <actions> = verbes séparés par « + », chacun `verbe[:argument]` :
#                     nav:Niniste   amener le focus sur ce texte
#                     press        activer l'élément focalisé (DPAD_CENTER)
#                     key:4        touche brute (BACK)
#                     tap:540,650  tap par coordonnées
#                     launch       lancer l'app
#                     wait:3       attendre (secondes, décimales acceptées)
#                   Exemple :
#                     bash patch/device-ui.sh step "Live Stream History" \
#                          "nav:Niniste+press" "Chat"
#
# Variables d'environnement :
#   ADB      binaire adb (défaut : détection automatique, cf. test-device.sh)
#   SERIAL   appareil visé (défaut : le seul en état « device »)
#   PKG      paquet lancé par `launch` (défaut : com.s0und.s0undtv)
#   UI_KEY   touche utilisée par `nav` (défaut : 20 = DPAD_DOWN)
#   UI_MAX   nombre maximum de déplacements pour `nav` (défaut : 30)
#   UI_XML   chemin de l'arbre sur l'appareil (défaut : /sdcard/device-ui.xml)
#
# POURQUOI CET OUTIL
#
# Sur certains appareils, l'injection **tactile** par ADB est silencieusement
# absorbée : `input tap` trace bien l'événement côté système, mais l'application
# n'y réagit jamais — ni sur un bouton, ni au milieu de l'écran, ni même au
# BACK. Les **touches**, elles, passent. C'est le cas mesuré sur la Freebox du
# foyer (les boutons de la fiche chaîne ne s'ouvrent qu'au D-pad, cf. § 2 étape 3
# de TEST-DEVICE.md) et sur un téléphone HyperOS/MIUI.
#
# Ailleurs (BlueStacks, mesuré aussi), `input tap` fonctionne parfaitement. Le
# canal n'est donc PAS une propriété d'Android : c'est une propriété de
# l'appareil. D'où `probe`, qui le mesure au lieu de le supposer — et qui évite
# de conclure à tort « l'app est figée » ou « l'écran est inatteignable ».
#
# Méthode complète, avec les pièges et les preuves : TEST-DEVICE.md § 8.
# --- fin-de-l-aide (marqueur ASCII : l'aide s'arrête ici, la suite est l'implémentation)
set -uo pipefail

# Git Bash (MSYS) réécrit les chemins absolus passés aux binaires natifs :
# `/sdcard/device-ui.xml` deviendrait `C:/Program Files/Git/sdcard/device-ui.xml`,
# ce qui fait réussir `uiautomator dump` en rendant l'arbre **vide**. Tout le
# reste de l'outil dépend de cet arbre. Même correctif que test-device.sh.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

# L'aide ne dépend d'aucun appareil : la traiter avant toute résolution, sinon
# un `help` sans téléphone branché échoue au lieu de renseigner. N'imprime que
# l'en-tête, jamais les commentaires d'implémentation qui le suivent.
show_help() {
    awk 'NR > 1 {
        if (!/^#/) exit
        if (/^# --- fin-de-l-aide/) exit
        sub(/^# ?/, "")
        print
    }' "$0"
}
case "${1:-}" in
    ""|-h|--help|help) show_help; exit 0 ;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKG="${PKG:-com.s0und.s0undtv}"
UI_KEY="${UI_KEY:-20}"   # 20 = DPAD_DOWN, 19 = DPAD_UP, 21 = DPAD_LEFT, 22 = DPAD_RIGHT
UI_MAX="${UI_MAX:-30}"
UI_XML="${UI_XML:-/sdcard/device-ui.xml}"

# ── Options globales (avant la commande) ────────────────────────────────
CONNECT=""
LIST_ONLY=0
while [ $# -gt 0 ]; do
    case "$1" in
        --connect)   CONNECT="${2:-}"; shift ;;
        --serial|-s) SERIAL="${2:-}"; shift ;;
        --list)      LIST_ONLY=1 ;;
        --*)         echo "option inconnue : $1 (essayer « bash $0 help »)" >&2; exit 2 ;;
        *)           break ;;
    esac
    shift
done
CMD="${1:-}"
ARG1="${2:-}"
ARG2="${3:-}"
ARG3="${4:-}"

# ── Résolution d'adb (mêmes candidats que test-device.sh) ───────────────
find_adb() {
    if [ -n "${ADB:-}" ] && [ -x "$ADB" ]; then echo "$ADB"; return; fi
    if command -v adb >/dev/null 2>&1; then command -v adb; return; fi
    for c in \
        "$LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe" \
        "/c/Users/$USERNAME/AppData/Local/Android/Sdk/platform-tools/adb.exe" \
        "/c/Users/$USERNAME/AppData/Local/ScrcpyGUI/scrcpy-bin/adb.exe" \
        "/c/Program Files/BlueStacks_nxt/HD-Adb.exe" \
        "/c/Program Files (x86)/BlueStacks_nxt/HD-Adb.exe" \
        "/c/Program Files/BlueStacks/HD-Adb.exe" \
        "/c/Program Files/Nox/bin/adb.exe" \
        "/usr/bin/adb" "/usr/local/bin/adb"; do
        [ -x "$c" ] && { echo "$c"; return; }
    done
    return 1
}
ADB="$(find_adb)" || {
    echo "❌ adb introuvable." >&2
    echo "   → Android SDK : installe 'platform-tools' (adb.exe)" >&2
    echo "   → BlueStacks  : C:\\Program Files\\BlueStacks_nxt\\HD-Adb.exe" >&2
    echo "   → ou : ADB=/chemin/vers/adb bash patch/device-ui.sh …" >&2
    exit 1
}

if [ -n "${CONNECT:-}" ] && [ "$LIST_ONLY" -eq 0 ]; then
    "$ADB" connect "$CONNECT" >/dev/null 2>&1 || true
fi

# ── Sélection de l'appareil ─────────────────────────────────────────────
list_devices() {
    "$ADB" devices 2>/dev/null | tr -d '\r' | awk 'NR>1 && $2=="device" {print $1}'
}

mapfile -t DEV_LINES < <(list_devices)
[ "${#DEV_LINES[@]}" -gt 0 ] || { "$ADB" start-server >/dev/null 2>&1; sleep 3; mapfile -t DEV_LINES < <(list_devices); }

if [ "$LIST_ONLY" -eq 1 ]; then
    echo "appareils utilisables : ${#DEV_LINES[@]}"
    for l in ${DEV_LINES[@]+"${DEV_LINES[@]}"}; do echo "   $l"; done
    exit 0
fi

if [ -z "${SERIAL:-}" ]; then
    case "${#DEV_LINES[@]}" in
        0)
            echo "❌ aucun appareil utilisable (état 'device')." >&2
            echo "   TV : Paramètres > Débogage ADB, puis  $ADB connect <ip>:5555" >&2
            echo "   BlueStacks : Avancé > ADB, puis      $ADB connect 127.0.0.1:5555" >&2
            exit 1 ;;
        1)  SERIAL="${DEV_LINES[0]}" ;;
        *)
            echo "❌ plusieurs appareils : précise lequel avec --serial." >&2
            for l in "${DEV_LINES[@]}"; do echo "     $l" >&2; done
            exit 1 ;;
    esac
fi

# ─── primitives ─────────────────────────────────────────────────────────

# Un `adb shell` peut échouer en « error: closed » quand deux binaires adb se
# disputent le port 5037 (cf. § 1 de TEST-DEVICE.md) : on redémarre le serveur
# une fois et on réessaie, comme test-device.sh.
adbs() {
    local out rc
    out="$("$ADB" -s "$SERIAL" shell "$@" 2>&1)"
    rc=$?
    if printf '%s' "$out" | grep -q 'error: closed'; then
        "$ADB" kill-server >/dev/null 2>&1; sleep 2
        "$ADB" start-server >/dev/null 2>&1; sleep 3
        out="$("$ADB" -s "$SERIAL" shell "$@" 2>&1)"
        rc=$?
    fi
    printf '%s\n' "$out"
    return $rc
}

# L'arbre d'accessibilité, un nœud par ligne. C'est la source de vérité de
# toute la méthode : il voit ce qu'un outil d'assistance verrait, focus compris.
ui_dump() {
    adbs uiautomator dump "$UI_XML" >/dev/null 2>&1
    adbs cat "$UI_XML" 2>/dev/null | tr '<' '\n'
}

# Textes affichés, dédoublonnés. Sert de **signature d'écran** : comparer deux
# relevés dit objectivement si une action a changé quelque chose — bien plus
# fiable qu'un hash d'image, qui échoue sur certains appareils (§ 8.3).
ui_texts() {
    ui_dump | grep -oE 'text="[^"]{2,}"' | sort -u
}

node_of() {  # node_of <texte> — nœud complet portant ce texte
    ui_dump | grep -F "text=\"$1\"" | head -1
}

field() {  # field <attribut> < <ligne de nœud>
    grep -oE "$1=\"[^\"]*\"" | head -1 | sed "s/^$1=\"//; s/\"$//"
}

# Centre d'un nœud, depuis bounds="[x1,y1][x2,y2]". Attention : les bornes sont
# séparées par des **virgules** — les confondre avec le « x » des tailles
# d'écran (`wm size` → 1220x2712) donne des coordonnées fausses sans le moindre
# message d'erreur (piège payé, § 8.4).
node_center() {
    local b x1 y1 x2 y2
    b="$(printf '%s' "$1" | field bounds)"
    read -r x1 y1 x2 y2 <<<"$(printf '%s' "$b" | sed -n \
        's/^\[\([0-9-]*\),\([0-9-]*\)\]\[\([0-9-]*\),\([0-9-]*\)\]$/\1 \2 \3 \4/p')"
    [ -n "${x1:-}" ] || return 1
    echo "$(( (x1 + x2) / 2 )) $(( (y1 + y2) / 2 ))"
}

focus_now() {
    local line t
    line="$(ui_dump | grep 'focused="true"' | head -1)"
    if [ -z "$line" ]; then
        echo "(aucun élément focalisé)"
        return 1
    fi
    t="$(printf '%s' "$line" | field text)"
    [ -n "$t" ] || t="$(printf '%s' "$line" | field content-desc)"
    printf '%s  [%s]  %s\n' "${t:-(sans texte)}" \
        "$(printf '%s' "$line" | field class)" "$(printf '%s' "$line" | field bounds)"
}

# ─── commandes ──────────────────────────────────────────────────────────

cmd_probe() {
    # Mesure les deux canaux au lieu de les supposer, sur l'écran courant.
    # Le test tactile vise un élément **cliquable** de l'arbre : viser le centre
    # de l'écran donnerait un faux négatif sur tout écran dont le milieu est
    # vide (la plupart des formulaires).
    echo "appareil : $SERIAL"
    echo "écran    : $(focus_now)"

    local line centre x y before after tactile="?" touches="?" tentatives=0

    echo
    echo "── canal tactile : input tap ──"
    # Jusqu'à trois cibles distinctes : un premier élément cliquable inerte
    # (vue désactivée, bouton recouvert) produirait un faux négatif sur un
    # appareil où le tactile marche parfaitement.
    while IFS= read -r line && [ "$tentatives" -lt 3 ]; do
        centre="$(node_center "$line")" || continue
        x="${centre% *}"; y="${centre#* }"
        tentatives=$(( tentatives + 1 ))
        echo "   cible $tentatives : « $(printf '%s' "$line" | field text) » @ ($x,$y)"
        before="$(ui_texts)"
        adbs input tap "$x" "$y" >/dev/null 2>&1
        sleep 2
        after="$(ui_texts)"
        if [ "$before" != "$after" ]; then
            echo "   ✓ agit — l'écran a changé"
            tactile=oui
            break
        fi
        echo "     sans effet"
        tactile=non
    done < <(ui_dump | grep 'clickable="true"' | grep -v 'bounds="\[0,0\]\[0,0\]"')

    [ "$tentatives" -gt 0 ] || {
        echo "   ? aucun élément cliquable à l'écran — non concluant"
        echo "     (ouvrir un écran contenant un bouton, puis relancer le probe)"
        tactile="?"
    }

    echo
    echo "── canal touches : input keyevent ──"
    before="$(ui_dump | grep 'focused="true"' | field text)"
    adbs input keyevent "$UI_KEY" >/dev/null 2>&1
    sleep 1
    after="$(ui_dump | grep 'focused="true"' | field text)"
    if [ -z "$before" ] && [ -z "$after" ]; then
        echo "   ? indéterminé — aucun élément focalisé avant ni après"
        echo "     (écran sans élément focusable, ou navigation à refaire ailleurs)"
    elif [ "$before" = "$after" ]; then
        echo "   ✗ la touche n'a pas déplacé le focus (« ${before:-(rien)} » → « ${after:-(rien)} »)"
        echo "     essayer un autre sens : UI_KEY=19|21|22"
        touches=non
    else
        echo "   ✓ agit — focus déplacé : « ${before:-(rien)} » → « $after »"
        touches=oui
    fi

    echo
    echo "── conclusion ──"
    printf '   tactile=%s   touches=%s\n' "$tactile" "$touches"
    case "$tactile$touches" in
        nonoui) echo "   → cas Freebox / MIUI : piloter au D-pad uniquement."
                echo "     bash patch/device-ui.sh nav \"<texte du bouton>\" && bash patch/device-ui.sh press" ;;
        *oui*)  echo "   → le tactile suffit ; garder le D-pad pour les éléments hors champ." ;;
        nonnon) echo "   → aucun canal : l'appareil ou l'écran ne répond pas à l'injection." ;;
        *)      echo "   → non concluant : refaire le probe sur un écran avec un bouton cliquable." ;;
    esac
    echo "   méthode complète : TEST-DEVICE.md § 8"
}

cmd_launch() {
    # Lance l'app par son activité de lancement (la voie monkey de test-live.sh),
    # puis relève le focus : c'est le point de départ de la boucle de navigation.
    adbs monkey -p "$PKG" -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
    sleep 6
    echo "✓ $PKG lancé — focus : $(focus_now)"
}

cmd_texts() { ui_texts; }

cmd_focus() { focus_now; }

cmd_clickables() {
    ui_dump | grep 'clickable="true"' | while IFS= read -r line; do
        local t; t="$(printf '%s' "$line" | field text)"
        printf '%-42s %s\n' "${t:-(sans texte)}" "$(printf '%s' "$line" | field bounds)"
    done
}

cmd_find() {
    local t="$1" line
    line="$(node_of "$t")"
    if [ -z "$line" ]; then echo "✗ « $t » absent de l'écran"; return 1; fi
    printf 'text     : %s\nclass    : %s\nclickable: %s\nfocusable: %s\nfocused  : %s\nbounds   : %s\n' \
        "$(printf '%s' "$line" | field text)" "$(printf '%s' "$line" | field class)" \
        "$(printf '%s' "$line" | field clickable)" "$(printf '%s' "$line" | field focusable)" \
        "$(printf '%s' "$line" | field focused)" "$(printf '%s' "$line" | field bounds)"
}

cmd_nav() {
    # Déplace le focus jusqu'à l'élément voulu. C'est cette primitive qui
    # remplace la boucle manuelle du § 2 étape 3 (« dumper, repérer le focus,
    # naviguer, re-dumper, valider ») — et qui lève la limite du dump en retard
    # d'un cran : le focus est relu **après chaque** déplacement.
    local target="$1" i cur vus=0
    for i in $(seq 1 "$UI_MAX"); do
        cur="$(ui_dump | grep 'focused="true"' | head -1)"
        [ -n "$cur" ] && vus=$((vus + 1))
        if printf '%s' "$cur" | grep -qF "text=\"$target\""; then
            echo "✓ focus sur « $target » après $((i-1)) déplacement(s)"
            return 0
        fi
        # Mauvais axe, ou écran qui ne donne le focus à personne : le dire tout
        # de suite. Mesuré sur un vrai écran d'accueil (aucun élément focalisé) :
        # `nav` brûlait sinon 30 crans de D-pad pendant **87 s** sur un direct en
        # cours avant de rendre le même verdict, sans la cause.
        if [ "$i" -ge 3 ] && [ "$vus" -eq 0 ]; then
            echo "✗ aucun élément n'a pris le focus après 3 déplacements (UI_KEY=$UI_KEY)" >&2
            echo "  → mauvais axe (essayer UI_KEY=19|21|22), ou écran qui ne focalise rien" >&2
            echo "    (une grille Leanback prend le focus dans l'axe de ses rangées)." >&2
            return 1
        fi
        adbs input keyevent "$UI_KEY" >/dev/null 2>&1
        sleep 0.4
    done
    echo "✗ « $target » non atteint en $UI_MAX déplacements (UI_KEY=$UI_KEY)" >&2
    echo "  focus actuel : $(focus_now)" >&2
    return 1
}

cmd_press() {
    # DPAD_CENTER (23) active l'élément focalisé — l'équivalent du clic sur une
    # UI TV. 66 (ENTER) est la variante clavier.
    adbs input keyevent 23 >/dev/null 2>&1
    sleep 1
    echo "✓ DPAD_CENTER envoyé — focus restant : $(focus_now)"
}

cmd_key() {
    adbs input keyevent "$1" >/dev/null 2>&1
    sleep 1
    echo "✓ touche $1 envoyée"
}

cmd_tap() {
    # Tap par coordonnées, mais on VÉRIFIE, et on le dit si ça n'a rien fait :
    # c'est ce qui distingue « le tactile est absorbé » de « la cible était
    # inerte », deux causes dont une seule appelle le repli D-pad.
    local x="$1" y="$2" before after
    before="$(ui_texts)"
    adbs input tap "$x" "$y" >/dev/null 2>&1
    sleep 2
    after="$(ui_texts)"
    if [ "$before" = "$after" ]; then
        echo "✗ tap ($x,$y) sans effet visible — le tactile paraît absorbé sur cet appareil."
        echo "  repli :  bash patch/device-ui.sh nav \"<texte du bouton>\" && bash patch/device-ui.sh press"
        return 1
    fi
    echo "✓ tap ($x,$y) a changé l'écran"
}

cmd_shot() {
    # Utile pour l'œil humain, mais à ne PAS utiliser comme signal de test :
    # sur BlueStacks, `screencap` écrit un fichier vide **sur l'appareil même**
    # (0 octet) — la copie n'y est pour rien, et un hash vide ressemble
    # exactement à « l'écran n'a pas changé ». Le signal fiable, c'est `texts`.
    local out="$1" taille
    adbs screencap -p /sdcard/device-ui.png >/dev/null 2>&1
    taille="$(adbs stat -c %s /sdcard/device-ui.png 2>/dev/null | tr -d '\r')"
    "$ADB" -s "$SERIAL" exec-out cat /sdcard/device-ui.png > "$out" 2>/dev/null
    adbs rm -f /sdcard/device-ui.png >/dev/null 2>&1
    if [ -s "$out" ]; then
        echo "✓ $out ($(wc -c < "$out" | tr -d ' ') octets)"
        return 0
    fi
    echo "✗ capture vide" >&2
    if [ "${taille:-0}" = "0" ]; then
        echo "  cause : screencap a écrit 0 octet SUR l'appareil — ce n'est pas la copie." >&2
        echo "  cet appareil ne sait pas capturer son écran ; utiliser « texts » comme signal." >&2
    fi
    return 1
}

# ─── une recette en une ligne ──────────────────────────────────────────

# Textes de l'écran, sans le préfixe `text=` — la signature d'écran, lisible.
screen_texts() {
    ui_dump | grep -oE 'text="[^"]{2,}"' | sed 's/^text="//; s/"$//' | sort -u
}

# L'écran contient-il ce texte ? La comparaison porte sur les attributs `text`
# de l'arbre, **sous-chaîne acceptée** : les libellés TV sont souvent composites
# (« Followed Channels (22) », « Radio Jeux vidéo Actualités … »), et exiger
# l'égalité stricte ferait échouer une recette sur une virgule.
screen_has() { screen_texts | grep -qF -- "$1"; }

# Écarte une étape dont la sortie attendue était **déjà là** : le test passerait
# sans rien prouver, ce qui est exactement le piège que `probe` évite pour le
# canal (un signal qui ne distingue pas ce qu'il prétend distinguer).
trim() { local s="$1"; s="${s#"${s%%[![:space:]]*}"}"; printf '%s' "${s%"${s##*[![:space:]]}"}"; }

step_actions() {   # step_actions <liste d'actions> <préfixe d'affichage> ; rc 1 si une action échoue
    local actions="$1" rc=0 tok out xy
    # L'IFS est confiné au `read` qui découpe : un `local IFS=+` posé dans cette
    # fonction resterait actif pour tout ce qu'elle appelle — et transformerait
    # silencieusement le `for i in $(seq 1 $UI_MAX)` de `cmd_nav` en une seule
    # itération (la nouvelle ligne n'étant plus un séparateur), donc en un `nav`
    # qui échoue après un seul déplacement. Trouvé par le harnais hors appareil.
    local -a TOKENS
    IFS=+ read -r -a TOKENS <<< "$actions"
    for tok in "${TOKENS[@]}"; do
        tok="$(trim "$tok")"
        [ -n "$tok" ] || continue
        case "$tok" in
            nav:*)  out="$(cmd_nav "${tok#nav:}" 2>&1)" || rc=1 ;;
            press)  out="$(cmd_press 2>&1)" ;;
            key:*)  out="$(cmd_key "${tok#key:}" 2>&1)" ;;
            tap:*)  xy="${tok#tap:}"; out="$(cmd_tap "${xy%,*}" "${xy#*,}" 2>&1)" || rc=1 ;;
            launch) out="$(cmd_launch 2>&1)" ;;
            wait:*) sleep "${tok#wait:}"; out="attente ${tok#wait:} s" ;;
            *)      echo "$2 verbe inconnu : « $tok » (voir l'aide du script)" >&2; return 2 ;;
        esac
        printf '%s %s → %s\n' "$2" "$tok" "$(printf '%s' "$out" | head -1)"
        # Une action qui échoue interrompt l'étape : enchaîner `press` après un
        # `nav` raté activerait un élément au hasard et rendrait le verdict faux.
        [ "$rc" -eq 0 ] || return 1
    done
    return 0
}

cmd_step() {
    local avant="$1" actions="$2" apres="$3"
    local before after gains pertes rc=0 debut=$SECONDS
    echo "▶ « $avant » → [$actions] → « $apres »"

    before="$(screen_texts)"
    if ! printf '%s\n' "$before" | grep -qF -- "$avant"; then
        echo "  avant  : ✗ « $avant » ABSENT — l'écran de départ n'est pas celui attendu" >&2
        printf '%s\n' "$before" | head -6 | sed 's/^/           /' >&2
        return 1
    fi
    echo "  avant  : ✓ « $avant » présent"
    if printf '%s\n' "$before" | grep -qF -- "$apres"; then
        echo "  ⚠  la sortie attendue est DÉJÀ présente avant l'action :"
        echo "     l'étape passera sans prouver le changement — vérifier le libellé."
    fi

    step_actions "$actions" "  action :" || rc=1
    [ "$rc" -eq 0 ] || { echo "✗ ÉCHEC — une action n'a pas abouti ("$((SECONDS-debut))" s)" >&2; return 1; }

    after="$(screen_texts)"
    # Jointure par awk et non par `paste -sd', '` : GNU paste fait tourner la
    # *liste* de délimiteurs («, » puis «, » puis « »), ce qui donne des lignes
    # irrégulières selon le nombre de textes — donc illisibles dans un diff.
    gains="$(comm -13 <(printf '%s\n' "$before") <(printf '%s\n' "$after") | head -4 \
            | awk 'NR>1 { printf ", " } { printf "%s", $0 }')"
    pertes="$(comm -23 <(printf '%s\n' "$before") <(printf '%s\n' "$after") | head -4 \
            | awk 'NR>1 { printf ", " } { printf "%s", $0 }')"
    echo "  delta  : +[${gains:-aucun}] −[${pertes:-aucun}]"

    if printf '%s\n' "$after" | grep -qF -- "$apres"; then
        echo "  après  : ✓ « $apres » présent"
        echo "✓ ÉTAPE CONFORME ($((SECONDS - debut)) s)"
        return 0
    fi
    echo "  après  : ✗ « $apres » ABSENT" >&2
    printf '%s\n' "$after" | head -6 | sed 's/^/           /' >&2
    echo "✗ ÉCHEC — écran obtenu différent de l'écran attendu ($((SECONDS - debut)) s)" >&2
    return 1
}

# ─── aiguillage ─────────────────────────────────────────────────────────

# L'usage ne signale qu'un **manque d'argument**, jamais l'échec de la commande
# elle-même : les deux étaient confondus, et un `shot` raté affichait en plus
# « usage: shot <fichier.png> ».
usage() { echo "usage: bash patch/device-ui.sh $1" >&2; exit 2; }

case "$CMD" in
    help|-h|--help) show_help ;;   # `--serial X help` passe par ici, pas par le test initial
    probe)      cmd_probe ;;
    launch)     cmd_launch ;;
    texts)      cmd_texts ;;
    focus)      cmd_focus ;;
    clickables) cmd_clickables ;;
    find)       [ -n "$ARG1" ] || usage "find <texte>";        cmd_find "$ARG1" ;;
    nav)        [ -n "$ARG1" ] || usage "nav <texte>";         cmd_nav "$ARG1" ;;
    press)      cmd_press ;;
    tap)        [ -n "$ARG2" ] || usage "tap <x> <y>";         cmd_tap "$ARG1" "$ARG2" ;;
    key)        [ -n "$ARG1" ] || usage "key <code>";          cmd_key "$ARG1" ;;
    shot)       [ -n "$ARG1" ] || usage "shot <fichier.png>";  cmd_shot "$ARG1" ;;
    step)       [ -n "$ARG2" ] && [ -n "$ARG3" ] \
                    || usage "step <texte avant> <actions> <texte apres>"
                cmd_step "$ARG1" "$ARG2" "$ARG3" ;;
    *)          echo "commande inconnue : $CMD (essayer « bash patch/device-ui.sh help »)" >&2; exit 2 ;;
esac
