#!/usr/bin/env python3
"""
patch.py — applique les modifications Twouich sur l'arbre apktool de S0undTV.

Source de vérité : ce script + patch/smali/. Il est idempotent (relancer ne
casse rien) et *échoue bruyamment* si un motif attendu a disparu, pour qu'un
changement en amont (nouvelle beta) ne passe jamais inaperçu.

Usage:
    python patch.py --decoded work/decoded [--version-code 148 --version-name v1.0.1]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import sys

# Console Windows (cp1252) : sans cela, les flèches/accents cassent le script.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

REPO = "Endymi0n74/Twouich"
UPSTREAM = "S0und/S0undTV"
# Nom du livrable tel qu'il est publié : ces défauts ne servent qu'à un appel
# manuel de patch.py — build.sh passe toujours --version-code/--version-name/
# --apk-name. Ils suivent donc le dernier bump (le nom d'APK finit dans l'URL
# que l'app interroge : un défaut en retard pointerait sur un asset inexistant).
DEFAULT_APK_NAME = "Twouich_v1.0.16.apk"

# ── Étape 1 : greffon anti-pub ────────────────────────────────────────────
# Libellés de l'UX smartphone. Le champ de saisie reprend celui de l'interface
# de référence (Twitch mobile / PurpleTV) plutôt que la formulation d'origine.
CHAT_HINT = "Envoyer un message"
CHAT_HINT_LEGACY = "Écrire dans le chat"

# Géométrie du lecteur empilé (téléphone). La vidéo 16:9 se calcule depuis la
# LARGEUR : au-delà de la hauteur disponible le chat recevait une hauteur
# négative (mesuré le 20/09 à 1920×899 : vidéo écrasée, chat à 0 px). Deux
# corrections ont eu lieu — plafonner la vidéo, puis refuser l'empilement quand
# la place restante ne vaut pas un tiers de la hauteur (paysage) — et les deux
# formes antérieures sont réparées au passage.
PHONE_GEO_OLD_TAIL = ("    const/16 v11, 0x70\n"
                      "    sub-int v7, v9, v10\n"
                      "    sub-int/2addr v7, v11\n")
PHONE_GEO_CLAMPED_TAIL = PHONE_GEO_OLD_TAIL.replace(
    "    const/16 v11, 0x70\n",
    "    const/16 v11, 0x70\n    sub-int v7, v9, v11\n"
    "    if-ge v10, v7, :twouich_phone_video_fits\n    move v10, v7\n"
    ":twouich_phone_video_fits\n",
)
# if-lt : on SAUTE le plafond quand la vidéo tient déjà (v10 < v7) ;
# if-ge : on empile quand il reste au moins un tiers de la hauteur pour le chat.
PHONE_GEO_ROOM_BLOCK = ("    const/4 v3, 0x3\n"
                        "    div-int v3, v9, v3\n"
                        "    if-ge v7, v3, :twouich_phone_room\n"
                        "    goto :return_phone_layout\n"
                        ":twouich_phone_room\n")
PHONE_GEO_TAIL = PHONE_GEO_CLAMPED_TAIL.replace(
    "    if-ge v10, v7, :twouich_phone_video_fits",
    "    if-lt v10, v7, :twouich_phone_video_fits",
) + PHONE_GEO_ROOM_BLOCK

# --- Incrustation (picture-in-picture) ---------------------------------------
# Le 20/09, l'acceptation PiP sur le téléphone a montré la barre « Envoyer un
# message » tracée sur le bas de la FENÊTRE D'INCRUSTATION : l'entrée en PiP fait
# perdre le focus et change la configuration, et chacun de ces rappels
# réappliquait l'empilement APRÈS le masquage posé par le rappel PiP. La
# disposition téléphone refuse donc de s'appliquer tant que l'état d'incrustation
# — un champ d'instance écrit en tête du rappel — est vrai. Ces textes servent à
# la fois au bloc injecté et à la réparation d'un arbre déjà patché : une seule
# source, donc pas de dérive entre les deux chemins.
PHONE_PIP_STATE_WRITE = (
    "\n"
    "    # L'état est écrit AVANT tout le reste : les rappels de perte de focus et de\n"
    "    # changement de configuration qui accompagnent la transition lisent ce champ\n"
    "    # (garde en tête de twouichPhoneStackedLayout).\n"
    "    iput-boolean p1, p0, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPipActive:Z\n"
)
# Needle exacte : « iput-boolean p1, p0, » tout court apparait déjà dans le code
# upstream (champ a2 de PlayerActivity), donc un test d'absence sur ce préfixe
# concluait « déjà écrit » et l'état n'était jamais posé — vu à la compilation du
# 20/09. Le nom du champ rend le test non ambigu.
PHONE_PIP_STATE_NEEDLE = ("iput-boolean p1, p0, Lcom/s0und/s0undtv/activities/"
                          "PlayerActivity;->twouichPipActive:Z")
# Polarity du garde de twouichPhoneView : « if-nez v0, :no_phone_view » sautait
# vers le retour nul dès que l'identifiant ETAIT trouve, donc la vue n'etait
# jamais rendue — le rappel PiP sortait aussitôt sur ses trois `if-eqz` et ne
# masquait rien (chat et saisie traces sur la video, mesures du 20/09).
PHONE_PIP_VIEW_OLD = "    if-nez v0, :no_phone_view"
PHONE_PIP_VIEW_NEW = "    if-eqz v0, :no_phone_view"
PHONE_PIP_SUPER = ("    invoke-super {p0, p1, p2}, Landroid/app/Activity;"
                   "->onPictureInPictureModeChanged(ZLandroid/content/res/Configuration;)V\n")
PHONE_PIP_GUARD = (
    "\n"
    "    # Pendant l'incrustation, la fenêtre fait déjà 16:9 et le rappel PiP a posé\n"
    "    # le masquage du chat et de la saisie. Toute réapplication de l'empilement\n"
    "    # ici — perte de focus du passage en PiP, changement de configuration —\n"
    "    # ferait réapparaître la barre de saisie PAR-DESSUS la vidéo : mesuré le\n"
    "    # 20/09 sur le téléphone (bande « Envoyer un message » tracée sur le bas de\n"
    "    # la fenêtre d'incrustation). Le champ twouichPipActive est écrit en tête de\n"
    "    # onPictureInPictureModeChanged, donc posé quel que soit l'ordre des rappels.\n"
    "    sget v11, Landroid/os/Build$VERSION;->SDK_INT:I\n"
    "\n"
    "    const/16 v10, 0x18\n"
    "\n"
    "    if-ge v11, v10, :twouich_phone_layout_ok\n"
    "\n"
    "    iget-boolean v11, p0, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPipActive:Z\n"
    "\n"
    "    if-eqz v11, :twouich_phone_layout_ok\n"
    "\n"
    "    const-string v11, \"Twouich\"\n"
    "\n"
    "    const-string v10, \"picture-in-picture : empilement ignore (incrustation active)\"\n"
    "\n"
    "    invoke-static {v11, v10}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I\n"
    "\n"
    "    return-void\n"
    "\n"
    "    :twouich_phone_layout_ok\n"
)
PHONE_PIP_HIDE_TRACE = (
    "\n"
    "    const-string v3, \"Twouich\"\n"
    "\n"
    "    const-string v4, \"picture-in-picture : video plein cadre, chat et saisie masques\"\n"
    "\n"
    "    invoke-static {v3, v4}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I\n"
)
PHONE_PIP_RESTORE_TRACE = (
    "\n"
    "    const-string v3, \"Twouich\"\n"
    "\n"
    "    const-string v4, \"picture-in-picture : disposition empilee restauree\"\n"
    "\n"
    "    invoke-static {v3, v4}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I\n"
)

# Chat replié dans la disposition empilée : twouichPhoneStackedLayout est
# rappelée à chaque reprise d'activité (onWindowFocusChanged,
# onConfigurationChanged) et remettait le chat VISIBLE — le chat replié
# revenait tout seul alors que l'état (twouichChatHidden) disait toujours
# « replié » (mesuré le 21/09). Le garde est réapposé aux arbres déjà patchés
# par la même mécanique que PHONE_PIP_GUARD : une seule source de texte.
# Ecran eteint : la lecture continue. onStop() demonte les deux instances
# ExoPlayer (`w2()`/`R1()`, `x2()`/`R1()`) puis `o3()` — et c'est ce demontage
# qui coupait le direct des que l'ecran s'eteignait (« si je mets le telephone
# en veille je veux que le stream continue », 21/09). Mesure du 21/09 sur le
# telephone, service de premier plan `mediaPlayback` actif : `disconnectFromSurface`
# (decodeur video) et `setStreamEndDone` (AudioTrack) a la seconde meme de
# l'extinction — proteger le seul `o3()` ne suffisait pas. Le garde enveloppe
# donc tout le demontage, et `invoke-super` reste appele dans tous les cas.

def _smali_lines(*rows: str) -> str:
    """Assemble un bloc smali, une ligne par element.

    Les gabarits du fichier ecrivent leurs fins de ligne en echappement ; ici on
    les produit, pour n'avoir aucun caractere d'echappement a relire ni a casser
    en modifiant le bloc.
    """
    return "".join(row + chr(10) for row in rows)


PHONE_SCREEN_OFF_NL = chr(10)

# Premiere ligne du demontage d'onStop() : point d'insertion du garde.
PHONE_SCREEN_OFF_ANCHOR = _smali_lines(
    "    invoke-virtual {p0}, "
    "Lcom/s0und/s0undtv/activities/PlayerActivity;->w2()LG6/i;",
)
# Appel qui fermait la lecture : la forme precedente du garde le protegeait seul.
PHONE_SCREEN_OFF_O3 = _smali_lines(
    "    invoke-virtual {p0}, "
    "Lcom/s0und/s0undtv/activities/PlayerActivity;->o3()V",
)
PHONE_SCREEN_OFF_SUPER = "    invoke-super {p0}, Landroid/app/Activity;->onStop()V"
PHONE_SCREEN_OFF_DONE = "    :twouich_screen_off_done"
PHONE_SCREEN_OFF_GOTO = "    goto :twouich_screen_off_done"

# Forme ecrite par la v1.0.13/159 (garde devant `o3()` seul, polarite inversee).
# Elle doit disparaitre d'un arbre deja patche : deux gardes ne peuvent pas
# cohabiter, et un arbre reutilise tel quel ne changerait jamais de SHA.
PHONE_SCREEN_OFF_LEGACY = _smali_lines(
    "    # Ecran eteint : on NE libere PAS les lecteurs, le telephone sert de",
    "    # lecteur de poche. Registres v0/v1 : ceux de la methode (.locals 2),",
    "    # tous deux morts a cet endroit du corps.",
    "    const-string v1, \"power\"",
    "    invoke-virtual {p0, v1}, Landroid/content/Context;->getSystemService(",
    "Ljava/lang/String;)Ljava/lang/Object;",
    "    move-result-object v1",
    "    check-cast v1, Landroid/os/PowerManager;",
    "    invoke-virtual {v1}, Landroid/os/PowerManager;->isInteractive()Z",
    "    move-result v1",
    "    if-eqz v1, :twouich_screen_off_stop",
    "    const-string v0, \"Twouich\"",
    "    const-string v1, \"ecran eteint : lecture maintenue\"",
    "    invoke-static {v0, v1}, Landroid/util/Log;->i(",
    "Ljava/lang/String;Ljava/lang/String;)I",
    "    goto :twouich_screen_off_done",
    "    :twouich_screen_off_stop",
) + PHONE_SCREEN_OFF_O3 + _smali_lines(PHONE_SCREEN_OFF_DONE)

# Garde : on saute tout le demontage quand l'ecran N'EST PAS interactif.
# Registres v0/v1 : ceux de la methode (`.locals 2`), morts a cet endroit.
PHONE_SCREEN_OFF_GUARD = _smali_lines(
    "    # Ecran eteint : on NE demonte PAS les lecteurs, le telephone sert de",
    "    # lecteur de poche. Mesure du 21/09 : ce demontage coupe le decodeur",
    "    # (disconnectFromSurface) et l'AudioTrack (setStreamEndDone) a la",
    "    # seconde de l'extinction, service de premier plan actif ou non.",
    "    # Polarite : `if-eqz` sur isInteractive() saute quand l'ecran est",
    "    # eteint ; ecran allume, on demonte comme avant.",
    "    const-string v1, \"power\"",
    "    invoke-virtual {p0, v1}, Landroid/content/Context;->getSystemService(",
    "Ljava/lang/String;)Ljava/lang/Object;",
    "    move-result-object v1",
    "    check-cast v1, Landroid/os/PowerManager;",
    "    invoke-virtual {v1}, Landroid/os/PowerManager;->isInteractive()Z",
    "    move-result v1",
    "    if-eqz v1, :twouich_screen_off_kept",
)
# Chemin « ecran eteint » : on trace et on rejoint la sortie, sans demonter.
PHONE_SCREEN_OFF_KEPT = _smali_lines(
    "    :twouich_screen_off_kept",
    "    const-string v0, \"Twouich\"",
    "    const-string v1, \"ecran eteint : lecture maintenue (demontage saute)\"",
    "    invoke-static {v0, v1}, Landroid/util/Log;->i(",
    "Ljava/lang/String;Ljava/lang/String;)I",
)


def _patch_screen_off_stop(text: str) -> tuple[str, bool]:
    """Maintient la lecture quand l'ecran s'eteint (cf. PHONE_SCREEN_OFF_GUARD).

    Le garde enveloppe TOUT le demontage d'onStop() (w2/R1/x2/R1/o3) : la mesure
    du 21/09 a montre que proteger le seul o3() laissait le demontage couper le
    decodeur video et l'AudioTrack a la seconde de l'extinction. `invoke-super`
    reste appele dans tous les cas.
    """
    match = re.search(r"(?ms)^[.]method protected onStop[(][)]V.*?^[.]end method", text)
    if match is None:
        fail("onStop() introuvable dans PlayerActivity.smali (veille)")
    body = match.group(0)
    # Arbre deja patche : on remet le corps d'origine avant de reposer le garde.
    if PHONE_SCREEN_OFF_LEGACY in body:
        body = body.replace(PHONE_SCREEN_OFF_LEGACY, PHONE_SCREEN_OFF_O3, 1)
    for injected in (PHONE_SCREEN_OFF_GUARD, PHONE_SCREEN_OFF_KEPT, PHONE_SCREEN_OFF_GOTO):
        if injected in body:
            body = body.replace(injected, "", 1)
    label = PHONE_SCREEN_OFF_DONE + PHONE_SCREEN_OFF_NL
    if label in body:
        body = body.replace(label, "", 1)
    anchor = body.find(PHONE_SCREEN_OFF_ANCHOR)
    if anchor < 0:
        fail("demontage (w2/R1) introuvable dans onStop() (veille)")
    super_call = body.find(PHONE_SCREEN_OFF_SUPER)
    if super_call < 0 or super_call < anchor:
        fail("invoke-super onStop() introuvable apres le demontage (veille)")
    new_body = (body[:anchor]
                + PHONE_SCREEN_OFF_GUARD
                + body[anchor:super_call]
                + PHONE_SCREEN_OFF_GOTO + PHONE_SCREEN_OFF_NL
                + PHONE_SCREEN_OFF_KEPT
                + PHONE_SCREEN_OFF_DONE + PHONE_SCREEN_OFF_NL
                + body[super_call:])
    if new_body == body:
        return text, False
    return text[:match.start()] + new_body + text[match.end():], True


# --- Interface TV : une seule source de verite --------------------------------
# Le mode TV ne se lit PAS dans les dp : un televiseur 1080p en 320 dpi declare
# 540 dp (mesure du 21/09 sur la Freebox), donc un seuil a 600 dp laissait la
# disposition telephone s'appliquer sur un vrai televiseur. Le test juste est le
# mode declare par le systeme : uiMode == UI_MODE_TYPE_TELEVISION, le seuil de
# dp restant comme filet pour les ecrans larges (tablettes, TV 4K).
TV_NL = chr(10)

# Le resultat du garde s'ecrit dans v2, JAMAIS dans v0 : dans
# twouichPhoneStackedLayout, v0 porte le `Resources` que la methode relit plus
# loin (getDisplayMetrics). Un `move-result v0` y ecrasait cette reference et le
# verificateur d'ART rejetait la CLASSE ENTIERE — lecteur plante a l'ouverture,
# reproduit sur le telephone le 21/09.
TV_INTERFACE_ROWS = (
    "    invoke-direct {p0}, Lcom/s0und/s0undtv/activities/PlayerActivity;"
    "->twouichTvInterface()Z",
    "    move-result v2",
)

TV_INTERFACE_METHOD = _smali_lines(
    "",
    ".method private twouichTvInterface()Z",
    "    .locals 5",
    "",
    "    invoke-virtual {p0}, Landroid/content/Context;->getResources()"
    "Landroid/content/res/Resources;",
    "    move-result-object v0",
    "    invoke-virtual {v0}, Landroid/content/res/Resources;->getConfiguration()"
    "Landroid/content/res/Configuration;",
    "    move-result-object v1",
    "    iget v2, v1, Landroid/content/res/Configuration;->uiMode:I",
    "    and-int/lit8 v2, v2, 0xf",
    "    const/4 v3, 0x4",
    # `if-eq` : le mode TV EST le type 4. Un `if-ne` ici envoyait tout appareil
    # NON television vers la branche TV — la Freebox ne s'en apercevait pas
    # (540 dp, seuil juste), un telephone, si.
    "    if-eq v2, v3, :twouich_tv_by_mode",
    "    iget v2, v1, Landroid/content/res/Configuration;->smallestScreenWidthDp:I",
    "    const/16 v3, 0x258",
    # ecran large : meme destination que le mode TV (TV 4K, tablettes).
    "    if-ge v2, v3, :twouich_tv_by_mode",
    "    :twouich_tv_by_mode",
    "    const-string v3, \"Twouich\"",
    "    const-string v4, \"interface : TV (mode systeme ou ecran large)\"",
    "    invoke-static {v3, v4}, Landroid/util/Log;->i("
    "Ljava/lang/String;Ljava/lang/String;)I",
    "    const/4 v4, 0x1",
    "    return v4",
    "    :twouich_phone_interface",
    "    const-string v3, \"Twouich\"",
    "    const-string v4, \"interface : telephone (disposition empilee)\"",
    "    invoke-static {v3, v4}, Landroid/util/Log;->i("
    "Ljava/lang/String;Ljava/lang/String;)I",
    "    const/4 v4, 0x0",
    "    return v4",
    ".end method",
)


def use_tv_interface_guard(text: str) -> tuple[str, int]:
    """Ramene les gardes d'interface au test de mode TV (twouichTvInterface).

    Quatre endroits lisaient le seuil de dp seul : l'empilement du lecteur, le
    repli du chat, l'incrustation et l'etat des en-tetes. Mesure du 21/09 sur la
    Freebox : un televiseur 1080p en 320 dpi declare 540 dp, donc la disposition
    telephone s'appliquait a la TV. Les quatre passent maintenant par la methode
    dediee — une seule source de verite, verifiee par l'invariant ci-dessous.
    """
    rows = text.split(TV_NL)
    out: list[str] = []
    changed = 0
    index = 0
    while index < len(rows):
        row = rows[index]
        if row.startswith("    iget ") and "smallestScreenWidthDp:I" in row:
            k = index + 1
            guard = [row]
            while (k < len(rows) and k - index <= 4
                   and (rows[k].strip() == "" or not rows[k].strip().startswith("if-"))):
                guard.append(rows[k])
                k += 1
            body = TV_NL.join(guard)
            if (k < len(rows) and rows[k].strip().startswith("if-ge ")
                    and "0x258" in body):
                label = rows[k].strip().split(",")[-1].strip()
                # Les deux labels internes de twouichTvInterface sont exclus :
                # sans cela, une seconde execution reecrirait le test de la
                # methode en un appel a elle-meme (recursion sans fin).
                if label not in (":twouich_tv_by_mode", ":twouich_phone_interface"):
                    out.extend(TV_INTERFACE_ROWS)
                    # Polarite : la garde d'origine sautait quand on etait sur un
                    # grand ecran (`if-ge dp, 600`) ; l'appel rend VRAI sur une
                    # TV, donc c'est `if-nez` qui saute au meme endroit. Un
                    # `if-eqz` y executait la disposition telephone SUR la TV
                    # (mesure du 21/09 sur la Freebox).
                    out.append("    if-nez v2, " + label)
                    changed += 1
                    index = k + 1
                    continue
        out.append(row)
        index += 1
    return TV_NL.join(out), changed


# Veille : le service de premier plan suit la vie du lecteur. `startIfPhone`
# sort tout seul quand l'interface est une TV (mode systeme) — c'est la meme
# source de verite que le reste de l'interface, implementee dans le service
# (il n'a pas acces a la methode privee du lecteur).
PHONE_SERVICE_START_ANCHOR = (
    "    invoke-direct {p0}, Lcom/s0und/s0undtv/activities/PlayerActivity;"
    "->twouichChatRestore()V\n"
)
PHONE_SERVICE_START_CALL = (
    PHONE_SERVICE_START_ANCHOR
    + "\n    invoke-static {p0}, Lcom/twouich/adblock/PlayerKeepAlive;"
      "->startIfPhone(Landroid/app/Activity;)V\n"
)
PHONE_SERVICE_STOP_ANCHOR = "    invoke-super {p0}, Landroid/app/Activity;->onDestroy()V\n"
PHONE_SERVICE_STOP_CALL = (
    PHONE_SERVICE_STOP_ANCHOR
    + "\n    invoke-static {p0}, Lcom/twouich/adblock/PlayerKeepAlive;"
      "->stop(Landroid/content/Context;)V\n"
)


def _patch_playback_calls(text: str) -> tuple[str, int]:
    """Branche le service de premier plan sur la vie du lecteur (demarrage/arret).

    Sans appel, la classe est dans le dex mais rien ne la demarre : la veille
    garde son defaut mesure le 21/09 (sockets TCP detruits, flux mort en 10 s).
    """
    changed = 0
    if "PlayerKeepAlive;->startIfPhone" not in text:
        if PHONE_SERVICE_START_ANCHOR in text:
            text = text.replace(PHONE_SERVICE_START_ANCHOR, PHONE_SERVICE_START_CALL, 1)
            changed += 1
        else:
            fail("appel twouichChatRestore() introuvable dans onResume() (veille)")
    if "PlayerKeepAlive;->stop(" not in text:
        if PHONE_SERVICE_STOP_ANCHOR in text:
            text = text.replace(PHONE_SERVICE_STOP_ANCHOR, PHONE_SERVICE_STOP_CALL, 1)
            changed += 1
        else:
            fail("invoke-super onDestroy() introuvable dans PlayerActivity (veille)")
    return text, changed


# --- Service de premier plan : declaration au manifeste -----------------------
PLAYBACK_SERVICE = "com.twouich.adblock.PlayerKeepAlive"
PLAYBACK_PERMISSIONS = (
    # FOREGROUND_SERVICE est deja declare par l'amont ; la seule manquante est
    # celle du type, exigee depuis Android 14 pour `mediaPlayback`.
    "android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK",
)


def install_playback_service(decoded: pathlib.Path) -> None:
    """Declare le service de premier plan `mediaPlayback` et sa permission.

    La classe peut etre dans le dex : sans declaration, `startForegroundService`
    est refuse et l'application reste une application d'arriere-plan — le systeme
    detruit alors ses sockets TCP des que l'ecran s'eteint (mesure du 21/09 sur
    le telephone : `InetDiagMessage: Destroyed live tcp sockets`, puis
    `UnknownHostException` au bout de 10 s).
    """
    print("[1j/5] Veille (service de premier plan mediaPlayback)")
    manifest = decoded / "AndroidManifest.xml"
    text = manifest.read_text(encoding="utf-8")
    original = text

    for permission in PLAYBACK_PERMISSIONS:
        if permission in text:
            continue
        anchor = "    <uses-permission "
        if anchor not in text:
            fail("aucune ligne uses-permission dans AndroidManifest.xml")
        text = text.replace(
            anchor,
            f'    <uses-permission android:name="{permission}"/>' + chr(10) + anchor,
            1,
        )
        log(f"veille : permission {permission.rsplit('.', 1)[-1]} declaree")

    service = (
        f'        <service android:name="{PLAYBACK_SERVICE}"'
        ' android:exported="false" android:foregroundServiceType="mediaPlayback" />'
    )
    if PLAYBACK_SERVICE not in text:
        close = "</application>"
        if close not in text:
            fail("fin de <application> introuvable dans AndroidManifest.xml")
        text = text.replace(close, service + chr(10) + close, 1)
        log("veille : service de premier plan mediaPlayback declare")

    if text != original:
        manifest.write_text(text, encoding="utf-8")
    else:
        log("déjà appliqué : service de premier plan mediaPlayback")


PHONE_CHAT_GATE_ANCHOR = ("    const/16 v2, 0x258\n"
                          "    if-ge v1, v2, :return_phone_layout\n")
PHONE_CHAT_GATE = (PHONE_CHAT_GATE_ANCHOR
                   + "\n"
                   + "    # Chat replié par le bouton : c'est la disposition repliée\n"
                   + "    # (vidéo plein écran) qui est réappliquée, jamais l'empilement.\n"
                   + "    iget-boolean v1, p0, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichChatHidden:Z\n"
                   # if-eqz : on GARDE l'empilement quand le drapeau est faux (chat
                   # affiché). Écrit if-nez le 21/09, le garde renvoyait dans la branche
                   # repliée à chaque appel sur un processus neuf — la disposition
                   # téléphone ne s'appliquait plus jamais, sans le moindre journal.
                   + "    if-eqz v1, :stacked_chat_shown\n"
                   + "    invoke-direct {p0}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichChatCollapse()V\n"
                   + "    return-void\n"
                   + "    :stacked_chat_shown\n")

# Le chat doit s'arrêter AU-DESSUS de la barre de saisie. Ancré au bas du parent
# (règle 12), il s'étirait jusque SOUS la saisie : les derniers messages étaient
# cachés par la barre (mesuré le 21/09 : chat `[0,405][720,1280]`, saisie
# `[0,1168][720,1280]` — 112 px de chat perdus).
#
# On ne peut PAS le borner par la règle 2 (AU-DESSUS de la saisie) : la saisie
# porte déjà `addRule(2, chat)` (elle est au-dessus du chat), donc la règle
# inverse ferme le cycle et RelativeLayout refuse de mesurer —
# `IllegalStateException: Circular dependencies cannot exist in RelativeLayout`,
# attrapée par l'acceptation au premier passage de mesure (21/09). On réserve
# donc la hauteur de la saisie par une marge basse, prise dans le MÊME registre
# (v11 = 0x70 = 112 px) que la hauteur donnée à la saisie : les deux valeurs ne
# peuvent pas diverger.
#
# Les deux textes vivent ici (source unique) et servent au gabarit comme à la
# réparation d'un arbre déjà patché. Le nouveau texte contient le même préfixe
# que l'ancien PLUS une ligne : le test de réparation ne peut donc pas boucler
# (il porte sur le bloc entier, ligne `setLayoutParams` comprise).
PHONE_CHAT_BELOW_OLD = (
    "    const/4 v9, 0x3\n"
    "    invoke-virtual {v0, v9, v1}, Landroid/widget/RelativeLayout$LayoutParams;->addRule(II)V\n"
    "    const/16 v9, 0xc\n"
    "    invoke-virtual {v0, v9}, Landroid/widget/RelativeLayout$LayoutParams;->addRule(I)V\n"
    "    invoke-virtual {v5, v0}, Landroid/view/View;->setLayoutParams(Landroid/view/ViewGroup$LayoutParams;)V\n"
)
PHONE_CHAT_BELOW_NEW = (
    "    const/4 v9, 0x3\n"
    "    invoke-virtual {v0, v9, v1}, Landroid/widget/RelativeLayout$LayoutParams;->addRule(II)V\n"
    "    const/16 v9, 0xc\n"
    "    invoke-virtual {v0, v9}, Landroid/widget/RelativeLayout$LayoutParams;->addRule(I)V\n"
    "    iput v11, v0, Landroid/view/ViewGroup$MarginLayoutParams;->bottomMargin:I\n"
    "    invoke-virtual {v5, v0}, Landroid/view/View;->setLayoutParams(Landroid/view/ViewGroup$LayoutParams;)V\n"
)
# État intermédiaire du même jour : le chat borné par la règle 2 (AU-DESSUS de la
# saisie), qui ferme le cycle et fait planter la passe de mesure. Conservé pour
# qu'un arbre de travail ayant vu cette version soit réparé, jamais livré.
PHONE_CHAT_ABOVE_OLD = (
    "    const/4 v9, 0x3\n"
    "    invoke-virtual {v0, v9, v1}, Landroid/widget/RelativeLayout$LayoutParams;->addRule(II)V\n"
    "    const-string v3, \"SendMessageWindow\"\n"
    "    invoke-direct {p0, v3}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhoneId(Ljava/lang/String;)I\n"
    "    move-result v3\n"
    "    const/4 v9, 0x2\n"
    "    invoke-virtual {v0, v9, v3}, Landroid/widget/RelativeLayout$LayoutParams;->addRule(II)V\n"
    "    invoke-virtual {v5, v0}, Landroid/view/View;->setLayoutParams(Landroid/view/ViewGroup$LayoutParams;)V\n"
)


# L'état du chat est relu au démarrage du lecteur AVANT la première application
# de la disposition : sans cela, la première image part de l'état par défaut et
# le choix de l'utilisateur n'arrive qu'après. Le rappel de focus est le seul
# point d'entrée du démarrage qui précède l'empilement — la relecture s'y glisse.
PHONE_CHAT_RESTORE_ANCHOR = (
    "    if-eqz p1, :return_focus\n"
    "    invoke-direct {p0}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhoneStackedLayout()V\n"
)
PHONE_CHAT_RESTORE_CALL = (
    "    if-eqz p1, :return_focus\n"
    "    invoke-direct {p0}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichChatRestore()V\n"
    "    invoke-direct {p0}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhoneStackedLayout()V\n"
)

# Le rappel de focus n'est PAS un point d'entrée fiable du démarrage : mesuré le
# 21/09 sur BlueStacks (Android 13), `onWindowFocusChanged` n'est jamais
# dispatché — l'état du chat n'était donc relu nulle part et un chat replié se
# rouvrait à chaque lancement de l'application. `onResume`, lui, est journalisé
# par l'app elle-même (« onResume() was called ») et précède la première image :
# c'est là que la préférence est relue. Une seule lecture par instance (le champ
# twouichChatRestored garde l'entrée), donc un retour depuis le fond ne relit pas.
# La géométrie empilée vient des DisplayMetrics, pas d'une vue mesurée :
# l'appeler depuis onResume (avant la première passe de disposition) est sûr.
PHONE_CHAT_RESUME_ANCHOR = (
    "    invoke-super {p0}, Landroid/app/Activity;->onResume()V\n"
)
PHONE_CHAT_RESUME_CALL = (
    PHONE_CHAT_RESUME_ANCHOR
    + "\n    invoke-direct {p0}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichChatRestore()V\n"
)
# L'appel lui-même, sans indentation imposée : sert aux contrôles du livrable.
CHAT_RESTORE_CALL_LINE = (
    "invoke-direct {p0}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichChatRestore()V"
)
# Garde de la relecture : un arbre patché le 21/09 avant la correction porte la
# polarité inversée (if-eqz sur un champ faux = sortie immédiate, sans journal).
PHONE_CHAT_RESTORE_GUARD_OLD = "if-eqz v0, :restore_done"
PHONE_CHAT_RESTORE_GUARD_NEW = "if-nez v0, :restore_done"

# Empreinte des greffes du lecteur, écrite À CÔTÉ de l'arbre décodé (jamais
# dedans : apktool empaquette les fichiers inconnus dans l'APK).
#
# Pourquoi : `build.sh` RÉUTILISE l'arbre décodé d'un build à l'autre (seul un
# bump de version le fait redésassembler). Un gabarit modifié — méthode ajoutée,
# garde corrigée — ne s'applique donc PAS à un arbre déjà patché : le build
# repart de l'ancien texte et livre l'ancien comportement, sans le moindre
# message. Le 21/09, une sonde ajoutée à CHAT_METHODS n'est jamais arrivée dans
# le livrable pour cette raison (et l'absence de trace a été cherchée dans le
# mauvais code pendant une heure). Une empreinte qui ne correspond plus fait
# échouer le patch, à charge de désassembler à neuf.
STAMP_SUFFIX = ".twouich-greffes"
# Renseignée par patch_smartphone_ux (les gabarits du lecteur y sont assemblés),
# vérifiée par main : une empreinte vide = le pas de greffe n'a pas tourné.
GREFFE_FINGERPRINT = ""


CHAT_METHODS = r"""
.method private twouichChatTraces()Ljava/lang/String;
    .locals 2

    # Libellé d'état, d'après le champ twouichChatHidden : une seule source de
    # vérité, lue par le toggle comme par l'analyseur logcat.
    # IGET (champ d'instance sur p0) — un sget-boolean compile mais lève une
    # IncompatibleClassChangeError au tap (attrapé sur BlueStacks le 21/09).
    iget-boolean v0, p0, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichChatHidden:Z

    if-eqz v0, :chat_traces_shown

    const-string v0, "chat masque"

    goto :chat_traces_done

    :chat_traces_shown
    const-string v0, "chat affiche"

    :chat_traces_done
    return-object v0
