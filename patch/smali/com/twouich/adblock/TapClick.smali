.class public final Lcom/twouich/adblock/TapClick;
.super Ljava/lang/Object;
.source "TapClick.java"


# Traduit un tap sur une carte Leanback en clic reel (telephone uniquement).
#
# Constat sur appareil (19/09, Xiaomi 1220x2712) : le PREMIER appui sur une carte
# ne fait que deplacer la selection — la rangee consomme le geste et relache la
# cible pendant la transition de focus, l'element n'est active qu'au SECOND appui.
# Au doigt, cela se lit comme « les menus ne repondent pas ».
#
# Ce traducteur est appele a l'entree de BaseGridView.dispatchTouchEvent : sur un
# tap (appui + relachement sans glissement), il clique la carte sous le doigt,
# exactement comme le fait la touche OK du D-pad, et consomme le relachement pour
# que le chemin natif ne puisse pas s'ajouter (un tap, exactement un clic).
#
# Deux mesures ont guide la regle, dans cet ordre :
#   * l'etat de la carte (focus, puis selection) ne predit PAS le clic natif :
#     le premier appui ne cliquait pas alors que la carte etait deja focussee,
#     puis deja selectionnee ; d'ou la regle deterministe « c'est nous qui
#     cliquons » plutot qu'une exception basee sur l'etat ;
#   * la television est hors de portee : au-dela de 600 dp de plus petit cote,
#     tout est laisse a Leanback, et le D-pad n'emet de toute facon aucun
#     MotionEvent (verifie sur appareil : D-pad -> aucune trace).


# static fields
# Etat du geste en cours (un tap est un geste unique, un doigt a la fois).
.field private static downX:F

.field private static downY:F

.field private static moved:Z


# direct methods
.method private constructor <init>()V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method


.method private static cancelGesture(Landroid/view/View;Landroid/view/MotionEvent;)V
    .locals 2

    # Le DOWN a ete livre a la carte : sans relachement, elle resterait « appuyee ».
    # On lui envoie donc l'annulation que le framework enverrait si un parent avait
    # vole le geste, avant de cliquer.
    invoke-static {p1}, Landroid/view/MotionEvent;->obtain(Landroid/view/MotionEvent;)Landroid/view/MotionEvent;

    move-result-object v0

    const/4 v1, 0x3

    invoke-virtual {v0, v1}, Landroid/view/MotionEvent;->setAction(I)V

    invoke-virtual {p0, v0}, Landroid/view/View;->dispatchTouchEvent(Landroid/view/MotionEvent;)Z

    invoke-virtual {v0}, Landroid/view/MotionEvent;->recycle()V

    return-void
.end method


