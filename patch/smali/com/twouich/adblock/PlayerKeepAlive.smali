.class public final Lcom/twouich/adblock/PlayerKeepAlive;
.super Landroid/app/Service;
.source "PlayerKeepAlive.java"


# Service de premier plan « mediaPlayback » : la LECTURE SURVIT A L'ECRAN ETEINT.
#
# Mesure du 21/09/2026 sur le telephone (Xiaomi 1220x2712, Android 16 / HyperOS,
# v1.0.12 soit 159) : ecran eteint, l'audio continuait ~10 s (statistiques
# AudioTrackImpl a 25 s puis 30 s, decodeurs actifs) puis le flux mourait sur
# `UnknownHostException (no network)`. Deux lignes du systeme, au meme instant :
#
#   21:36:05.656 AS.AudioService: AudioHardening background playback would be
#                muted for com.s0und.s0undtv (10267), level: partial
#   21:36:05.663 InetDiagMessage: Destroyed live tcp sockets for uids={10267} in 18ms
#
# Autrement dit : l'application passait en arriere-plan SANS service de premier
# plan, donc (1) le systeme detruisait ses sockets TCP — le lecteur mourait au
# bout de son tampon — et (2) HyperOS annoncait sa mise en sourdine. Ce n'est pas
# un manque de verrous d'eveil : le reseau de l'appareil tenait (Wi-Fi valide,
# ping IP et DNS reussis ecran eteint, wifi_sleep_policy=2) et aucune restriction
# de donnees ne visait l'app (Restrict background: false). C'est le STATUT de
# l'application qui changeait.
#
# Un service de premier plan de type `mediaPlayback` remet l'application du bon
# cote : elle n'est plus « en arriere-plan sans service », ses sockets survivent,
# et HyperOS ne la met plus en sourdine. Prerequis (doc Android 14+) : declarer
# le type au manifeste + la permission FOREGROUND_SERVICE_MEDIA_PLAYBACK, et
# AUCUN prerequis d'execution. Le type est declare au manifeste, donc l'appel
# `startForeground(I, Notification)` a deux arguments suffit.
#
# Trois choix, chacun pour une raison mesuree :
#   * une MediaSession active (etat PLAYING) : c'est le signal « application
#     media » que lit la politique audio de HyperOS — sans elle, l'app reste un
#     lecteur quelconque ;
#   * un verrou d'eveil PARTIEL : le service rend la lecture prioritaire, il ne
#     garde pas le processeur eveille. La lecture audio par AudioTrack n'en tient
#     aucun par elle-meme, et le tampon n'aurait qu'a s'epuiser pendant que le
#     processeur dort ;
#   * TELEPHONE SEULEMENT (`smallestScreenWidthDp < 600`) : le mode TV est
#     intact, il n'a ni ecran eteint ni notification a porter.
#
# L'icone de la notification est celle de l'application, lue a l'execution :
# aucun identifiant de ressource en dur, donc rien a maintenir si le branding
# change.


# static fields
.field private static session:Landroid/media/session/MediaSession;

.field private static wake:Landroid/os/PowerManager$WakeLock;


# direct methods
.method public constructor <init>()V
    .locals 0

    invoke-direct {p0}, Landroid/app/Service;-><init>()V

    return-void
.end method