.end method

.method private twouichChatCollapse()V
    .locals 3

    # Chat replié : le bloc chat et la saisie disparaissent et la vidéo prend
    # tout l'écran. Replier n'a d'intérêt que si l'image en profite : mesuré le
    # 21/09, le repli laissait la vidéo en 16:9 et deux tiers d'écran noirs.
    # Téléphone seulement : même garde que twouichPhoneStackedLayout, dont
    # cette méthode est le pendant replié.
    invoke-virtual {p0}, Landroid/content/Context;->getResources()Landroid/content/res/Resources;

    move-result-object v0

    invoke-virtual {v0}, Landroid/content/res/Resources;->getConfiguration()Landroid/content/res/Configuration;

    move-result-object v0

    iget v0, v0, Landroid/content/res/Configuration;->smallestScreenWidthDp:I

    const/16 v1, 0x258

    if-ge v0, v1, :return_chat_collapse

    # Vidéo plein écran : de NOUVEAUX paramètres, sans aucune règle — une
    # instance fraîche n'en porte pas, la vue remplit donc le parent.
    # L'empilement est rétabli au dépli par twouichPhoneStackedLayout : la
    # géométrie empilée n'existe qu'à un seul endroit.
    const-string v0, "ExoPlayer"

    invoke-direct {p0, v0}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhoneView(Ljava/lang/String;)Landroid/view/View;

    move-result-object v0

    if-eqz v0, :return_chat_collapse

    const/4 v1, -0x1

    new-instance v2, Landroid/widget/RelativeLayout$LayoutParams;

    invoke-direct {v2, v1, v1}, Landroid/widget/RelativeLayout$LayoutParams;-><init>(II)V

    invoke-virtual {v0, v2}, Landroid/view/View;->setLayoutParams(Landroid/view/ViewGroup$LayoutParams;)V

    # Le chat et la saisie sont RETIRÉS (GONE), pas seulement transparents :
    # c'est tout l'intérêt du repli sur un écran de téléphone.
    const-string v0, "ChatRecycleView"

    invoke-direct {p0, v0}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhoneView(Ljava/lang/String;)Landroid/view/View;

    move-result-object v0

    if-eqz v0, :chat_collapse_input

    const/16 v1, 0x8

    invoke-virtual {v0, v1}, Landroid/view/View;->setVisibility(I)V

    :chat_collapse_input
    const-string v0, "SendMessageWindow"

    invoke-direct {p0, v0}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhoneView(Ljava/lang/String;)Landroid/view/View;

    move-result-object v0

    if-eqz v0, :return_chat_collapse

    const/16 v1, 0x8

    invoke-virtual {v0, v1}, Landroid/view/View;->setVisibility(I)V

    :return_chat_collapse
    return-void
.end method

.method private twouichChatApply(Z)V
    .locals 2

    # Une seule source de vérité : le champ est écrit ici, puis lu par
    # twouichChatTraces (trace logcat) et par twouichPhoneStackedLayout (qui
    # refuse de ressusciter un chat replié à chaque reprise d'activité).
    # IGET/IPUT (champ d'instance) : un sget compile mais lève une
    # IncompatibleClassChangeError au tap (attrapé sur BlueStacks le 21/09).
    iput-boolean p1, p0, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichChatHidden:Z

    invoke-direct {p0}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichChatTraces()Ljava/lang/String;

    move-result-object v0

    const-string v1, "Twouich"

    invoke-static {v1, v0}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    # Persistance : le choix survit à la fermeture de l'application (relu par
    # twouichChatRestore au démarrage du lecteur). Le contrat, ce sont le
    # fichier et la clé — ils doivent rester les mêmes des deux côtés.
    const-string v0, "twouich"

    const/4 v1, 0x0

    invoke-virtual {p0, v0, v1}, Landroid/content/Context;->getSharedPreferences(Ljava/lang/String;I)Landroid/content/SharedPreferences;

    move-result-object v0

    invoke-interface {v0}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;

    move-result-object v0

    const-string v1, "chat_hidden"

    invoke-interface {v0, v1, p1}, Landroid/content/SharedPreferences$Editor;->putBoolean(Ljava/lang/String;Z)Landroid/content/SharedPreferences$Editor;

    move-result-object v0

    invoke-interface {v0}, Landroid/content/SharedPreferences$Editor;->apply()V

    # Le champ est écrit AVANT de choisir la disposition : les deux chemins
    # lisent l'état pour se garder eux-mêmes.
    if-eqz p1, :chat_apply_stacked

    invoke-direct {p0}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichChatCollapse()V

    return-void

    :chat_apply_stacked
    invoke-direct {p0}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhoneStackedLayout()V

    return-void
.end method

.method private twouichChatRestore()V
    .locals 3

    # État du chat relu au démarrage du lecteur : le choix de l'utilisateur
    # survit à la fermeture de l'application. Une seule lecture par instance —
    # ensuite le champ est la seule source de vérité, écrit par
    # twouichChatApply (et la préférence n'est écrite qu'au même endroit).
    # IGET sur un champ d'instance (cf. twouichChatTraces pour la leçon).
    iget-boolean v0, p0, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichChatRestored:Z

    # if-nez : on saute quand la relecture a DÉJÀ eu lieu (v0 = 1). Écrit
    # if-eqz le 21/09, le garde sautait sur un processus neuf (v0 = 0) et la
    # méthode sortait aussitôt : la préférence n'était jamais lue, sans le
    # moindre journal — le chat replié se rouvrait à chaque lancement. Sonde
    # posée en tête de la méthode pour trancher ("restauration : entrée"
    # journalisée, trace d'état absente).
    if-nez v0, :restore_done

    const/4 v0, 0x1

    iput-boolean v0, p0, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichChatRestored:Z

    const-string v0, "twouich"

    const/4 v1, 0x0

    invoke-virtual {p0, v0, v1}, Landroid/content/Context;->getSharedPreferences(Ljava/lang/String;I)Landroid/content/SharedPreferences;

    move-result-object v0

    const-string v1, "chat_hidden"

    const/4 v2, 0x0

    invoke-interface {v0, v1, v2}, Landroid/content/SharedPreferences;->getBoolean(Ljava/lang/String;Z)Z

    move-result v1

    iput-boolean v1, p0, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichChatHidden:Z

    # Trace distincte de celle du toggle : « état relu » n'est pas « tap ».
    if-eqz v1, :restore_shown

    const-string v2, "chat restaure masque"

    goto :restore_log

    :restore_shown
    const-string v2, "chat restaure affiche"

    :restore_log
    const-string v0, "Twouich"

    invoke-static {v0, v2}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    # La disposition suit l'état relu, par le même chemin que le toggle.
    invoke-direct {p0, v1}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichChatApply(Z)V

    :restore_done
    return-void
.end method

.method public twouichPhoneChatToggle(Landroid/view/View;)V
    .locals 2

    # Le tap ne fait que basculer l'état, puis délègue : twouichChatHidden reste
    # la seule source de vérité, et la disposition suit l'état (replié : vidéo
    # plein écran ; affiché : empilement). Le bouton ne bouge jamais de la
    # vidéo : ancré ailleurs, il finissait dans le même rectangle que le bouton
    # d'incrustation, donc sous lui, donc intappable (mesuré le 21/09).
    const/4 v0, 0x1

    iget-boolean v1, p0, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichChatHidden:Z

    if-eqz v1, :chat_toggle_hide

    const/4 v0, 0x0

    :chat_toggle_hide
    invoke-direct {p0, v0}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichChatApply(Z)V

    return-void
.end method
"""

# Méthode exacte qui prouve la présence des greffons chat — jamais un nom nu,
# les commentaires des méthodes citent leurs voisines (piège du 21/09). C'est
# aussi le MARQUEUR DE VERSION du câblage : elle doit rester la plus récente des
# méthodes chat, pour qu'un arbre écrit par une version antérieure soit nettoyé
# puis reposé (l'état persisté ajouté le 21/09 a coûté ce changement).
CHAT_REPAIR_ANCHOR = ".method private twouichChatRestore()V"

GRAFT_DIR = "com/twouich/adblock"

# Méthode remplacée dans z3/u$b (Factory OkHttpDataSource d'ExoPlayer, Lz3/l$a).
# Chaque source de données HLS passe désormais par notre wrapper.
FACTORY_OLD = re.compile(
    r"\.method public bridge synthetic a\(\)Lz3/l;\r?\n.*?\r?\n\.end method",
    re.DOTALL,
)
FACTORY_NEW = """.method public bridge synthetic a()Lz3/l;
    .locals 2

    invoke-virtual {p0}, Lz3/u$b;->b()Lz3/u;

    move-result-object v0

    new-instance v1, Lcom/twouich/adblock/AdBlockDataSource;

    invoke-direct {v1, v0}, Lcom/twouich/adblock/AdBlockDataSource;-><init>(Lz3/l;)V

    return-object v1