.method private static clickableAt(Landroid/view/View;FF)Landroid/view/View;
    .locals 12

    # Plus profonde vue cliquable sous (p1, p2), coordonnees exprimees dans p0.
    invoke-virtual {p0}, Landroid/view/View;->getVisibility()I

    move-result v1

    if-nez v1, :null

    invoke-virtual {p0}, Landroid/view/View;->isEnabled()Z

    move-result v1

    if-eqz v1, :null

    # if-eqz : on descend dans les enfants quand c'est BIEN un ViewGroup. Avec
    # if-nez, la descente etait court-circuitee et la grille (cliquable) se
    # declarait elle-meme cible : le tap ne faisait rien (mesure du 19/09).
    instance-of v1, p0, Landroid/view/ViewGroup;

    if-eqz v1, :clickable

    move-object v0, p0

    check-cast v0, Landroid/view/ViewGroup;

    invoke-virtual {v0}, Landroid/view/ViewGroup;->getChildCount()I

    move-result v1

    add-int/lit8 v1, v1, -0x1

    :loop

    if-ltz v1, :clickable

    invoke-virtual {v0, v1}, Landroid/view/ViewGroup;->getChildAt(I)Landroid/view/View;

    move-result-object v2

    if-eqz v2, :next

    # Coordonnees dans l'enfant : positions de mise en page, translation et
    # defilement du parent retires.
    invoke-virtual {v2}, Landroid/view/View;->getLeft()I

    move-result v3

    int-to-float v3, v3

    invoke-virtual {v2}, Landroid/view/View;->getTranslationX()F

    move-result v4

    add-float/2addr v3, v4

    invoke-virtual {v0}, Landroid/view/ViewGroup;->getScrollX()I

    move-result v4

    int-to-float v4, v4

    sub-float/2addr v3, v4

    move v5, p1

    sub-float/2addr v5, v3

    invoke-virtual {v2}, Landroid/view/View;->getTop()I

    move-result v3

    int-to-float v3, v3

    invoke-virtual {v2}, Landroid/view/View;->getTranslationY()F

    move-result v4

    add-float/2addr v3, v4

    invoke-virtual {v0}, Landroid/view/ViewGroup;->getScrollY()I

    move-result v4

    int-to-float v4, v4

    sub-float/2addr v3, v4

    move v6, p2

    sub-float/2addr v6, v3

    const/4 v3, 0x0

    int-to-float v3, v3

    # Hors cadre si cx < 0 ou cy < 0 (cmpg : -1 seulement si le premier est plus petit).
    cmpg-float v4, v5, v3

    if-ltz v4, :next

    cmpg-float v4, v6, v3

    if-ltz v4, :next

    # Hors cadre si cx >= largeur ou cy >= hauteur (comparaison inversee : la
    # largeur est le premier operande, donc « <= 0 » veut dire « cadre depasse »).
    invoke-virtual {v2}, Landroid/view/View;->getWidth()I

    move-result v4

    int-to-float v4, v4

    cmpg-float v7, v4, v5

    if-lez v7, :next

    invoke-virtual {v2}, Landroid/view/View;->getHeight()I

    move-result v4

    int-to-float v4, v4

    cmpg-float v7, v4, v6

    if-lez v7, :next

    invoke-static {v2, v5, v6}, Lcom/twouich/adblock/TapClick;->clickableAt(Landroid/view/View;FF)Landroid/view/View;

    move-result-object v3

    if-eqz v3, :next

    return-object v3

    :next

    add-int/lit8 v1, v1, -0x1

    goto :loop

    :clickable

    invoke-virtual {p0}, Landroid/view/View;->isClickable()Z

    move-result v1

    if-eqz v1, :null

    return-object p0

    :null

    const/4 v0, 0x0

    return-object v0
.end method


.method private static isPhone(Landroid/view/View;)Z
    .locals 3

    invoke-virtual {p0}, Landroid/view/View;->getContext()Landroid/content/Context;

    move-result-object v0

    invoke-virtual {v0}, Landroid/content/Context;->getResources()Landroid/content/res/Resources;

    move-result-object v0

    invoke-virtual {v0}, Landroid/content/res/Resources;->getConfiguration()Landroid/content/res/Configuration;

    move-result-object v0

    iget v0, v0, Landroid/content/res/Configuration;->smallestScreenWidthDp:I

    const/16 v1, 0x258

    const/4 v2, 0x0

    if-ge v0, v1, :tv

    const/4 v2, 0x1

    :tv

    return v2
.end method


.method private static trace(Ljava/lang/String;)V
    .locals 1

    # Trace logcat : chaque geste laisse une ligne, y compris quand on s'abstient.
    # C'est la seule facon de distinguer « le hook n'est pas appele » de « aucun
    # tap franc » quand une carte ne reagit pas sur un appareil.
    const-string v0, "TWOUICH-TAP"

    invoke-static {v0, p0}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    return-void
.end method