# Demarre le service quand l'application est au premier plan, et RIEN en mode TV.
# Le garde est celui du lecteur (twouichTvInterface) : le mode TV DECLARE par le
# systeme d'abord, le seuil de dp ensuite comme filet (TV 4K, tablettes). Le seul
# seuil de dp laissait un televiseur 1080p/320dpi (540 dp) passer pour un
# telephone — meme cause que la regression d'interface du 21/09.
.method public static startIfPhone(Landroid/app/Activity;)V
    .locals 3

    invoke-virtual {p0}, Landroid/app/Activity;->getResources()Landroid/content/res/Resources;
    move-result-object v0

    invoke-virtual {v0}, Landroid/content/res/Resources;->getConfiguration()Landroid/content/res/Configuration;
    move-result-object v0

    # Le mode DECLARE par le systeme fait foi : la Freebox Pop declare 540 dp
    # (1920x1080 en 320 dpi) et passait donc pour un telephone avec le seul
    # seuil de dp — le service de premier plan se serait lance sur la TV, avec
    # sa notification (mesure du 21/09). Meme source de verite que le lecteur.
    iget v1, v0, Landroid/content/res/Configuration;->uiMode:I

    and-int/lit8 v1, v1, 0xf

    const/4 v2, 0x4

    # if-eq : « uiMode == UI_MODE_TYPE_TELEVISION » -> television, on sort.
    # Un `if-ne` ici faisait exactement l'inverse : la Freebox (mode TV, 540 dp)
    # demarrait le service — notification comprise (mesure du 22/09).
    if-eq v1, v2, :twouich_pe_tv

    iget v1, v0, Landroid/content/res/Configuration;->smallestScreenWidthDp:I

    const/16 v2, 0x258

    # if-ge : « v1 >= v2 » -> ecran large (TV 4K, tablette), on sort aussi.
    if-ge v1, v2, :twouich_pe_tv

    invoke-static {p0}, Lcom/twouich/adblock/PlayerKeepAlive;->start(Landroid/content/Context;)V

    :twouich_pe_tv
    return-void
.end method


.method public static start(Landroid/content/Context;)V
    .locals 4

    new-instance v0, Landroid/content/Intent;

    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;
    move-result-object v1

    const-class v2, Lcom/twouich/adblock/PlayerKeepAlive;

    invoke-direct {v0, v1, v2}, Landroid/content/Intent;-><init>(Landroid/content/Context;Ljava/lang/Class;)V

    sget v1, Landroid/os/Build$VERSION;->SDK_INT:I

    const/16 v2, 0x1a

    # if-lt : « SDK_INT < 26 » -> demarrage classique (le premier plan existe
    # depuis l'API 26 ; startForegroundService y leve une exception).
    if-lt v1, v2, :twouich_pe_legacy

    invoke-virtual {p0, v0}, Landroid/content/Context;->startForegroundService(Landroid/content/Intent;)Landroid/content/ComponentName;

    move-result-object v1

    goto :twouich_pe_started

    :twouich_pe_legacy
    invoke-virtual {p0, v0}, Landroid/content/Context;->startService(Landroid/content/Intent;)Landroid/content/ComponentName;

    move-result-object v1

    :twouich_pe_started
    const-string v1, "Twouich"

    const-string v2, "veille : service de premier plan demande (mediaPlayback)"

    invoke-static {v1, v2}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    return-void
.end method


.method public static stop(Landroid/content/Context;)V
    # TROIS registres locaux : v2 porte la classe, et avec `.locals 2` v2 serait
    # p0 (le Context) — le const-class remplacerait le Context par un Class et le
    # verificateur d'ART rejetterait toute la classe au premier onResume.
    .locals 3

    new-instance v0, Landroid/content/Intent;

    invoke-virtual {p0}, Landroid/content/Context;->getApplicationContext()Landroid/content/Context;
    move-result-object v1

    const-class v2, Lcom/twouich/adblock/PlayerKeepAlive;

    invoke-direct {v0, v1, v2}, Landroid/content/Intent;-><init>(Landroid/content/Context;Ljava/lang/Class;)V

    invoke-virtual {p0, v0}, Landroid/content/Context;->stopService(Landroid/content/Intent;)Z

    const-string v0, "Twouich"

    const-string v1, "veille : service de premier plan arrete"

    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    return-void
.end method


.method public onBind(Landroid/content/Intent;)Landroid/os/IBinder;
    .locals 1

    const/4 v0, 0x0

    return-object v0
.end method


.method public onCreate()V
    .locals 0

    invoke-super {p0}, Landroid/app/Service;->onCreate()V

    invoke-direct {p0}, Lcom/twouich/adblock/PlayerKeepAlive;->twouichChannel()V

    return-void
.end method


