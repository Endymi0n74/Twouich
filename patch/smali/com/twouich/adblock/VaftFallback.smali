.class public final Lcom/twouich/adblock/VaftFallback;
.super Ljava/lang/Object;
.source "VaftFallback.java"


# Flux propre de secours (methode TwVodNoAdsJCed / VaFT).
#
# Twitch insere la pub cote serveur : pendant un pod, la playlist de la session
# du lecteur ne contient QUE la pub (flux de substitution, MEDIA-SEQUENCE:0).
# La retirer laisse donc le lecteur sans segment : image figee + roue pendant
# toute la duree du pod (60 s et plus). C'est ce blocage que ce greffon supprime.
#
# Mesure du 23/10/2026 (meme instant, meme chaine) : un jeton `playerType:site`
# sert une playlist `stitched-ad` (3 segments Amazon), un jeton `playerType:embed`
# sert le contenu (`src="live"`, aucun marqueur). On sert donc le flux embed
# pendant le pod : le contenu continue au lieu de geler.
#
# Securite : toute erreur reseau, tout 404, toute playlist de secours qui
# contient encore une pub -> on rend la playlist d'origine, que
# PlaylistSanitizer nettoie comme avant. Le comportement d'avant reste le
# filet, jamais l'inverse.

.field public static ENABLED:Z = true

# Cache de l'URL de variante propre : une chaine, une URL, 20 s.
# Evite trois requetes HTTP toutes les deux secondes pendant un pod.
.field private static cachedChannel:Ljava/lang/String;

.field private static cachedVariant:Ljava/lang/String;

# Echeance du cache. En cas d'echec, sert aussi de pause (30 s) : pas de
# nouvelle tentative a chaque rafraichissement de playlist.
.field private static cachedUntil:J


# direct methods
.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method


# Point d'entree, appele par AdBlockDataSource.read() sur la playlist BRUTE,
# AVANT PlaylistSanitizer : c'est la seule façon de voir les marqueurs pub.
# Rend la playlist d'origine si aucune pub n'est detectee, si le secours echoue,
# ou si le flux de secours contient lui-meme une pub.
.method public static a(Ljava/lang/String;)Ljava/lang/String;
    .locals 4

    # if-eqz = "p0 == null". Ecrit if-nez jusqu'au 23/10/2026 : toute playlist
    # non nulle sortait ici, donc a() n'a jamais servi le flux de secours.
    if-eqz p0, :ret_raw

    # secours desactive -> comportement d'origine
    sget-boolean v0, Lcom/twouich/adblock/VaftFallback;->ENABLED:Z
    if-eqz v0, :ret_raw

    # VOD : une playlist de VOD peut nommer un segment « Amazon » ; le flux
    # embed est un direct, il ne faut surtout pas le lui substituer.
    const-string v0, "#EXT-X-ENDLIST"
    invoke-virtual {p0, v0}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v0
    if-nez v0, :ret_raw

    # pas de marqueur pub -> rien a faire (cas normal, toutes les 2 s)
    invoke-static {p0}, Lcom/twouich/adblock/VaftFallback;->c(Ljava/lang/String;)Z
    move-result v0
    if-eqz v0, :ret_raw

    # trace de passage : sans elle, un retour brut ne dit pas OU il a eu lieu
    const-string v0, "Twouich"
    const-string v1, "vaft a : marqueur pub vu"
    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    # chaine courante, capturee par AdBlockDataSource.c() sur l'URL usher
    # if-eqz = "v0 == null" : sans chaine on ne peut rien demander.
    # (Ecrit if-nez jusqu'au 23/10/2026 : toute chaine connue renvoyait la
    # playlist BRUTE, donc le secours ne s'executait jamais.)
    sget-object v0, Lcom/twouich/adblock/AdBlockDataSource;->lastChannel:Ljava/lang/String;
    if-eqz v0, :ret_raw
    invoke-virtual {v0}, Ljava/lang/String;->length()I
    move-result v1
    if-eqz v1, :ret_raw

    # v0 garde lastChannel (d() le lit) : la trace passe par v2/v3
    const-string v2, "Twouich"
    const-string v3, "vaft a : chaine connue, appel d()"
    invoke-static {v2, v3}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    # URL de variante propre (reseau, cachee 20 s)
    invoke-static {v0}, Lcom/twouich/adblock/VaftFallback;->d(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v1
    # echec de resolution de variante -> playlist d'origine
    if-eqz v1, :ret_raw

    # playlist fraiche de cette variante
    invoke-static {v1}, Lcom/twouich/adblock/VaftFallback;->e(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v1
    if-eqz v1, :ret_raw

    # le secours ne doit servir que s'il est PROPRE : une playlist de secours
    # qui porte encore une pub est rejetee (c'est l'inversion qui rendait
    # l'ancien VaFT inoperant : il n'acceptait que les flux... publicitaires).
    invoke-static {v1}, Lcom/twouich/adblock/VaftFallback;->c(Ljava/lang/String;)Z
    move-result v2
    # c() rend vrai quand la playlist PORTE une pub : on ne sert que si faux.
    if-eqz v2, :use_clean

    goto :ret_raw

    :use_clean
    const-string v0, "Twouich"
    new-instance v2, Ljava/lang/StringBuilder;
    invoke-direct {v2}, Ljava/lang/StringBuilder;-><init>()V
    const-string v3, "vaft backup : flux propre servi ("
    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v1}, Ljava/lang/String;->length()I
    move-result v3
    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;
    const-string v3, " octets)"
    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v2}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v2
    invoke-static {v0, v2}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    return-object v1

    :ret_raw
    return-object p0
