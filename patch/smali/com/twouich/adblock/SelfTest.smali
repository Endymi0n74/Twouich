.class public final Lcom/twouich/adblock/SelfTest;
.super Ljava/lang/Object;
.source "SelfTest.java"


# Self-test embarque.
#
# Pourquoi il existe : sur nos deux premiers passages sur appareil, la lecture
# etait cassee par quatre erreurs que NI le miroir Python (test_sanitizer.py) NI
# le controle statique (test_smali_branches.py) ne pouvaient voir : elles ne se
# manifestent qu'a l'execution, sur la semantique Dalvik reelle (array-length
# sur null, branchements contre zero, boucle de remplissage vide). En rejouant
# des playlists publicitaires aux formats Twitch reels DANS le code compile, ce
# self-test ferme ce trou sans dependre d'une vraie coupure publicitaire.
#
# Il tourne une fois par demarrage (injecte dans MainApp.onCreate) et reste
# discret : une seule ligne en cas de succes, le detail des echecs sinon.
#
# Les jeux d'essai sont les memes que ceux de patch/tests/test_sanitizer.py :
# toute divergence entre les deux se voit immediatement.
#
# Le bloc 8 rejoue en plus la TABLE DE VERITE DE L'UPDATER (UpdateHelper.b(),
# v1.0.0 : comparaison a la version installee) via pick(IIII)I — le miroir
# Dalvik de la table de patch/tests/test_update_check.py : « annonce en
# retard » -> silence, sur les deux canaux, dans le code compile. Depuis le
# 22/09/2026 il porte aussi les DEUX preconditions du canal beta (l'entree
# stable ET l'entree beta doivent exister), qui manquaient aux deux miroirs.


# static fields
# Interrupteur : passer a false pour ne plus executer le self-test au demarrage.
.field private static final ENABLED:Z = true

.field private static final TAG:Ljava/lang/String; = "Twouich"


# direct methods
.method private constructor <init>()V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method


# ── helpers de verification ─────────────────────────────────────────────

# Journalise un echec (succes silencieux : les journaux restent parcimonieux).
# Retourne 1 si la verification passe, 0 sinon.
.method private static check(ZLjava/lang/String;)I
    .locals 3

    if-eqz p0, :ko

    const/4 v0, 0x1

    return v0

    :ko
    new-instance v0, Ljava/lang/StringBuilder;

    invoke-direct {v0}, Ljava/lang/StringBuilder;-><init>()V

    const-string v1, "SELFTEST KO : "

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v0, p1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    const-string v1, "Twouich"

    invoke-static {v1, v0}, Landroid/util/Log;->e(Ljava/lang/String;Ljava/lang/String;)I

    const/4 v0, 0x0

    return v0
.end method


.method private static contains(Ljava/lang/String;Ljava/lang/String;)Z
    .locals 1

    invoke-virtual {p0, p1}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z

    move-result v0

    return v0
.end method


# Absence d'un marqueur : evite d'ecrire des negations partout dans run().
.method private static absent(Ljava/lang/String;Ljava/lang/String;)Z
    .locals 1

    invoke-virtual {p0, p1}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z

    move-result v0

    # if-eqz : "contains a renvoye faux" -> le marqueur est absent (vrai).
    if-eqz v0, :not_contained

    const/4 v0, 0x0

    return v0

    :not_contained
    const/4 v0, 0x1

    return v0
.end method