.method public onStartCommand(Landroid/content/Intent;II)I
    .locals 4

    invoke-direct {p0}, Lcom/twouich/adblock/PlayerKeepAlive;->twouichSession()Landroid/media/session/MediaSession;
    move-result-object v0

    invoke-direct {p0, v0}, Lcom/twouich/adblock/PlayerKeepAlive;->twouichNotification(Landroid/media/session/MediaSession;)Landroid/app/Notification;
    move-result-object v1

    const/16 v2, 0x7a11

    invoke-virtual {p0, v2, v1}, Landroid/app/Service;->startForeground(ILandroid/app/Notification;)V

    invoke-direct {p0}, Lcom/twouich/adblock/PlayerKeepAlive;->twouichWake()V

    const-string v2, "Twouich"

    const-string v3, "veille : service de premier plan actif (mediaPlayback)"

    invoke-static {v2, v3}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    const/4 v0, 0x2

    return v0
.end method


.method public onDestroy()V
    .locals 2

    invoke-super {p0}, Landroid/app/Service;->onDestroy()V

    sget-object v0, Lcom/twouich/adblock/PlayerKeepAlive;->wake:Landroid/os/PowerManager$WakeLock;

    if-eqz v0, :twouich_pe_no_wake

    invoke-virtual {v0}, Landroid/os/PowerManager$WakeLock;->isHeld()Z

    move-result v1

    if-eqz v1, :twouich_pe_no_wake

    invoke-virtual {v0}, Landroid/os/PowerManager$WakeLock;->release()V

    :twouich_pe_no_wake
    const/4 v0, 0x0

    sput-object v0, Lcom/twouich/adblock/PlayerKeepAlive;->wake:Landroid/os/PowerManager$WakeLock;

    sget-object v0, Lcom/twouich/adblock/PlayerKeepAlive;->session:Landroid/media/session/MediaSession;

    if-eqz v0, :twouich_pe_no_session

    const/4 v1, 0x0

    invoke-virtual {v0, v1}, Landroid/media/session/MediaSession;->setActive(Z)V

    invoke-virtual {v0}, Landroid/media/session/MediaSession;->release()V

    :twouich_pe_no_session
    const/4 v0, 0x0

    sput-object v0, Lcom/twouich/adblock/PlayerKeepAlive;->session:Landroid/media/session/MediaSession;

    const/4 v0, 0x1

    invoke-virtual {p0, v0}, Landroid/app/Service;->stopForeground(Z)V

    return-void
.end method