.end method


# Cette playlist contient-elle un marqueur publicitaire ?
# Couvre les trois familles observees : plage SSAI (stitched-ad / quartile
# en ligne), bloc client-side CUE-OUT, et segment titre « Amazon ».
.method private static c(Ljava/lang/String;)Z
    .locals 1

    const-string v0, "stitched-ad"
    invoke-virtual {p0, v0}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v0
    if-nez v0, :yes

    const-string v0, "X-TV-TWITCH-AD-QUARTILE"
    invoke-virtual {p0, v0}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v0
    if-nez v0, :yes

    const-string v0, "#EXT-X-CUE-OUT"
    invoke-virtual {p0, v0}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v0
    # if-eqz = "pas de CUE-OUT" -> on teste le marqueur Amazon.
    # Ecrit if-nez jusqu'au 23/10/2026 : une playlist SANS CUE-OUT tombait
    # sur :yes, donc toute playlist propre etait declaree publicitaire.
    if-eqz v0, :maybe_amazon

    goto :yes

    :maybe_amazon
    const-string v0, "Amazon"
    invoke-virtual {p0, v0}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v0
    # pas de marqueur Amazon -> pas de pub
    if-eqz v0, :no

    :yes
    const/4 v0, 0x1
    return v0

    :no
    const/4 v0, 0x0
    return v0
.end method