.end method"""

# Self-test embarqué : exécuté une fois par démarrage, il rejoue des playlists
# publicitaires Twitch réelles dans le code compilé et publie son verdict sur
# logcat. C'est la seule preuve déterministe que le filtre agit vraiment : les
# quatre bugs qui ont cassé la lecture étaient invisibles pour les tests hors
# appareil et n'apparaissaient qu'à la lecture d'une vraie playlist.
SELFTEST_PATH = "smali/com/s0und/s0undtv/MainApp.smali"
APP_ONCREATE = re.compile(
    r"(?m)^([ \t]*invoke-super \{p0\}, Landroid/app/Application;->onCreate\(\)V\r?\n)"
)
SELFTEST_HOOK = (
    r"\1\n    invoke-static {}, Lcom/twouich/adblock/SelfTest;->run()V\n"
)

# Étape 3 : mise à jour automatique — tout doit pointer vers notre dépôt,
# plus jamais vers celui de S0und (sinon l'app tenterait de s'écraser elle-même).
URL_FILES = [
    "smali_classes2/com/s0und/s0undtv/helpers/UpdateHelper.smali",
    "smali_classes2/com/s0und/s0undtv/helpers/a.smali",
]
DEAD_UPDATE_URL = "https://share.s0und.cloudns.cl/app-release.apk"

# The upstream updater compared releases to a hard-coded 144, so it repeatedly
# offered the already-installed build. Read the installed package version instead.
UPDATE_VERSION_CALL = "    invoke-direct {p0}, Lcom/s0und/s0undtv/helpers/a;->i()I\n\n    move-result v1"
UPDATE_VERSION_METHOD = """.method private i()I
    .locals 3

    :try_start_0
    iget-object v0, p0, Lcom/s0und/s0undtv/helpers/UpdateHelper;->a:Ljava/lang/ref/WeakReference;
    invoke-virtual {v0}, Ljava/lang/ref/Reference;->get()Ljava/lang/Object;
    move-result-object v0
    check-cast v0, Landroid/content/Context;
    invoke-virtual {v0}, Landroid/content/Context;->getPackageManager()Landroid/content/pm/PackageManager;
    move-result-object v1
    invoke-virtual {v0}, Landroid/content/Context;->getPackageName()Ljava/lang/String;
    move-result-object v2
    const/4 v0, 0x0
    invoke-virtual {v1, v2, v0}, Landroid/content/pm/PackageManager;->getPackageInfo(Ljava/lang/String;I)Landroid/content/pm/PackageInfo;
    move-result-object v0
    iget v0, v0, Landroid/content/pm/PackageInfo;->versionCode:I
    return v0
    :try_end_0
    .catch Ljava/lang/Exception; {:try_start_0 .. :try_end_0} :catch_0

    :catch_0
    move-exception v0
    const/4 v0, -0x1
    return v0
.end method