.method private static equals(Ljava/lang/String;Ljava/lang/String;)Z
    .locals 1

    invoke-virtual {p0, p1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result v0

    return v0
.end method


.method private static eq(II)Z
    .locals 1

    const/4 v0, 0x0

    if-ne p0, p1, :done

    const/4 v0, 0x1

    :done
    return v0
.end method


.method private static logKo(Ljava/lang/Throwable;)V
    .locals 3

    new-instance v0, Ljava/lang/StringBuilder;

    invoke-direct {v0}, Ljava/lang/StringBuilder;-><init>()V

    const-string v1, "SELFTEST KO : exception dans le flux filtre : "

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {p0}, Ljava/lang/Throwable;->toString()Ljava/lang/String;

    move-result-object v1

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    const-string v1, "Twouich"

    invoke-static {v1, v0}, Landroid/util/Log;->e(Ljava/lang/String;Ljava/lang/String;)I

    return-void
.end method


# Verdict : une ligne. Log.e quand quelque chose casse (plus visible).
# Miroir Dalvik de la logique de UpdateHelper.b()V (verifiee par
# patch/tests/test_update_check.py). pick(canal, version installee, entree
# stable, entree beta) -> 0 silence, 1 dialogue(stable), 2 dialogue(beta).
# -1 = entree absente OU version installee illisible (echec de i()I :
# fail-loud, tout semble plus recent). La stricte superiorite porte le silence
# (publiee <= installee -> JAMAIS de dialogue) et la preference de l'entree
# beta (c gagne ssi strictement plus recente que tout).
#
# Les arguments sont les ENTREES DU FICHIER, pas les canaux : b = ReleaseType 0
# (stable), c = ReleaseType 1 (beta) — c'est UpdateHelper.e() qui les remplit.
# Le canal choisit l'ORDRE dans lequel on les regarde, pas laquelle est lue :
# sur le canal beta, les DEUX doivent exister, sinon silence (mesure du
# 22/09/2026 sur le bytecode livre : une annonce stable seule ne reveille pas
# une installation restee en Beta).
.method private static pick(IIII)I
    .locals 2

    # v0 = verdict ; v1 = registre de travail
    const/4 v0, 0x0

    # canal stable (0) ?
    if-eqz p0, :stable

    # canal beta (1) ; tout le reste est un canal non gere -> silence
    const/4 v1, 0x1

    if-ne p0, v1, :done

    const/4 v1, -0x1

    # Les DEUX entrees doivent exister (a.smali : l'entree stable est chargee
    # d'abord, son absence rend la main ; puis l'entree beta, meme chose).
    # Sans l'une des deux : silence, meme si l'annonce est plus recente —
    # c'est le cas d'une publication stable seule face a un canal beta.
    if-eq p2, v1, :done

    if-eq p3, v1, :done

    # cond_2 : l'entree stable (b) gagne ssi b > installee (absente ou en
    # retard : silence) — structure conforme a a.smali (if-le saute vers
    # cond_2, jamais l'inverse)
    if-le p3, p1, :cond_2

    if-le p3, p2, :cond_2

    const/4 v0, 0x2

    goto :done

    :cond_2
    if-le p2, p1, :done

    const/4 v0, 0x1

    goto :done

    :stable
    # b absente -> silence ; sinon dialogue ssi b strictement superieure
    const/4 v1, -0x1

    if-eq p2, v1, :done

    if-le p2, p1, :done

    const/4 v0, 0x1

    :done
    return v0
.end method


.method private static report(III)V
    .locals 3

    new-instance v0, Ljava/lang/StringBuilder;

    invoke-direct {v0}, Ljava/lang/StringBuilder;-><init>()V

    const-string v1, "SELFTEST ECHEC "

    if-ne p0, p1, :prefix_ok

    const-string v1, "SELFTEST "

    :prefix_ok
    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-static {p0}, Ljava/lang/String;->valueOf(I)Ljava/lang/String;

    move-result-object v1

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    const-string v1, "/"

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-static {p1}, Ljava/lang/String;->valueOf(I)Ljava/lang/String;

    move-result-object v1

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    const-string v1, " verifications, flux filtre : "

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-static {p2}, Ljava/lang/String;->valueOf(I)Ljava/lang/String;

    move-result-object v1

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    const-string v1, " octets"

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    const-string v1, "Twouich"

    # if-ne : "passees != total" -> echec, donc Log.e (plus visible dans les
    # filtres de capture). Le succes reste discret : une seule ligne en Log.i.
    if-ne p0, p1, :log_ko

    invoke-static {v1, v0}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    return-void

    :log_ko
    invoke-static {v1, v0}, Landroid/util/Log;->e(Ljava/lang/String;Ljava/lang/String;)I

    return-void
.end method


# ── chemin de lecture complet ────────────────────────────────────────────
# Fait passer la playlist SSAI publicitaire par AdBlockDataSource (le vrai
# decorateur de source du lecteur) alimente par une source factice, et relit le
# flux par tranches de 64 octets -- beaucoup plus petites que la playlist :
# chaque read() depend donc de la boucle de remplissage et du service par
# tranches, les deux endroits ou la lecture cassait.
# Retourne le texte servi (chaine vide si une exception est survenue).
.method private static e2e()Ljava/lang/String;
    .locals 12

    const-string v0, ""

    :try_start
    # v0 = octets du fixture (puis texte servi), v1 = source factice,
    # v2 = source decoree, v3 = DataSpec, v4 = Uri, v5..v8 = temporaires,
    # v9 = tampon de sortie, v10 = bloc de lecture, v11 = octets lus
    const-string v0, "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:4\n#EXT-X-MEDIA-SEQUENCE:1200\n#EXTINF:2.000,\nhttps://video-weaver.example/hls/seg1200.ts\n#EXTINF:2.000,\nhttps://video-weaver.example/hls/seg1201.ts\n#EXT-X-DISCONTINUITY\n#EXT-X-DATERANGE:ID=\"stitched-ad-1757920000-1234\",CLASS=\"twitch-stitched-ad\",START-DATE=\"2026-09-15T09:00:00.000Z\",DURATION=6.000\n#EXTINF:2.000,\nhttps://video-weaver.example/hls/ad1.ts\n#EXTINF:2.000,\nhttps://video-weaver.example/hls/ad2.ts\n#EXTINF:2.000,\nhttps://video-weaver.example/hls/ad3.ts\n#EXT-X-DISCONTINUITY\n#EXT-X-TWITCH-LIVE-SEQUENCE:1206\n#EXTINF:2.000,\nhttps://video-weaver.example/hls/seg1206.ts\n"

    const-string v1, "UTF-8"

    invoke-virtual {v0, v1}, Ljava/lang/String;->getBytes(Ljava/lang/String;)[B

    move-result-object v0

    new-instance v1, Lcom/twouich/adblock/SelfTest$Fake;

    invoke-direct {v1, v0}, Lcom/twouich/adblock/SelfTest$Fake;-><init>([B)V

    new-instance v2, Lcom/twouich/adblock/AdBlockDataSource;

    invoke-direct {v2, v1}, Lcom/twouich/adblock/AdBlockDataSource;-><init>(Lz3/l;)V

    # DataSpec(uri, 0, -1) : le chemin finit par .m3u8 -> mode playlist.
    # Appel en /range : une liste est limitee a 5 registres, or deux longs
    # (chacun ecrit dans deux registres consecutifs) en demandent six.
    const-string v0, "https://video-weaver.example/hls/index-dyn.m3u8"

    invoke-static {v0}, Landroid/net/Uri;->parse(Ljava/lang/String;)Landroid/net/Uri;

    move-result-object v4

    new-instance v3, Lz3/p;

    const-wide/16 v5, 0x0

    const-wide/16 v7, -0x1

    invoke-direct/range {v3 .. v8}, Lz3/p;-><init>(Landroid/net/Uri;JJ)V

    invoke-virtual {v2, v3}, Lcom/twouich/adblock/AdBlockDataSource;->c(Lz3/p;)J

    move-result-wide v5

    new-instance v9, Ljava/io/ByteArrayOutputStream;

    invoke-direct {v9}, Ljava/io/ByteArrayOutputStream;-><init>()V

    const/16 v5, 0x40

    new-array v10, v5, [B

    :read
    const/4 v5, 0x0

    array-length v6, v10

    invoke-virtual {v2, v10, v5, v6}, Lcom/twouich/adblock/AdBlockDataSource;->read([BII)I

    move-result v11

    # Dalvik : if-ltz = "v11 < 0" -> fin du flux simule.
    if-ltz v11, :done

    const/4 v5, 0x0

    invoke-virtual {v9, v10, v5, v11}, Ljava/io/ByteArrayOutputStream;->write([BII)V

    goto :read

    :done
    const-string v5, "UTF-8"

    invoke-virtual {v9, v5}, Ljava/io/ByteArrayOutputStream;->toString(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v0
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :ko

    return-object v0

    :ko
    move-exception v0

    invoke-static {v0}, Lcom/twouich/adblock/SelfTest;->logKo(Ljava/lang/Throwable;)V

    const-string v0, ""

    return-object v0
.end method


# virtual methods
# Entree autonome, sans passer par l'app : utiles pour verifier un dex fraichement
# construit avant de l'installer.
#   adb shell CLASSPATH=/data/local/tmp/twouich.apk app_process /system/bin \\
#       com.twouich.adblock.SelfTest
.method public static main([Ljava/lang/String;)V
    .locals 0

    invoke-static {}, Lcom/twouich/adblock/SelfTest;->run()V

    return-void
.end method


# ── point d'entree ───────────────────────────────────────────────────────
.method public static run()V
    .locals 14

    # v0 = verifications passees, v1 = verifications executees
    sget-boolean v2, Lcom/twouich/adblock/SelfTest;->ENABLED:Z

    if-nez v2, :body

    return-void

    :body
    const/4 v0, 0x0

    const/4 v1, 0x0

    # v2 = SSAI, v3 = CUE, v4 = Amazon, v5 = daterange non pub
    const-string v2, "#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:4\n#EXT-X-MEDIA-SEQUENCE:1200\n#EXTINF:2.000,\nhttps://video-weaver.example/hls/seg1200.ts\n#EXTINF:2.000,\nhttps://video-weaver.example/hls/seg1201.ts\n#EXT-X-DISCONTINUITY\n#EXT-X-DATERANGE:ID=\"stitched-ad-1757920000-1234\",CLASS=\"twitch-stitched-ad\",START-DATE=\"2026-09-15T09:00:00.000Z\",DURATION=6.000\n#EXTINF:2.000,\nhttps://video-weaver.example/hls/ad1.ts\n#EXTINF:2.000,\nhttps://video-weaver.example/hls/ad2.ts\n#EXTINF:2.000,\nhttps://video-weaver.example/hls/ad3.ts\n#EXT-X-DISCONTINUITY\n#EXT-X-TWITCH-LIVE-SEQUENCE:1206\n#EXTINF:2.000,\nhttps://video-weaver.example/hls/seg1206.ts\n"

    const-string v3, "#EXTM3U\n#EXTINF:2.000,\nhttps://video-weaver.example/hls/seg1.ts\n#EXT-X-CUE-OUT:30.000\n#EXTINF:6.000,\nhttps://video-weaver.example/hls/client-ad.ts\n#EXT-X-CUE-IN\n#EXTINF:2.000,\nhttps://video-weaver.example/hls/seg2.ts\n"

    const-string v4, "#EXTM3U\n#EXTINF:2.000,\nhttps://video-weaver.example/hls/seg1.ts\n#EXTINF:10.000,Amazon\nhttps://video-weaver.example/hls/ssai.ts\n#EXTINF:2.000,\nhttps://video-weaver.example/hls/seg2.ts\n"

    const-string v5, "#EXTM3U\n#EXT-X-DATERANGE:ID=\"playlist-creation-1757920000\",CLASS=\"twitch-playlist\",START-DATE=\"2026-09-15T09:00:00.000Z\"\n#EXTINF:2.000,\nhttps://video-weaver.example/hls/seg1.ts\n"

    # ── 1. un corps qui n'est pas une playlist repart intact ──
    const-string v6, "bonjour"

    invoke-static {v6}, Lcom/twouich/adblock/PlaylistSanitizer;->a(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v6

    const-string v12, "bonjour"

    invoke-static {v6, v12}, Lcom/twouich/adblock/SelfTest;->equals(Ljava/lang/String;Ljava/lang/String;)Z

    move-result v13

    const-string v12, "corps non-playlist rendu tel quel"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # ── 2. playlist live avec plage publicitaire SSAI ──
    invoke-static {v2}, Lcom/twouich/adblock/PlaylistSanitizer;->a(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v6

    const-string v12, "stitched-ad"

    invoke-static {v6, v12}, Lcom/twouich/adblock/SelfTest;->absent(Ljava/lang/String;Ljava/lang/String;)Z

    move-result v13

    const-string v12, "SSAI : plage publicitaire retiree"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    const-string v12, "ad1.ts"

    invoke-static {v6, v12}, Lcom/twouich/adblock/SelfTest;->absent(Ljava/lang/String;Ljava/lang/String;)Z

    move-result v13

    const-string v12, "SSAI : segments publicitaires retires"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    const-string v12, "seg1200.ts"

    invoke-static {v6, v12}, Lcom/twouich/adblock/SelfTest;->contains(Ljava/lang/String;Ljava/lang/String;)Z

    move-result v13

    const-string v12, "SSAI : contenu avant la pub conserve"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    const-string v12, "#EXT-X-DISCONTINUITY"

    invoke-static {v6, v12}, Lcom/twouich/adblock/SelfTest;->contains(Ljava/lang/String;Ljava/lang/String;)Z

    move-result v13

    const-string v12, "SSAI : discontinuite conservee"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    const-string v12, "#EXT-X-TWITCH-LIVE-SEQUENCE:1206"

    invoke-static {v6, v12}, Lcom/twouich/adblock/SelfTest;->contains(Ljava/lang/String;Ljava/lang/String;)Z

    move-result v13

    const-string v12, "SSAI : sequence live conservee"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    const-string v12, "seg1206.ts"

    invoke-static {v6, v12}, Lcom/twouich/adblock/SelfTest;->contains(Ljava/lang/String;Ljava/lang/String;)Z

    move-result v13

    const-string v12, "SSAI : contenu repris apres la pub"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    sget v13, Lcom/twouich/adblock/PlaylistSanitizer;->lastCut:I

    const/16 v12, 0x3

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->eq(II)Z

    move-result v13

    const-string v12, "SSAI : compteur de segments pub = 3"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # ── 3. bloc CUE-OUT / CUE-IN ──
    invoke-static {v3}, Lcom/twouich/adblock/PlaylistSanitizer;->a(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v7

    const-string v12, "client-ad.ts"

    invoke-static {v7, v12}, Lcom/twouich/adblock/SelfTest;->absent(Ljava/lang/String;Ljava/lang/String;)Z

    move-result v13

    const-string v12, "CUE : segment publicitaire retire"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    const-string v12, "#EXT-X-CUE-OUT"

    invoke-static {v7, v12}, Lcom/twouich/adblock/SelfTest;->absent(Ljava/lang/String;Ljava/lang/String;)Z

    move-result v13

    const-string v12, "CUE : balises CUE-OUT/CUE-IN retirees"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    sget v13, Lcom/twouich/adblock/PlaylistSanitizer;->lastCut:I

    const/16 v12, 0x1

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->eq(II)Z

    move-result v13

    const-string v12, "CUE : compteur de segments pub = 1"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # ── 4. segment marque par son titre Amazon : segment ET URI ──
    invoke-static {v4}, Lcom/twouich/adblock/PlaylistSanitizer;->a(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v8

    const-string v12, "ssai.ts"

    invoke-static {v8, v12}, Lcom/twouich/adblock/SelfTest;->absent(Ljava/lang/String;Ljava/lang/String;)Z

    move-result v13

    const-string v12, "Amazon : segment pub et son URI retires"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    sget v13, Lcom/twouich/adblock/PlaylistSanitizer;->lastCut:I

    const/16 v12, 0x1

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->eq(II)Z

    move-result v13

    const-string v12, "Amazon : compteur de segments pub = 1"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # ── 5. plage non publicitaire : intouchee ──
    invoke-static {v5}, Lcom/twouich/adblock/PlaylistSanitizer;->a(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v9

    const-string v12, "playlist-creation-1757920000"

    invoke-static {v9, v12}, Lcom/twouich/adblock/SelfTest;->contains(Ljava/lang/String;Ljava/lang/String;)Z

    move-result v13

    const-string v12, "daterange non publicitaire conservee"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # ── 6. idempotence : nettoyer deux fois ne change rien de plus ──
    invoke-static {v6}, Lcom/twouich/adblock/PlaylistSanitizer;->a(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v10

    invoke-static {v10, v6}, Lcom/twouich/adblock/SelfTest;->equals(Ljava/lang/String;Ljava/lang/String;)Z

    move-result v13

    const-string v12, "nettoyage idempotent"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # ── 7. chemin de lecture complet (source -> filtre -> lecteur) ──
    invoke-static {}, Lcom/twouich/adblock/SelfTest;->e2e()Ljava/lang/String;

    move-result-object v11

    const-string v12, "#EXTM3U"

    invoke-static {v11, v12}, Lcom/twouich/adblock/SelfTest;->contains(Ljava/lang/String;Ljava/lang/String;)Z

    move-result v13

    const-string v12, "flux : playlist servie complete"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    const-string v12, "seg1206.ts"

    invoke-static {v11, v12}, Lcom/twouich/adblock/SelfTest;->contains(Ljava/lang/String;Ljava/lang/String;)Z

    move-result v13

    const-string v12, "flux : contenu repris apres la pub servie"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    const-string v12, "stitched-ad"

    invoke-static {v11, v12}, Lcom/twouich/adblock/SelfTest;->absent(Ljava/lang/String;Ljava/lang/String;)Z

    move-result v13

    const-string v12, "flux : aucune pub dans ce que lit le lecteur"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # ── 8. table de vérité de l'updater (miroir Dalvik de test_update_check.py) ──
    # pick(canal, installée, entrée stable, entrée beta) -> 0 silence,
    # 1 dialogue(stable), 2 dialogue(beta) ; -1 = absente / version illisible :
    # c'est l'entrée `ReleaseType` qui compte, pas le canal. Les cas 8.11 à 8.13
    # portent les deux préconditions du canal beta (corrigées le 22/09/2026).

    # 8.1 stable + annonce en retard -> silence
    const/4 v9, 0x0

    const/16 v10, 0x99

    const/16 v12, 0x98

    const/4 v13, -0x1

    invoke-static {v9, v10, v12, v13}, Lcom/twouich/adblock/SelfTest;->pick(IIII)I

    move-result v12

    const/4 v13, 0x0

    invoke-static {v12, v13}, Lcom/twouich/adblock/SelfTest;->eq(II)Z

    move-result v13

    const-string v12, "updater : annonce en retard -> silence (canal stable)"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # 8.2 beta + annonce en retard -> silence
    const/4 v9, 0x1

    const/16 v10, 0x99

    const/16 v12, 0x98

    const/4 v13, -0x1

    invoke-static {v9, v10, v12, v13}, Lcom/twouich/adblock/SelfTest;->pick(IIII)I

    move-result v12

    const/4 v13, 0x0

    invoke-static {v12, v13}, Lcom/twouich/adblock/SelfTest;->eq(II)Z

    move-result v13

    const-string v12, "updater : annonce en retard -> silence (canal beta)"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # 8.3 stable + annonce egale -> silence (pas de boucle d'update)
    const/4 v9, 0x0

    const/16 v10, 0x99

    const/16 v12, 0x99

    const/4 v13, -0x1

    invoke-static {v9, v10, v12, v13}, Lcom/twouich/adblock/SelfTest;->pick(IIII)I

    move-result v12

    const/4 v13, 0x0

    invoke-static {v12, v13}, Lcom/twouich/adblock/SelfTest;->eq(II)Z

    move-result v13

    const-string v12, "updater : annonce egale -> silence (pas de boucle)"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # 8.4 stable + annonce plus recente -> dialogue
    const/4 v9, 0x0

    const/16 v10, 0x98

    const/16 v12, 0x99

    const/4 v13, -0x1

    invoke-static {v9, v10, v12, v13}, Lcom/twouich/adblock/SelfTest;->pick(IIII)I

    move-result v12

    const/4 v13, 0x1

    invoke-static {v12, v13}, Lcom/twouich/adblock/SelfTest;->eq(II)Z

    move-result v13

    const-string v12, "updater : annonce plus recente -> dialogue"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # 8.5 beta + entree stable plus recente -> dialogue sur l'autre canal
    const/4 v9, 0x1

    const/16 v10, 0x98

    const/16 v12, 0x98

    const/16 v13, 0x99

    invoke-static {v9, v10, v12, v13}, Lcom/twouich/adblock/SelfTest;->pick(IIII)I

    move-result v12

    const/4 v13, 0x2

    invoke-static {v12, v13}, Lcom/twouich/adblock/SelfTest;->eq(II)Z

    move-result v13

    const-string v12, "updater : l'autre canal plus recent gagne"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # 8.6 beta + les deux entrees en retard -> silence
    const/4 v9, 0x1

    const/16 v10, 0x99

    const/16 v12, 0x98

    const/16 v13, 0x97

    invoke-static {v9, v10, v12, v13}, Lcom/twouich/adblock/SelfTest;->pick(IIII)I

    move-result v12

    const/4 v13, 0x0

    invoke-static {v12, v13}, Lcom/twouich/adblock/SelfTest;->eq(II)Z

    move-result v13

    const-string v12, "updater : aucune entree plus recente -> silence (beta)"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # 8.7 beta + entree du canal plus recente que l'autre -> dialogue(b)
    const/4 v9, 0x1

    const/16 v10, 0x96

    const/16 v12, 0x99

    const/16 v13, 0x98

    invoke-static {v9, v10, v12, v13}, Lcom/twouich/adblock/SelfTest;->pick(IIII)I

    move-result v12

    const/4 v13, 0x1

    invoke-static {v12, v13}, Lcom/twouich/adblock/SelfTest;->eq(II)Z

    move-result v13

    const-string v12, "updater : l'entree du canal gagne si plus recente que l'autre"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # 8.8 canal inconnu -> silence meme si l'annonce est plus recente
    const/4 v9, 0x2

    const/16 v10, 0x98

    const/16 v12, 0x99

    const/4 v13, -0x1

    invoke-static {v9, v10, v12, v13}, Lcom/twouich/adblock/SelfTest;->pick(IIII)I

    move-result v12

    const/4 v13, 0x0

    invoke-static {v12, v13}, Lcom/twouich/adblock/SelfTest;->eq(II)Z

    move-result v13

    const-string v12, "updater : canal inconnu -> silence"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # 8.9 aucune entree candidate -> silence
    const/4 v9, 0x0

    const/16 v10, 0x96

    const/4 v12, -0x1

    const/4 v13, -0x1

    invoke-static {v9, v10, v12, v13}, Lcom/twouich/adblock/SelfTest;->pick(IIII)I

    move-result v12

    const/4 v13, 0x0

    invoke-static {v12, v13}, Lcom/twouich/adblock/SelfTest;->eq(II)Z

    move-result v13

    const-string v12, "updater : aucune entree candidate -> silence"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # 8.10 version installee illisible (-1) -> dialogue (fail-loud)
    const/4 v9, 0x0

    const/4 v10, -0x1

    const/16 v12, 0x99

    const/4 v13, -0x1

    invoke-static {v9, v10, v12, v13}, Lcom/twouich/adblock/SelfTest;->pick(IIII)I

    move-result v12

    const/4 v13, 0x1

    invoke-static {v12, v13}, Lcom/twouich/adblock/SelfTest;->eq(II)Z

    move-result v13

    const-string v12, "updater : version illisible -> dialogue (fail-loud)"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # 8.11 beta + aucune entree beta (stable seule, plus recente) -> silence.
    # C'est notre update.json reel : une entree stable, pas d'entree beta.
    const/4 v9, 0x1

    const/16 v10, 0x98

    const/16 v12, 0x99

    const/4 v13, -0x1

    invoke-static {v9, v10, v12, v13}, Lcom/twouich/adblock/SelfTest;->pick(IIII)I

    move-result v12

    const/4 v13, 0x0

    invoke-static {v12, v13}, Lcom/twouich/adblock/SelfTest;->eq(II)Z

    move-result v13

    const-string v12, "updater : aucune entree beta -> silence (canal beta)"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # 8.12 beta + aucune entree stable (beta seule, plus recente) -> silence
    const/4 v9, 0x1

    const/16 v10, 0x98

    const/4 v12, -0x1

    const/16 v13, 0x99

    invoke-static {v9, v10, v12, v13}, Lcom/twouich/adblock/SelfTest;->pick(IIII)I

    move-result v12

    const/4 v13, 0x0

    invoke-static {v12, v13}, Lcom/twouich/adblock/SelfTest;->eq(II)Z

    move-result v13

    const-string v12, "updater : aucune entree stable -> silence (canal beta)"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # 8.13 stable + entree beta plus recente -> silence (c est ignoree en stable)
    const/4 v9, 0x0

    const/16 v10, 0x98

    const/4 v12, -0x1

    const/16 v13, 0x99

    invoke-static {v9, v10, v12, v13}, Lcom/twouich/adblock/SelfTest;->pick(IIII)I

    move-result v12

    const/4 v13, 0x0

    invoke-static {v12, v13}, Lcom/twouich/adblock/SelfTest;->eq(II)Z

    move-result v13

    const-string v12, "updater : canal stable ignore l'entree beta"

    invoke-static {v13, v12}, Lcom/twouich/adblock/SelfTest;->check(ZLjava/lang/String;)I

    move-result v12

    add-int/2addr v0, v12

    add-int/lit8 v1, v1, 0x1

    # ── verdict ──
    const-string v12, "UTF-8"

    invoke-virtual {v11, v12}, Ljava/lang/String;->getBytes(Ljava/lang/String;)[B

    move-result-object v12

    array-length v12, v12

    invoke-static {v0, v1, v12}, Lcom/twouich/adblock/SelfTest;->report(III)V

    return-void
.end method
