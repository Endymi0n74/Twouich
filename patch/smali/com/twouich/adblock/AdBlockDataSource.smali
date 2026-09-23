.class public final Lcom/twouich/adblock/AdBlockDataSource;
.super Ljava/lang/Object;
.implements Lz3/l;
.source "AdBlockDataSource.java"


# static fields
# Proxy anti-pub optionnel : hôte (sans schéma) d'un proxy qui relaie les URL usher telles quelles.
# Laisser vide pour désactiver. Le stripping local (PlaylistSanitizer) reste actif dans tous les cas.
.field private static final PROXY_HOST:Ljava/lang/String; = ""

# VaFT : dernier channel vu sur usher (pour fallback backup stream)
.field public static lastChannel:Ljava/lang/String; = ""


# instance fields
.field private a:Lz3/l;

.field private b:Ljava/io/ByteArrayOutputStream;

.field private c:[B

.field private d:I

.field private e:Z


# direct methods
.method public constructor <init>(Lz3/l;)V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    iput-object p1, p0, Lcom/twouich/adblock/AdBlockDataSource;->a:Lz3/l;

    return-void
.end method

# Trace lisible sur logcat : tailles avant/apres et nombre de segments pub retires.
.method private static a(II)V
    .locals 6

    new-instance v0, Ljava/lang/StringBuilder;

    invoke-direct {v0}, Ljava/lang/StringBuilder;-><init>()V

    const-string v1, "playlist nettoyee "

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-static {p0}, Ljava/lang/String;->valueOf(I)Ljava/lang/String;

    move-result-object v1

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    const-string v1, " -> "

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-static {p1}, Ljava/lang/String;->valueOf(I)Ljava/lang/String;

    move-result-object v1

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    const-string v1, " octets, segments pub retires : "

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    sget v1, Lcom/twouich/adblock/PlaylistSanitizer;->lastCut:I

    invoke-static {v1}, Ljava/lang/String;->valueOf(I)Ljava/lang/String;

    move-result-object v1

    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    const-string v1, "Twouich"

    invoke-static {v1, v0}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    return-void
.end method

.method private static b(Lz3/p;)Lz3/p;
    .locals 4

    sget-object v0, Lcom/twouich/adblock/AdBlockDataSource;->PROXY_HOST:Ljava/lang/String;

    iget-object v1, p0, Lz3/p;->a:Landroid/net/Uri;

    invoke-virtual {v1}, Landroid/net/Uri;->buildUpon()Landroid/net/Uri$Builder;

    move-result-object v2

    invoke-virtual {v2, v0}, Landroid/net/Uri$Builder;->authority(Ljava/lang/String;)Landroid/net/Uri$Builder;

    move-result-object v2

    invoke-virtual {v2}, Landroid/net/Uri$Builder;->build()Landroid/net/Uri;

    move-result-object v0

    invoke-virtual {p0}, Lz3/p;->a()Lz3/p$b;

    move-result-object v1

    invoke-virtual {v1, v0}, Lz3/p$b;->i(Landroid/net/Uri;)Lz3/p$b;

    move-result-object v0

    invoke-virtual {v0}, Lz3/p$b;->a()Lz3/p;

    move-result-object v0

    return-object v0
.end method


# virtual methods
.method public c(Lz3/p;)J
    .locals 6

    iget-object v0, p1, Lz3/p;->a:Landroid/net/Uri;

    invoke-virtual {v0}, Landroid/net/Uri;->getPath()Ljava/lang/String;

    move-result-object v1

    const/4 v2, 0x0

    if-nez v1, :path_ok

    goto :not_playlist

    :path_ok
    const-string v3, ".m3u8"

    invoke-virtual {v1, v3}, Ljava/lang/String;->endsWith(Ljava/lang/String;)Z

    move-result v3

    if-eqz v3, :not_playlist

    const/4 v2, 0x1

    :not_playlist
    iput-boolean v2, p0, Lcom/twouich/adblock/AdBlockDataSource;->e:Z

    # VaFT : capture du channel si url usher channel/hls
    :try_capture_start
    invoke-virtual {v0}, Landroid/net/Uri;->toString()Ljava/lang/String;
    move-result-object v3
    const-string v4, "usher.ttvnw.net"
    invoke-virtual {v3, v4}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v4
    if-eqz v4, :no_capture
    const-string v4, "channel/hls/"
    invoke-virtual {v3, v4}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v4
    if-eqz v4, :no_capture
    const-string v4, "channel/hls/"
    invoke-virtual {v3, v4}, Ljava/lang/String;->indexOf(Ljava/lang/String;)I
    move-result v4
    add-int/lit8 v4, v4, 0xc
    const-string v5, ".m3u8"
    invoke-virtual {v3, v5}, Ljava/lang/String;->indexOf(Ljava/lang/String;)I
    move-result v5
    if-le v5, v4, :no_capture
    invoke-virtual {v3, v4, v5}, Ljava/lang/String;->substring(II)Ljava/lang/String;
    move-result-object v3
    sput-object v3, Lcom/twouich/adblock/AdBlockDataSource;->lastChannel:Ljava/lang/String;
    :no_capture
    :try_capture_end
    .catch Ljava/lang/Exception; {:try_capture_start .. :try_capture_end} :capture_catch
    goto :capture_done
    :capture_catch
    move-exception v3
    :capture_done

    if-eqz v2, :open_direct

    new-instance v3, Ljava/io/ByteArrayOutputStream;

    invoke-direct {v3}, Ljava/io/ByteArrayOutputStream;-><init>()V

    iput-object v3, p0, Lcom/twouich/adblock/AdBlockDataSource;->b:Ljava/io/ByteArrayOutputStream;

    const/4 v3, 0x0

    iput-object v3, p0, Lcom/twouich/adblock/AdBlockDataSource;->c:[B

    iput v3, p0, Lcom/twouich/adblock/AdBlockDataSource;->d:I

    :open_direct
    sget-object v3, Lcom/twouich/adblock/AdBlockDataSource;->PROXY_HOST:Ljava/lang/String;

    invoke-virtual {v3}, Ljava/lang/String;->length()I

    move-result v3

    if-lez v3, :try_direct

    invoke-virtual {v0}, Landroid/net/Uri;->getHost()Ljava/lang/String;

    move-result-object v3

    const-string v4, "usher.ttvnw.net"

    invoke-virtual {v4, v3}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result v3

    if-eqz v3, :try_direct
    :try_start
    invoke-static {p1}, Lcom/twouich/adblock/AdBlockDataSource;->b(Lz3/p;)Lz3/p;

    move-result-object v3

    iget-object v4, p0, Lcom/twouich/adblock/AdBlockDataSource;->a:Lz3/l;

    invoke-interface {v4, v3}, Lz3/l;->c(Lz3/p;)J

    move-result-wide v4

    return-wide v4
    :try_end
    .catch Ljava/lang/Exception; {:try_start .. :try_end} :catch_proxy

    :catch_proxy
    move-exception v3

    const-string v4, "Twouich"

    const-string v5, "proxy indisponible : repli sur la requete directe"

    invoke-static {v4, v5}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I

    :try_direct
    iget-object v3, p0, Lcom/twouich/adblock/AdBlockDataSource;->a:Lz3/l;

    invoke-interface {v3, p1}, Lz3/l;->c(Lz3/p;)J

    move-result-wide v3

    return-wide v3
.end method

.method public close()V
    .locals 2

    const/4 v0, 0x0

    iput-object v0, p0, Lcom/twouich/adblock/AdBlockDataSource;->b:Ljava/io/ByteArrayOutputStream;

    iput-object v0, p0, Lcom/twouich/adblock/AdBlockDataSource;->c:[B

    iget-object v1, p0, Lcom/twouich/adblock/AdBlockDataSource;->a:Lz3/l;

    invoke-interface {v1}, Lz3/l;->close()V

    return-void
.end method

.method public e(Lz3/O;)V
    .locals 1

    iget-object v0, p0, Lcom/twouich/adblock/AdBlockDataSource;->a:Lz3/l;

    invoke-interface {v0, p1}, Lz3/l;->e(Lz3/O;)V

    return-void
.end method

.method public j()Ljava/util/Map;
    .locals 1

    iget-object v0, p0, Lcom/twouich/adblock/AdBlockDataSource;->a:Lz3/l;

    invoke-interface {v0}, Lz3/l;->j()Ljava/util/Map;

    move-result-object v0

    return-object v0
.end method

.method public n()Landroid/net/Uri;
    .locals 1

    iget-object v0, p0, Lcom/twouich/adblock/AdBlockDataSource;->a:Lz3/l;

    invoke-interface {v0}, Lz3/l;->n()Landroid/net/Uri;

    move-result-object v0

    return-object v0
.end method

.method public read([BII)I
    .locals 7

    iget-boolean v0, p0, Lcom/twouich/adblock/AdBlockDataSource;->e:Z

    if-eqz v0, :passthrough

    iget-object v0, p0, Lcom/twouich/adblock/AdBlockDataSource;->c:[B

    # if-eqz : "c == null" -> il faut remplir le cache une seule fois.
    # (if-nez ici envoyait le premier appel directement sur array-length(null) = NPE)
    if-eqz v0, :fill

    :serve
    iget v1, p0, Lcom/twouich/adblock/AdBlockDataSource;->d:I

    array-length v2, v0

    sub-int v3, v2, v1

    # Dalvik : if-lez = "v3 <= 0" (if-gtz signifierait "v3 > 0", soit l'inverse).
    if-lez v3, :eof

    move v4, p3

    if-le v4, v3, :copy

    move v4, v3

    :copy
    const/4 v5, 0x0

    invoke-static {v0, v1, p1, p2, v4}, Ljava/lang/System;->arraycopy(Ljava/lang/Object;ILjava/lang/Object;II)V

    add-int/2addr v1, v4

    iput v1, p0, Lcom/twouich/adblock/AdBlockDataSource;->d:I

    return v4

    :eof
    const/4 v0, -0x1

    return v0

    :fill
    const/16 v1, 0x2000

    new-array v1, v1, [B

    iget-object v2, p0, Lcom/twouich/adblock/AdBlockDataSource;->b:Ljava/io/ByteArrayOutputStream;

    :drain
    iget-object v3, p0, Lcom/twouich/adblock/AdBlockDataSource;->a:Lz3/l;

    const/4 v4, 0x0

    array-length v5, v1

    invoke-interface {v3, v1, v4, v5}, Lz3/l;->read([BII)I

    move-result v3

    # Dalvik : if-ltz = "v3 < 0" -> fin du flux. (if-gez teste ">= 0" : la boucle
    # s'arretait des la premiere lecture, avant meme d'ecrire le moindre octet.)
    if-ltz v3, :drained

    invoke-virtual {v2, v1, v4, v3}, Ljava/io/ByteArrayOutputStream;->write([BII)V

    goto :drain

    :drained
    invoke-virtual {v2}, Ljava/io/ByteArrayOutputStream;->size()I

    move-result v5

    const-string v3, "UTF-8"

    invoke-virtual {v2, v3}, Ljava/io/ByteArrayOutputStream;->toString(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v3

    invoke-static {v3}, Lcom/twouich/adblock/PlaylistSanitizer;->a(Ljava/lang/String;)Ljava/lang/String;

    move-result-object v3

    # VaFT fallback (TwVodNoAdsJCed processM3U8) - désactivé par défaut : 0 régression
    # Quand ENABLED=false, VaftFallback.a() retourne p0 tel quel (no-op, try/catch de sécurité)
    :try_vaft_start
    invoke-static {v3}, Lcom/twouich/adblock/VaftFallback;->a(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v3
    :try_vaft_end
    .catch Ljava/lang/Exception; {:try_vaft_start .. :try_vaft_end} :vaft_fallback_catch
    goto :vaft_done
    :vaft_fallback_catch
    move-exception v6
    # on garde v3 tel quel (déjà nettoyé), pas de log bruyant hors debug
    :vaft_done

    const-string v4, "UTF-8"

    invoke-virtual {v3, v4}, Ljava/lang/String;->getBytes(Ljava/lang/String;)[B

    move-result-object v3

    iput-object v3, p0, Lcom/twouich/adblock/AdBlockDataSource;->c:[B

    array-length v4, v3

    invoke-static {v5, v4}, Lcom/twouich/adblock/AdBlockDataSource;->a(II)V

    const/4 v3, 0x0

    iput-object v3, p0, Lcom/twouich/adblock/AdBlockDataSource;->b:Ljava/io/ByteArrayOutputStream;

    iput v3, p0, Lcom/twouich/adblock/AdBlockDataSource;->d:I

    iget-object v0, p0, Lcom/twouich/adblock/AdBlockDataSource;->c:[B

    goto :serve

    :passthrough
    iget-object v0, p0, Lcom/twouich/adblock/AdBlockDataSource;->a:Lz3/l;

    invoke-interface {v0, p1, p2, p3}, Lz3/l;->read([BII)I

    move-result v0

    return v0
.end method