.method public static touch(Landroid/view/View;Landroid/view/MotionEvent;)Z
    .locals 6

    if-eqz p0, :refuse

    if-eqz p1, :refuse

    invoke-static {p0}, Lcom/twouich/adblock/TapClick;->isPhone(Landroid/view/View;)Z

    move-result v0

    if-eqz v0, :refuse

    invoke-virtual {p1}, Landroid/view/MotionEvent;->getActionMasked()I

    move-result v0

    if-nez v0, :not_down

    # ACTION_DOWN : position de depart du geste. Le DOWN part a la grille, pour
    # que le defilement et la selection au doigt continuent de fonctionner.
    invoke-virtual {p1}, Landroid/view/MotionEvent;->getX()F

    move-result v1

    sput v1, Lcom/twouich/adblock/TapClick;->downX:F

    invoke-virtual {p1}, Landroid/view/MotionEvent;->getY()F

    move-result v1

    sput v1, Lcom/twouich/adblock/TapClick;->downY:F

    const/4 v1, 0x0

    sput-boolean v1, Lcom/twouich/adblock/TapClick;->moved:Z

    const-string v1, "appui"

    invoke-static {v1}, Lcom/twouich/adblock/TapClick;->trace(Ljava/lang/String;)V

    goto :refuse

    :not_down

    const/4 v1, 0x2

    if-ne v0, v1, :not_move

    # ACTION_MOVE : au-dela du seuil de glissement, c'est un defilement, pas un tap.
    invoke-virtual {p0}, Landroid/view/View;->getContext()Landroid/content/Context;

    move-result-object v1

    invoke-static {v1}, Landroid/view/ViewConfiguration;->get(Landroid/content/Context;)Landroid/view/ViewConfiguration;

    move-result-object v1

    invoke-virtual {v1}, Landroid/view/ViewConfiguration;->getScaledTouchSlop()I

    move-result v1

    int-to-float v1, v1

    invoke-virtual {p1}, Landroid/view/MotionEvent;->getX()F

    move-result v2

    sget v3, Lcom/twouich/adblock/TapClick;->downX:F

    sub-float/2addr v2, v3

    invoke-static {v2}, Ljava/lang/Math;->abs(F)F

    move-result v2

    # cmpg(slop, |dx|) : negatif quand le doigt a bouge plus que le seuil.
    cmpg-float v3, v1, v2

    if-ltz v3, :mark_moved

    invoke-virtual {p1}, Landroid/view/MotionEvent;->getY()F

    move-result v2

    sget v3, Lcom/twouich/adblock/TapClick;->downY:F

    sub-float/2addr v2, v3

    invoke-static {v2}, Ljava/lang/Math;->abs(F)F

    move-result v2

    cmpg-float v3, v1, v2

    if-ltz v3, :mark_moved

    goto :refuse

    :mark_moved

    const/4 v1, 0x1

    sput-boolean v1, Lcom/twouich/adblock/TapClick;->moved:Z

    goto :refuse

    :not_move

    const/4 v1, 0x1

    if-ne v0, v1, :not_up

    # ACTION_UP : un tap franc active la carte sous le doigt.
    # if-nez : on refuse des que `moved` est VRAI (un glissement n'est pas un tap).
    sget-boolean v1, Lcom/twouich/adblock/TapClick;->moved:Z

    if-nez v1, :up_moved

    invoke-virtual {p1}, Landroid/view/MotionEvent;->getX()F

    move-result v2

    invoke-virtual {p1}, Landroid/view/MotionEvent;->getY()F

    move-result v3

    invoke-static {p0, v2, v3}, Lcom/twouich/adblock/TapClick;->clickableAt(Landroid/view/View;FF)Landroid/view/View;

    move-result-object v1

    if-eqz v1, :up_nothing

    # Trace logcat : preuve, sur appareil, qu'un tap a bien ete traduit en clic.
    invoke-virtual {v1}, Ljava/lang/Object;->getClass()Ljava/lang/Class;

    move-result-object v2

    invoke-virtual {v2}, Ljava/lang/Class;->getName()Ljava/lang/String;

    move-result-object v2

    new-instance v3, Ljava/lang/StringBuilder;

    invoke-direct {v3}, Ljava/lang/StringBuilder;-><init>()V

    const-string v4, "tap -> clic "

    invoke-virtual {v3, v4}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v3, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v3}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v2

    invoke-static {v2}, Lcom/twouich/adblock/TapClick;->trace(Ljava/lang/String;)V

    invoke-static {p0, p1}, Lcom/twouich/adblock/TapClick;->cancelGesture(Landroid/view/View;Landroid/view/MotionEvent;)V

    invoke-virtual {v1}, Landroid/view/View;->performClick()Z

    const/4 v0, 0x1

    return v0

    :up_moved

    const-string v1, "relachement ignore : glissement"

    invoke-static {v1}, Lcom/twouich/adblock/TapClick;->trace(Ljava/lang/String;)V

    goto :refuse

    :up_nothing

    const-string v1, "relachement ignore : rien de cliquable sous le doigt"

    invoke-static {v1}, Lcom/twouich/adblock/TapClick;->trace(Ljava/lang/String;)V

    goto :refuse

    :not_up

    const/4 v1, 0x3

    if-ne v0, v1, :refuse

    # ACTION_CANCEL : geste abandonne, le relachement ne vaut plus rien.
    const/4 v0, 0x1

    sput-boolean v0, Lcom/twouich/adblock/TapClick;->moved:Z

    :refuse

    const/4 v0, 0x0

    return v0
.end method