"""

# Étape 3b : le socle upstream est un build beta — le flag gravé
# Lcom/s0und/s0undtv/b;->a:Z = true fait écrire pref_update_channel = "1"
# (Beta) au premier lancement de TOUTE installation neuve (MainApp.p()).
# Or, sur le canal Beta, l'updater n'accepte que des entrées ReleaseType: 1 :
# une update.json ne publiant qu'une entrée stable n'y produit AUCUN dialogue,
# sans erreur nulle part. Forcer le flag à false rend le canal stable par
# défaut : g() lit "0" quand la préférence est absente, ce qui est exactement
# ce que nous publions.
BETA_FLAG_PATH = "smali/com/s0und/s0undtv/b.smali"
BETA_FLAG_OLD = ".field public static final a:Z = true"
BETA_FLAG_NEW = ".field public static final a:Z = false"


# ── Étape 2 : identité visuelle ───────────────────────────────────────────
# L'arbre `patch/branding/assets/res/` est produit par make_brand.py et recopié
# tel quel : une seule source de vérité pour l'écran de démarrage, les icônes et
# la bannière. Tout le reste (nom affiché, thème, palette) est réécrit ici.
BRAND_DIR = "branding/assets"
BRAND_RES = "branding/assets/res"
BRAND_JSON = "branding/assets/brand.json"
BRAND_EMIT = "python patch/branding/make_brand.py emit"

# Le rouge de S0und : il ne doit plus subsister sur aucune surface d'identité
# (écran de démarrage, bannière, icônes, pages embarquées). Seule la palette des
# thèmes garde sa teinte rouge — c'est un choix d'utilisateur, pas la marque.
DEAD_RED = "a30f2c"
PALETTE_FILES = {"values/colors.xml", "values/public.xml"}
TEXT_SUFFIXES = {".xml", ".html", ".htm", ".js", ".css", ".json", ".txt"}

APP_NAME_OLD = '<string name="app_name">S0undTV</string>'
APP_NAME_NEW = '<string name="app_name">Twouich</string>'
APP_LABEL_OLD = 'android:label="Sound TV"'
APP_LABEL_NEW = 'android:label="Twouich"'

# Les activités déclarent un thème rouge dans le manifeste ; le thème retenu à
# l'exécution est choisi par la préférence (sombre par défaut). On aligne la
# déclaration sur le violet Twitch : plus aucun aplat rouge au lancement.
MANIFEST_THEMES = [
    ("@style/AppTheme_Red", "@style/AppTheme_Purple"),
    ("@style/LeanbackPreferencesRed", "@style/LeanbackPreferencesPurple"),
]
SPLASH_THEME = "SplashScreenThemeVector"

# Pages légales Twouich : sources de vérité sous patch/branding/, injectées dans
# assets/ à l'étape 5 (mention légale + politique de confidentialité). La source
# fait foi : si le fichier source manque, le build échoue (pas de page muette).
LEGAL_PAGES = [
    ("branding/twouich_legal.html", "assets/twouich_legal.html",
     "Twouich — mentions légales"),
    ("branding/twouich_privacy.html", "assets/twouich_privacy.html",
     "Twouich — politique de confidentialité"),
]

ABOUT_OLD = """<body>
    <h1>Contact</h1>"""
ABOUT_NEW = """<body>
    <h1>Twouich</h1>
    <p class="spacing">
    <b>client: </b>an Android TV client for Twitch<br>
    <b>sources: </b><a href="https://github.com/Endymi0n74/Twouich">Twouich project</a><br>
    <b>based on: </b><a href="https://github.com/S0und/S0undTV">the original project</a><br>
    <b>credits: </b>thanks to the original authors and contributors. This build redistributes only patched binaries and the patches themselves.<br>
    </p>

    <hr>
    <h1>Contact</h1>"""

CHANGELOG_OLD = """    <hr>
    <h1>beta_144 (2025.12.28)</h1>"""
# Le titre porte la version réellement construite (passée par build.sh) : la page
# « Nouveautés » de l'app cite donc la release d'où vient le build, pas celle d'avant.
CHANGELOG_NEW = """    <hr>
    <h1>Twouich {version} ({date})</h1>
    <p class="spacing"><a href="https://github.com/Endymi0n74/Twouich">Twouich</a> — un client Android TV pour Twitch.</p>

    <h3>Ce qui change</h3>
    <ul>
        <li>Blocage des publicités SSAI dans les playlists Twitch avant lecture.</li>
        <li>Nouvelle identité Twouich : splash, icônes, bannière TV, thème violet et interface revue.</li>
        <li>Accent par défaut recoloré aux couleurs Twouich : plus de rouge d'origine dans l'interface.</li>
        <li>Mise à jour automatique depuis les releases Twouich.</li>
    </ul>

    <h3>Source et remerciements</h3>
    <ul>
        <li>Projet d'origine : <a href="https://github.com/S0und/S0undTV">S0undTV</a>.</li>
        <li>Merci à ses auteurs et contributeurs pour le travail initial.</li>
        <li>Ce projet redistribue uniquement des binaires patchés et les patchs associés.</li>
    </ul>

    <hr>

    <h1>beta_144 (2025.12.28)</h1>"""


# Cartes Leanback : la grille (BaseGridView, obfusquee en androidx/leanback/widget/e)
# est le premier point de passage de toute touche posee sur une rangee. On y
# branche TapClick, qui traduit un tap en clic (voir patch_smartphone_tap).
BASE_GRID_CLASS = ".class public abstract Landroidx/leanback/widget/e;"
TAP_HOOK_CALL = ("    invoke-static {p0, p1}, Lcom/twouich/adblock/TapClick;->"
                 "touch(Landroid/view/View;Landroid/view/MotionEvent;)Z")
TAP_HOOK_LABEL = ":twouich_tap_unhandled"


def log(msg: str) -> None:
    print(f"  {msg}")


def fail(msg: str) -> None:
    print(f"\n❌ {msg}", file=sys.stderr)
    sys.exit(1)


def replace_once(path: pathlib.Path, old: str, new: str, what: str) -> bool:
    """Remplace un motif unique, en respectant la convention de fin de ligne du
    fichier : l'arbre apktool est en CRLF (les pages HTML aussi) alors que les
    motifs de ce script sont écrits en LF."""
    text = path.read_text(encoding="utf-8")
    nl = "\r\n" if "\r\n" in text else "\n"
    if nl != "\n":
        old = old.replace("\n", nl)
        new = new.replace("\n", nl)
    if new in text and old not in text:
        log(f"déjà appliqué : {what}")
        return False
    if old not in text:
        fail(f"motif introuvable ({what}) dans {path} — la cible a changé, adapter patch.py")
    path.write_text(text.replace(old, new), encoding="utf-8")
    log(f"appliqué : {what}")
    return True


def find_factory(decoded: pathlib.Path) -> pathlib.Path:
    """Localise la fabrique de sources de données (Lz3/u$b) dans l'arbre décodé.

    apktool place les classes du dex secondaire sous `smali_classes2/`, et le
    nommage `z3.1`/`z3` varie selon la plateforme/le nombre de dex : le chemin
    n'est pas supposé, il est localisé — et l'absence reste une erreur bruyante
    (c'est la détection de rupture, pas une tolérance).
    """
    candidates = [
        decoded / "smali" / "z3.1" / "u$b.smali",  # décoder Windows
        decoded / "smali" / "z3" / "u$b.smali",    # décodages Linux/CI
        decoded / "smali_classes2" / "z3" / "u$b.smali",
    ]
    for c in candidates:
        if c.is_file():
            return c
    fail("factory ExoPlayer introuvable (z3/u$b.smali) — socle upstream changé ?")


def install_graft(decoded: pathlib.Path, here: pathlib.Path) -> None:
    print("[1/5] Greffon anti-pub (AdBlockDataSource + PlaylistSanitizer + self-test)")
    src = here / "smali" / GRAFT_DIR
    dst = decoded / "smali_classes2" / GRAFT_DIR
    if not src.is_dir():
        fail(f"greffon absent : {src}")
    dst.mkdir(parents=True, exist_ok=True)
    for f in sorted(src.glob("*.smali")):
        shutil.copy2(f, dst / f.name)
        log(f"copié : {f.name}")

    factory = find_factory(decoded)
    text = factory.read_text(encoding="utf-8")
    if "AdBlockDataSource" in text:
        log("injection déjà présente dans z3/u$b.a()")
        return
    new_text, count = FACTORY_OLD.subn(FACTORY_NEW, text)
    if count != 1:
        fail(f"méthode z3/u$b.a() attendue 1 fois, trouvée {count} fois")
    factory.write_text(new_text, encoding="utf-8")
    log("injecté : z3/u$b.a() renvoie AdBlockDataSource")


def neutralize_firebase(decoded: pathlib.Path) -> None:
    """Désactive les composants Firebase hérités avant tout démarrage Android.

    Les bibliothèques peuvent rester dans le dex (elles font partie du binaire
    upstream), mais aucun provider/service/receiver Firebase ou Measurement ne
    doit être déclaré et aucun identifiant du projet S0und ne doit rester dans
    les ressources. Sans point d'entrée manifeste ni configuration, ces
    bibliothèques sont inertes et ne peuvent pas ouvrir de connexion réseau.
    """
    print("[1b/5] Télémétrie Firebase/Measurement désactivée")
    manifest = decoded / "AndroidManifest.xml"
    text = manifest.read_text(encoding="utf-8")
    text = re.sub(r"(?ms)^        <receiver[^>]*AppMeasurementReceiver[^>]*/>\r?\n", "", text)
    text = re.sub(r"(?ms)^        <service[^>]*AppMeasurement(?:Service|JobService)[^>]*/>\r?\n", "", text)
    text = re.sub(r"(?ms)^        <service[^>]*ComponentDiscoveryService[^>]*>.*?</service>\r?\n", "", text)
    text = re.sub(r"(?ms)^        <provider[^>]*FirebaseInitProvider[^>]*/>\r?\n", "", text)
    manifest.write_text(text, encoding="utf-8")

    strings = decoded / "res" / "values" / "strings.xml"
    text = strings.read_text(encoding="utf-8")
    removed = []
    dropping = False
    for line in text.splitlines():
        if '<string name="' in line and any(
            key in line for key in (
                'google_app_id', 'google_api_key', 'google_crash_reporting_api_key',
                'firebase_database_url', 'com.google.firebase.crashlytics.'
            )
        ):
            dropping = not line.rstrip().endswith('</string>')
            removed.append('')
            continue
        if dropping:
            if '</string>' in line:
                dropping = False
            removed.append('')
            continue
        removed.append(line)
    text = "\n".join(line for line in removed if line != "") + "\n"
    text, _ = re.subn(
        r"(?ms)^    <string name=\"(?:google_app_id|google_crash_reporting_api_key|firebase_database_url|com\\.google\\.firebase\\.crashlytics\\.[^\"]+)\">.*?</string>\\n?",
        "",
        text,
    )
    strings.write_text(text, encoding="utf-8")

    for rel in ("res/raw/firebase_common_keep.xml", "res/raw/firebase_crashlytics_keep.xml"):
        path = decoded / rel
        if path.exists():
            path.unlink()
    public = decoded / "res/values/public.xml"
    if public.is_file():
        text = public.read_text(encoding="utf-8")
        text = "\n".join(line for line in text.splitlines()
                         if not any(name in line for name in (
                             'name="firebase_common_keep"',
                             'name="firebase_crashlytics_keep"',
                             'name="com.google.firebase.crashlytics.mapping_file_id"',
                             'name="com.google.firebase.crashlytics.version_control_info"',
                             'name="firebase_database_url"',
                             'name="google_api_key"',
                             'name="google_app_id"',
                             'name="google_crash_reporting_api_key"',
                         ))) + "\n"
        public.write_text(text, encoding="utf-8")


def disable_remote_config_calls(decoded: pathlib.Path) -> None:
    """Neutralise les appels applicatifs à Firebase Remote Config.

    Le provider manifeste retiré empêche l'initialisation automatique, mais le
    code upstream appelait encore RemoteConfig au démarrage et dans le lecteur.
    Ces appels doivent devenir des no-op : sinon l'app peut planter en cherchant
    un Default FirebaseApp, et aucun trafic ne serait réellement garanti.
    """
    targets = [
        (decoded / "smali/com/s0und/s0undtv/MainApp.smali", "q", "V"),
        (decoded / "smali/com/s0und/s0undtv/activities/PlayerActivity.smali", "J3", "V"),
    ]
    replacement = ".method private {name}()V\n    .locals 0\n    return-void\n.end method"
    for path, name, ret in targets:
        if not path.is_file():
            fail(f"cible Remote Config absente : {path}")
        text = path.read_text(encoding="utf-8")
        # Le test d'idempotence porte sur le CORPS déjà remplacé, pas sur le motif :
        # le motif (méthode … .end method) matche encore après remplacement, donc
        # re.subn renvoyait toujours 1 et l'arbre déjà patché était réécrit à chaque
        # passage — avec les fins de ligne de la plateforme (CRLF sous Windows), ce
        # qui faisait diverger les smali entre le premier et le second passage
        # (constaté le 21/09 en vérifiant l'idempotence du patch).
        noop = replacement.format(name=name)
        if noop in text:
            log(f"déjà appliqué : {path.name}.{name}() sans Remote Config")
            continue
        pattern = rf"(?ms)^\.method private {re.escape(name)}\(\){ret}.*?^\.end method"
        new, count = re.subn(pattern, noop, text, count=1)
        if count == 0:
            fail(f"méthode Remote Config introuvable : {path.name}.{name}()")
        path.write_text(new, encoding="utf-8", newline="\n")
        log(f"désactivé : {path.name}.{name}() (Remote Config)")


def disable_crashlytics_facade(decoded: pathlib.Path) -> None:
    """Rend muet le facade applicatif upstream qui envoyait les erreurs à Crashlytics.

    Retirer seulement le provider ne suffit pas : le code de l'application appelait
    encore P6/e, dont chaque méthode demandait le singleton Firebase et provoquait
    une exception quand l'initialisation était désactivée. Les signatures restent
    intactes pour ne pas modifier les appelants, mais les cinq opérations deviennent
    des no-op locaux.
    """
    path = decoded / "smali_classes2/P6/e.smali"
    if not path.is_file():
        fail(f"facade Crashlytics absent : {path}")
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"(?ms)^(\.method public static [a-e]\([^\n]*\)V\r?\n).*?^\.end method")
    def noop(match: re.Match[str]) -> str:
        return match.group(1) + "    .locals 0\n    return-void\n.end method"
    new, count = pattern.subn(noop, text)
    if count != 5:
        fail(f"facade Crashlytics P6/e : 5 méthodes attendues, trouvées {count}")
    if new != text:
        path.write_text(new, encoding="utf-8")
        log("désactivé : P6/e (facade Crashlytics applicative, 5 no-op)")
    else:
        log("déjà appliqué : P6/e (facade Crashlytics muette)")

    # Analytics applicatif : même principe, les signatures restent disponibles
    # mais les événements ne sortent plus de l'application.
    for rel, method_re, label in (
        ("smali_classes2/P6/b.smali", r"public static a", "P6/b.a()"),
        ("smali_classes2/P6/l.smali", r"private static i", "P6/l.i()"),
    ):
        target = decoded / rel
        source = target.read_text(encoding="utf-8")
        method = re.compile(rf"(?ms)^(\.method [^\r\n]*{method_re}[^\r\n]*\r?\n).*?^\.end method")
        rewritten, found = method.subn(
            lambda m: m.group(1) + "    .locals 0\n    return-void\n.end method",
            source,
            count=1,
        )
        if found != 1:
            if "    .locals 0\n    return-void\n.end method" in source:
                log(f"déjà appliqué : {label} (no-op)")
                continue
            fail(f"méthode Analytics introuvable : {rel}")
        target.write_text(rewritten, encoding="utf-8")
        log(f"désactivé : {label} (Analytics no-op)")


def patch_smartphone_features(decoded: pathlib.Path) -> int:
    """Rend les capacités matérielles optionnelles pour les catalogues smartphone.

    Seul l'attribut android:required des lignes uses-feature est touché : les noms,
    permissions, activités et tous les autres attributs du manifeste restent
    inchangés. Une ligne sans attribut required reçoit explicitement false, car
    l'absence vaut true côté Android.
    """
    manifest = decoded / "AndroidManifest.xml"
    text = manifest.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    feature_count = 0
    rewritten = []
    line_re = re.compile(r"^(?P<prefix>\s*<uses-feature\b)(?P<body>.*?)(?P<close>/?>)(?P<eol>\r?\n)?$")
    for line in lines:
        match = line_re.match(line)
        if match is None:
            rewritten.append(line)
            continue
        feature_count += 1
        body = match.group("body")
        if re.search(r'\bandroid:required="[^\"]*"', body):
            body = re.sub(r'android:required="[^\"]*"', 'android:required="false"', body, count=1)
        else:
            body = body + ' android:required="false"'
        rewritten.append(match.group("prefix") + body + match.group("close") + (match.group("eol") or ""))
    if feature_count == 0:
        fail("aucune ligne uses-feature dans AndroidManifest.xml — cible smartphone absente")
    new_text = "".join(rewritten)
    if new_text != text:
        manifest.write_text(new_text, encoding="utf-8")
        log(f"smartphone : {feature_count} uses-feature rendues optionnelles")
    else:
        log(f"déjà appliqué : {feature_count} uses-feature sont optionnelles")
    return feature_count


def install_tv_layout(decoded: pathlib.Path, here: pathlib.Path, name: str) -> None:
    """Pose la version TV d'origine d'un layout reecrit par le mode telephone.

    L'amont ne livre QU'UNE configuration de ces layouts : un televiseur qui ne
    declare pas sw600dp gonfle donc `layout/` — mesure sur la Freebox Pop
    (1920x1080 en 320 dpi = 540 dp), ou la barre de navigation telephone
    s'affichait sur le televiseur. Trois qualifiers portent la version d'origine :
    « television » (mode declare par le systeme), sw600dp (TV 4K, tablettes) et
    sw540dp (le cas Freebox, garde du premier correctif).

    La source est VERSIONNEE (patch/res-tv/) : une copie faite depuis le layout
    de base finirait par recopier la greffe telephone sur la TV, et un arbre de
    travail deja patche ne redeviendrait jamais vierge.
    """
    source = here / "res-tv" / name
    if not source.is_file():
        fail(f"layout TV de reference absent : {source}")
    text = source.read_text(encoding="utf-8").replace(chr(13) + chr(10), chr(10))
    if "twouich" in text:
        fail(f"le layout TV de reference {name} porte une greffe telephone")
    for qualifier in ("layout-television", "layout-sw600dp", "layout-sw540dp"):
        destination = decoded / "res" / qualifier / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        current = ""
        if destination.is_file():
            current = destination.read_text(encoding="utf-8").replace(
                chr(13) + chr(10), chr(10))
        if current != text:
            destination.write_text(text, encoding="utf-8", newline=chr(10))
            log(f"layout TV restaure : res/{qualifier}/{name}")


def patch_smartphone_ux(decoded: pathlib.Path, here: pathlib.Path) -> None:
    """Installe une variante tactile du lecteur sans dégrader l'interface TV.

    Android sélectionne `layout/` sur téléphone et `layout-sw600dp/` sur les
    grands écrans. On conserve donc l'original dans le qualifier TV, puis on
    rend le chat du layout téléphone large et ancré en bas : il devient visible
    sans le geste de balayage découvert lors de l'observation du 19/09.
    """
    print("[1d/5] UX smartphone (orientation multi-capteur + chat tactile visible)")
    manifest = decoded / "AndroidManifest.xml"
    text = manifest.read_text(encoding="utf-8")
    if "android:screenOrientation=\"sensorLandscape\"" in text:
        text = text.replace(
            'android:screenOrientation="sensorLandscape"',
            'android:screenOrientation="fullSensor"',
        )
        manifest.write_text(text, encoding="utf-8")
        log("smartphone : orientations sensorLandscape → fullSensor")
    elif "android:screenOrientation=\"fullSensor\"" in text:
        log("déjà appliqué : manifeste multi-orientation")
    else:
        fail("aucune orientation sensorLandscape/fullSensor dans AndroidManifest.xml")

    phone = decoded / "res/layout/activity_player.xml"
    if not phone.is_file():
        fail(f"layout lecteur absent : {phone}")
    install_tv_layout(decoded, here, "activity_player.xml")

    source = phone.read_text(encoding="utf-8")
    marker = 'android:id="@id/ChatRecycleView"'
    if marker not in source:
        fail("ChatRecycleView absent du layout lecteur")
    # Ne touche que le premier chat (le chat principal) ; le multiview conserve
    # ses dimensions upstream et reste disponible sur les grands écrans.
    match = re.search(r"<com\.s0und\.s0undtv\.chat\.ChatRecyclerView\b(?P<body>[^>]*)/>", source)
    if match is None:
        fail("élément ChatRecycleView introuvable dans activity_player.xml")
    body = match.group("body")
    body = re.sub(r'android:layout_width="[^"]*"',
                  'android:layout_width="match_parent"', body, count=1)
    body = re.sub(r'android:layout_height="[^"]*"',
                  'android:layout_height="@dimen/twouich_phone_chat_height"', body, count=1)
    if 'android:layout_alignParentBottom=' not in body:
        body += ' android:layout_alignParentBottom="true"'
    if 'android:layout_alignParentStart=' not in body:
        body += ' android:layout_alignParentStart="true"'
    rewritten = source[:match.start("body")] + body + source[match.end("body"):]
    send_new = ('<include android:id="@id/SendMessageWindow" android:visibility="visible"'
                ' android:layout_width="match_parent" android:layout_height="wrap_content"'
                ' android:layout_alignParentBottom="true"'
                ' android:layout_marginBottom="@dimen/twouich_phone_chat_height"'
                ' android:layout_alignParentStart="true"'
                ' layout="@layout/include_send_chat_message_window" />')
    send_pattern = r'<include\s+[^>]*android:id="@id/SendMessageWindow"[^>]*/>'
    rewritten, send_count = re.subn(send_pattern, send_new, rewritten, count=1)
    if send_count != 1:
        fail("SendMessageWindow absent du layout lecteur smartphone")
    if rewritten != source:
        phone.write_text(rewritten, encoding="utf-8")
        log("smartphone : chat principal large, visible et ancré en bas")
        log("smartphone : champ de saisie affiché au-dessus du chat")
    else:
        log("déjà appliqué : layout lecteur smartphone")

    send_layout = decoded / "res/layout/include_send_chat_message_window.xml"
    if not send_layout.is_file():
        fail(f"layout de saisie chat absent : {send_layout}")
    send_text = send_layout.read_text(encoding="utf-8")
    send_text_new = send_text.replace(f'android:hint="{CHAT_HINT_LEGACY}"',
                                      f'android:hint="{CHAT_HINT}"')
    if f'android:hint="{CHAT_HINT}"' not in send_text_new:
        send_text_new = send_text_new.replace(
            'android:id="@id/ET_SendMessage"',
            f'android:imeOptions="actionSend" android:hint="{CHAT_HINT}" android:id="@id/ET_SendMessage"',
            1,
        )
    # Une version antérieure du patch a pu écrire l'attribut deux fois : on
    # déduplique la paire (apktool ne préserve pas l'ordre d'insertion).
    send_text_new = re.sub(
        rf'(android:hint="{re.escape(CHAT_HINT)}"\s+android:imeOptions="actionSend"\s+)'
        rf'(?:android:hint="{re.escape(CHAT_HINT)}"\s+android:imeOptions="actionSend"\s+)+',
        r'\1', send_text_new,
    )
    if send_text_new != send_text:
        send_layout.write_text(send_text_new, encoding="utf-8", newline="\n")
        log(f"smartphone : champ de chat « {CHAT_HINT} » (libellé + touche Envoyer)")

    player_smali = decoded / "smali/com/s0und/s0undtv/activities/PlayerActivity.smali"
    if not player_smali.is_file():
        fail(f"activité lecteur absente : {player_smali}")
    # Fins de ligne normalisées : apktool décode le smali dans les fins de ligne
    # de la machine, et un motif de réparation écrit en LF ne peut pas atteindre
    # un bloc injecté en CRLF (le cas de l'arbre déjà patché sur Windows).
    player_text = player_smali.read_text(encoding="utf-8").replace("\r\n", "\n")
    player_text, tv_guard_count = use_tv_interface_guard(player_text)
    if tv_guard_count:
        log(f"lecteur : {tv_guard_count} garde(s) d'interface ramenee(s) au mode TV")
    player_text, screen_off_patched = _patch_screen_off_stop(player_text)
    if screen_off_patched:
        log("veille : le demontage d'onStop() est saute quand l'ecran est eteint")

    def write_player(final: str) -> None:
        """Ecrit le smali du lecteur : point unique de la source TV.

        Les gardes de dp vivent dans les gabarits, donc c'est ici — et nulle
        part ailleurs — qu'elles sont ramenees a l'appel de twouichTvInterface.
        La methode dediee est posee si elle manque, et l'invariant est verifie
        sur le texte REELLEMENT ecrit : un seul seuil de dp dans tout le
        fichier, celui de la methode.
        """
        final, lowered = use_tv_interface_guard(final)
        if ".method private twouichTvInterface()Z" not in final:
            final = (final.rstrip() + "\n\n"
                     + TV_INTERFACE_METHOD.rstrip() + "\n")
        if final.count("smallestScreenWidthDp:I") != 1:
            fail("le seuil de dp garde encore l'interface ailleurs que dans "
                 "twouichTvInterface : le mode TV ne serait plus fiable")
        player_smali.write_text(final, encoding="utf-8", newline="\n")
        if lowered:
            log(f"lecteur : {lowered} garde(s) d'interface ramenee(s) au mode "
                "systeme (mode TV, plus de seuil de dp)")

    player_methods = r'''

.method private twouichPhoneId(Ljava/lang/String;)I
    .locals 3
    invoke-virtual {p0}, Landroid/content/Context;->getResources()Landroid/content/res/Resources;
    move-result-object v0
    const-string v1, "id"
    const-string v2, "com.s0und.s0undtv"
    invoke-virtual {v0, p1, v1, v2}, Landroid/content/res/Resources;->getIdentifier(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)I
    move-result v0
    return v0
.end method

.method private twouichPhoneStackedLayout()V
    .locals 12
''' + PHONE_PIP_GUARD + r'''
    invoke-virtual {p0}, Landroid/content/Context;->getResources()Landroid/content/res/Resources;
    move-result-object v0
    invoke-virtual {v0}, Landroid/content/res/Resources;->getConfiguration()Landroid/content/res/Configuration;
    move-result-object v1
    iget v1, v1, Landroid/content/res/Configuration;->smallestScreenWidthDp:I
    const/16 v2, 0x258
    if-ge v1, v2, :return_phone_layout

    const-string v1, "ExoPlayer"
    invoke-direct {p0, v1}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhoneId(Ljava/lang/String;)I
    move-result v1
    const-string v2, "ChatRecycleView"
    invoke-direct {p0, v2}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhoneId(Ljava/lang/String;)I
    move-result v2
    const-string v3, "SendMessageWindow"
    invoke-direct {p0, v3}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhoneId(Ljava/lang/String;)I
    move-result v3
    invoke-virtual {p0, v1}, Landroid/app/Activity;->findViewById(I)Landroid/view/View;
    move-result-object v4
    invoke-virtual {p0, v2}, Landroid/app/Activity;->findViewById(I)Landroid/view/View;
    move-result-object v5
    invoke-virtual {p0, v3}, Landroid/app/Activity;->findViewById(I)Landroid/view/View;
    move-result-object v6
    if-eqz v4, :return_phone_layout
    if-eqz v5, :return_phone_layout
    if-eqz v6, :return_phone_layout

    # Masquer le BottomBar (info stream) en mode telephone. v10 et v11 sont
    # reecrits juste apres (16:9 puis hauteur de saisie) : les clobberer ici est
    # sans effet. v1 et v2 portent les ids des vues et sont donc INTERDITS : les
    # ecraser par une reference de vue casserait la verification Dalvik de toute
    # la methode (VerifyError attrape sur le telephone le 21/09).
    const-string v10, "BottomBar"
    invoke-direct {p0, v10}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhoneId(Ljava/lang/String;)I
    move-result v10
    invoke-virtual {p0, v10}, Landroid/app/Activity;->findViewById(I)Landroid/view/View;
    move-result-object v11
    if-eqz v11, :skip_bottom_bar_hide
    const/16 v10, 0x8
    invoke-virtual {v11, v10}, Landroid/view/View;->setVisibility(I)V
    :skip_bottom_bar_hide

    invoke-virtual {v0}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;
    move-result-object v7
    iget v8, v7, Landroid/util/DisplayMetrics;->widthPixels:I
    iget v9, v7, Landroid/util/DisplayMetrics;->heightPixels:I
    mul-int/lit8 v10, v8, 0x9
    div-int/lit8 v10, v10, 0x10

    # Orientation : paysage (largeur > hauteur) -> disposition cote a cote
    if-le v8, v9, :portrait_layout

    # -- Paysage : video a gauche (toute la hauteur), chat et saisie a droite --
    # v11 = hauteur de la saisie (112 px), v0 = largeur video, v1 = largeur du
    # chat, v10 = hauteur du chat. La video vise la largeur 16:9 de la HAUTEUR
    # d'ecran : elle occupe alors tout le bord gauche jusqu'en bas, sans bande
    # noire (mesure du 21/09 : video 16:9 centree, bandes noires de chaque
    # cote). Plafond de surete a 85 % de la largeur seulement : sur un ecran
    # 19,5:9 la largeur 16:9 de la hauteur vaut 80 % et passe donc telle quelle
    # (aucune bande noire) ; le garde-fou ne mord que sur des ratios extremes,
    # ou mieux vaut une bande qu'un chat de quelques pixels.
    const/16 v11, 0x70
    mul-int/lit8 v0, v9, 0x10
    div-int/lit8 v0, v0, 0x9
    mul-int/lit8 v10, v8, 0x55
    div-int/lit8 v10, v10, 0x64
    if-le v0, v10, :twouich_phone_landscape_video
    move v0, v10
    :twouich_phone_landscape_video
    sub-int v1, v8, v0
    sub-int v10, v9, v11

    # Video : largeur v0, hauteur plein cadre, collee au bord gauche
    new-instance v7, Landroid/widget/RelativeLayout$LayoutParams;
    const/4 v2, -0x1
    invoke-direct {v7, v0, v2}, Landroid/widget/RelativeLayout$LayoutParams;-><init>(II)V
    const/16 v2, 0x9
    invoke-virtual {v7, v2}, Landroid/widget/RelativeLayout$LayoutParams;->addRule(I)V
    invoke-virtual {v4, v7}, Landroid/view/View;->setLayoutParams(Landroid/view/ViewGroup$LayoutParams;)V

    # Chat : largeur v1, hauteur v10, colle au bord droit
    new-instance v7, Landroid/widget/RelativeLayout$LayoutParams;
    invoke-direct {v7, v1, v10}, Landroid/widget/RelativeLayout$LayoutParams;-><init>(II)V
    const/16 v2, 0xb
    invoke-virtual {v7, v2}, Landroid/widget/RelativeLayout$LayoutParams;->addRule(I)V
    const/16 v2, 0xa
    invoke-virtual {v7, v2}, Landroid/widget/RelativeLayout$LayoutParams;->addRule(I)V
    invoke-virtual {v5, v7}, Landroid/view/View;->setLayoutParams(Landroid/view/ViewGroup$LayoutParams;)V
    const/4 v2, 0x0
    invoke-virtual {v5, v2}, Landroid/view/View;->setVisibility(I)V

    # Saisie : largeur v1, hauteur v11, collee en bas a droite
    new-instance v7, Landroid/widget/RelativeLayout$LayoutParams;
    invoke-direct {v7, v1, v11}, Landroid/widget/RelativeLayout$LayoutParams;-><init>(II)V
    const/16 v2, 0xb
    invoke-virtual {v7, v2}, Landroid/widget/RelativeLayout$LayoutParams;->addRule(I)V
    const/16 v2, 0xc
    invoke-virtual {v7, v2}, Landroid/widget/RelativeLayout$LayoutParams;->addRule(I)V
    invoke-virtual {v6, v7}, Landroid/view/View;->setLayoutParams(Landroid/view/ViewGroup$LayoutParams;)V
    const/4 v2, 0x0
    invoke-virtual {v6, v2}, Landroid/view/View;->setVisibility(I)V
    goto :return_phone_layout

    :portrait_layout
    # Le 16:9 est calcule depuis la LARGEUR : sur un écran plus large que haut il
    # dépasse la hauteur et le chat reçoit une hauteur négative. On plafonne donc
    # la vidéo, puis on refuse l'empilement quand il ne reste pas un tiers de la
    # hauteur pour le chat : en paysage, le chat en surimpression du layout
    # d'origine (vidéo plein écran, chat ancré en bas) reste plus utile qu'un
    # chat de 0 px, et c'est aussi la disposition de l'interface de référence.
'''
    player_methods = (player_methods
                      + PHONE_GEO_TAIL
                      + r'''
    new-instance v0, Landroid/widget/RelativeLayout$LayoutParams;
    const/4 v9, -0x1
    invoke-direct {v0, v9, v10}, Landroid/widget/RelativeLayout$LayoutParams;-><init>(II)V
    const/16 v9, 0xa
    invoke-virtual {v0, v9}, Landroid/widget/RelativeLayout$LayoutParams;->addRule(I)V
    invoke-virtual {v4, v0}, Landroid/view/View;->setLayoutParams(Landroid/view/ViewGroup$LayoutParams;)V

    new-instance v0, Landroid/widget/RelativeLayout$LayoutParams;
    const/4 v9, -0x1
    invoke-direct {v0, v9, v7}, Landroid/widget/RelativeLayout$LayoutParams;-><init>(II)V
    const/4 v9, 0x3
    invoke-virtual {v0, v9, v1}, Landroid/widget/RelativeLayout$LayoutParams;->addRule(II)V
    const/16 v9, 0xc
    invoke-virtual {v0, v9}, Landroid/widget/RelativeLayout$LayoutParams;->addRule(I)V
    invoke-virtual {v5, v0}, Landroid/view/View;->setLayoutParams(Landroid/view/ViewGroup$LayoutParams;)V
    const/4 v9, 0x0
    invoke-virtual {v5, v9}, Landroid/view/View;->setVisibility(I)V

    new-instance v0, Landroid/widget/RelativeLayout$LayoutParams;
    const/4 v9, -0x1
    invoke-direct {v0, v9, v11}, Landroid/widget/RelativeLayout$LayoutParams;-><init>(II)V
    const/4 v9, 0x2
    invoke-virtual {v0, v9, v2}, Landroid/widget/RelativeLayout$LayoutParams;->addRule(II)V
    const/16 v9, 0xc
    invoke-virtual {v0, v9}, Landroid/widget/RelativeLayout$LayoutParams;->addRule(I)V
    invoke-virtual {v6, v0}, Landroid/view/View;->setLayoutParams(Landroid/view/ViewGroup$LayoutParams;)V
    const/4 v9, 0x0
    invoke-virtual {v6, v9}, Landroid/view/View;->setVisibility(I)V
:return_phone_layout
    return-void
.end method

.method public onWindowFocusChanged(Z)V
    .locals 1
    invoke-super {p0, p1}, Landroid/app/Activity;->onWindowFocusChanged(Z)V
    if-eqz p1, :return_focus
    invoke-direct {p0}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhoneStackedLayout()V
:return_focus
    return-void
.end method

'''
    )
    # Le garde du chat replié fait partie de la disposition empilée : posé dans
    # la source unique (player_methods), donc présent à l'identique sur un arbre
    # vierge et sur un arbre réparé.
    if PHONE_CHAT_GATE_ANCHOR not in player_methods:
        fail("garde du chat replié absent du gabarit de twouichPhoneStackedLayout")
    player_methods = player_methods.replace(PHONE_CHAT_GATE_ANCHOR, PHONE_CHAT_GATE, 1)
    if ":stacked_chat_shown" not in player_methods:
        fail("garde du chat replié non posé dans le gabarit")
    # Le chat s'arrête au-dessus de la saisie, jamais au bas du parent : la
    # géométrie du gabarit est réécrite ici (même idiome que PHONE_GEO_TAIL).
    if PHONE_CHAT_BELOW_OLD not in player_methods:
        fail("géométrie du chat introuvable dans le gabarit de twouichPhoneStackedLayout")
    player_methods = player_methods.replace(PHONE_CHAT_BELOW_OLD, PHONE_CHAT_BELOW_NEW, 1)
    # Relecture de l'état au démarrage, avant la première disposition.
    if PHONE_CHAT_RESTORE_ANCHOR not in player_methods:
        fail("rappel de focus introuvable dans le gabarit — état du chat non relu au démarrage")
    player_methods = player_methods.replace(PHONE_CHAT_RESTORE_ANCHOR, PHONE_CHAT_RESTORE_CALL, 1)
        # Picture-in-picture (API 26) : bouton dans le lecteur téléphone, fenêtre
    # 16:9, et disparition du chat pendant que la vidéo est en incrustation.
    # Les trois overrides de callback du framework sont PUBLICS : Activity
    # implémente Window.Callback, un override plus faible fait rejeter la classe
    # entière par le lieur ART (voir onWindowFocusChanged, §6 de memory.md).
    pip_methods = r'''

.method private twouichPhoneView(Ljava/lang/String;)Landroid/view/View;
    .locals 2

    # On ne cherche la vue que si son identifiant a été résolu : findViewById(0)
    # n'est pas une erreur inoffensive, et l'appelant doit pouvoir s'abstenir.
    invoke-direct {p0, p1}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhoneId(Ljava/lang/String;)I

    move-result v0

    if-eqz v0, :no_phone_view

    invoke-virtual {p0, v0}, Landroid/app/Activity;->findViewById(I)Landroid/view/View;

    move-result-object v1

    return-object v1

    :no_phone_view
    const/4 v1, 0x0

    return-object v1
.end method


.method public twouichPhonePip(Landroid/view/View;)V
    .locals 3

    # Sous API 26, PictureInPictureParams n'existe pas : on ne tente rien plutôt
    # que de laisser la résolution de la classe échouer à l'exécution.
    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I

    const/16 v1, 0x1a

    if-lt v0, v1, :return_pip

    new-instance v0, Landroid/util/Rational;

    const/16 v1, 0x10

    const/16 v2, 0x9

    invoke-direct {v0, v1, v2}, Landroid/util/Rational;-><init>(II)V

    new-instance v1, Landroid/app/PictureInPictureParams$Builder;

    invoke-direct {v1}, Landroid/app/PictureInPictureParams$Builder;-><init>()V

    invoke-virtual {v1, v0}, Landroid/app/PictureInPictureParams$Builder;->setAspectRatio(Landroid/util/Rational;)Landroid/app/PictureInPictureParams$Builder;

    move-result-object v1

    invoke-virtual {v1}, Landroid/app/PictureInPictureParams$Builder;->build()Landroid/app/PictureInPictureParams;

    move-result-object v1

    invoke-virtual {p0, v1}, Landroid/app/Activity;->enterPictureInPictureMode(Landroid/app/PictureInPictureParams;)Z

    :return_pip
    return-void
.end method


.method public onConfigurationChanged(Landroid/content/res/Configuration;)V
    .locals 2

    invoke-super {p0, p1}, Landroid/app/Activity;->onConfigurationChanged(Landroid/content/res/Configuration;)V

    # L'activité déclare désormais screenSize/orientation : elle n'est plus
    # recréée à la rotation ni à l'entrée en PiP, donc c'est ici que la
    # disposition est réappliquée avec les nouvelles dimensions.
    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I

    const/16 v1, 0x18

    if-lt v0, v1, :pip_check_on_config

    goto :apply_layout_on_config

    :pip_check_on_config
    invoke-virtual {p0}, Landroid/app/Activity;->isInPictureInPictureMode()Z

    move-result v0

    if-eqz v0, :return_config

    :apply_layout_on_config
    invoke-direct {p0}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhoneStackedLayout()V

    :return_config
    return-void
.end method


.method public onPictureInPictureModeChanged(ZLandroid/content/res/Configuration;)V
    .locals 5

    invoke-super {p0, p1, p2}, Landroid/app/Activity;->onPictureInPictureModeChanged(ZLandroid/content/res/Configuration;)V
''' + PHONE_PIP_STATE_WRITE + r'''

    # Télévision : rien n'est empilé, et masquer le chat TV ici le laisserait
    # masqué à la sortie du PiP.
    invoke-virtual {p0}, Landroid/content/Context;->getResources()Landroid/content/res/Resources;

    move-result-object v0

    invoke-virtual {v0}, Landroid/content/res/Resources;->getConfiguration()Landroid/content/res/Configuration;

    move-result-object v0

    iget v0, v0, Landroid/content/res/Configuration;->smallestScreenWidthDp:I

    const/16 v1, 0x258

    if-ge v0, v1, :return_pip_mode

    const-string v0, "ExoPlayer"

    invoke-direct {p0, v0}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhoneView(Ljava/lang/String;)Landroid/view/View;

    move-result-object v0

    const-string v1, "ChatRecycleView"

    invoke-direct {p0, v1}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhoneView(Ljava/lang/String;)Landroid/view/View;

    move-result-object v1

    const-string v2, "SendMessageWindow"

    invoke-direct {p0, v2}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhoneView(Ljava/lang/String;)Landroid/view/View;

    move-result-object v2

    if-eqz v0, :return_pip_mode

    if-eqz v1, :return_pip_mode

    if-eqz v2, :return_pip_mode

    # Sortie de l'incrustation : on réapplique l'empilement validé (vidéo 16:9,
    # chat, saisie) au lieu de deviner des visibilités intermédiaires.
    if-eqz p1, :restore_pip_layout

    # Entrée en incrustation : la fenêtre prend le rapport 16:9, donc la vidéo
    # remplit tout le cadre et le chat plus la saisie sont masqués.
    new-instance v3, Landroid/widget/RelativeLayout$LayoutParams;

    const/4 v4, -0x1

    invoke-direct {v3, v4, v4}, Landroid/widget/RelativeLayout$LayoutParams;-><init>(II)V

    invoke-virtual {v0, v3}, Landroid/view/View;->setLayoutParams(Landroid/view/ViewGroup$LayoutParams;)V

    const/16 v3, 0x8

    invoke-virtual {v1, v3}, Landroid/view/View;->setVisibility(I)V

    invoke-virtual {v2, v3}, Landroid/view/View;->setVisibility(I)V
''' + PHONE_PIP_HIDE_TRACE + r'''

    goto :return_pip_mode

    :restore_pip_layout
''' + PHONE_PIP_RESTORE_TRACE + r'''
    invoke-direct {p0}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhoneStackedLayout()V

    :return_pip_mode
    return-void
.end method
'''
    player_fixed = player_text.replace(
        'invoke-direct {v0, -1, v10}, Landroid/widget/RelativeLayout$LayoutParams;-><init>(II)V',
        'const/4 v9, -0x1\n    invoke-direct {v0, v9, v10}, Landroid/widget/RelativeLayout$LayoutParams;-><init>(II)V',
    ).replace(
        'invoke-direct {v0, -1, v7}, Landroid/widget/RelativeLayout$LayoutParams;-><init>(II)V',
        'const/4 v9, -0x1\n    invoke-direct {v0, v9, v7}, Landroid/widget/RelativeLayout$LayoutParams;-><init>(II)V',
    ).replace(
        'invoke-direct {v0, -1, v11}, Landroid/widget/RelativeLayout$LayoutParams;-><init>(II)V',
        'const/4 v9, -0x1\n    invoke-direct {v0, v9, v11}, Landroid/widget/RelativeLayout$LayoutParams;-><init>(II)V',
    # Bug corrigé : setVisibility recevait un LayoutParams (objet) au lieu d'un int,
    # ce qui faisait échouer la vérification Dalvik à l'ouverture du lecteur.
    ).replace(
        # Bug corrigé : l'override était déclaré « protected ». Activity
        # implémente Window.Callback, dont onWindowFocusChanged(boolean) est
        # public : un override plus faible fait rejeter la CLASSE ENTIÈRE par le
        # lieur ART (« implementing interface method is not public » de
        # Window$Callback). PlayerActivity devenait alors introuvable
        # (ClassNotFoundException puis NoClassDefFoundError) et l'ouverture d'un
        # direct plantait l'application — reproduit le 20/09 sur BlueStacks
        # (API 25), invisible sur l'appareil précédent.
        ".method protected onWindowFocusChanged(Z)V",
        ".method public onWindowFocusChanged(Z)V",
    ).replace(
        'invoke-virtual {v5, v0}, Landroid/view/View;->setLayoutParams(Landroid/view/ViewGroup$LayoutParams;)V\n    const/4 v0, 0x0\n    invoke-virtual {v5, v0}, Landroid/view/View;->setVisibility(I)V',
        'invoke-virtual {v5, v0}, Landroid/view/View;->setLayoutParams(Landroid/view/ViewGroup$LayoutParams;)V\n    const/4 v9, 0x0\n    invoke-virtual {v5, v9}, Landroid/view/View;->setVisibility(I)V',
    ).replace(
        'invoke-virtual {v6, v0}, Landroid/view/View;->setLayoutParams(Landroid/view/ViewGroup$LayoutParams;)V\n    invoke-virtual {v6, v0}, Landroid/view/View;->setVisibility(I)V',
        'invoke-virtual {v6, v0}, Landroid/view/View;->setLayoutParams(Landroid/view/ViewGroup$LayoutParams;)V\n    const/4 v9, 0x0\n    invoke-virtual {v6, v9}, Landroid/view/View;->setVisibility(I)V',
    # Bugs corrigés dans la géométrie du lecteur empilé : vidéo 16:9 calculée
    # depuis la largeur sans plafond, puis empilement tenté en paysage faute de
    # place pour le chat.
    ).replace(
        PHONE_GEO_CLAMPED_TAIL, PHONE_GEO_TAIL,
    ).replace(
        PHONE_GEO_OLD_TAIL, PHONE_GEO_TAIL,
    # Polarité des deux tests de place : ils ont déjà été écrits à l'envers une
    # fois (la vidéo qui tenait était plafonnée, et l'empilement se faisait
    # exactement quand il n'y avait pas la place). Même famille que §6.
    ).replace(
        "    if-ge v10, v7, :twouich_phone_video_fits",
        "    if-lt v10, v7, :twouich_phone_video_fits",
    ).replace(
        "    if-lt v7, v3, :twouich_phone_room",
        "    if-ge v7, v3, :twouich_phone_room",
    # Un arbre qui portait déjà le bloc de place voit la réparation ci-dessus en
    # insérer un second : on recolle les doublons, sinon apktool refuse le fichier
    # (« There is already a label with that name »).
    ).replace(
        PHONE_GEO_ROOM_BLOCK + PHONE_GEO_ROOM_BLOCK, PHONE_GEO_ROOM_BLOCK,
    )
    # Incrustation : un arbre déjà patché avant le 20/09 porte la disposition
    # empilée sans garde d'incrustation — c'est le cas de tout arbre de travail
    # mis à jour sur place. On repose le garde et ses traces ici (une seule
    # source de texte : les constantes PHONE_PIP_*).
    if (".method private twouichPhoneStackedLayout()V" in player_fixed
            and "twouich_phone_layout_ok" not in player_fixed):
        head = ".method private twouichPhoneStackedLayout()V\n    .locals 12\n"
        player_fixed = player_fixed.replace(head, head + PHONE_PIP_GUARD + "\n", 1)
    if (".method private twouichPhoneStackedLayout()V" in player_fixed
            and ":stacked_chat_shown" not in player_fixed):
        player_fixed = player_fixed.replace(PHONE_CHAT_GATE_ANCHOR, PHONE_CHAT_GATE, 1)
    # Garde à polarité inversée (if-nez) : l'arbre de travail écrit avant la
    # correction se repliait lui-même à chaque reprise d'activité. On le remet
    # dans le bon sens sur place — l'ancrage ci-dessus ne le verrait pas, le
    # label étant déjà présent.
    if "    if-nez v1, :stacked_chat_shown\n" in player_fixed:
        player_fixed = player_fixed.replace(
            "    if-nez v1, :stacked_chat_shown\n",
            "    if-eqz v1, :stacked_chat_shown\n", 1)
    # Chat étiré sous la barre de saisie (arbre de travail écrit avant le 21/09), et
    # l'état intermédiaire qui bornait le chat par la règle 2 — cycle de dépendances,
    # plantage à la mesure. Les deux sont ramenés à la marge basse.
    for chat_old in (PHONE_CHAT_BELOW_OLD, PHONE_CHAT_ABOVE_OLD):
        if chat_old in player_fixed:
            player_fixed = player_fixed.replace(chat_old, PHONE_CHAT_BELOW_NEW, 1)
    # Relecture de l'état au démarrage : un arbre patché avant le 21/09 appelle
    # l'empilement depuis le rappel de focus sans jamais relire la préférence.
    if PHONE_CHAT_RESTORE_ANCHOR in player_fixed:
        player_fixed = player_fixed.replace(PHONE_CHAT_RESTORE_ANCHOR, PHONE_CHAT_RESTORE_CALL, 1)
    # Point d'entrée RÉEL de la relecture : onResume. Posé ici (et pas dans le
    # gabarit) parce que onResume appartient au fichier d'origine, donc présent
    # à l'identique sur un arbre vierge et sur un arbre déjà patché.
    # Idempotence : le test porte sur le texte AVEC l'appel — l'ancre, elle,
    # reste présente après l'insertion, donc un test sur l'ancre seule serait
    # toujours vrai et empilerait les appels à chaque passage.
    if PHONE_CHAT_RESUME_CALL not in player_fixed:
        if player_fixed.count(PHONE_CHAT_RESUME_ANCHOR) != 1:
            fail("onResume introuvable (ou ambigu) dans PlayerActivity "
                 "— état du chat impossible à relire au démarrage")
        player_fixed = player_fixed.replace(PHONE_CHAT_RESUME_ANCHOR, PHONE_CHAT_RESUME_CALL, 1)
    # Polarité du garde de relecture : l'arbre de travail du 21/09 porte
    # `if-eqz` (le corps sortait aussitôt) — ramené à `if-nez`.
    if PHONE_CHAT_RESTORE_GUARD_OLD in player_fixed:
        player_fixed = player_fixed.replace(
            PHONE_CHAT_RESTORE_GUARD_OLD, PHONE_CHAT_RESTORE_GUARD_NEW, 1)
    if PHONE_PIP_VIEW_OLD in player_fixed:
        player_fixed = player_fixed.replace(
            PHONE_PIP_VIEW_OLD, PHONE_PIP_VIEW_NEW, 1,
        )
    if (".method public onPictureInPictureModeChanged" in player_fixed
            and PHONE_PIP_STATE_NEEDLE not in player_fixed):
        player_fixed = player_fixed.replace(
            PHONE_PIP_SUPER, PHONE_PIP_SUPER + PHONE_PIP_STATE_WRITE + "\n", 1,
        )
    if (".method public onPictureInPictureModeChanged" in player_fixed
            and "picture-in-picture : video plein cadre" not in player_fixed):
        player_fixed = player_fixed.replace(
            "    invoke-virtual {v2, v3}, Landroid/view/View;->setVisibility(I)V\n",
            "    invoke-virtual {v2, v3}, Landroid/view/View;->setVisibility(I)V\n"
            + PHONE_PIP_HIDE_TRACE + "\n", 1,
        )
    if (".method public onPictureInPictureModeChanged" in player_fixed
            and "picture-in-picture : disposition empilee restauree" not in player_fixed):
        player_fixed = player_fixed.replace(
            "    :restore_pip_layout\n",
            "    :restore_pip_layout\n" + PHONE_PIP_RESTORE_TRACE + "\n", 1,
        )
    # Champ d'état d'incrustation : la disposition téléphone le lit pour ne pas
    # réappliquer l'empilement pendant que la vidéo est en incrustation.
    # Champs d'état (incrustation + toggle chat) : écrits dans TOUS les cas
    # où ils manquent — même quand les méthodes sont déjà présentes, sinon un
    # arbre déjà patché garde des méthodes qui lisent un champ inexistant.
    # (Bug corrigé le 21/09 : la version précédente n'écrivait le champ que
    # dans la branche « arbre vierge », et un arbre déjà patché par la version
    # sans toggle se retrouvait avec 2 méthodes et 0 champ.)
    fields_block = ("\n\n.field private twouichPipActive:Z"
                    "\n.field private twouichChatHidden:Z"
                    "\n.field private twouichChatRestored:Z")
    if ".field private twouichPipActive:Z" not in player_fixed:
        player_fixed = player_fixed.replace(
            ".super Landroid/app/Activity;",
            ".super Landroid/app/Activity;" + fields_block,
            1,
        )
    if ".field private twouichChatHidden:Z" not in player_fixed:
        player_fixed = player_fixed.replace(
            ".field private twouichPipActive:Z",
            ".field private twouichPipActive:Z\n.field private twouichChatHidden:Z\n.field private twouichChatRestored:Z",
            1,
        )
    # Arbre déjà patché par la version qui n'avait que le champ d'état : le champ
    # de la relecture lui manque, et les méthodes qui le lisent rejetteraient la
    # classe entière (mieux vaut le poser que le découvrir à l'exécution).
    if ".field private twouichChatRestored:Z" not in player_fixed:
        player_fixed = player_fixed.replace(
            ".field private twouichChatHidden:Z",
            ".field private twouichChatHidden:Z\n.field private twouichChatRestored:Z",
            1,
        )
    # Toggle du chat : un arbre déjà patché par la version précédente ne
    # connaît pas le champ d'état — on retire alors les méthodes chat (elles
    # lisent ce champ, elles rejetteraient la classe) pour les repose ensuite.
    # Les regex sont ANCRÉES À LA FIN DU FICHIER (dernière occurrence = la
    # méthode ajoutée par nous, jamais une autre) : un .*? non ancré traversait
    # les frontières de méthodes et avalait les blocs voisins (constaté le
    # 21/09 : stacked et PiP disparus après un second passage).
    # Marqueur de version du câblage chat : la méthode repliée n'existe que
    # dans la version courante. Le test porte sur le texte LU DU DISQUE, jamais
    # sur la copie de travail — les champs et les méthodes y sont ajoutés juste
    # avant, et un test sur la copie conclurait « déjà fait » (piège du 21/09).
    chat_current = CHAT_REPAIR_ANCHOR in player_text
    if not chat_current:
        for sig in (
            ".method private twouichChatRestore()V",
            ".method private twouichChatTraces()Ljava/lang/String;",
            ".method private twouichChatCollapse()V",
            ".method private twouichChatApply(Z)V",
            ".method public twouichPhoneChatToggle(Landroid/view/View;)V",
        ):
            k = player_fixed.rfind(sig)
            if k < 0:
                continue
            e = player_fixed.find(".end method", k)
            if e > k:
                player_fixed = player_fixed[:k].rstrip() + "\n" + player_fixed[e + len(".end method"):]
    repaired_chat = False
    if not chat_current:
        player_fixed = player_fixed.rstrip() + "\n" + CHAT_METHODS.replace("\r\n", "\n").rstrip() + "\n"
        repaired_chat = True
    # Puis les méthodes lecteur/PiP si elles manquent encore (le test lit
    # player_fixed, donc APRÈS l'ajout des méthodes chat) — un seul ordre
    # possible : chat d'abord, lecteur ensuite, sinon le bloc lecteur écrit
    # sans les méthodes chat et la réparation les rejoue après (doublon).
    # Le toggle est déjà dans player_methods (une seule source) : la seule
    # décision d'écriture est celle du bloc lecteur — le if ci-dessous —, et
    # repaired_chat ne déclenche jamais une écriture qui doublerait la méthode.
    # Tests de présence par SIGNATURE de méthode, jamais par nom nu : les
    # commentaires des méthodes injectées citent leurs voisines, et un nom nu
    # dans un commentaire fait passer une méthode pour présente (constaté le
    # 21/09 : CHAT_METHODS mentionne la disposition empilée, le bloc lecteur
    # n'était plus jamais écrit, onPictureInPictureModeChanged disparaissait).
    # Veille : le service de premier plan suit la vie du lecteur.
    player_fixed, service_calls = _patch_playback_calls(player_fixed)

    if ".method private twouichPhoneStackedLayout()V" not in player_fixed:
        write_player(player_fixed.rstrip() + "\n"
                     + player_methods.replace("\r\n", "\n").rstrip() + "\n"
                     + pip_methods.replace("\r\n", "\n").rstrip() + "\n")
        log("smartphone : lecteur empilé vidéo en haut, chat puis saisie en bas")
        log("smartphone : picture-in-picture branché sur le lecteur")
    # PiP absent du fichier : on l'ajoute, et rien d'autre — les méthodes chat
    # sont déjà dans player_fixed (nettoyage puis ajout ci-dessus), les
    # réécrire ici les dupliquerait et apktool refuserait le fichier.
    elif ".method public twouichPhonePip(Landroid/view/View;)V" not in player_fixed:
        write_player(player_fixed.rstrip() + "\n"
                     + pip_methods.replace("\r\n", "\n").rstrip() + "\n")
        log("smartphone : picture-in-picture branché sur le lecteur")
    elif repaired_chat:
        # Arbre écrit par la version précédente : méthodes chat retirées puis
        # reposées, garde du chat replié ajouté — on écrit l'état corrigé.
        write_player(player_fixed)
        log("smartphone : chat repliable rebranché sur le lecteur (réparation)")
    elif (player_fixed != player_text or tv_guard_count or screen_off_patched
          or service_calls):
        write_player(player_fixed)
        log("smartphone : correction des paramètres du lecteur empilé")
    else:
        log("déjà appliqué : lecteur empilé smartphone")

    # Empreinte des greffes écrites dans ce lecteur (cf. STAMP_SUFFIX) : le texte
    # des gabarits, jamais le fichier — réparer un arbre ancien ne la change pas,
    # modifier un gabarit si.
    global GREFFE_FINGERPRINT
    GREFFE_FINGERPRINT = hashlib.sha256(
        "\n".join((CHAT_METHODS, player_methods, pip_methods, TV_INTERFACE_METHOD,
                    PHONE_SCREEN_OFF_GUARD, PHONE_SCREEN_OFF_KEPT)).encode("utf-8")
    ).hexdigest()

    values = decoded / "res/values/dimens.xml"
    if not values.is_file():
        fail(f"ressources dimens absentes : {values}")
    dims = values.read_text(encoding="utf-8")
    dim = '<dimen name="twouich_phone_chat_height">280dp</dimen>'
    if dim not in dims:
        insertion = "\n    " + dim
        anchor = "</resources>"
        if anchor not in dims:
            fail("fin de res/values/dimens.xml introuvable")
        values.write_text(dims.replace(anchor, insertion + "\n" + anchor, 1), encoding="utf-8")
        log("smartphone : hauteur de chat tactile 280dp")
    else:
        log("déjà appliqué : dimension du chat smartphone")


def patch_smartphone_headers(decoded: pathlib.Path) -> None:
    """Sur téléphone, replie le panneau latéral Leanback au profit des rangées.

    `MainFragment` force HEADERS_ENABLED : sur un téléphone, la colonne de navigation
    du BrowseSupportFragment occupe alors ~70 % de la largeur (mesuré : `[0,0][852,2504]`
    sur un écran de 1220 px), ne laissant aux cartes qu'une bande de 362 px — un tap y
    déplace la mise en page (repli du panneau) au lieu d'ouvrir la carte. HEADERS_HIDDEN
    rend la même navigation accessible par la touche retour, mais laisse les rangées
    occuper toute la largeur : elles deviennent utilisables au doigt.

    Le seuil 600dp est celui d'Android : au-delà (TV, grande tablette) le comportement
    d'origine est conservé à l'identique.
    """
    path = decoded / "smali_classes2/com/s0und/s0undtv/fragments/MainFragment.smali"
    if not path.is_file():
        fail(f"fragment principal absent : {path}")
    text = path.read_text(encoding="utf-8")
    # Un Fragment n'est pas un Context : ses accesseurs sont obfusqués par R8 et un
    # appel littéral à getResources() sur la classe parente lève un NoSuchMethodError
    # au démarrage (crash observé sur appareil). On passe donc par B1(), qui est
    # requireContext() dans l'arbre décodé, puis par le Context obtenu.
    context_lookup = (
        "    invoke-virtual {p0}, Landroidx/fragment/app/f;->B1()Landroid/content/Context;\n"
        "    move-result-object v0\n"
        "    invoke-virtual {v0}, Landroid/content/Context;->getResources()"
        "Landroid/content/res/Resources;\n"
        "    move-result-object v0\n"
    )
    broken_lookup = (
        "    invoke-virtual {p0}, Landroidx/fragment/app/f;->getResources()"
        "Landroid/content/res/Resources;\n"
        "    move-result-object v0\n"
    )
    # États de setHeadersState dans le Leanback embarqué (mesurés le 19/09 dans la
    # table de branchement de BrowseSupportFragment.N2) : 1 (DISABLED) et 2
    # (ENABLED) laissent le panneau VISIBLE — 2 est l'état TV d'origine — et seul
    # 3 (HIDDEN) le met en GONE. Passer 1 sur téléphone laissait donc le panneau
    # déployé sur 852 px et écrasait les rangées dans une bande de 362 px.
    helper = (
        "\n\n.method private twouichPhoneHeadersState()I\n"
        "    .locals 3\n"
        + context_lookup +
        "    invoke-virtual {v0}, Landroid/content/res/Resources;->getConfiguration()"
        "Landroid/content/res/Configuration;\n"
        "    move-result-object v0\n"
        "    iget v1, v0, Landroid/content/res/Configuration;->uiMode:I\n"
        "    and-int/lit8 v1, v1, 0xf\n"
        "    const/4 v2, 0x4\n"
        # `if-eq` : le mode TV (type 4) deploie le panneau. Avec `if-ne`,
        # c'est un TELEPHONE qui le recevait deploye — la regression d'UX
        # corrigee le 19/09 — et une Freebox 540 dp qui perdait sa colonne.
        "    if-eq v1, v2, :cond_twouich_tv_headers\n"
        "    iget v1, v0, Landroid/content/res/Configuration;->smallestScreenWidthDp:I\n"
        "    const/16 v2, 0x258\n"
        "    if-ge v1, v2, :cond_twouich_tv_headers\n"
        "    const/4 v2, 0x3\n"
        "    return v2\n"
        ":cond_twouich_tv_headers\n"
        "    const/4 v2, 0x2\n"
        "    return v2\n"
        ".end method\n"
    )
    broken_state = (
        "    if-ge v0, v1, :cond_twouich_tv_headers\n"
        "    const/4 v2, 0x1\n"
    )
    fixed_state = (
        "    if-ge v0, v1, :cond_twouich_tv_headers\n"
        "    const/4 v2, 0x3\n"
    )
    call_old = "    invoke-virtual {p0, v3}, Landroidx/leanback/app/f;->N2(I)V"
    # Dalvik refuse invoke-virtual sur une méthode privée de la même classe : il
    # faut invoke-direct, sinon la classe entière est rejetée par le vérificateur
    # (VerifyError au démarrage). Le move-result doit rester collé à l'appel.
    call_direct = "    invoke-direct {p0}, Lcom/s0und/s0undtv/fragments/MainFragment;"
    call_new = (call_direct + "->twouichPhoneHeadersState()I\n\n    move-result v0\n\n"
                "    invoke-virtual {p0, v0}, Landroidx/leanback/app/f;->N2(I)V")
    # Réparation d'une version antérieure fautive (invoke-virtual + comparaison
    # inversée), pour que « relancer patch.py » suffise à assainir un arbre déjà patché.
    text = text.replace(
        "    invoke-virtual {p0}, Lcom/s0und/s0undtv/fragments/MainFragment;"
        "->twouichPhoneHeadersState()I",
        call_direct + "->twouichPhoneHeadersState()I",
    ).replace(
        "if-lt v0, v1, :cond_twouich_tv_headers",
        "if-ge v0, v1, :cond_twouich_tv_headers",
    )
    # Réparation du helper écrit dans une version antérieure, dont l'accès aux
    # ressources faisait planter l'application au démarrage, et dont l'état 1
    # (DISABLED) laissait le panneau TV déployé sur téléphone.
    if broken_lookup in text:
        text = text.replace(broken_lookup, context_lookup)
    # Arbre ecrit avant le 21/09 : le helper testait les seuls dp. Un
    # televiseur 1080p (540 dp) y passait pour un telephone et perdait sa
    # colonne de navigation. On remplace le test, garde par garde.
    dp_only_guard = (
        "    iget v0, v0, Landroid/content/res/Configuration;->smallestScreenWidthDp:I\n"
        "    const/16 v1, 0x258\n"
        "    const/4 v2, 0x2\n"
        "    if-ge v0, v1, :cond_twouich_tv_headers\n"
        "    const/4 v2, 0x3\n"
        ":cond_twouich_tv_headers\n"
        "    return v2\n"
    )
    tv_mode_guard = (
        "    iget v1, v0, Landroid/content/res/Configuration;->uiMode:I\n"
        "    and-int/lit8 v1, v1, 0xf\n"
        "    const/4 v2, 0x4\n"
        # `if-eq` : le mode TV (type 4) deploie le panneau. Avec `if-ne`,
        # c'est un TELEPHONE qui le recevait deploye — la regression d'UX
        # corrigee le 19/09 — et une Freebox 540 dp qui perdait sa colonne.
        "    if-eq v1, v2, :cond_twouich_tv_headers\n"
        "    iget v1, v0, Landroid/content/res/Configuration;->smallestScreenWidthDp:I\n"
        "    const/16 v2, 0x258\n"
        "    if-ge v1, v2, :cond_twouich_tv_headers\n"
        "    const/4 v2, 0x3\n"
        "    return v2\n"
        ":cond_twouich_tv_headers\n"
        "    const/4 v2, 0x2\n"
        "    return v2\n"
    )
    if dp_only_guard in text:
        text = text.replace(dp_only_guard, tv_mode_guard, 1)
        log("smartphone : panneau lateral — mode TV lu dans le mode systeme")
    if broken_state in text:
        text = text.replace(broken_state, fixed_state, 1)
    if "twouichPhoneHeadersState" in text:
        if call_old in text:
            text = text.replace(call_old, call_new, 1)
            path.write_text(text, encoding="utf-8", newline="\n")
            log("smartphone : appel du calcul d'état du panneau corrigé")
        elif text != path.read_text(encoding="utf-8"):
            path.write_text(text, encoding="utf-8", newline="\n")
            log("smartphone : panneau latéral assaini (invoke-direct)")
        else:
            log("déjà appliqué : état du panneau latéral selon la taille d'écran")
        return
    if call_old not in text:
        fail("appel setHeadersState introuvable dans MainFragment — cible changée")
    text = text.replace(call_old, call_new, 1)
    text = text.rstrip() + "\n" + helper + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    log("smartphone : panneau latéral replié au profit des rangées (HEADERS_HIDDEN)")


def find_base_grid(decoded: pathlib.Path) -> pathlib.Path:
    """Retrouve le fichier smali de BaseGridView (nom obfusqué, numéroté par apktool).

    Le nom de fichier dépend des collisions de casse (e.smali / e.1.smali) : on
    identifie donc le fichier par sa déclaration de classe, jamais par son nom.
    """
    directory = decoded / "smali/androidx/leanback/widget"
    for candidate in sorted(directory.glob("*.smali")):
        if BASE_GRID_CLASS in candidate.read_text(encoding="utf-8")[:200]:
            return candidate
    fail(f"BaseGridView ({BASE_GRID_CLASS}) absent de {directory} — cible changée")
    raise AssertionError("inatteignable")


def patch_smartphone_chat_toggle(decoded: pathlib.Path) -> None:
    """Bouton masquer/afficher le chat du lecteur téléphone.

    Depuis le 20/09 le chat est visible en bas du lecteur portrait (empilement),
    mais rien ne permettait de le replier : il occupait la moitié basse de
    l'écran sans contrôle pour le retirer. Le bouton vit sur la vidéo et n'en
    bouge jamais — ancré au coin bas droit, il tombait dans le même rectangle
    que le bouton d'incrustation, donc dessous, donc intappable (repli mesuré
    sur BlueStacks le 21/09). Le repli donne l'écran entier à la vidéo ; l'état
    (twouichChatHidden) et l'application (twouichChatApply) vivent dans
    PlayerActivity, le layout ici.
    Retiré depuis la v1.0.12 : le chat vit SOUS la vidéo, donc le replier ne
    changeait plus la taille de l'image (« l'icône à côté du PiP ne sert à
    rien », 21/09). La machinerie du repli (twouichChatApply, twouichChatCollapse)
    reste dans le dex — sans prise : aucune vue ne l'appelle. Ce passage est donc
    une RÉPARATION : il retire le bouton d'un arbre déjà patché.
    """
    print("[1i/5] UX smartphone (bouton masquer/afficher le chat)")
    phone = decoded / "res/layout/activity_player.xml"
    if not phone.is_file():
        fail(f"layout lecteur absent : {phone}")
    source = phone.read_text(encoding="utf-8")
    # Un arbre écrit par la version précédente peut porter le bouton : on le
    # retire, quel que soit son emplacement.
    button = re.compile(r"\s*<ImageButton android:id=\"@\+id/twouich_phone_chat\".*?/>",
                        re.DOTALL)
    new, count = button.subn("", source, count=1)
    if count == 0:
        log("déjà appliqué : aucun bouton de chat dans le lecteur")
        return
    phone.write_text(new, encoding="utf-8", newline="\n")
    log("smartphone : bouton masquer/afficher le chat retiré du lecteur")

def patch_smartphone_tap(decoded: pathlib.Path) -> None:
    """Traduit un tap sur une carte Leanback en clic, sur téléphone seulement.

    Constat sur appareil (19/09, 1220×2712) : le premier appui sur une carte ne
    fait que déplacer la sélection — la carte n'est activée qu'au second appui,
    ce qui rend les rangées inutilisables au doigt. On branche donc TapClick à
    l'entrée de BaseGridView.dispatchTouchEvent : un tap déclenche le même clic
    que la touche OK du D-pad.

    Le D-pad n'émet aucun MotionEvent, et TapClick laisse tout passer au-delà de
    600 dp de plus petit côté : la télévision garde le comportement d'origine.
    """
    print("[1f/5] UX smartphone (tap → clic sur les cartes Leanback)")
    path = find_base_grid(decoded)
    text = path.read_text(encoding="utf-8")
    head_old = ".method public dispatchTouchEvent(Landroid/view/MotionEvent;)Z\n    .locals 1\n"
    head_new = (".method public dispatchTouchEvent(Landroid/view/MotionEvent;)Z\n"
                "    .locals 3\n"
                "\n"
                "    # Twouich : un tap vaut un clic (téléphone uniquement).\n"
                + TAP_HOOK_CALL + "\n"
                "\n"
                "    move-result v0\n"
                "\n"
                f"    if-eqz v0, {TAP_HOOK_LABEL}\n"
                "\n"
                "    const/4 v0, 0x1\n"
                "\n"
                "    return v0\n"
                "\n"
                f"{TAP_HOOK_LABEL}\n")
    if TAP_HOOK_CALL in text:
        log(f"déjà appliqué : tap → clic dans {path.name} (dispatchTouchEvent)")
        return
    if head_old not in text:
        fail(f"en-tête de dispatchTouchEvent introuvable dans {path.name} — cible changée")
    text = text.replace(head_old, head_new, 1)
    path.write_text(text, encoding="utf-8", newline="\n")
    log(f"injecté : tap → clic en tête de dispatchTouchEvent ({path.name})")


def install_phone_assets(decoded: pathlib.Path, here: pathlib.Path) -> None:
    """Pose les ressources propres au téléphone : icônes de la barre basse + teinte inactive.

    Le thème upstream ne fournit pas d'icône d'onglet « Accueil » : la barre
    basse reste donc plate et sans repère visuel. Les vectoriels sont dédiés
    (ils ne remplacent aucune ressource existante) et la teinte inactive est une
    couleur, pour qu'un changement de thème reste possible.
    """
    print("[1g/5] UX smartphone (icônes de la barre basse)")
    src = here / "res" / "drawable"
    dst = decoded / "res" / "drawable"
    if not src.is_dir():
        fail(f"icônes smartphone absentes : {src}")
    dst.mkdir(parents=True, exist_ok=True)
    copied = 0
    for f in sorted(src.glob("*.xml")):
        target = dst / f.name
        if not target.exists() or target.read_bytes() != f.read_bytes():
            shutil.copy2(f, target)
            copied += 1
    log(f"{copied} icône(s) smartphone posée(s) dans res/drawable")

    colors = decoded / "res" / "values" / "colors.xml"
    if not colors.is_file():
        fail(f"ressources de couleurs absentes : {colors}")
    text = colors.read_text(encoding="utf-8")
    if "twouich_phone_nav_inactive" not in text:
        anchor = "</resources>"
        if anchor not in text:
            fail("fin de res/values/colors.xml introuvable")
        color = '<color name="twouich_phone_nav_inactive">#ffd9d9d9</color>'
        colors.write_text(text.replace(anchor, "    " + color + "\n" + anchor, 1),
                          encoding="utf-8")
        log("smartphone : teinte des onglets inactifs")
    else:
        log("déjà appliqué : teinte des onglets inactifs")


def patch_smartphone_pip(decoded: pathlib.Path) -> None:
    """Branche le picture-in-picture sur le lecteur téléphone.

    Trois choses, et rien de plus : l'activité se déclare compatible PiP, elle
    annonce qu'elle gère elle-même les changements de taille — sans quoi Android
    la recrée à chaque entrée en incrustation, donc le direct repart de zéro —,
    et le lecteur téléphone reçoit un bouton dédié. Le layout TV n'est pas
    touché : son lecteur garde ses contrôles d'origine.
    """
    print("[1h/5] UX smartphone (picture-in-picture)")
    manifest = decoded / "AndroidManifest.xml"
    text = manifest.read_text(encoding="utf-8")
    activity = re.search(r'<activity[^>]*PlayerActivity[^>]*>', text)
    if activity is None:
        fail("activité lecteur introuvable dans AndroidManifest.xml")
    element = activity.group(0)
    new_element = element
    if "android:supportsPictureInPicture" not in new_element:
        new_element = new_element.replace(
            'android:name="com.s0und.s0undtv.activities.PlayerActivity"',
            'android:name="com.s0und.s0undtv.activities.PlayerActivity"'
            ' android:supportsPictureInPicture="true"',
            1,
        )
    if "android:configChanges=" not in new_element:
        fail("PlayerActivity sans android:configChanges — cible changée")
    for change in ("screenSize", "smallestScreenSize", "screenLayout", "orientation"):
        new_element = re.sub(
            r'android:configChanges="([^"]*)"',
            lambda m: m.group(0) if change in m.group(1).split("|")
            else f'android:configChanges="{m.group(1)}|{change}"',
            new_element, count=1,
        )
    if new_element != element:
        manifest.write_text(text.replace(element, new_element, 1), encoding="utf-8")
        log("smartphone : lecteur déclaré compatible picture-in-picture")
    else:
        log("déjà appliqué : picture-in-picture déclaré")

    phone = decoded / "res/layout/activity_player.xml"
    if not phone.is_file():
        fail(f"layout lecteur absent : {phone}")
    source = phone.read_text(encoding="utf-8")
    if "twouich_phone_pip" in source:
        log("déjà appliqué : bouton picture-in-picture")
        return
    anchor = ('(<ImageView android:id="@id/BackgroundCardImage"[^>]*/>\s*'
              '</com\.google\.android\.exoplayer2\.ui\.StyledPlayerView>)')
    button = ('\n    <ImageButton android:id="@+id/twouich_phone_pip"\n'
              '        android:layout_width="48dp" android:layout_height="48dp"\n'
              '        android:layout_alignTop="@id/ExoPlayer" android:layout_alignEnd="@id/ExoPlayer"\n'
              '        android:layout_marginTop="8dp" android:layout_marginEnd="8dp"\n'
              '        android:padding="12dp" android:scaleType="fitCenter"\n'
              '        android:background="#66000000" android:src="@drawable/twouich_ic_pip"\n'
              '        android:contentDescription="Picture-in-picture"\n'
              '        android:onClick="twouichPhonePip" />')
    new, count = re.subn(anchor, lambda m: m.group(1) + button, source, count=1)
    if count != 1:
        fail("lecteur vidéo principal introuvable dans activity_player.xml — cible changée")
    phone.write_text(new, encoding="utf-8")
    log("smartphone : bouton picture-in-picture posé sur la vidéo")


def patch_smartphone_navigation(decoded: pathlib.Path, here: pathlib.Path) -> None:
    """Ajoute une navigation tactile au shell téléphone, sans modifier le shell TV."""
    print("[1e/5] UX smartphone (navigation tactile)")
    phone = decoded / "res/layout/activity_main.xml"
    if not phone.is_file():
        fail(f"layout principal absent : {phone}")
    install_tv_layout(decoded, here, "activity_main.xml")

    # Barre basse sobre : fond opaque de la marque, hairline de séparation et trois
    # libellés — plus aucune « bouton Android » grise par défaut, qui jurait avec le
    # thème sombre du lecteur et de l'accueil.
    layout = """<?xml version="1.0" encoding="utf-8"?>