# URL de la premiere variante du flux embed pour cette chaine.
# Cache 20 s (une entree) ; un echec pose une pause de 30 s et rend null.
# Peut lever IOException : l'appelant (AdBlockDataSource.read) attrape
# Exception et repart sur la playlist d'origine.
.method private static d(Ljava/lang/String;)Ljava/lang/String;
    .locals 11

    # -- cache --
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J
    move-result-wide v0

    sget-wide v2, Lcom/twouich/adblock/VaftFallback;->cachedUntil:J

    # now < cachedUntil -> cache encore valide (cachedUntil vaut 0 au depart,
    # donc le premier appel part toujours en fetch).
    cmp-long v4, v0, v2
    if-ltz v4, :cache_valid
    goto :fetch

    :cache_valid
    sget-object v4, Lcom/twouich/adblock/VaftFallback;->cachedVariant:Ljava/lang/String;
    # null = echec recent : on respecte la pause de 30 s
    # (ecrit if-nez jusqu'au 23/10/2026 : une URL en cache partait en backoff,
    # donc le secours ne marchait qu'au tout premier appel)
    if-eqz v4, :backoff

    sget-object v5, Lcom/twouich/adblock/VaftFallback;->cachedChannel:Ljava/lang/String;
    invoke-virtual {p0, v5}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v5
    if-eqz v5, :fetch

    return-object v4

    :backoff
    const/4 v0, 0x0
    return-object v0

    :fetch
    const-string v4, "Twouich"
    const-string v5, "vaft : fetch"
    invoke-static {v4, v5}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    # -- jeton GQL embed --
    new-instance v4, Ljava/lang/StringBuilder;
    invoke-direct {v4}, Ljava/lang/StringBuilder;-><init>()V
    const-string v5, "{\"operationName\":\"PlaybackAccessToken\",\"variables\":{\"isLive\":true,\"login\":\""
    invoke-virtual {v4, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v4, p0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v5, "\",\"isVod\":false,\"vodID\":\"\",\"playerType\":\"embed\",\"platform\":\"web\"},\"extensions\":{\"persistedQuery\":{\"version\":1,\"sha256Hash\":\"ed230aa1e33e07eebb8928504583da78a5173989fadfb1ac94be06a04f3cdbe9\"}}}"
    invoke-virtual {v4, v5}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v4}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v5

    new-instance v4, Ljava/net/URL;
    const-string v6, "https://gql.twitch.tv/gql"
    invoke-direct {v4, v6}, Ljava/net/URL;-><init>(Ljava/lang/String;)V
    invoke-virtual {v4}, Ljava/net/URL;->openConnection()Ljava/net/URLConnection;
    move-result-object v4
    check-cast v4, Ljava/net/HttpURLConnection;

    const-string v6, "POST"
    invoke-virtual {v4, v6}, Ljava/net/HttpURLConnection;->setRequestMethod(Ljava/lang/String;)V
    const-string v6, "Client-ID"
    const-string v7, "kimne78kx3ncx6brgo4mv6wki5h1ko"
    invoke-virtual {v4, v6, v7}, Ljava/net/HttpURLConnection;->setRequestProperty(Ljava/lang/String;Ljava/lang/String;)V
    const-string v6, "Content-Type"
    const-string v7, "application/json"
    invoke-virtual {v4, v6, v7}, Ljava/net/HttpURLConnection;->setRequestProperty(Ljava/lang/String;Ljava/lang/String;)V
    const-string v6, "User-Agent"
    const-string v7, "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    invoke-virtual {v4, v6, v7}, Ljava/net/HttpURLConnection;->setRequestProperty(Ljava/lang/String;Ljava/lang/String;)V
    const/4 v6, 0x1
    invoke-virtual {v4, v6}, Ljava/net/HttpURLConnection;->setDoOutput(Z)V
    # 1500 ms : trois requetes au pire, on ne veut pas immobiliser le loader
    const/16 v6, 0x5dc
    invoke-virtual {v4, v6}, Ljava/net/HttpURLConnection;->setConnectTimeout(I)V
    invoke-virtual {v4, v6}, Ljava/net/HttpURLConnection;->setReadTimeout(I)V

    invoke-virtual {v4}, Ljava/net/HttpURLConnection;->getOutputStream()Ljava/io/OutputStream;
    move-result-object v6
    const-string v7, "UTF-8"
    invoke-virtual {v5, v7}, Ljava/lang/String;->getBytes(Ljava/lang/String;)[B
    move-result-object v5
    invoke-virtual {v6, v5}, Ljava/io/OutputStream;->write([B)V
    invoke-virtual {v6}, Ljava/io/OutputStream;->close()V

    invoke-virtual {v4}, Ljava/net/HttpURLConnection;->getResponseCode()I
    move-result v5
    # trace de diagnostic : un seul evenement par tentative de secours
    const-string v6, "Twouich"
    new-instance v7, Ljava/lang/StringBuilder;
    invoke-direct {v7}, Ljava/lang/StringBuilder;-><init>()V
    const-string v8, "vaft : gql "
    invoke-virtual {v7, v8}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v7, v5}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;
    invoke-virtual {v7}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v7
    invoke-static {v6, v7}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    const/16 v6, 0xc8
    if-eq v5, v6, :gql_ok
    invoke-virtual {v4}, Ljava/net/HttpURLConnection;->disconnect()V
    goto :fail

    :gql_ok
    invoke-virtual {v4}, Ljava/net/HttpURLConnection;->getInputStream()Ljava/io/InputStream;
    move-result-object v5
    invoke-static {v5}, Lcom/twouich/adblock/VaftFallback;->f(Ljava/io/InputStream;)Ljava/lang/String;
    move-result-object v5
    invoke-virtual {v4}, Ljava/net/HttpURLConnection;->disconnect()V

    # -- jeton : parsing JSON.
    # Le champ "value" est une CHAINE JSON echappee (ses guillemets internes
    # sont des \" dans la reponse). Chercher le prochain guillemet coupait donc
    # la valeur au premier \" — usher repondait 400 et le secours rendait null,
    # mesure sur l'appareil le 23/10/2026. JSONObject desechappe correctement.
    new-instance v6, Lorg/json/JSONObject;
    invoke-direct {v6, v5}, Lorg/json/JSONObject;-><init>(Ljava/lang/String;)V
    const-string v7, "data"
    invoke-virtual {v6, v7}, Lorg/json/JSONObject;->getJSONObject(Ljava/lang/String;)Lorg/json/JSONObject;
    move-result-object v6
    const-string v7, "streamPlaybackAccessToken"
    invoke-virtual {v6, v7}, Lorg/json/JSONObject;->getJSONObject(Ljava/lang/String;)Lorg/json/JSONObject;
    move-result-object v6
    const-string v7, "signature"
    invoke-virtual {v6, v7}, Lorg/json/JSONObject;->getString(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v8
    const-string v7, "value"
    invoke-virtual {v6, v7}, Lorg/json/JSONObject;->getString(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v9

    # trace de diagnostic (longueurs seulement, jamais le jeton)
    const-string v6, "Twouich"
    new-instance v7, Ljava/lang/StringBuilder;
    invoke-direct {v7}, Ljava/lang/StringBuilder;-><init>()V
    const-string v10, "vaft : jeton sig="
    invoke-virtual {v7, v10}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v8}, Ljava/lang/String;->length()I
    move-result v10
    invoke-virtual {v7, v10}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;
    const-string v10, " val="
    invoke-virtual {v7, v10}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v9}, Ljava/lang/String;->length()I
    move-result v10
    invoke-virtual {v7, v10}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;
    invoke-virtual {v7}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v7
    invoke-static {v6, v7}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    # -- URL usher v2 --
    new-instance v6, Ljava/lang/StringBuilder;
    invoke-direct {v6}, Ljava/lang/StringBuilder;-><init>()V
    # /api/channel/hls/ est le chemin de reference (radar_ads.py, streamlink) ;
    # /api/v2/ repondait aussi le 23/10/2026, mais les 404 observes venaient
    # de chaines hors ligne, pas du chemin.
    const-string v7, "https://usher.ttvnw.net/api/channel/hls/"
    invoke-virtual {v6, v7}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v6, p0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v7, ".m3u8?sig="
    invoke-virtual {v6, v7}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v7, "UTF-8"
    invoke-static {v8, v7}, Ljava/net/URLEncoder;->encode(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v8
    invoke-virtual {v6, v8}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v7, "&token="
    invoke-virtual {v6, v7}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v7, "UTF-8"
    invoke-static {v9, v7}, Ljava/net/URLEncoder;->encode(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v9
    invoke-virtual {v6, v9}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v7, "&allow_source=true&fast_bread=true"
    invoke-virtual {v6, v7}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v6}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v3

    # -- playlist maitre -> premiere variante --
    invoke-static {v3}, Lcom/twouich/adblock/VaftFallback;->e(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v4
    if-eqz v4, :fail

    # trace de diagnostic : taille du master, tete et position de la premiere URL
    const-string v5, "https://"
    invoke-virtual {v4, v5}, Ljava/lang/String;->indexOf(Ljava/lang/String;)I
    move-result v5

    const-string v6, "Twouich"
    new-instance v7, Ljava/lang/StringBuilder;
    invoke-direct {v7}, Ljava/lang/StringBuilder;-><init>()V
    const-string v8, "vaft : master len="
    invoke-virtual {v7, v8}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v4}, Ljava/lang/String;->length()I
    move-result v8
    invoke-virtual {v7, v8}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;
    const-string v8, " idx="
    invoke-virtual {v7, v8}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v7, v5}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;
    const-string v8, " tete="
    invoke-virtual {v7, v8}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const/4 v8, 0x0
    const/16 v9, 0x28
    invoke-virtual {v4}, Ljava/lang/String;->length()I
    move-result v10
    if-le v10, v9, :head_ok
    move v9, v10

    :head_ok
    invoke-virtual {v4, v8, v9}, Ljava/lang/String;->substring(II)Ljava/lang/String;
    move-result-object v8
    const/16 v9, 0xa
    const/16 v10, 0x20
    invoke-virtual {v8, v9, v10}, Ljava/lang/String;->replace(CC)Ljava/lang/String;
    move-result-object v8
    invoke-virtual {v7, v8}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v7}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v7
    invoke-static {v6, v7}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    if-ltz v5, :fail

    # La variante doit etre prise jusqu'a la fin de SA ligne : les URL usher
    # sont du type /v1/playlist/<id> (pas de .m3u8) et portent des parametres
    # de session. S'arreter a « .m3u8 » produisait une URL tronquee -> 403
    # (mesure du 23/10/2026 : master 200, variante 403).
    const-string v6, "\n"
    invoke-virtual {v4, v6, v5}, Ljava/lang/String;->indexOf(Ljava/lang/String;I)I
    move-result v6
    if-ltz v6, :no_line_end
    goto :have_end

    :no_line_end
    invoke-virtual {v4}, Ljava/lang/String;->length()I
    move-result v6

    :have_end
    invoke-virtual {v4, v5, v6}, Ljava/lang/String;->substring(II)Ljava/lang/String;
    move-result-object v5
    invoke-virtual {v5}, Ljava/lang/String;->trim()Ljava/lang/String;
    move-result-object v5

    # trace de diagnostic : debut de la variante retenue
    const-string v6, "Twouich"
    new-instance v7, Ljava/lang/StringBuilder;
    invoke-direct {v7}, Ljava/lang/StringBuilder;-><init>()V
    const-string v8, "vaft : variante "
    invoke-virtual {v7, v8}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const/16 v8, 0x50
    invoke-virtual {v5}, Ljava/lang/String;->length()I
    move-result v9
    # len <= 80 -> variante entiere
    if-le v9, v8, :short_variant
    const/4 v9, 0x0
    invoke-virtual {v5, v9, v8}, Ljava/lang/String;->substring(II)Ljava/lang/String;
    move-result-object v9
    goto :log_variant

    :short_variant
    move-object v9, v5

    :log_variant
    invoke-virtual {v7, v9}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v7}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v7
    invoke-static {v6, v7}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    # -- cache 20 s --
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J
    move-result-wide v0
    const-wide/32 v6, 0x4e20
    add-long v0, v0, v6
    sput-wide v0, Lcom/twouich/adblock/VaftFallback;->cachedUntil:J
    sput-object p0, Lcom/twouich/adblock/VaftFallback;->cachedChannel:Ljava/lang/String;
    sput-object v5, Lcom/twouich/adblock/VaftFallback;->cachedVariant:Ljava/lang/String;

    return-object v5

    :fail
    # pause de 30 s : reseau absent, flux embed refuse, jeton illisible…
    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J
    move-result-wide v0
    const-wide/32 v2, 0x7530
    add-long v0, v0, v2
    sput-wide v0, Lcom/twouich/adblock/VaftFallback;->cachedUntil:J
    sput-object p0, Lcom/twouich/adblock/VaftFallback;->cachedChannel:Ljava/lang/String;
    const/4 v10, 0x0
    sput-object v10, Lcom/twouich/adblock/VaftFallback;->cachedVariant:Ljava/lang/String;
    const/4 v10, 0x0
    return-object v10
