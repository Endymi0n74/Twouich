# PointsLongPress — appui long sur les deux commandes de la pastille de points.
#
# La pastille de visionnage se masque d'un appui long : le choix est ecrit dans
# les SharedPreferences de WatchPoints, donc il survit a la fermeture du
# lecteur et a la reinstalation de l'APK.
#
# Une fois masquee, la pastille n'est plus atteignable au doigt : c'est le
# bouton d'incrustation — toujours present — qui porte le meme geste et bascule
# le choix. Le message affiche au masquage nomme ce chemin de retour, sans quoi
# la fonction serait definitive.
.class public final Lcom/twouich/phone/PointsLongPress;
.super Ljava/lang/Object;
.implements Landroid/view/View$OnLongClickListener;


.field private final activity:Lcom/s0und/s0undtv/activities/PlayerActivity;

# true : le geste bascule le choix (bouton d'incrustation). false : il masque
# (pastille, qui n'est de toute facon atteignable que lorsqu'elle est visible).
.field private final toggle:Z


.method public constructor <init>(Lcom/s0und/s0undtv/activities/PlayerActivity;Z)V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    iput-object p1, p0, Lcom/twouich/phone/PointsLongPress;->activity:Lcom/s0und/s0undtv/activities/PlayerActivity;

    iput-boolean p2, p0, Lcom/twouich/phone/PointsLongPress;->toggle:Z

    return-void
.end method


.method public onLongClick(Landroid/view/View;)Z
    .locals 4

    iget-object v0, p0, Lcom/twouich/phone/PointsLongPress;->activity:Lcom/s0und/s0undtv/activities/PlayerActivity;

    if-eqz v0, :consumed

    const/4 v1, 0x1

    iget-boolean v2, p0, Lcom/twouich/phone/PointsLongPress;->toggle:Z

    # `if-eqz` : la pastille elle-meme (toggle = false) se masque directement ;
    # le bouton d'incrustation bascule le choix dans les deux sens.
    if-eqz v2, :hide_badge

    invoke-static {v0}, Lcom/twouich/phone/WatchPoints;->toggle(Landroid/content/Context;)Z

    move-result v1

    goto :applied

    :hide_badge
    invoke-static {v0, v1}, Lcom/twouich/phone/WatchPoints;->setHidden(Landroid/content/Context;Z)V

    :applied
    # L'affichage suit le choix immediatement — via le proprietaire unique de la
    # visibilite, qui ne rouvre PAS la session de comptage ni la cadence :
    # un appui long pendant une pause ne doit pas faire courir les points.
    invoke-virtual {v0}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhonePointsApply()V

    if-eqz v1, :shown

    const-string v2, "Points masqués — appui long sur le bouton PiP pour les réafficher"

    goto :toast

    :shown
    const-string v2, "Points affichés"

    :toast
    const/4 v3, 0x0

    invoke-static {v0, v2, v3}, Landroid/widget/Toast;->makeText(Landroid/content/Context;Ljava/lang/CharSequence;I)Landroid/widget/Toast;

    move-result-object v2

    invoke-virtual {v2}, Landroid/widget/Toast;->show()V

    :consumed
    # Le geste est toujours consomme : un appui long sur la pastille ne doit pas
    # atteindre la video en dessous.
    const/4 v0, 0x1

    return v0
.end method