<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent" android:layout_height="match_parent"
    android:background="@color/black">
    <fragment android:name="com.s0und.s0undtv.fragments.MainFragment"
        android:id="@id/main_browse_fragment" android:layout_width="match_parent"
        android:layout_height="match_parent" android:layout_marginBottom="64dp" />
    <LinearLayout android:id="@+id/twouich_phone_nav_bar"
        android:layout_width="match_parent" android:layout_height="58dp"
        android:layout_gravity="bottom" android:orientation="vertical"
        android:background="#0e0e10" android:elevation="16dp">
        <View android:layout_width="match_parent" android:layout_height="1dp"
            android:background="#2a2a2e" />
        <LinearLayout android:layout_width="match_parent" android:layout_height="match_parent"
            android:orientation="horizontal" android:baselineAligned="false">
            <TextView android:id="@+id/twouich_phone_nav_home"
                android:layout_width="0dp" android:layout_height="match_parent" android:layout_weight="1"
                android:gravity="center" android:text="Accueil" android:textSize="11sp"
                android:drawableTop="@drawable/twouich_ic_home" android:drawablePadding="4dp"
                android:drawableTint="@color/theme_purple_bright"
                android:textColor="@color/theme_purple_bright" android:ellipsize="end" android:maxLines="1"
                android:background="?android:attr/selectableItemBackground"
                android:clickable="true" android:focusable="true"
                android:contentDescription="Accueil" android:onClick="twouichPhoneHome" />
            <TextView android:id="@+id/twouich_phone_nav_search"
                android:layout_width="0dp" android:layout_height="match_parent" android:layout_weight="1"
                android:gravity="center" android:text="Parcourir" android:textSize="11sp"
                android:drawableTop="@drawable/twouich_ic_search" android:drawablePadding="4dp"
                android:drawableTint="@color/twouich_phone_nav_inactive"
                android:textColor="@color/twouich_phone_nav_inactive" android:ellipsize="end" android:maxLines="1"
                android:background="?android:attr/selectableItemBackground"
                android:clickable="true" android:focusable="true"
                android:contentDescription="Parcourir" android:onClick="twouichPhoneSearch" />
            <TextView android:id="@+id/twouich_phone_nav_settings"
                android:layout_width="0dp" android:layout_height="match_parent" android:layout_weight="1"
                android:gravity="center" android:text="Reglages" android:textSize="11sp"
                android:drawableTop="@drawable/twouich_ic_settings" android:drawablePadding="4dp"
                android:drawableTint="@color/twouich_phone_nav_inactive"
                android:textColor="@color/twouich_phone_nav_inactive" android:ellipsize="end" android:maxLines="1"
                android:background="?android:attr/selectableItemBackground"
                android:clickable="true" android:focusable="true"
                android:contentDescription="Reglages" android:onClick="twouichPhoneSettings" />
        </LinearLayout>
    </LinearLayout>