.end method


# GET simple (playlist m3u8). Rend null hors 200.
.method private static e(Ljava/lang/String;)Ljava/lang/String;
    .locals 7

    new-instance v0, Ljava/net/URL;
    invoke-direct {v0, p0}, Ljava/net/URL;-><init>(Ljava/lang/String;)V
    invoke-virtual {v0}, Ljava/net/URL;->openConnection()Ljava/net/URLConnection;
    move-result-object v0
    check-cast v0, Ljava/net/HttpURLConnection;

    const/16 v1, 0x5dc
    invoke-virtual {v0, v1}, Ljava/net/HttpURLConnection;->setConnectTimeout(I)V
    invoke-virtual {v0, v1}, Ljava/net/HttpURLConnection;->setReadTimeout(I)V
    const-string v1, "User-Agent"
    const-string v2, "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    invoke-virtual {v0, v1, v2}, Ljava/net/HttpURLConnection;->setRequestProperty(Ljava/lang/String;Ljava/lang/String;)V
    const-string v1, "Referer"
    const-string v2, "https://www.twitch.tv/"
    invoke-virtual {v0, v1, v2}, Ljava/net/HttpURLConnection;->setRequestProperty(Ljava/lang/String;Ljava/lang/String;)V

    invoke-virtual {v0}, Ljava/net/HttpURLConnection;->getResponseCode()I
    move-result v1
    # trace de diagnostic : code HTTP du master puis de la variante
    const-string v2, "Twouich"
    new-instance v3, Ljava/lang/StringBuilder;
    invoke-direct {v3}, Ljava/lang/StringBuilder;-><init>()V
    const-string v4, "vaft : http "
    invoke-virtual {v3, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v3, v1}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;
    const-string v4, " "
    invoke-virtual {v3, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    # URL tronquee a 70 caracteres : de quoi identifier la requete sans bruit
    const/16 v4, 0x46
    invoke-virtual {p0}, Ljava/lang/String;->length()I
    move-result v5
    # longueur <= 70 -> URL entiere
    if-le v5, v4, :short_url
    const/4 v5, 0x0
    invoke-virtual {p0, v5, v4}, Ljava/lang/String;->substring(II)Ljava/lang/String;
    move-result-object v6
    goto :url_ready

    :short_url
    move-object v6, p0

    :url_ready
    invoke-virtual {v3, v6}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v3}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v3
    invoke-static {v2, v3}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    const/16 v2, 0xc8
    if-eq v1, v2, :http_ok
    invoke-virtual {v0}, Ljava/net/HttpURLConnection;->disconnect()V
    const/4 v1, 0x0
    return-object v1

    :http_ok
    const-string v2, "Twouich"
    const-string v3, "vaft : http_ok entree"
    invoke-static {v2, v3}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    invoke-virtual {v0}, Ljava/net/HttpURLConnection;->getInputStream()Ljava/io/InputStream;
    move-result-object v1
    invoke-static {v1}, Lcom/twouich/adblock/VaftFallback;->f(Ljava/io/InputStream;)Ljava/lang/String;
    move-result-object v1
    invoke-virtual {v0}, Ljava/net/HttpURLConnection;->disconnect()V
    return-object v1
