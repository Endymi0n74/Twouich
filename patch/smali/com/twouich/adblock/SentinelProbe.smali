.class public final Lcom/twouich/adblock/SentinelProbe;
.super Ljava/lang/Object;
.source "SentinelProbe.java"


# Sonde de la sentinelle « marqueur pub inconnu » (PlaylistSanitizer.b()).
#
# Jouable via app_process sans rien installer :
#   CLASSPATH=/data/local/tmp/twouich-selftest.apk \
#     app_process /system/bin com.twouich.adblock.SentinelProbe
#
# Elle verifie, DANS le code compile, que la sentinelle :
#   1-2. leve le drapeau sur un pod SSAI au format RENOMME (classe differente
#        portant les memes attributs X-TV-TWITCH-AD-*) et sur une balise CUE
#        inconnue — les deux scenarios de changement de format cote Twitch ;
#   3.   reste muette sur le format reel servi le 18/09/2026 (pod SSAI complet) ;
#   4.   reste muette sur les DATERANGE utilitaires (session, stream-source) ;
#   5.   ne MODIFIE PAS le nettoyage (observation pure : le pod renomme reste
#        intact dans la sortie, le vrai pod reconnu est retire) ;
#   6.   reinitialise son etat a chaque playlist.
#
# Verdict : I/Twouich: SENTINEL 6/6 verifications
# Les lignes Log.w « marqueur pub inconnu : ... » produites par les cas 1-2
# sont ATTENDUES (c'est le signal teste) et sont levees pendant la sonde.
# Le nettoyage lui-meme n'est pas touche : la sentinelle n'observe pas.


# direct methods
.method private constructor <init>()V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method


# Journalise un echec (succes silencieux). Retourne 1 si la verification passe,
# 0 sinon — meme convention que SelfTest.check.
.method private static check(ZLjava/lang/String;)I
    .locals 3

    if-eqz p0, :ko

    const/4 v0, 0x1

    return v0

    :ko
    new-instance v0, Ljava/lang/StringBuilder;

    invoke-direct {v0}, Ljava/lang/StringBuilder;-><init>()V

    const-string v1, "SENTINEL KO : "

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v0, p1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    const-string v1, "Twouich"

    invoke-static {v1, v0}, Landroid/util/Log;->e(Ljava/lang/String;Ljava/lang/String;)I

    const/4 v0, 0x0

    return v0
.end method


