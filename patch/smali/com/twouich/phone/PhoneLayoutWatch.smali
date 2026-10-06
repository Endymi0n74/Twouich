.class public final Lcom/twouich/phone/PhoneLayoutWatch;
.super Ljava/lang/Object;
.implements Landroid/view/ViewTreeObserver$OnGlobalLayoutListener;
.implements Landroid/view/View$OnApplyWindowInsetsListener;

# Veille de disposition du lecteur telephone (posee par
# twouichPhoneStackedLayout, telephone seul).
#
# Mesure du 06/10 sur le Xiaomi (Android 16) : en passant de portrait en
# paysage EN COURS DE LECTURE, la disposition restait celle du portrait avec
# des dimensions perimees — video pleine largeur de 686 px (image lettree au
# MILIEU de l'ecran), chat en lambeau de 144 px sous la video, saisie pleine
# largeur en bas. Le rappel onConfigurationChanged arrive AVANT la re-mesure
# de l'arbre : la disposition s'appliquait avec les boites de l'orientation
# precedente, et rien ne la reappliquait ensuite.
#
# Deux declencheurs rappellent la disposition :
#   - onGlobalLayout : la boite de mise en page change (rotation) — le rappel
#     part une fois la mesure faite, la disposition lit alors des dimensions
#     fraiches ;
#   - onApplyWindowInsets : le clavier s'ouvre/ferme sans que la boite bouge
#     (fenetre edge-to-edge : adjustResize ne redimensionne plus rien).
#
# La signature de garde est (largeur, hauteur utile, bas de la zone visible) :
# le clavier reduit la zone VISIBLE sans toucher a la boite, et c'est ce
# troisieme signal qui declenche le repositionnement de la saisie. La frame
# visible fait foi — les insets IME ne rendaient RIEN sur l'appareil du 06/10
# (getRootWindowInsets() et le rappel d'insets rendaient 0 clavier ouvert).
#
# La disposition ne modifie ni la boite ni la zone visible : le rappel se
# stabilise au passage suivant (aucune boucle — sans cette garde, chaque
# setLayoutParams relancerait la disposition en boucle).

.field private final activity:Lcom/s0und/s0undtv/activities/PlayerActivity;
.field private final anchor:Landroid/view/View;
.field private lastW:I
.field private lastH:I
.field private lastVb:I

.method public constructor <init>(Lcom/s0und/s0undtv/activities/PlayerActivity;Landroid/view/View;)V
    .locals 1

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    iput-object p1, p0, Lcom/twouich/phone/PhoneLayoutWatch;->activity:Lcom/s0und/s0undtv/activities/PlayerActivity;

    iput-object p2, p0, Lcom/twouich/phone/PhoneLayoutWatch;->anchor:Landroid/view/View;

    invoke-virtual {p2}, Landroid/view/View;->getViewTreeObserver()Landroid/view/ViewTreeObserver;

    move-result-object v0

    invoke-virtual {v0, p0}, Landroid/view/ViewTreeObserver;->addOnGlobalLayoutListener(Landroid/view/ViewTreeObserver$OnGlobalLayoutListener;)V

    invoke-virtual {p2, p0}, Landroid/view/View;->setOnApplyWindowInsetsListener(Landroid/view/View$OnApplyWindowInsetsListener;)V

    return-void
.end method

.method public onApplyWindowInsets(Landroid/view/View;Landroid/view/WindowInsets;)Landroid/view/WindowInsets;
    .locals 1

    invoke-direct {p0}, Lcom/twouich/phone/PhoneLayoutWatch;->update()V

    return-object p2
.end method

.method public onGlobalLayout()V
    .locals 0

    invoke-direct {p0}, Lcom/twouich/phone/PhoneLayoutWatch;->update()V

    return-void
.end method

.method private update()V
    .locals 6

    iget-object v0, p0, Lcom/twouich/phone/PhoneLayoutWatch;->anchor:Landroid/view/View;

    invoke-virtual {v0}, Landroid/view/View;->getParent()Landroid/view/ViewParent;

    move-result-object v0

    instance-of v1, v0, Landroid/view/View;

    if-eqz v1, :watch_done

    check-cast v0, Landroid/view/View;

    invoke-virtual {v0}, Landroid/view/View;->getWidth()I

    move-result v1

    invoke-virtual {v0}, Landroid/view/View;->getHeight()I

    move-result v2

    if-lez v1, :watch_done

    if-lez v2, :watch_done

    invoke-virtual {v0}, Landroid/view/View;->getPaddingTop()I

    move-result v3

    sub-int/2addr v2, v3

    invoke-virtual {v0}, Landroid/view/View;->getPaddingBottom()I

    move-result v3

    sub-int/2addr v2, v3

    # Le clavier ne bouge pas la boite mais reduit la zone visible : troisieme
    # signal de la signature (voir l'entete, les insets IME ne rendaient rien).
    new-instance v3, Landroid/graphics/Rect;

    invoke-direct {v3}, Landroid/graphics/Rect;-><init>()V

    iget-object v4, p0, Lcom/twouich/phone/PhoneLayoutWatch;->anchor:Landroid/view/View;

    invoke-virtual {v4, v3}, Landroid/view/View;->getWindowVisibleDisplayFrame(Landroid/graphics/Rect;)V

    iget v5, v3, Landroid/graphics/Rect;->bottom:I

    iget v3, p0, Lcom/twouich/phone/PhoneLayoutWatch;->lastW:I

    if-ne v3, v1, :watch_changed

    iget v3, p0, Lcom/twouich/phone/PhoneLayoutWatch;->lastH:I

    if-ne v3, v2, :watch_changed

    iget v3, p0, Lcom/twouich/phone/PhoneLayoutWatch;->lastVb:I

    if-ne v3, v5, :watch_changed

    goto :watch_done

    :watch_changed
    iput v1, p0, Lcom/twouich/phone/PhoneLayoutWatch;->lastW:I

    iput v2, p0, Lcom/twouich/phone/PhoneLayoutWatch;->lastH:I

    iput v5, p0, Lcom/twouich/phone/PhoneLayoutWatch;->lastVb:I

    const-string v0, "Twouich"

    const-string v1, "veille : boite/clavier changes, disposition reappliquee"

    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I

    iget-object v0, p0, Lcom/twouich/phone/PhoneLayoutWatch;->activity:Lcom/s0und/s0undtv/activities/PlayerActivity;

    invoke-virtual {v0}, Lcom/s0und/s0undtv/activities/PlayerActivity;->twouichPhoneRelayout()V

    :watch_done
    return-void
.end method
