.class public final Lcom/twouich/adblock/PlaylistSanitizer;
.super Ljava/lang/Object;
.source "PlaylistSanitizer.java"


# static fields
# Nombre de segments publicitaires retires lors du dernier nettoyage.
# Lu par AdBlockDataSource pour tracer le resultat sur logcat.
.field public static lastCut:I

# Sentinelle « marqueur pub inconnu » : true si la derniere playlist contenait
# une balise ressemblant a un marqueur publicitaire qu'aucune regle connue ne
# couvre (cf. b()). Purement indicative : le nettoyage n'en depend pas.
.field public static suspicious:Z


# direct methods
.method public constructor <init>()V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method


# virtual methods
# Retire les plages publicitaires d'une playlist HLS Twitch.
# Regles (alignees sur Streamlink plugins/twitch.py) :
#   - plage pub  : #EXT-X-DATERANGE contenant "stitched-ad"
#   - segment pub: titre #EXTINF contenant "Amazon", ou dans une plage pub
#   - bloc pub   : #EXT-X-CUE-OUT ... #EXT-X-CUE-IN
#   - fin de pub : #EXT-X-DISCONTINUITY et #EXT-X-TWITCH-LIVE-SEQUENCE sont
#                  CONSERVES (ils signalent le saut de timeline au lecteur)
.method public static a(Ljava/lang/String;)Ljava/lang/String;
    .locals 12

    # v2 = i, v3 = n, v4 = ligne, v5 = temporaire, v6 = skipUri,
    # v7 = inAd, v8 = inCue, v9 = StringBuilder, v10 = lignes, v11 = segments retires

    if-nez p0, :body_ok

    const/4 v0, 0x0

    return-object v0

    :body_ok
    const-string v1, "#EXTM3U"

    invoke-virtual {p0, v1}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z

    move-result v1

    # if-nez : "contient #EXTM3U" -> c'est une playlist, on la nettoie.
    # (if-eqz ici faisait l'inverse : les vraies playlists repartaient intactes,
    #  pubs comprises, et les corps non-playlist etaient nettoyes pour rien)
    if-nez v1, :is_playlist

    # pas une playlist : on la rend telle quelle
    return-object p0

    :is_playlist
    const-string v1, "\n"

    const/4 v2, -0x1

    invoke-virtual {p0, v1, v2}, Ljava/lang/String;->split(Ljava/lang/String;I)[Ljava/lang/String;

    move-result-object v10

    array-length v3, v10

    new-instance v9, Ljava/lang/StringBuilder;

    invoke-direct {v9}, Ljava/lang/StringBuilder;-><init>()V

    const/4 v2, 0x0

    const/4 v7, 0x0

    const/4 v8, 0x0

    const/4 v6, 0x0

    const/4 v11, 0x0

    # sentinelle : drapeau reinitialise a chaque playlist
    const/4 v0, 0x0

    sput-boolean v0, Lcom/twouich/adblock/PlaylistSanitizer;->suspicious:Z

    :loop
    if-ge v2, v3, :end_loop

    aget-object v4, v10, v2

    invoke-virtual {v4}, Ljava/lang/String;->trim()Ljava/lang/String;

    move-result-object v4

    invoke-virtual {v4}, Ljava/lang/String;->length()I

    move-result v5

    if-nez v5, :not_empty

    # ligne vide : ignoree
    goto :inc

    :not_empty
    if-eqz v6, :no_skip_uri

    # URI du segment pub qui suivait un #EXTINF Amazon : ignoree
    const/4 v6, 0x0

    goto :drop

    :no_skip_uri
    const-string v5, "#EXT-X-DATERANGE"

    invoke-virtual {v4, v5}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v5

    if-eqz v5, :after_daterange

    const-string v5, "stitched-ad"

    invoke-virtual {v4, v5}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z

    move-result v5

    if-eqz v5, :after_daterange

    # debut d'une plage publicitaire : le tag disparait, la zone est sautee
    const/4 v7, 0x1

    goto :drop

    :after_daterange
    const-string v5, "#EXT-X-CUE-OUT"

    invoke-virtual {v4, v5}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v5

    if-eqz v5, :after_cue_out

    const/4 v8, 0x1

    goto :drop

    :after_cue_out
    const-string v5, "#EXT-X-CUE-IN"

    invoke-virtual {v4, v5}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v5

    if-eqz v5, :after_cue_in

    const/4 v8, 0x0

    goto :drop

    :after_cue_in
    const-string v5, "#EXT-X-DISCONTINUITY"

    invoke-virtual {v4, v5}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v5

    if-eqz v5, :after_discontinuity

    # fin de la plage pub : on garde le tag pour que le lecteur gere le saut
    const/4 v7, 0x0

    goto :emit

    :after_discontinuity
    const-string v5, "#EXT-X-TWITCH-LIVE-SEQUENCE"

    invoke-virtual {v4, v5}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v5

    if-eqz v5, :after_live_sequence

    const/4 v7, 0x0

    goto :emit

    :after_live_sequence
    or-int v5, v7, v8

    if-eqz v5, :not_in_ad

    # dans une zone publicitaire : tout est jete
    goto :drop

    :not_in_ad
    # sentinelle « marqueur pub inconnu » : observation pure, aucune consequence
    # sur le nettoyage (voir b() et le miroir patch/tests/test_sanitizer.py).
    # Pose ici (hors de toute zone pub deja reconnue) pour ne pas signaler les
    # balises d'un pod identifie ; une seule alerte par playlist (drapeau).
    invoke-static {v4}, Lcom/twouich/adblock/PlaylistSanitizer;->b(Ljava/lang/String;)V

    const-string v5, "#EXTINF"

    invoke-virtual {v4, v5}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v5

    if-eqz v5, :emit

    const-string v5, "Amazon"

    invoke-virtual {v4, v5}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z

    move-result v5

    if-eqz v5, :emit

    # segment pub marque uniquement par son titre : on jette aussi son URI
    const/4 v6, 0x1

    goto :drop

    :emit
    invoke-virtual {v9, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    const/16 v5, 0xa

    invoke-virtual {v9, v5}, Ljava/lang/StringBuilder;->append(C)Ljava/lang/StringBuilder;

    goto :inc

    # ligne jetee : on ne compte que les URI (une par segment publicitaire).
    # Les balises (#EXTINF, #EXT-X-DATERANGE...) ne doivent PAS etre comptees :
    # sinon la trace logcat annonce des « segments pub retires » qui sont en
    # realite des balises (constate sur appareil le 15/09/2026 : 4 annonces
    # pour 3 segments).
    # if-nez = "v5 != 0" = la ligne commence bien par # -> on ne compte pas.
    # (if-eqz comptait les balises et ignorait les URI, soit l'inverse.)
    :drop
    const-string v5, "#"

    invoke-virtual {v4, v5}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v5

    if-nez v5, :drop_nocount

    add-int/lit8 v11, v11, 0x1

    :drop_nocount
    :inc
    add-int/lit8 v2, v2, 0x1

    goto :loop

    :end_loop
    sput v11, Lcom/twouich/adblock/PlaylistSanitizer;->lastCut:I

    invoke-virtual {v9}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object p0

    return-object p0
.end method


# Sentinelle « marqueur pub inconnu » : cette balise ressemble-t-elle a un
# marqueur publicitaire qu'aucune regle connue ne couvre ? Si oui, Log.w une
# fois par playlist (drapeau suspicious). Appelée depuis a() en :not_in_ad,
# uniquement pour des lignes hors zone pub deja reconnue — donc les balises
# d'un pod identifie (DATERANGE stitched-ad, CUE-OUT/IN...) n'arrivent jamais
# ici par le flux normal.
# Scenario couvert : Twitch renomme son format (classe SSAI differente avec les
# memes attributs de diffusion X-TV-TWITCH-AD-*, ou nouvelle balise CUE).
# Miroir exact : suspicious_tag() dans patch/tests/test_sanitizer.py.
.method public static b(Ljava/lang/String;)V
    .locals 3

    # p0 = ligne (deja trimmee par a())

    # famille CUE client-side : tout #EXT-X-CUE* autre que CUE-OUT / CUE-IN
    const-string v0, "#EXT-X-CUE"

    invoke-virtual {p0, v0}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v0

    if-eqz v0, :not_cue

    const-string v0, "#EXT-X-CUE-OUT"

    invoke-virtual {p0, v0}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v0

    if-nez v0, :silent

    const-string v0, "#EXT-X-CUE-IN"

    invoke-virtual {p0, v0}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v0

    if-nez v0, :silent

    goto :report

    :not_cue
    # seule une plage DATERANGE peut porter des attributs de diffusion pub
    const-string v0, "#EXT-X-DATERANGE"

    invoke-virtual {p0, v0}, Ljava/lang/String;->startsWith(Ljava/lang/String;)Z

    move-result v0

    if-eqz v0, :silent

    # sans attribut X-TV-TWITCH-AD-* : plage utilitaire (timestamp, session,
    # stream-source, trigger...) — rien a signaler
    const-string v0, "X-TV-TWITCH-AD-"

    invoke-virtual {p0, v0}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z

    move-result v0

    if-eqz v0, :silent

    # classe connue
    const-string v0, "stitched-ad"

    invoke-virtual {p0, v0}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z

    move-result v0

    if-nez v0, :silent

    # metadonnee de pod connue : twitch-ad-quartile
    const-string v0, "quartile"

    invoke-virtual {p0, v0}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z

    move-result v0

    if-eqz v0, :report

    goto :silent

    :report
    # une seule alerte par playlist
    sget-boolean v0, Lcom/twouich/adblock/PlaylistSanitizer;->suspicious:Z

    if-nez v0, :silent

    const/4 v0, 0x1

    sput-boolean v0, Lcom/twouich/adblock/PlaylistSanitizer;->suspicious:Z

    const-string v0, "Twouich"

    new-instance v1, Ljava/lang/StringBuilder;

    invoke-direct {v1}, Ljava/lang/StringBuilder;-><init>()V

    const-string v2, "marqueur pub inconnu : "

    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v1, p0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v1

    invoke-static {v0, v1}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;)I

    :silent
    return-void
.end method