# Canal de notification (obligatoire a partir de l'API 26) : en dessous, la
# notification n'a pas besoin de canal et il ne faut surtout pas creer l'objet
# (classe absente du framework avant l'API 26, donc NoClassDefFoundError).
.method private twouichChannel()V
    .locals 5

    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I

    const/16 v1, 0x1a

    # if-ge : « SDK_INT >= 26 » -> creation du canal ; en dessous on sort AVANT de
    # toucher a la classe (absente du framework avant l'API 26). Avec if-lt, la
    # creation etait sautee sur toutes les API recentes : plus aucune
    # notification de lecture, et un startForeground sans canal.
    if-ge v0, v1, :twouich_chan_go

    return-void

    :twouich_chan_go
    const-string v0, "notification"

    invoke-virtual {p0, v0}, Landroid/content/Context;->getSystemService(Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v0

    check-cast v0, Landroid/app/NotificationManager;

    new-instance v1, Landroid/app/NotificationChannel;

    const-string v2, "twouich_lecture"

    const-string v3, "Lecture Twouich"

    const/4 v4, 0x2

    invoke-direct {v1, v2, v3, v4}, Landroid/app/NotificationChannel;-><init>(Ljava/lang/String;Ljava/lang/CharSequence;I)V

    invoke-virtual {v0, v1}, Landroid/app/NotificationManager;->createNotificationChannel(Landroid/app/NotificationChannel;)V

    return-void
.end method


# Session media active : c'est le signal « application media » que lit la
# politique audio de HyperOS (celle qui annoncait la mise en sourdine). Creee une
# seule fois, gardee en champ statique, liberee dans onDestroy.
.method private twouichSession()Landroid/media/session/MediaSession;
    .locals 6

    sget-object v0, Lcom/twouich/adblock/PlayerKeepAlive;->session:Landroid/media/session/MediaSession;

    # if-nez : une session deja creee est renvoyee telle quelle ; avec if-eqz, un
    # champ nul sautait la creation et la methode RENVOYAIT NUL (aucune session
    # media, donc aucun signal « application media » pour HyperOS).
    if-nez v0, :twouich_sess_done

    new-instance v0, Landroid/media/session/MediaSession;

    const-string v1, "Twouich"

    invoke-direct {v0, p0, v1}, Landroid/media/session/MediaSession;-><init>(Landroid/content/Context;Ljava/lang/String;)V

    new-instance v1, Landroid/media/session/PlaybackState$Builder;

    invoke-direct {v1}, Landroid/media/session/PlaybackState$Builder;-><init>()V

    const/4 v2, 0x3

    # position inconnue : -1, vitesse 1.0f (0x3f800000).
    const-wide/16 v3, -0x1

    const v5, 0x3f800000

    invoke-virtual {v1, v2, v3, v4, v5}, Landroid/media/session/PlaybackState$Builder;->setState(IJF)Landroid/media/session/PlaybackState$Builder;

    move-result-object v1

    invoke-virtual {v1}, Landroid/media/session/PlaybackState$Builder;->build()Landroid/media/session/PlaybackState;
    move-result-object v1

    invoke-virtual {v0, v1}, Landroid/media/session/MediaSession;->setPlaybackState(Landroid/media/session/PlaybackState;)V

    const/4 v1, 0x1

    invoke-virtual {v0, v1}, Landroid/media/session/MediaSession;->setActive(Z)V

    sput-object v0, Lcom/twouich/adblock/PlayerKeepAlive;->session:Landroid/media/session/MediaSession;

    :twouich_sess_done
    return-object v0
.end method


# Notification de lecture : icone de l'application (lue a l'execution), titre
# fixe, retour dans l'application au toucher, style media si la session existe.
.method private twouichNotification(Landroid/media/session/MediaSession;)Landroid/app/Notification;
    .locals 8

    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I

    const/16 v1, 0x1a

    # if-lt : « SDK_INT < 26 » -> constructeur sans canal + priorite basse.
    if-lt v0, v1, :twouich_notif_old

    new-instance v2, Landroid/app/Notification$Builder;

    const-string v3, "twouich_lecture"

    invoke-direct {v2, p0, v3}, Landroid/app/Notification$Builder;-><init>(Landroid/content/Context;Ljava/lang/String;)V

    goto :twouich_notif_ready

    :twouich_notif_old
    new-instance v2, Landroid/app/Notification$Builder;

    invoke-direct {v2, p0}, Landroid/app/Notification$Builder;-><init>(Landroid/content/Context;)V

    const/4 v3, -0x1

    invoke-virtual {v2, v3}, Landroid/app/Notification$Builder;->setPriority(I)Landroid/app/Notification$Builder;
    move-result-object v2

    :twouich_notif_ready
    invoke-virtual {p0}, Landroid/content/Context;->getApplicationInfo()Landroid/content/pm/ApplicationInfo;
    move-result-object v3

    iget v3, v3, Landroid/content/pm/ApplicationInfo;->icon:I

    invoke-virtual {v2, v3}, Landroid/app/Notification$Builder;->setSmallIcon(I)Landroid/app/Notification$Builder;
    move-result-object v2

    const-string v3, "Twouich"

    invoke-virtual {v2, v3}, Landroid/app/Notification$Builder;->setContentTitle(Ljava/lang/CharSequence;)Landroid/app/Notification$Builder;
    move-result-object v2

    const-string v3, "Lecture en cours"

    invoke-virtual {v2, v3}, Landroid/app/Notification$Builder;->setContentText(Ljava/lang/CharSequence;)Landroid/app/Notification$Builder;
    move-result-object v2

    const/4 v3, 0x1

    invoke-virtual {v2, v3}, Landroid/app/Notification$Builder;->setOngoing(Z)Landroid/app/Notification$Builder;
    move-result-object v2

    const/4 v3, 0x0

    invoke-virtual {v2, v3}, Landroid/app/Notification$Builder;->setShowWhen(Z)Landroid/app/Notification$Builder;
    move-result-object v2

    invoke-virtual {p0}, Landroid/content/Context;->getPackageManager()Landroid/content/pm/PackageManager;
    move-result-object v3

    invoke-virtual {p0}, Landroid/content/Context;->getPackageName()Ljava/lang/String;
    move-result-object v4

    invoke-virtual {v3, v4}, Landroid/content/pm/PackageManager;->getLaunchIntentForPackage(Ljava/lang/String;)Landroid/content/Intent;
    move-result-object v3

    if-eqz v3, :twouich_notif_no_intent

    const/4 v4, 0x0

    # FLAG_IMMUTABLE (0x04000000) | FLAG_UPDATE_CURRENT (0x08000000).
    const v5, 0xc000000

    invoke-static {p0, v4, v3, v5}, Landroid/app/PendingIntent;->getActivity(Landroid/content/Context;ILandroid/content/Intent;I)Landroid/app/PendingIntent;
    move-result-object v3

    invoke-virtual {v2, v3}, Landroid/app/Notification$Builder;->setContentIntent(Landroid/app/PendingIntent;)Landroid/app/Notification$Builder;
    move-result-object v2

    :twouich_notif_no_intent
    if-eqz p1, :twouich_notif_plain

    new-instance v3, Landroid/app/Notification$MediaStyle;

    invoke-direct {v3}, Landroid/app/Notification$MediaStyle;-><init>()V

    invoke-virtual {p1}, Landroid/media/session/MediaSession;->getSessionToken()Landroid/media/session/MediaSession$Token;
    move-result-object v4

    invoke-virtual {v3, v4}, Landroid/app/Notification$MediaStyle;->setMediaSession(Landroid/media/session/MediaSession$Token;)Landroid/app/Notification$MediaStyle;
    move-result-object v3

    invoke-virtual {v2, v3}, Landroid/app/Notification$Builder;->setStyle(Landroid/app/Notification$Style;)Landroid/app/Notification$Builder;
    move-result-object v2

    :twouich_notif_plain
    invoke-virtual {v2}, Landroid/app/Notification$Builder;->build()Landroid/app/Notification;
    move-result-object v3

    return-object v3
.end method


# Verrou d'eveil PARTIEL : le service n'empeche pas le processeur de dormir,
# ce verrou si. Sans lui, la lecture s'arrete quand le tampon s'epuise pendant
# que le telephone dort, meme avec le service en premier plan.
.method private twouichWake()V
    .locals 4

    sget-object v0, Lcom/twouich/adblock/PlayerKeepAlive;->wake:Landroid/os/PowerManager$WakeLock;

    # if-nez : « v0 != 0 » -> le verrou existe deja, on saute a la verification.
    # Avec if-eqz, un champ nul sautait la CREATION et isHeld() tombait sur un
    # objet nul : NullPointerException mesuree sur le telephone le 21/09.
    if-nez v0, :twouich_wake_ready

    const-string v1, "power"

    invoke-virtual {p0, v1}, Landroid/content/Context;->getSystemService(Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v1

    check-cast v1, Landroid/os/PowerManager;

    const/4 v2, 0x1

    const-string v3, "twouich:lecture"

    invoke-virtual {v1, v2, v3}, Landroid/os/PowerManager;->newWakeLock(ILjava/lang/String;)Landroid/os/PowerManager$WakeLock;
    move-result-object v0

    sput-object v0, Lcom/twouich/adblock/PlayerKeepAlive;->wake:Landroid/os/PowerManager$WakeLock;

    :twouich_wake_ready
    invoke-virtual {v0}, Landroid/os/PowerManager$WakeLock;->isHeld()Z

    move-result v1

    if-eqz v1, :twouich_wake_done

    invoke-virtual {v0}, Landroid/os/PowerManager$WakeLock;->acquire()V

    :twouich_wake_done
    const-string v1, "Twouich"
    const-string v2, "veille : verrou partiel demande (twouich:lecture)"
    invoke-static {v1, v2}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    return-void
.end method