</FrameLayout>
"""
    if phone.read_text(encoding="utf-8") != layout:
        phone.write_text(layout, encoding="utf-8", newline="\n")
        log("smartphone : shell tactile avec navigation basse")
    else:
        log("déjà appliqué : shell tactile smartphone")

    main = decoded / "smali/com/s0und/s0undtv/activities/MainActivity.smali"
    if not main.is_file():
        fail(f"activité principale absente : {main}")
    source = main.read_text(encoding="utf-8")
    methods = """\n.method public twouichPhoneHome(Landroid/view/View;)V
    .locals 0
    return-void
.end method

.method public twouichPhoneSearch(Landroid/view/View;)V
    .locals 3
    new-instance v0, Landroid/content/Intent;
    invoke-direct {v0}, Landroid/content/Intent;-><init>()V
    const-string v1, "com.s0und.s0undtv"
    const-string v2, "com.s0und.s0undtv.activities.SearchActivity"
    invoke-virtual {v0, v1, v2}, Landroid/content/Intent;->setClassName(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;
    invoke-virtual {p0, v0}, Landroid/app/Activity;->startActivity(Landroid/content/Intent;)V
    return-void
.end method

.method public twouichPhoneSettings(Landroid/view/View;)V
    .locals 3
    new-instance v0, Landroid/content/Intent;
    invoke-direct {v0}, Landroid/content/Intent;-><init>()V
    const-string v1, "com.s0und.s0undtv"
    const-string v2, "com.s0und.s0undtv.activities.SettingsActivity"
    invoke-virtual {v0, v1, v2}, Landroid/content/Intent;->setClassName(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;
    invoke-virtual {p0, v0}, Landroid/app/Activity;->startActivity(Landroid/content/Intent;)V
    return-void
.end method
"""
    legacy = "invoke-virtual {v0, p0, v1, v2}, Landroid/content/Intent;->setClassName(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;"
    current = "invoke-virtual {v0, v1, v2}, Landroid/content/Intent;->setClassName(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;"
    source = source.replace(legacy, current)
    if "twouichPhoneSearch" not in source:
        main.write_text(source.rstrip() + methods + "\n", encoding="utf-8", newline="\n")
        log("smartphone : actions Recherche/Réglages branchées")
    elif source != main.read_text(encoding="utf-8"):
        main.write_text(source, encoding="utf-8", newline="\n")
        log("smartphone : appels de navigation corrigés")
    else:
        log("déjà appliqué : actions de navigation smartphone")


def install_selftest(decoded: pathlib.Path) -> None:
    """Branche le self-test sur le démarrage de l'application (une fois par
    processus). Le point d'ancrage est MainApp.onCreate : il existe dans toutes
    les betas, s'exécute avant toute activité et n'exige aucun écran dédié."""
    path = decoded / SELFTEST_PATH
    if not path.is_file():
        fail(f"classe Application introuvable : {SELFTEST_PATH}")
    text = path.read_text(encoding="utf-8")
    if "Lcom/twouich/adblock/SelfTest;" in text:
        log("injection déjà présente dans MainApp.onCreate()")
        return
    new_text, count = APP_ONCREATE.subn(SELFTEST_HOOK, text)
    if count != 1:
        fail(
            "méthode MainApp.onCreate() attendue 1 fois, "
            f"trouvée {count} fois — la cible a changé, adapter patch.py"
        )
    path.write_text(new_text, encoding="utf-8")
    log("injecté : MainApp.onCreate() exécute SelfTest.run()")


def replace_in_style(path: pathlib.Path, style: str, old: str, new: str, what: str) -> bool:
    """Remplace un attribut *dans un seul bloc <style name="style">*.

    Le même couple clé/valeur existe dans une dizaine de thèmes : réécrire le
    fichier entier changerait aussi les thèmes que l'utilisateur peut choisir.
    """
    text = path.read_text(encoding="utf-8")
    match = re.search(
        rf'(<style name="{re.escape(style)}"[^>]*>)(.*?)(</style>)', text, re.DOTALL
    )
    if match is None:
        fail(f"style introuvable : {style} dans {path.name}")
    body = match.group(2)
    if new in body and old not in body:
        log(f"déjà appliqué : {what}")
        return False
    if old not in body:
        fail(f"motif introuvable ({what}) dans {path.name} → style {style}")
    path.write_text(text[: match.start(2)] + body.replace(old, new) + text[match.end(2) :],
                    encoding="utf-8")
    log(f"appliqué : {what}")
    return True


def install_branding(decoded: pathlib.Path, here: pathlib.Path, version_name: str,
                     release_date: str) -> dict[str, str]:
    print("[2/5] Identité Twouich (écran de démarrage, icônes, bannière, nom)")
    res = here / BRAND_RES
    if not (here / BRAND_JSON).is_file() or not res.is_dir():
        fail(f"assets de marque absents ({here / BRAND_DIR}) — lancer : {BRAND_EMIT}")
    brand = json.loads((here / BRAND_JSON).read_text(encoding="utf-8"))

    # 1. L'arborescence res/ du générateur est recopiée telle quelle : splash,
    #    bannière et icônes de lancement (mêmes noms de fichiers que l'original,
    #    donc aucun renommage de ressource à propager ailleurs).
    copied = 0
    for src in sorted(res.rglob("*")):
        if src.is_file():
            dst = decoded / "res" / src.relative_to(res)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied += 1
    log(f"{copied} assets copiés dans res/ — piste {brand['variant']} « {brand['label']} »")

    # 2. Nom affiché : launcher, réglages, notification.
    strings = decoded / "res" / "values" / "strings.xml"
    replace_once(strings, APP_NAME_OLD, APP_NAME_NEW, "nom de l'application (app_name)")
    replace_once(
        strings,
        "section -> S0undTV. Notifications should be turned ON.",
        "section -> Twouich. Notifications should be turned ON.",
        "nom dans le résumé de la notification de test",
    )
    manifest = decoded / "AndroidManifest.xml"
    replace_once(manifest, APP_LABEL_OLD, APP_LABEL_NEW, "libellé de l'application (manifeste)")

    # 3. Plus aucun thème rouge déclaré, et le splash n'emprunte plus le rouge
    #    au thème rouge : la couleur d'accent passe au violet Twitch.
    for old, new in MANIFEST_THEMES:
        replace_once(manifest, old, new, f"manifeste : {old} → {new}")
    replace_in_style(
        decoded / "res" / "values" / "styles.xml",
        SPLASH_THEME,
        "<item name=\"android:colorPrimary\">@color/theme_red</item>",
        "<item name=\"android:colorPrimary\">@color/theme_purple</item>",
        "splash : couleur d'accent rouge → violet Twitch",
    )

    # 4. Palette : l'icône adaptative prenait le rouge de S0und en fond, le thème
    #    « violet » de l'app était le violet Twitch d'avant (#6441a4).
    colors = decoded / "res" / "values" / "colors.xml"
    replace_once(
        colors,
        '<color name="ic_launcher_background">#a30f2c</color>',
        f'<color name="ic_launcher_background">{brand["brand"]}</color>',
        "fond de l'icône adaptative",
    )
    replace_once(colors, '<color name="theme_purple">#6441a4</color>',
                 f'<color name="theme_purple">{brand["brand"]}</color>',
                 "thème violet : teinte Twitch actuelle")
    replace_once(colors, '<color name="theme_purple_bright">#8658db</color>',
                 '<color name="theme_purple_bright">#a970ff</color>',
                 "thème violet : accent clair")

    # 4b. L'accent d'usine est l'index 0 (« Red (default) », prefs_accent_color =
    #     "0") : c'est lui que les installations — neuves comme existantes —
    #     affichent, et c'est le rouge visible sur les cartes focalisées. Plutôt
    #     que de déplacer l'index par défaut (fragile côté smali, et muet pour
    #     les installations existantes qui gardent la valeur sauvegardée), on
    #     recolore la famille theme_red* avec la palette de marque : l'accent
    #     « par défaut » est visuellement Twouich, et le rouge de S0und sort des
    #     couleurs sélectionnables.
    replace_once(
        colors,
        '<color name="theme_red">#a30f2c</color>',
        f'<color name="theme_red">{brand["brand"]}</color>',
        "accent par défaut : theme_red → couleur de marque",
    )
    replace_once(
        colors,
        '<color name="theme_red_bright">#db002c</color>',
        '<color name="theme_red_bright">#a970ff</color>',
        "accent par défaut : theme_red_bright → accent clair",
    )
    replace_once(
        colors,
        '<color name="theme_red_dark">#4d000f</color>',
        f'<color name="theme_red_dark">{brand["brand_dark"]}</color>',
        "accent par défaut : theme_red_dark → fond sombre de marque",
    )
    replace_once(
        colors,
        '<color name="theme_red_main_background">#1f0006</color>',
        '<color name="theme_red_main_background">#130c1f</color>',
        "accent par défaut : theme_red_main_background → fond principal de marque",
    )
    replace_once(
        decoded / "res" / "values" / "arrays.xml",
        "<item>Red (default)</item>",
        "<item>Twouich</item>",
        "réglages : libellé de l'accent par défaut",
    )

    # 5. Pages embarquées (À propos / Nouveautés) : fond rouge → fond sombre, et
    #    l'en-tête dit ce qu'est ce build. Fins de ligne canonisées en LF : ces
    #    fichiers sont stockés bruts dans l'APK, et la traduction CRLF (Windows)
    #    / LF (Linux) de Python briserait la reproductibilité inter-plateformes.
    #    Conformité HTML sans impact (CRLF n'est qu'une tolérance d'affichage).
    #    La date affichée est une constante de build (build.sh) — pas today() :
    #    sinon chaque journée de rebuild change les octets du livrable.
    about = decoded / "assets" / "S0undTV_about.html"
    replace_once(about, ABOUT_OLD, ABOUT_NEW, "page À propos : en-tête Twouich")
    replace_once(about, "background-color: #a30f2d00;", "background-color: #0e0e10;",
                 "page À propos : fond")
    # L'ancien contact block contenait le Discord et le test beta. Les crédits
    # ci-dessus remplacent cette section : ne laissez pas une page de compatibilité
    # technique devenir une surface de marque ou de support historique.
    about_text = about.read_text(encoding="utf-8")
    about_text = re.sub(r"(?m)^\s*<b>discord:.*?\n", "", about_text)
    about_text = re.sub(r"(?m)^\s*<b>beta:.*?\n", "", about_text)
    # Liens vers les pages légales embarquées (remplacent la ligne « Legal »
    # upstream, qui n'était qu'un disclaimer sans politique de confidentialité).
    LEGAL_BLOCK = (
        "    <a href=\"file:///android_asset/twouich_legal.html\">Mentions légales</a>"
        " &nbsp;·&nbsp; "
        "<a href=\"file:///android_asset/twouich_privacy.html\">"
        "Politique de confidentialité</a>"
    )
    if LEGAL_BLOCK not in about_text:
        about_text = about_text.replace(
            '    <div class="legal">',
            f"{LEGAL_BLOCK}\n    <div class=\"legal\">",
            1,
        )
        if LEGAL_BLOCK not in about_text:
            fail("page À propos : ancre du bloc légal introuvable")
        log("appliqué : page À propos : liens vers les pages légales")
    else:
        log("déjà appliqué : page À propos : liens vers les pages légales")
    about.write_text(about_text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")

    # La « Politique de confidentialité » du menu latéral (MainFragment) ouvre
    # PrivacyPolicyActivity, qui charge une politique upstream en ligne
    # (Google Sites de S0undTV) : hors sujet pour ce fork. On la repointe vers
    # la page locale embarquée — même fenêtre, pas de réseau, contenu Twouich.
    privacy_act = decoded / "smali/com/s0und/s0undtv/activities/PrivacyPolicyActivity.smali"
    replace_once(
        privacy_act,
        'const-string v0, "https://sites.google.com/view/privacy-policy-for-s0undtv/home"',
        'const-string v0, "file:///android_asset/twouich_privacy.html"',
        "PrivacyPolicyActivity : politique Twouich locale au lieu de la page upstream",
    )

    # Injection des pages légales (source = patch/branding/, canonisation LF,
    # cf. plus haut : ces fichiers sont stockés bruts dans l'APK).
    for src_name, dest_rel, what in LEGAL_PAGES:
        src = here / src_name
        if not src.is_file():
            fail(f"source de page légale manquante : {src} — le build refuse d'embarquer une page muette")
        dest = decoded / dest_rel
        dest.write_text(src.read_text(encoding="utf-8").replace("\r\n", "\n"),
                        encoding="utf-8", newline="\n")
        log(f"appliqué : {what} (embarquée)")

    changelog = decoded / "assets" / "S0undTV_changelog.html"
    changelog_new = CHANGELOG_NEW.format(
        version=version_name, date=release_date
    )
    if f"<h1>Twouich {version_name}" in changelog.read_text(encoding="utf-8"):
        log("déjà appliqué : page Nouveautés : entrée Twouich")
    else:
        replace_once(
            changelog,
            CHANGELOG_OLD,
            changelog_new,
            "page Nouveautés : entrée Twouich",
        )
    replace_once(changelog, "background-color: #a30f2d;", "background-color: #0e0e10;",
                 "page Nouveautés : fond rouge → sombre")
    # Repartir de zéro signifie réellement supprimer l'historique HTML hérité :
    # le changelog ne garde que l'entrée Twouich courante et le lien de crédits
    # vers le projet source.
    changelog_text = changelog.read_text(encoding="utf-8")
    historical = re.search(r"\n\s*<h1>beta_144\b", changelog_text)
    if historical:
        changelog_text = changelog_text[:historical.start()] + "\n</body>\n</html>\n"
    # No inherited support channel or historical invitation survives in the new
    # page; credits point only to the source project above.
    changelog_text = re.sub(r"(?im)^.*(?:discord|discord channel|zmNjK2S).*$\n?", "", changelog_text)
    changelog.write_text(changelog_text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    return brand


def patch_update_version_comparison(decoded: pathlib.Path) -> None:
    path = decoded / "smali_classes2/com/s0und/s0undtv/helpers/a.smali"
    text = path.read_text(encoding="utf-8")
    old = "    const/16 v1, 0x90"
    if UPDATE_VERSION_CALL in text:
        log("déjà appliqué : comparaison avec la version installée")
        return
    if old not in text:
        fail("comparaison de version figée introuvable dans helpers/a.smali")
    text = text.replace(old, UPDATE_VERSION_CALL, 1)
    marker = ".method b()V\n"
    if marker not in text:
        fail("point d'insertion de la méthode de version introuvable")
    text = text.replace(marker, UPDATE_VERSION_METHOD + marker, 1)
    path.write_text(text, encoding="utf-8")
    log("corrigé : l'updater compare désormais la version installée")


def force_stable_channel(decoded: pathlib.Path) -> None:
    """Étape 3b — Toute installation neuve démarre en canal Beta.

    Cause racine (mesurée sur appareil le 16/09) : le socle upstream est un
    build beta, flag gravé `b.a = true`, et MainApp.p() en déduit
    pref_update_channel = "1" au premier lancement. Or le canal Beta ne voit
    que des entrées ReleaseType: 1 — notre publication stable y est muette.
    Remettre le flag à false supprime l'impasse pour les nouveaux utilisateurs
    (les installations existantes gardent leur préférence, c'est voulu).
    """
    path = decoded / BETA_FLAG_PATH
    if not path.is_file():
        fail(f"fichier attendu absent : {BETA_FLAG_PATH}")
    text = path.read_text(encoding="utf-8")
    if BETA_FLAG_NEW in text:
        log("déjà appliqué : flag beta désactivé (canal stable par défaut)")
        return
    if BETA_FLAG_OLD not in text:
        fail(f"champ beta introuvable dans {BETA_FLAG_PATH} (attendu : {BETA_FLAG_OLD!r})")
    path.write_text(text.replace(BETA_FLAG_OLD, BETA_FLAG_NEW, 1), encoding="utf-8")
    log("corrigé : le flag beta gravé est désactivé (canal stable par défaut)")


def repoint_updater(decoded: pathlib.Path, apk_name: str) -> None:
    print("[3/5] Mise à jour automatique → dépôt Twouich")
    for rel in URL_FILES:
        path = decoded / rel
        if not path.is_file():
            fail(f"fichier attendu absent : {rel}")
        # Couvre github.com/<repo> ET raw.githubusercontent.com/<repo>
        replace_once(
            path,
            UPSTREAM,
            REPO,
            f"{path.name} : URLs de release",
        )

    patch_update_version_comparison(decoded)
    force_stable_channel(decoded)

    service = decoded / "smali_classes2/com/s0und/s0undtv/service/AutoUpdateService.smali"
    if service.is_file():
        replace_once(
            service,
            DEAD_UPDATE_URL,
            f"https://github.com/{REPO}/releases/latest/download/{apk_name}",
            "AutoUpdateService : endpoint cloudns mort",
        )


def check_brand_assets(decoded: pathlib.Path, here: pathlib.Path) -> int:
    """Vérifie que chaque asset émis par le générateur est bien posé dans l'APK,
    octet pour octet. Un APK dont l'écran de démarrage n'a pas été remplacé est le
    pire des cas : il s'installe, démarre, et affiche encore la marque d'avant."""
    res = here / BRAND_RES
    checked = 0
    for src in sorted(res.rglob("*")):
        if not src.is_file():
            continue
        dst = decoded / "res" / src.relative_to(res)
        if not dst.is_file() or dst.stat().st_size != src.stat().st_size:
            fail(f"asset de marque absent ou différent : {dst.relative_to(decoded)}")
        checked += 1
    if checked == 0:
        fail("aucun asset de marque dans l'arbre décodé")
    return checked


def scan_dead_red(decoded: pathlib.Path) -> list[str]:
    """Fichiers d'identité portant encore le rouge de S0und (#a30f2c).

    La palette (`values/colors.xml`, `values/public.xml`) est exclue : la famille
    `theme_red*` y est recolorée par ailleurs (elle porte l'accent par défaut),
    et les identifiants de ressources ne sont pas des chaînes affichées.
    """
    found: list[str] = []
    for root in (decoded / "res", decoded / "assets"):
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            rel = path.relative_to(decoded).as_posix()
            if rel.removeprefix("res/") in PALETTE_FILES:
                continue
            if DEAD_RED in path.read_text(encoding="utf-8", errors="ignore").lower():
                found.append(rel)
    return found


def set_manifest_version(decoded: pathlib.Path, code: int, name: str) -> None:
    """apktool 3 sort versionCode/versionName du manifest vers apktool.yml et ne
    les réinjecte pas au build : on les réécrit donc explicitement dans le manifest,
    sinon l'APK produit n'a plus aucune version (installation refusée)."""
    manifest = decoded / "AndroidManifest.xml"
    text = manifest.read_text(encoding="utf-8")
    attrs = f'android:versionCode="{code}" android:versionName="{name}"'
    if attrs in text:
        log("déjà appliqué (manifest)")
        return
    # manifeste déjà porteur d'attributs de version : on les remplace
    new = re.sub(
        r'(\s)android:versionCode="[^"]*"',
        rf'\g<1>android:versionCode="{code}"',
        text,
        count=1,
    )
    new = re.sub(
        r'(\s)android:versionName="[^"]*"',
        rf'\g<1>android:versionName="{name}"',
        new,
        count=1,
    )
    if "android:versionCode" not in new:
        m = re.search(r'(package="[^"]*")', new)
        if not m:
            fail("élément <manifest package=…> introuvable")
        new = new[: m.end()] + " " + attrs + new[m.end() :]
    manifest.write_text(new, encoding="utf-8")
    log(f"manifest : versionCode={code} versionName={name}")


def bump_version(decoded: pathlib.Path, code: int, name: str) -> None:
    print(f"[4/5] Version → {name} (versionCode {code})")
    set_manifest_version(decoded, code, name)
    yml = decoded / "apktool.yml"
    text = yml.read_text(encoding="utf-8")
    if f"versionCode: {code}" in text and f"versionName: {name}" in text:
        log("déjà appliqué")
        return
    new = re.sub(r"(?m)^(\s*versionCode: )[^\r\n]*", rf"\g<1>{code}", text, count=1)
    new = re.sub(r"(?m)^(\s*versionName: )[^\r\n]*", rf"\g<1>{name}", new, count=1)
    if new == text:
        fail("versionInfo introuvable dans apktool.yml")
    yml.write_text(new, encoding="utf-8")
    log(f"versionCode={code} versionName={name}")


def main() -> int:
    here = pathlib.Path(__file__).resolve().parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--decoded", required=True, type=pathlib.Path)
    parser.add_argument("--version-code", type=int, default=162)
    parser.add_argument("--version-name", default="v1.0.15")
    parser.add_argument("--apk-name", default=DEFAULT_APK_NAME)
    parser.add_argument("--release-date", default=None,
                        help="date affichée dans la page Nouveautés (AAA.MM.JJ). "
                             "Défaut : VERSION_RELEASE_DATE de build.sh — jamais "
                             "today(), pour que la date du livrable ne dépende "
                             "pas du jour de compilation (build reproductible).")
    args = parser.parse_args()

    decoded: pathlib.Path = args.decoded.resolve()
    if not (decoded / "apktool.yml").is_file():
        fail(f"arbre apktool invalide : {decoded}")

    if not args.release_date:
        fail("--release-date manquant : build.sh doit passer VERSION_RELEASE_DATE "
             "(constante figée par version — un livrable ne doit pas dépendre "
             "du jour où on le compile)")

    install_graft(decoded, here)
    brand = install_branding(decoded, here, args.version_name, args.release_date)
    neutralize_firebase(decoded)
    disable_remote_config_calls(decoded)
    disable_crashlytics_facade(decoded)
    patch_smartphone_features(decoded)
    install_playback_service(decoded)
    install_phone_assets(decoded, here)
    patch_smartphone_ux(decoded, here)
    patch_smartphone_headers(decoded)
    patch_smartphone_tap(decoded)
    patch_smartphone_navigation(decoded, here)
    patch_smartphone_pip(decoded)
    patch_smartphone_chat_toggle(decoded)
    install_selftest(decoded)
    repoint_updater(decoded, args.apk_name)
    bump_version(decoded, args.version_code, args.version_name)

    print("[5/5] Contrôles")
    checks = 0
    for rel_or_marker, needle in [
        (None, "AdBlockDataSource"),  # fabrique : chemin variable (voir find_factory)
        ("smali_classes2/com/twouich/adblock/AdBlockDataSource.smali", "PROXY_HOST"),
        ("smali_classes2/com/twouich/adblock/PlaylistSanitizer.smali", "stitched-ad"),
        ("smali_classes2/com/twouich/adblock/SelfTest.smali", "SELFTEST"),
        ("smali_classes2/com/twouich/adblock/SelfTest$Fake.smali", "Lz3/l;"),
        (SELFTEST_PATH, "SelfTest;->run()V"),
        ("smali_classes2/com/s0und/s0undtv/helpers/UpdateHelper.smali", f"raw.githubusercontent.com/{REPO}"),
        ("smali_classes2/com/s0und/s0undtv/helpers/a.smali", f"github.com/{REPO}/releases/download/"),
        ("smali_classes2/com/s0und/s0undtv/helpers/a.smali", "PackageManager;->getPackageInfo"),
        (BETA_FLAG_PATH, BETA_FLAG_NEW),
        ("res/values/strings.xml", APP_NAME_NEW),
        ("AndroidManifest.xml", APP_LABEL_NEW),
        ("res/drawable/s0undtv_logo_with_text_2.xml", "@drawable/twouich_splash"),
        ("res/values/colors.xml", f'<color name="ic_launcher_background">{brand["brand"]}</color>'),
        ("res/values/colors.xml", f'<color name="theme_red">{brand["brand"]}</color>'),
        ("res/values/arrays.xml", "<item>Twouich</item>"),
        ("assets/S0undTV_about.html", "Twouich"),
        ("assets/S0undTV_changelog.html", "Twouich"),
        ("assets/twouich_legal.html", "Mentions légales"),
        ("assets/twouich_privacy.html", "Politique de confidentialité"),
        ("assets/S0undTV_about.html", "twouich_legal.html"),
        ("smali/com/s0und/s0undtv/activities/PrivacyPolicyActivity.smali",
         "twouich_privacy.html"),
        ("smali_classes2/P6/e.smali", "return-void"),
        ("smali_classes2/P6/b.smali", "return-void"),
        ("smali_classes2/P6/l.smali", "return-void"),
        ("res/layout/activity_player.xml", "twouich_phone_chat_height"),
        ("res/layout/activity_player.xml", "SendMessageWindow"),
        ("res/layout/include_send_chat_message_window.xml", "ET_SendMessage"),
        ("res/layout-sw600dp/activity_player.xml", "ChatRecycleView"),
        ("res/layout/activity_main.xml", "twouich_phone_nav_search"),
        ("res/layout-sw600dp/activity_main.xml", "main_browse_fragment"),
        ("smali/com/s0und/s0undtv/activities/MainActivity.smali", "twouichPhoneSearch"),
        ("smali/com/s0und/s0undtv/activities/PlayerActivity.smali", "twouichPhoneStackedLayout"),
        ("smali_classes2/com/s0und/s0undtv/fragments/MainFragment.smali",
         "invoke-direct {p0}, Lcom/s0und/s0undtv/fragments/MainFragment;->twouichPhoneHeadersState()I"),
        ("res/values/dimens.xml", "twouich_phone_chat_height"),
        ("smali_classes2/com/twouich/adblock/TapClick.smali",
         ".method public static touch(Landroid/view/View;Landroid/view/MotionEvent;)Z"),
        # UX smartphone : barre basse avec icônes, bouton d'incrustation, et
        # l'activité lecteur déclarée compatible picture-in-picture.
        ("res/drawable/twouich_ic_home.xml", "<vector"),
        ("res/drawable/twouich_ic_search.xml", "<vector"),
        ("res/drawable/twouich_ic_settings.xml", "<vector"),
        ("res/drawable/twouich_ic_pip.xml", "<vector"),
        ("res/values/colors.xml", "twouich_phone_nav_inactive"),
        ("res/layout/activity_main.xml", "twouich_ic_home"),
        ("res/layout/activity_player.xml", "twouich_phone_pip"),
        ("AndroidManifest.xml", 'android:supportsPictureInPicture="true"'),
        ("AndroidManifest.xml", "smallestScreenSize"),
        ("smali/com/s0und/s0undtv/activities/PlayerActivity.smali", "twouichPhonePip"),
        ("smali/com/s0und/s0undtv/activities/PlayerActivity.smali", "twouichPhoneChatToggle"),
        ("smali/com/s0und/s0undtv/activities/PlayerActivity.smali", ".field private twouichChatHidden:Z"),
        ("smali/com/s0und/s0undtv/activities/PlayerActivity.smali",
         ".method private twouichChatCollapse()V"),
        ("smali/com/s0und/s0undtv/activities/PlayerActivity.smali",
         ":stacked_chat_shown"),
        ("smali/com/s0und/s0undtv/activities/PlayerActivity.smali",
         ".method private twouichChatRestore()V"),
        ("smali/com/s0und/s0undtv/activities/PlayerActivity.smali",
         ".field private twouichChatRestored:Z"),
        ("smali/com/s0und/s0undtv/activities/PlayerActivity.smali",
         "chat restaure masque"),
        ("smali/com/s0und/s0undtv/activities/PlayerActivity.smali",
         CHAT_RESTORE_CALL_LINE),
        ("smali/com/s0und/s0undtv/activities/PlayerActivity.smali",
         '"chat_hidden"'),
        ("smali/com/s0und/s0undtv/activities/PlayerActivity.smali",
         "SharedPreferences$Editor;->putBoolean"),
        ("smali/com/s0und/s0undtv/activities/PlayerActivity.smali",
         "if-eqz v1, :stacked_chat_shown"),
        ("smali/com/s0und/s0undtv/activities/PlayerActivity.smali", "onPictureInPictureModeChanged"),
        ("smali/com/s0und/s0undtv/activities/PlayerActivity.smali",
         ".field private twouichPipActive:Z"),
        ("smali/com/s0und/s0undtv/activities/PlayerActivity.smali",
         "if-eqz v11, :twouich_phone_layout_ok"),
        ("smali/com/s0und/s0undtv/activities/PlayerActivity.smali",
         PHONE_PIP_STATE_NEEDLE),
    ]:
        if rel_or_marker is None:
            path = find_factory(decoded)
        else:
            path = decoded / rel_or_marker
        if rel_or_marker == "AndroidManifest.xml" and needle == "com.google.firebase":
            if not path.is_file() or needle in path.read_text(encoding="utf-8"):
                fail(f"contrôle échoué : télémétrie Firebase encore déclarée dans {path.relative_to(decoded)}")
        elif not path.is_file() or needle not in path.read_text(encoding="utf-8"):
            fail(f"contrôle échoué : {needle!r} absent de {path.relative_to(decoded)}")
        checks += 1
    # Le bouton du chat est RETIRÉ depuis la v1.0.12 : le chat vit sous la
    # vidéo, donc replier ne changeait plus la taille de l'image. La preuve est
    # donc l'INVERSE — plus de bouton dans le layout téléphone — tandis que la
    # machinerie du repli reste dans le lecteur (contrôlée ci-dessus).
    phone_layout = decoded / "res/layout/activity_player.xml"
    phone_layout_text = phone_layout.read_text(encoding="utf-8")
    for needle in ('twouich_phone_chat"',
                   'android:onClick="twouichPhoneChatToggle"'):
        if needle in phone_layout_text:
            fail(f"contrôle échoué : le bouton du chat est encore dans le lecteur "
                 f"({needle})")
        checks += 1
    # Garde-fou : setVisibility(int) recevait un objet LayoutParams — erreur de
    # vérification Dalvik qui faisait planter le lecteur à l'ouverture.
    player_check = decoded / "smali/com/s0und/s0undtv/activities/PlayerActivity.smali"
    player_src = player_check.read_text(encoding="utf-8")
    for reg in ("v5", "v6"):
        if f"invoke-virtual {{{reg}, v0}}, Landroid/view/View;->setVisibility(I)V" in player_src:
            fail(f"contrôle échoué : setVisibility({reg}) reçoit un LayoutParams au lieu d'un int")
        if f"invoke-virtual {{{reg}, v9}}, Landroid/view/View;->setVisibility(I)V" not in player_src:
            fail(f"contrôle échoué : setVisibility({reg}) attendu avec un registre entier")
    checks += 2
    # Garde-fou : un override d'un callback public de Window.Callback doit rester
    # public. En « protected », le lieur ART rejette la classe entière
    # (IllegalAccessError « implementing interface method is not public ») :
    # PlayerActivity devient introuvable et l'ouverture d'un direct plante
    # l'application (reproduit sur BlueStacks/API 25 le 20/09).
    if ".method protected onWindowFocusChanged(Z)V" in player_src:
        fail("contrôle échoué : onWindowFocusChanged est protected — ART rejetterait PlayerActivity")
    if ".method public onWindowFocusChanged(Z)V" not in player_src:
        fail("contrôle échoué : onWindowFocusChanged public absent de PlayerActivity")
    checks += 2
    # L'état du chat est relu au DÉMARRAGE du lecteur : le point d'entrée est
    # onResume, pas le rappel de focus (jamais dispatché sur BlueStacks/API 33,
    # mesuré le 21/09). Le contrôle lit le CORPS de onResume, pas le fichier.
    resume_head = player_src.find(".method protected onResume()V")
    if resume_head < 0:
        fail("contrôle échoué : onResume absent de PlayerActivity — état du chat non relu")
    resume_body = player_src[resume_head:player_src.find(".end method", resume_head)]
    if CHAT_RESTORE_CALL_LINE not in resume_body:
        fail("contrôle échoué : onResume ne relit pas l'état du chat au démarrage")
    checks += 1
    # Polarité du garde de relecture : la faute qui a coûté une session (le
    # corps ne s'exécutait jamais, sans le moindre journal — 21/09).
    if PHONE_CHAT_RESTORE_GUARD_NEW not in player_src:
        fail("contrôle échoué : garde de la relecture du chat absent — l'état ne serait jamais relu")
    if PHONE_CHAT_RESTORE_GUARD_OLD in player_src:
        fail("contrôle échoué : garde de la relecture du chat à polarité inversée (if-eqz)")
    checks += 1
    # Contrat de la persistance : le fichier et la clé sont écrits par
    # twouichChatApply et relus par twouichChatRestore — deux littéraux
    # divergents donneraient un état qui ne survit à rien, sans la moindre
    # erreur à l'exécution. Les deux littéraux doivent donc être présents
    # au moins deux fois (une écriture, une lecture).
    for literal in ('"chat_hidden"', '"twouich"'):
        if player_src.count(literal) < 2:
            fail(f"contrôle échoué : contrat de la préférence du chat incomplet ({literal})")
    checks += 1
    # Garde-fou : la vidéo 16:9 est calculée depuis la largeur ; sans plafond,
    # le chat reçoit une hauteur négative sur un écran plus large que haut
    # (mesuré le 20/09 : chat à 0 px, disposition inutilisable en paysage).
    for marker in (":twouich_phone_video_fits", ":twouich_phone_room", PHONE_GEO_TAIL):
        if marker not in player_src:
            fail(f"contrôle échoué : géométrie du lecteur téléphone incomplète ({marker!r})")
        checks += 1
    # Les deux formes fautives (sans plafond, puis sans test de place) sont des
    # préfixes de la forme corrigée : les chercher dans une copie élaguée.
    pruned = player_src.replace(PHONE_GEO_TAIL, "")
    for faulty in (PHONE_GEO_OLD_TAIL, PHONE_GEO_CLAMPED_TAIL):
        if faulty in pruned:
            fail("contrôle échoué : une géométrie fautive du lecteur est revenue")
        checks += 1
    # Polarité des deux tests de place : c'est la faute qui a coûté le plus cher
    # à ce projet (§6 de memory.md), et elle se relit ici en une ligne.
    for expected, what in (
        ("    if-lt v10, v7, :twouich_phone_video_fits",
         "le plafond vidéo doit être sauté quand la vidéo tient"),
        ("    if-ge v7, v3, :twouich_phone_room",
         "l'empilement doit se faire quand le chat a un tiers de l'écran"),
    ):
        if expected not in player_src:
            fail(f"contrôle échoué : {what}")
        checks += 1
    # Un label en double fait échouer apktool tard, sur un message qui ne dit pas
    # quelle méthode est en cause : on le refuse ici, à la source.
    for label in (":twouich_phone_video_fits", ":twouich_phone_room"):
        if player_src.count(label) != 2:
            fail(f"contrôle échoué : label {label} attendu 1 fois "
                 f"(déclaration + saut), trouvé {player_src.count(label)}")
        checks += 1
    # Garde-fou : l'entrée/sortie d'incrustation doit avoir ses propres overrides
    # publics, et l'activité doit continuer d'appliquer sa disposition quand elle
    # est redimensionnée (rotation, incrustation) sans être recréée.
    for signature in (
        ".method public onPictureInPictureModeChanged(ZLandroid/content/res/Configuration;)V",
        ".method public onConfigurationChanged(Landroid/content/res/Configuration;)V",
        ".method public twouichPhonePip(Landroid/view/View;)V",
    ):
        if signature not in player_src:
            fail(f"contrôle échoué : {signature} absent de PlayerActivity")
        checks += 1
    for weak in (".method protected onPictureInPictureModeChanged",
                 ".method private onPictureInPictureModeChanged",
                 ".method protected onConfigurationChanged",
                 ".method private onConfigurationChanged"):
        if weak in player_src:
            fail(f"contrôle échoué : {weak} — ART rejetterait PlayerActivity")
        checks += 1
    # Garde-fou : pendant l'incrustation, la disposition téléphone ne doit PLUS
    # s'appliquer. Le rappel PiP masque chat et saisie ; une réapplication
    # tardive (perte de focus du passage en PiP, changement de configuration)
    # remet la barre « Envoyer un message » par-dessus la vidéo — défaut mesuré
    # le 20/09 sur le téléphone, dans la fenêtre d'incrustation elle-même.
    pip_field = ".field private twouichPipActive:Z"
    pip_read = ("iget-boolean v11, p0, Lcom/s0und/s0undtv/activities/"
                "PlayerActivity;->twouichPipActive:Z")
    pip_write = PHONE_PIP_STATE_NEEDLE
    if pip_field not in player_src:
        fail("contrôle échoué : champ d'état d'incrustation absent de PlayerActivity")
    if pip_read not in player_src or "if-eqz v11, :twouich_phone_layout_ok" not in player_src:
        fail("contrôle échoué : garde d'incrustation absent de twouichPhoneStackedLayout")
    if "if-nez v11, :twouich_phone_layout_ok" in player_src:
        fail("contrôle échoué : garde d'incrustation inversé (if-nez) — "
             "l'empilement s'appliquerait exactement pendant l'incrustation")
    if pip_write not in player_src:
        fail("contrôle échoué : l'état d'incrustation n'est pas écrit par le rappel")
    # Le garde de twouichPhoneView a été écrit à l'envers : il rendait null dès
    # que l'identifiant était trouvé, donc le rappel PiP sortait aussitôt.
    if f"    {PHONE_PIP_VIEW_OLD.strip()}" in player_src:
        fail("contrôle échoué : twouichPhoneView est inversé — le rappel PiP "
             "sortirait sans rien masquer")
    if PHONE_PIP_VIEW_NEW not in player_src:
        fail("contrôle échoué : garde d'identifiant absent de twouichPhoneView")
    checks += 5
    # Ordre : le garde précède la mise en place de l'empilement, et l'écriture de
    # l'état précède la restauration appelée à la sortie d'incrustation.
    stacked_at = player_src.find(".method private twouichPhoneStackedLayout()V")
    guard_at = player_src.find("if-eqz v11, :twouich_phone_layout_ok", stacked_at)
    exo_at = player_src.find('const-string v1, "ExoPlayer"', stacked_at)
    pip_at = player_src.find(".method public onPictureInPictureModeChanged")
    write_at = player_src.find(pip_write)
    restore_at = player_src.find(":restore_pip_layout", pip_at)
    if not (stacked_at != -1 and guard_at != -1 and exo_at != -1 and guard_at < exo_at):
        fail("contrôle échoué : le garde d'incrustation arrive après la mise en "
             "place de l'empilement")
    if not (pip_at != -1 and write_at != -1 and restore_at != -1 and pip_at < write_at < restore_at):
        fail("contrôle échoué : l'état d'incrustation est écrit trop tard — "
             "la sortie d'incrustation ne restaurerait pas l'empilement")
    checks += 2
    # Garde-fou : nos champs d'état sont des champs D'INSTANCE — tout accès
    # statique (sget-boolean/sput-boolean) compile puis lève une
    # IncompatibleClassChangeError au premier tap (crash mesuré sur
    # BlueStacks le 21/09 : twouichChatHidden lu par sget dans le toggle).
    for opcode in ("sget-boolean", "sput-boolean"):
        for field in ("twouichPipActive", "twouichChatHidden"):
            bad = re.compile(
                rf"{opcode}\s+\w+,\s*Lcom/s0und/s0undtv/activities/PlayerActivity;->{field}:Z")
            if bad.search(player_src):
                fail(f"contrôle échoué : {field} accédé en statique ({opcode}) — "
                     "c'est un champ d'instance, ART lèvera IncompatibleClassChangeError")
            checks += 1
    # Garde-fou : le tap → clic doit être branché AVANT la logique d'origine de
    # BaseGridView, sinon la grille consomme le premier appui et la carte reste
    # activable au seul second appui (le défaut constaté au doigt).
    grid_src = find_base_grid(decoded).read_text(encoding="utf-8")
    if TAP_HOOK_CALL not in grid_src or TAP_HOOK_LABEL not in grid_src:
        fail("contrôle échoué : tap → clic absent de BaseGridView.dispatchTouchEvent")
    if grid_src.index(TAP_HOOK_CALL) > grid_src.index("iget-object v0, p0, Landroidx/leanback/widget/e;->g1"):
        fail("contrôle échoué : tap → clic branché après la logique de la grille")
    checks += 2
    manifest_path = decoded / "AndroidManifest.xml"
    manifest_text = manifest_path.read_text(encoding="utf-8")
    if "android:screenOrientation=\"sensorLandscape\"" in manifest_text:
        fail("contrôle échoué : une activité reste forcée en sensorLandscape")
    if "android:screenOrientation=\"fullSensor\"" not in manifest_text:
        fail("contrôle échoué : aucune activité multi-orientation fullSensor")
    checks += 1
    manifest_features = manifest_path
    feature_lines = [line for line in manifest_features.read_text(encoding="utf-8").splitlines()
                     if "<uses-feature" in line]
    if not feature_lines or any('android:required="false"' not in line for line in feature_lines):
        fail("contrôle échoué : chaque uses-feature doit porter android:required=\"false\"")
    checks += len(feature_lines)
    assets = check_brand_assets(decoded, here)
    checks += assets
    logos = scan_dead_red(decoded)
    if logos:
        fail("le rouge de S0und subsiste sur : " + ", ".join(logos))
    checks += 1
    # ── Empreinte des greffes (cf. STAMP_SUFFIX) ──────────────────────────────
    # Écrite seulement après des contrôles verts : un arbre estampillé est un
    # arbre dont les greffes sont celles de ce patch.py.
    stamp_now = GREFFE_FINGERPRINT
    if not stamp_now:
        fail("empreinte des greffes absente : le lecteur n'a pas été greffé par ce patch")
    stamp_file = decoded.with_name(decoded.name + STAMP_SUFFIX)
    if stamp_file.is_file():
        stamp_seen = stamp_file.read_text(encoding="utf-8").strip()
        if stamp_seen and stamp_seen != stamp_now:
            fail("arbre décodé périmé : les greffes du lecteur ont changé depuis son "
                 "patchage, et un arbre réutilisé garde l'ancien texte "
                 "(désassembler à neuf : rm -rf " + str(decoded) + ")")
    stamp_file.write_text(stamp_now + "\n", encoding="utf-8")
    log(f"{checks} contrôles OK ({assets} assets de marque + 1 balayage du rouge)")
    print("\n✅ patch.py terminé")
    return 0


if __name__ == "__main__":
    sys.exit(main())