.method private static equals(Ljava/lang/String;Ljava/lang/String;)Z
    .locals 1

    invoke-virtual {p0, p1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result v0

    return v0
.end method


.method private static contains(Ljava/lang/String;Ljava/lang/String;)Z
    .locals 1

    invoke-virtual {p0, p1}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z

    move-result v0

    return v0
.end method


# Lit le drapeau de la sentinelle.
.method private static suspicious()Z
    .locals 1

    sget-boolean v0, Lcom/twouich/adblock/PlaylistSanitizer;->suspicious:Z

    return v0
.end method


# Le drapeau est-il DOWN (faux) ?
.method private static silent()Z
    .locals 1

    sget-boolean v0, Lcom/twouich/adblock/PlaylistSanitizer;->suspicious:Z

    # if-nez : drapeau LEVE (v0 != 0) -> pas silencieux -> retourne 0.
    # (if-eqz etait ici une inversion : silent() retournait suspicious(),
    #  et les trois cas de silence echouaient sans que la sentinelle ne parle.)
    if-nez v0, :raised

    const/4 v0, 0x1

    return v0

    :raised
    const/4 v0, 0x0

    return v0
.end method


# ── point d'entree CLI ───────────────────────────────────────────────────
.method public static main([Ljava/lang/String;)V
    .locals 0

    invoke-static {}, Lcom/twouich/adblock/SentinelProbe;->run()V

    return-void
.end method


# ── point d'entree ───────────────────────────────────────────────────────
.method public static run()V
    .locals 9

    # v0 = verifications passees, v1 = verifications executees
    # v2 = playlist d'essai, v3 = sortie du nettoyeur, v4 = booleen,
    # v5 = libelle, v6/v7 = temporaires, v8 = verdict
    const/4 v0, 0x0

    const/4 v1, 0x0

    # pod SSAI au format RENOMME (classe differente, memes attributs de diffusion)
    const-string v2, "#EXTM3U\n#EXT-X-DATERANGE:ID=\"stitched-promo-1789717100\",CLASS=\"twitch-stitched-promo\",START-DATE=\"2026-09-18T07:38:20.212Z\",X-TV-TWITCH-AD-ROLL-TYPE=\"PREROLL\",X-TV-TWITCH-AD-POD-LENGTH=\"1\"\n#EXTINF:2.000,Amazon|2474283100494\nhttps://seg.example/ad-1.ts\n#EXTINF:2.000,\nhttps://seg.example/live-1.ts\n"

    # ── 1. pod SSAI renomme : drapeau leve ──
    invoke-static {v2}, Lcom/twouich/adblock/PlaylistSanitizer;->a(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v3

    invoke-static {}, Lcom/twouich/adblock/SentinelProbe;->suspicious()Z

    move-result v4

    const-string v5, "pod SSAI renomme detecte"

    invoke-static {v4, v5}, Lcom/twouich/adblock/SentinelProbe;->check(ZLjava/lang/String;)I

    move-result v6

    add-int/2addr v0, v6

    add-int/lit8 v1, v1, 0x1

    # v8 = sortie du cas 1 (pod renomme, intact) — relue au cas 5
    move-object v8, v3

    # ── 2. balise CUE inconnue : drapeau leve ──
    const-string v2, "#EXTM3U\n#EXT-X-CUE-PREPARE:30.000\n#EXTINF:2.000,\nhttps://seg.example/1.ts\n"

    invoke-static {v2}, Lcom/twouich/adblock/PlaylistSanitizer;->a(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v3

    invoke-static {}, Lcom/twouich/adblock/SentinelProbe;->suspicious()Z

    move-result v4

    const-string v5, "balise CUE inconnue detectee"

    invoke-static {v4, v5}, Lcom/twouich/adblock/SentinelProbe;->check(ZLjava/lang/String;)I

    move-result v6

    add-int/2addr v0, v6

    add-int/lit8 v1, v1, 0x1

    # ── 3. format reel du 18/09/2026 : silence ──
    # (pod SSAI tel que servi : DATERANGE stitched-ad + quartile + titres Amazon)
    const-string v2, "#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:0\n#EXT-X-START:TIME-OFFSET=0.000\n#EXT-X-DATERANGE:ID=\"stitched-ad-1789717100-30235000000\",CLASS=\"twitch-stitched-ad\",X-TV-TWITCH-AD-ROLL-TYPE=\"PREROLL\"\n#EXT-X-DATERANGE:ID=\"quartile-1789717100-0\",CLASS=\"twitch-ad-quartile\",X-TV-TWITCH-AD-QUARTILE=\"0\"\n#EXT-X-DISCONTINUITY\n#EXTINF:2.000,Amazon|2474283100494\nhttps://seg.example/ad-1.ts\n#EXT-X-DISCONTINUITY\n#EXT-X-TWITCH-LIVE-SEQUENCE:1206\n#EXTINF:2.000,\nhttps://seg.example/live-1.ts\n"

    invoke-static {v2}, Lcom/twouich/adblock/PlaylistSanitizer;->a(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v3

    invoke-static {}, Lcom/twouich/adblock/SentinelProbe;->silent()Z

    move-result v4

    const-string v5, "format reel 18/09 silencieux"

    invoke-static {v4, v5}, Lcom/twouich/adblock/SentinelProbe;->check(ZLjava/lang/String;)I

    move-result v6

    add-int/2addr v0, v6

    add-int/lit8 v1, v1, 0x1

    # v7 = sortie du cas 3 (pod reel, nettoye) — relue au cas 5
    move-object v7, v3

    # ── 4. DATERANGE utilitaires : silence (dont une porteuse d'attribut Amazon) ──
    const-string v2, "#EXTM3U\n#EXT-X-DATERANGE:ID=\"playlist-session-1789717104\",CLASS=\"twitch-session\",X-TV-TWITCH-SESSIONID=\"0\"\n#EXT-X-DATERANGE:ID=\"source-1789717100\",CLASS=\"twitch-stream-source\",X-TV-TWITCH-STREAM-SOURCE=\"Amazon|2474283100494\"\n#EXT-X-DATERANGE:ID=\"trigger-1789717100\",CLASS=\"twitch-trigger\",X-TV-TWITCH-TRIGGER-URL=\"https://euw33.playlist.ttvnw.net/trigger/x\"\n#EXTINF:2.000,\nhttps://seg.example/1.ts\n"

    invoke-static {v2}, Lcom/twouich/adblock/PlaylistSanitizer;->a(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v3

    invoke-static {}, Lcom/twouich/adblock/SentinelProbe;->silent()Z

    move-result v4

    const-string v5, "DATERANGE utilitaires silencieuses"

    invoke-static {v4, v5}, Lcom/twouich/adblock/SentinelProbe;->check(ZLjava/lang/String;)I

    move-result v6

    add-int/2addr v0, v6

    add-int/lit8 v1, v1, 0x1

    # ── 5. observation pure : le nettoyage n'a pas change ──
    # le pod renomme (cas 1, v8) reste ENTIER dans la sortie...
    const-string v6, "CLASS=\"twitch-stitched-promo\""

    invoke-static {v8, v6}, Lcom/twouich/adblock/SentinelProbe;->contains(Ljava/lang/String;Ljava/lang/String;)Z

    move-result v4

    # ... et le vrai pod reconnu (cas 3, v7) a bien ete retire
    const-string v6, "twitch-stitched-ad"

    invoke-static {v7, v6}, Lcom/twouich/adblock/SentinelProbe;->contains(Ljava/lang/String;Ljava/lang/String;)Z

    move-result v6

    # v6 = 1 si le marqueur reconnu est ABSENT (retire), 0 sinon
    if-eqz v6, :keep_ok

    const/4 v6, 0x0

    goto :keep_merge

    :keep_ok
    const/4 v6, 0x1

    :keep_merge
    and-int v4, v4, v6

    const-string v5, "sentinelle sans effet sur le nettoyage"

    invoke-static {v4, v5}, Lcom/twouich/adblock/SentinelProbe;->check(ZLjava/lang/String;)I

    move-result v6

    add-int/2addr v0, v6

    add-int/lit8 v1, v1, 0x1

    # ── 6. etat reinitialise a chaque playlist ──
    const-string v2, "#EXTM3U\n#EXT-X-CUE-PREPARE:30.000\n#EXTINF:2.000,\nhttps://seg.example/1.ts\n"

    invoke-static {v2}, Lcom/twouich/adblock/PlaylistSanitizer;->a(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v3

    const-string v2, "#EXTM3U\n#EXTINF:2.000,\nhttps://seg.example/1.ts\n"

    invoke-static {v2}, Lcom/twouich/adblock/PlaylistSanitizer;->a(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v3

    invoke-static {}, Lcom/twouich/adblock/SentinelProbe;->silent()Z

    move-result v4

    const-string v5, "drapeau reinitialise a chaque playlist"

    invoke-static {v4, v5}, Lcom/twouich/adblock/SentinelProbe;->check(ZLjava/lang/String;)I

    move-result v6

    add-int/2addr v0, v6

    add-int/lit8 v1, v1, 0x1

    # ── verdict, une ligne (Log.i) ──
    new-instance v8, Ljava/lang/StringBuilder;

    invoke-direct {v8}, Ljava/lang/StringBuilder;-><init>()V

    const-string v2, "SENTINEL "

    invoke-virtual {v8, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v8, v0}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    const-string v2, "/"

    invoke-virtual {v8, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v8, v1}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    const-string v2, " verifications, sentinelle marqueur inconnu"

    invoke-virtual {v8, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v8}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v8

    const-string v2, "Twouich"

    invoke-static {v2, v8}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    return-void
.end method