.end method


# Corps d'une reponse HTTP -> String (UTF-8, lignes reconstituees).
.method private static f(Ljava/io/InputStream;)Ljava/lang/String;
    .locals 5

    const-string v0, "Twouich"
    const-string v1, "vaft : f entree"
    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    new-instance v0, Ljava/io/BufferedReader;
    new-instance v1, Ljava/io/InputStreamReader;
    const-string v2, "UTF-8"
    invoke-direct {v1, p0, v2}, Ljava/io/InputStreamReader;-><init>(Ljava/io/InputStream;Ljava/lang/String;)V
    invoke-direct {v0, v1}, Ljava/io/BufferedReader;-><init>(Ljava/io/Reader;)V

    new-instance v1, Ljava/lang/StringBuilder;
    invoke-direct {v1}, Ljava/lang/StringBuilder;-><init>()V

    :read
    invoke-virtual {v0}, Ljava/io/BufferedReader;->readLine()Ljava/lang/String;
    move-result-object v2
    if-eqz v2, :done
    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v2, "\n"
    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    goto :read

    :done
    invoke-virtual {v0}, Ljava/io/BufferedReader;->close()V
    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v0

    const-string v2, "Twouich"
    new-instance v1, Ljava/lang/StringBuilder;
    invoke-direct {v1}, Ljava/lang/StringBuilder;-><init>()V
    const-string v3, "vaft : f sortie "
    invoke-virtual {v1, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v0}, Ljava/lang/String;->length()I
    move-result v3
    invoke-virtual {v1, v3}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;
    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v1
    invoke-static {v2, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    return-object v0
.end method
