.class final Lcom/twouich/adblock/SelfTest$Fake;
.super Ljava/lang/Object;
.implements Lz3/l;
.source "SelfTest.java"


# Source de donnees factice, utilisee par le self-test embarqué.
#
# Elle ne fait qu'une chose : servir un tableau d'octets en memoire, comme le
# ferait le reseau pour une playlist. Cela permet de faire traverser le VRAI
# AdBlockDataSource (c() puis read()) sans appareil reseau, et donc de verifier
# sur l'appareil la boucle de remplissage et le service par tranches -- les
# deux endroits qui rendaient une playlist vide et cassaient la lecture.


# instance fields
.field private a:[B

.field private b:I


# direct methods
.method public constructor <init>([B)V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    iput-object p1, p0, Lcom/twouich/adblock/SelfTest$Fake;->a:[B

    return-void
.end method


# virtual methods
# Ouverture : la "ressource" est en memoire, sa taille suffit.
.method public c(Lz3/p;)J
    .locals 2

    iget-object v0, p0, Lcom/twouich/adblock/SelfTest$Fake;->a:[B

    array-length v0, v0

    int-to-long v0, v0

    return-wide v0
.end method


.method public read([BII)I
    .locals 4

    # v0 = contenu, v1 = position courante, v2 = octets restants
    iget-object v0, p0, Lcom/twouich/adblock/SelfTest$Fake;->a:[B

    array-length v1, v0

    iget v2, p0, Lcom/twouich/adblock/SelfTest$Fake;->b:I

    sub-int v3, v1, v2

    # Dalvik : if-lez = "v3 <= 0" -> plus rien a servir, fin de flux.
    if-lez v3, :eof

    # longueur servie = min(demande, restant) :
    # if-lt (forme a deux registres, litterale) = "restant < demande" -> on sert
    # le restant, qui est deja dans v3 ; sinon la demande est plus petite.
    if-lt v3, p3, :copy

    move v3, p3

    :copy
    const/4 v1, 0x0

    invoke-static {v0, v2, p1, p2, v3}, Ljava/lang/System;->arraycopy(Ljava/lang/Object;ILjava/lang/Object;II)V

    add-int/2addr v2, v3

    iput v2, p0, Lcom/twouich/adblock/SelfTest$Fake;->b:I

    return v3

    :eof
    const/4 v0, -0x1

    return v0
.end method


.method public close()V
    .locals 0

    return-void
.end method


.method public e(Lz3/O;)V
    .locals 0

    return-void
.end method


.method public j()Ljava/util/Map;
    .locals 1

    const/4 v0, 0x0

    return-object v0
.end method


.method public n()Landroid/net/Uri;
    .locals 1

    const/4 v0, 0x0

    return-object v0
.end method
