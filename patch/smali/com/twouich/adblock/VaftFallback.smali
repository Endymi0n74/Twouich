.class public final Lcom/twouich/adblock/VaftFallback;
.super Ljava/lang/Object;
.source "VaftFallback.java"

.field public static ENABLED:Z = true

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    return-void
.end method

# VaFT backup stream - TwVodNoAdsJCed processM3U8() porte
# p0 = playlist nettoyee par PlaylistSanitizer (deja sans la plupart des pubs)
# Si p0 contient encore stitched-ad, tente un fetch backup via GQL embed -> usher -> variante
.method public static a(Ljava/lang/String;)Ljava/lang/String;
    .locals 12
    sget-boolean v0, Lcom/twouich/adblock/VaftFallback;->ENABLED:Z
    if-eqz v0, :disabled
    const-string v0, "stitched-ad"
    invoke-virtual {p0, v0}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v0
    if-eqz v0, :disabled
    sget-object v1, Lcom/twouich/adblock/AdBlockDataSource;->lastChannel:Ljava/lang/String;
    if-eqz v1, :disabled
    invoke-virtual {v1}, Ljava/lang/String;->length()I
    move-result v0
    if-eqz v0, :disabled
    # log declenchement
    const-string v0, "Twouich"
    const-string v2, "vaft backup: tentative pour channel "
    new-instance v3, Ljava/lang/StringBuilder;
    invoke-direct {v3}, Ljava/lang/StringBuilder;-><init>()V
    invoke-virtual {v3, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v3, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v3}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v2
    invoke-static {v0, v2}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    :try_vaft
    # GQL token fetch (embed)
    new-instance v2, Ljava/lang/StringBuilder;
    invoke-direct {v2}, Ljava/lang/StringBuilder;-><init>()V
    const-string v3, "{\"operationName\":\"PlaybackAccessToken\",\"variables\":{\"isLive\":true,\"login\":\""
    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v2, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v3, "\",\"isVod\":false,\"vodID\":\"\",\"playerType\":\"embed\",\"platform\":\"web\"},\"extensions\":{\"persistedQuery\":{\"version\":1,\"sha256Hash\":\"ed230aa1e33e07eebb8928504583da78a5173989fadfb1ac94be06a04f3cdbe9\"}}}"
    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v2}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v2
    new-instance v3, Ljava/net/URL;
    const-string v4, "https://gql.twitch.tv/gql"
    invoke-direct {v3, v4}, Ljava/net/URL;-><init>(Ljava/lang/String;)V
    invoke-virtual {v3}, Ljava/net/URL;->openConnection()Ljava/net/URLConnection;
    move-result-object v3
    check-cast v3, Ljava/net/HttpURLConnection;
    const-string v4, "POST"
    invoke-virtual {v3, v4}, Ljava/net/HttpURLConnection;->setRequestMethod(Ljava/lang/String;)V
    const-string v4, "Client-ID"
    const-string v5, "kimne78kx3ncx6brgo4mv6wki5h1ko"
    invoke-virtual {v3, v4, v5}, Ljava/net/HttpURLConnection;->setRequestProperty(Ljava/lang/String;Ljava/lang/String;)V
    const-string v4, "Content-Type"
    const-string v5, "application/json"
    invoke-virtual {v3, v4, v5}, Ljava/net/HttpURLConnection;->setRequestProperty(Ljava/lang/String;Ljava/lang/String;)V
    const/4 v4, 0x1
    invoke-virtual {v3, v4}, Ljava/net/HttpURLConnection;->setDoOutput(Z)V
    const/16 v4, 0x1388
    invoke-virtual {v3, v4}, Ljava/net/HttpURLConnection;->setConnectTimeout(I)V
    invoke-virtual {v3, v4}, Ljava/net/HttpURLConnection;->setReadTimeout(I)V
    invoke-virtual {v3}, Ljava/net/HttpURLConnection;->getOutputStream()Ljava/io/OutputStream;
    move-result-object v4
    const-string v5, "UTF-8"
    invoke-virtual {v2, v5}, Ljava/lang/String;->getBytes(Ljava/lang/String;)[B
    move-result-object v2
    invoke-virtual {v4, v2}, Ljava/io/OutputStream;->write([B)V
    invoke-virtual {v4}, Ljava/io/OutputStream;->close()V
    invoke-virtual {v3}, Ljava/net/HttpURLConnection;->getResponseCode()I
    move-result v4
    const/16 v5, 0xc8
    if-eq v4, v5, :gql_ok
    invoke-virtual {v3}, Ljava/net/HttpURLConnection;->disconnect()V
    goto :disabled
    :gql_ok
    invoke-virtual {v3}, Ljava/net/HttpURLConnection;->getInputStream()Ljava/io/InputStream;
    move-result-object v4
    new-instance v5, Ljava/io/BufferedReader;
    new-instance v6, Ljava/io/InputStreamReader;
    const-string v7, "UTF-8"
    invoke-direct {v6, v4, v7}, Ljava/io/InputStreamReader;-><init>(Ljava/io/InputStream;Ljava/lang/String;)V
    invoke-direct {v5, v6}, Ljava/io/BufferedReader;-><init>(Ljava/io/Reader;)V
    new-instance v6, Ljava/lang/StringBuilder;
    invoke-direct {v6}, Ljava/lang/StringBuilder;-><init>()V
    :gql_read
    invoke-virtual {v5}, Ljava/io/BufferedReader;->readLine()Ljava/lang/String;
    move-result-object v7
    if-eqz v7, :gql_done
    invoke-virtual {v6, v7}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    goto :gql_read
    :gql_done
    invoke-virtual {v5}, Ljava/io/BufferedReader;->close()V
    invoke-virtual {v3}, Ljava/net/HttpURLConnection;->disconnect()V
    invoke-virtual {v6}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v3
    # extraction signature
    const-string v4, "\"signature\":\""
    invoke-virtual {v3, v4}, Ljava/lang/String;->indexOf(Ljava/lang/String;)I
    move-result v4
    if-ltz v4, :disabled
    add-int/lit8 v4, v4, 0xd
    const-string v5, "\""
    invoke-virtual {v3, v5, v4}, Ljava/lang/String;->indexOf(Ljava/lang/String;I)I
    move-result v5
    if-le v5, v4, :disabled
    invoke-virtual {v3, v4, v5}, Ljava/lang/String;->substring(II)Ljava/lang/String;
    move-result-object v4
    const-string v6, "\"value\":\""
    invoke-virtual {v3, v6}, Ljava/lang/String;->indexOf(Ljava/lang/String;)I
    move-result v6
    if-ltz v6, :disabled
    add-int/lit8 v6, v6, 0x9
    const-string v7, "\""
    invoke-virtual {v3, v7, v6}, Ljava/lang/String;->indexOf(Ljava/lang/String;I)I
    move-result v7
    if-le v7, v6, :disabled
    invoke-virtual {v3, v6, v7}, Ljava/lang/String;->substring(II)Ljava/lang/String;
    move-result-object v6
    # URL encode token (espace -> %20 minimal, le token est deja URL safe base64)
    # Build usher URL
    new-instance v3, Ljava/lang/StringBuilder;
    invoke-direct {v3}, Ljava/lang/StringBuilder;-><init>()V
    const-string v7, "https://usher.ttvnw.net/api/v2/channel/hls/"
    invoke-virtual {v3, v7}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v3, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v7, ".m3u8?sig="
    invoke-virtual {v3, v7}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v7, "UTF-8"
    invoke-static {v4, v7}, Ljava/net/URLEncoder;->encode(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v4
    invoke-virtual {v3, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v4, "&token="
    invoke-virtual {v3, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v4, "UTF-8"
    invoke-static {v6, v4}, Ljava/net/URLEncoder;->encode(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v4
    invoke-virtual {v3, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v4, "&allow_source=true&fast_bread=true"
    invoke-virtual {v3, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    invoke-virtual {v3}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v3
    # fetch encodings
    new-instance v4, Ljava/net/URL;
    invoke-direct {v4, v3}, Ljava/net/URL;-><init>(Ljava/lang/String;)V
    invoke-virtual {v4}, Ljava/net/URL;->openConnection()Ljava/net/URLConnection;
    move-result-object v3
    check-cast v3, Ljava/net/HttpURLConnection;
    const/16 v4, 0x1388
    invoke-virtual {v3, v4}, Ljava/net/HttpURLConnection;->setConnectTimeout(I)V
    invoke-virtual {v3, v4}, Ljava/net/HttpURLConnection;->setReadTimeout(I)V
    invoke-virtual {v3}, Ljava/net/HttpURLConnection;->getResponseCode()I
    move-result v4
    const/16 v5, 0xc8
    if-eq v4, v5, :usher_ok
    invoke-virtual {v3}, Ljava/net/HttpURLConnection;->disconnect()V
    goto :disabled
    :usher_ok
    invoke-virtual {v3}, Ljava/net/HttpURLConnection;->getInputStream()Ljava/io/InputStream;
    move-result-object v4
    new-instance v5, Ljava/io/BufferedReader;
    new-instance v6, Ljava/io/InputStreamReader;
    const-string v7, "UTF-8"
    invoke-direct {v6, v4, v7}, Ljava/io/InputStreamReader;-><init>(Ljava/io/InputStream;Ljava/lang/String;)V
    invoke-direct {v5, v6}, Ljava/io/BufferedReader;-><init>(Ljava/io/Reader;)V
    new-instance v6, Ljava/lang/StringBuilder;
    invoke-direct {v6}, Ljava/lang/StringBuilder;-><init>()V
    :usher_read
    invoke-virtual {v5}, Ljava/io/BufferedReader;->readLine()Ljava/lang/String;
    move-result-object v7
    if-eqz v7, :usher_done
    invoke-virtual {v6, v7}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v7, "\n"
    invoke-virtual {v6, v7}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    goto :usher_read
    :usher_done
    invoke-virtual {v5}, Ljava/io/BufferedReader;->close()V
    invoke-virtual {v3}, Ljava/net/HttpURLConnection;->disconnect()V
    invoke-virtual {v6}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v3
    # trouver premiere variante https://...m3u8
    const-string v4, "https://"
    invoke-virtual {v3, v4}, Ljava/lang/String;->indexOf(Ljava/lang/String;)I
    move-result v4
    if-ltz v4, :disabled
    const-string v5, ".m3u8"
    invoke-virtual {v3, v5, v4}, Ljava/lang/String;->indexOf(Ljava/lang/String;I)I
    move-result v5
    if-le v5, v4, :disabled
    add-int/lit8 v5, v5, 0x5
    invoke-virtual {v3, v4, v5}, Ljava/lang/String;->substring(II)Ljava/lang/String;
    move-result-object v3
    # fetch variante
    new-instance v4, Ljava/net/URL;
    invoke-direct {v4, v3}, Ljava/net/URL;-><init>(Ljava/lang/String;)V
    invoke-virtual {v4}, Ljava/net/URL;->openConnection()Ljava/net/URLConnection;
    move-result-object v3
    check-cast v3, Ljava/net/HttpURLConnection;
    const/16 v4, 0x1388
    invoke-virtual {v3, v4}, Ljava/net/HttpURLConnection;->setConnectTimeout(I)V
    invoke-virtual {v3, v4}, Ljava/net/HttpURLConnection;->setReadTimeout(I)V
    invoke-virtual {v3}, Ljava/net/HttpURLConnection;->getResponseCode()I
    move-result v4
    const/16 v5, 0xc8
    if-eq v4, v5, :var_ok
    invoke-virtual {v3}, Ljava/net/HttpURLConnection;->disconnect()V
    goto :disabled
    :var_ok
    invoke-virtual {v3}, Ljava/net/HttpURLConnection;->getInputStream()Ljava/io/InputStream;
    move-result-object v4
    new-instance v5, Ljava/io/BufferedReader;
    new-instance v6, Ljava/io/InputStreamReader;
    const-string v7, "UTF-8"
    invoke-direct {v6, v4, v7}, Ljava/io/InputStreamReader;-><init>(Ljava/io/InputStream;Ljava/lang/String;)V
    invoke-direct {v5, v6}, Ljava/io/BufferedReader;-><init>(Ljava/io/Reader;)V
    new-instance v6, Ljava/lang/StringBuilder;
    invoke-direct {v6}, Ljava/lang/StringBuilder;-><init>()V
    :var_read
    invoke-virtual {v5}, Ljava/io/BufferedReader;->readLine()Ljava/lang/String;
    move-result-object v7
    if-eqz v7, :var_done
    invoke-virtual {v6, v7}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    const-string v7, "\n"
    invoke-virtual {v6, v7}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    goto :var_read
    :var_done
    invoke-virtual {v5}, Ljava/io/BufferedReader;->close()V
    invoke-virtual {v3}, Ljava/net/HttpURLConnection;->disconnect()V
    invoke-virtual {v6}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v3
    const-string v4, "stitched-ad"
    invoke-virtual {v3, v4}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z
    move-result v4
    if-nez v4, :disabled
    const-string v4, "Twouich"
    const-string v5, "vaft backup reussi - playlist propre utilisee"
    invoke-static {v4, v5}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    # nettoyer aussi le backup via sanitizer (au cas ou)
    invoke-static {v3}, Lcom/twouich/adblock/PlaylistSanitizer;->a(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v3
    return-object v3
    :try_vaft_end
    .catch Ljava/lang/Exception; {:try_vaft .. :try_vaft_end} :vaft_catch
    goto :disabled
    :vaft_catch
    move-exception v0
    const-string v1, "Twouich"
    const-string v2, "vaft backup echec, repli stripping local"
    invoke-static {v1, v2}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I
    :disabled
    return-object p0
.end method
