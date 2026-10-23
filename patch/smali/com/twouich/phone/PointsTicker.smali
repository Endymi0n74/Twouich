# PointsTicker — rafraichit la pastille de points pendant la lecture, TELEPHONE.
#
# Sans lui le compteur ne se voyait avancer qu'en quittant puis rouvrant le
# lecteur : `twouichPhonePoints()` n'est appele qu'aux passes de disposition
# (onResume, focus, rotation, clavier). Une minute entiere s'ecoulait donc avec
# une pastille figee sur son ancienne valeur.
#
# Une seule cadence vit a la fois : `start()` est idempotent (il ne fait que
# retenir l'activite si le message est deja pose), chaque tir reprogramme le
# suivant, et `stop()` (onPause) retire le message en attente au lieu de le
# laisser courir — sinon chaque pause/reprise laissait une chaine de plus.
.class public final Lcom/twouich/phone/PointsTicker;
.super Ljava/lang/Object;
.implements Ljava/lang/Runnable;

.field private static handler:Landroid/os/Handler;

# Instance unique reprogrammee a chaque tir (removeCallbacks la reconnait).
.field private static ticker:Lcom/twouich/phone/PointsTicker;

.field private static target:Landroid/app/Activity;

.field private static scheduled:Z


.method public constructor <init>()V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method


.method private static handler()Landroid/os/Handler;
    .locals 2

    sget-object v0, Lcom/twouich/phone/PointsTicker;->handler:Landroid/os/Handler;

    # `if-nez` : handler deja cree (non nul) -> on saute la creation. Un `if-eqz`
    # ici sautait la creation quand il etait NUL et rendait null : postDelayed
    # levait alors une NPE qui tuait le lecteur a l'onResume (mesure du 23/10).
    if-nez v0, :have

    new-instance v0, Landroid/os/Handler;

    invoke-static {}, Landroid/os/Looper;->getMainLooper()Landroid/os/Looper;

    move-result-object v1

    invoke-direct {v0, v1}, Landroid/os/Handler;-><init>(Landroid/os/Looper;)V

    sput-object v0, Lcom/twouich/phone/PointsTicker;->handler:Landroid/os/Handler;

    :have
    sget-object v0, Lcom/twouich/phone/PointsTicker;->handler:Landroid/os/Handler;

    return-object v0
.end method


# Rejoue la pastille de points de `activity` a chaque quart de minute.
.method public static start(Landroid/app/Activity;)V
    .locals 4

    if-eqz p0, :done

    sput-object p0, Lcom/twouich/phone/PointsTicker;->target:Landroid/app/Activity;

    sget-boolean v0, Lcom/twouich/phone/PointsTicker;->scheduled:Z

    # `if-eqz` : pas encore de cadence (0) -> on l'arme. Un `if-nez` ici
    # inversait la garde : la cadence n'etait jamais posee, et un `postDelayed`
    # sur un Handler nul tuait le lecteur a l'onResume (mesure du 23/10).
    if-eqz v0, :arm

    goto :done

    :arm
    const/4 v0, 0x1

    sput-boolean v0, Lcom/twouich/phone/PointsTicker;->scheduled:Z

    sget-object v0, Lcom/twouich/phone/PointsTicker;->ticker:Lcom/twouich/phone/PointsTicker;

    # `if-nez` : non nul -> l'instance existe deja, on saute la creation.
    # Avec `if-eqz` (mesure du 23/10), on sautait la creation quand elle etait
    # NULLE et `postDelayed` recevait un Runnable nul : un message sans callback,
    # donc aucune cadence et aucun tir, sans la moindre erreur.
    if-nez v0, :ticker_ready

    new-instance v0, Lcom/twouich/phone/PointsTicker;

    invoke-direct {v0}, Lcom/twouich/phone/PointsTicker;-><init>()V

    sput-object v0, Lcom/twouich/phone/PointsTicker;->ticker:Lcom/twouich/phone/PointsTicker;

    :ticker_ready
    invoke-static {}, Lcom/twouich/phone/PointsTicker;->handler()Landroid/os/Handler;

    move-result-object v1

    const-wide/16 v2, 0x3a98

    invoke-virtual {v1, v0, v2, v3}, Landroid/os/Handler;->postDelayed(Ljava/lang/Runnable;J)Z

    # Une ligne par session de lecture : elle date l'armement de la cadence sans
    # remplir le journal (le tir, lui, est muet toutes les 15 s).
    const-string v2, "Twouich"

    const-string v3, "points : cadence posee"

    invoke-static {v2, v3}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I

    :done
    return-void
.end method


# Arrete la cadence (lecteur en pause) : le message en attente est retire.
.method public static stop()V
    .locals 2

    const/4 v0, 0x0

    sput-object v0, Lcom/twouich/phone/PointsTicker;->target:Landroid/app/Activity;

    sput-boolean v0, Lcom/twouich/phone/PointsTicker;->scheduled:Z

    sget-object v1, Lcom/twouich/phone/PointsTicker;->handler:Landroid/os/Handler;

    if-eqz v1, :done

    sget-object v0, Lcom/twouich/phone/PointsTicker;->ticker:Lcom/twouich/phone/PointsTicker;

    if-eqz v0, :done

    invoke-virtual {v1, v0}, Landroid/os/Handler;->removeCallbacks(Ljava/lang/Runnable;)V

    :done
    return-void
.end method


.method public run()V
    .locals 3

    const/4 v0, 0x0

    sput-boolean v0, Lcom/twouich/phone/PointsTicker;->scheduled:Z

    sget-object v0, Lcom/twouich/phone/PointsTicker;->target:Landroid/app/Activity;

    if-eqz v0, :done

    instance-of v1, v0, Lcom/s0und/s0undtv/activities/PlayerActivity;

    if-eqz v1, :done

    # Le verificateur ne deduit pas le type du test instance-of : cast explicite,
    # sinon invoke-virtual sur twouichPhonePoints() est rejete a l'assemblage.
    move-object v1, v0

    check-cast v1, Lcom/s0und/s0undtv/activities/PlayerActivity;

    invoke-virtual {v1}, Landroid/app/Activity;->isFinishing()Z

    move-result v2

    # `if-nez` : l'activite se termine (non nul) -> plus rien a rafraichir.
    if-nez v2, :done

    invoke-virtual {v1}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhonePoints()V

    :done
    return-void
.end method
