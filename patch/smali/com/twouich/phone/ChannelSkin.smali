# ChannelSkin — habillage de l'écran de chaîne, TELEPHONE SEULEMENT.
#
# L'écran de chaîne est le gabarit Leanback : le fragment repeint lui-même la
# carte (`details_frame`) et la bande d'actions avec la couleur de marque lue
# dans le theme — ce qui annule la surface sombre posée dans le gabarit — et
# pose l'image de banniere a largeur pleine en conservant son rapport, d'ou un
# aplat plein cadre puis une bande vide sous l'image.
#
# Les sites concerçés sont donc remplacés par les deux methodes ci-dessous :
# sur telephone la peinture runtime est ignoree (la surface du gabarit reste)
# et le bitmap de bandeau est recadre en 16:9. Sur la TV, chaque methode
# s'efface et laisse passer l'appel d'origine a l'identique.
#
# Garde : memes criteres que le lecteur (PlayerKeepAlive) —
# `uiMode == UI_MODE_TYPE_TELEVISION` ou `smallestScreenWidthDp >= 600` -> TV.
# La Freebox (mode TV, 540 dp) est donc bien reconnue comme television.
#
# ATTENTION (mesure du 23/10) : le contexte vient de l'APPELANT (view/context).
# `Resources.getSystem()` ne suit pas l'override d'ecran de l'emulateur : il
# annoncait 720 dp (TV) sur un ecran regle en 720x1280 (480 dp), et les deux
# greffes restaient silencieuses. Lire la configuration du contexte de l'app
# est la seule source fiable.
.class public final Lcom/twouich/phone/ChannelSkin;
.super Ljava/lang/Object;


.method public constructor <init>()V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method


# Vrai sur telephone, faux sur la TV (y compris un ecran 540 dp en mode TV).
# Sans contexte, on ne touche a rien : la TV est le comportement par defaut.
.method public static isPhone(Landroid/content/Context;)Z
    .locals 3

    if-eqz p0, :tv

    invoke-virtual {p0}, Landroid/content/Context;->getResources()Landroid/content/res/Resources;

    move-result-object v0

    invoke-virtual {v0}, Landroid/content/res/Resources;->getConfiguration()Landroid/content/res/Configuration;

    move-result-object v0

    iget v1, v0, Landroid/content/res/Configuration;->uiMode:I

    and-int/lit8 v1, v1, 0xf

    const/4 v2, 0x4

    # if-eq : « uiMode == UI_MODE_TYPE_TELEVISION » -> television.
    # (Un `if-ne` ici faisait exactement l'inverse : tout ecran non-TV, donc
    # tout telephone, etait declare television — mesure du 23/10.)
    if-eq v1, v2, :tv

    iget v1, v0, Landroid/content/res/Configuration;->smallestScreenWidthDp:I

    const/16 v2, 0x258

    # if-lt : « largeur < 600 dp » -> telephone. `if-ge` sautait dans le cas
    # oppose et rendait la garde toujours fausse sur telephone.
    if-lt v1, v2, :phone

    :tv
    const/4 v0, 0x0

    return v0

    :phone
    const/4 v0, 0x1

    return v0
.end method


# Peint le fond comme le fragment l'entend — sauf sur telephone, ou la surface
# sombre du gabarit doit rester (pas d'aplat de couleur de marque).
.method public static paint(Landroid/view/View;I)V
    .locals 2

    if-eqz p0, :done

    invoke-virtual {p0}, Landroid/view/View;->getContext()Landroid/content/Context;

    move-result-object v0

    invoke-static {v0}, Lcom/twouich/phone/ChannelSkin;->isPhone(Landroid/content/Context;)Z

    move-result v0

    if-eqz v0, :tv

    return-void

    :tv
    invoke-virtual {p0, p1}, Landroid/view/View;->setBackgroundColor(I)V

    :done
    return-void
.end method


# Recadre le bitmap de bandeau en 16:9 (centré, sans agrandir) pour qu'il
# remplisse la bande reservee du gabarit. Sur la TV, rend le bitmap tel quel.
# Ne modifie jamais la source : le meme bitmap peut servir ailleurs (avatar).
.method public static banner(Landroid/content/Context;Landroid/graphics/Bitmap;)Landroid/graphics/Bitmap;
    .locals 8

    if-eqz p1, :null

    invoke-static {p0}, Lcom/twouich/phone/ChannelSkin;->isPhone(Landroid/content/Context;)Z

    move-result v0

    if-eqz v0, :done

    invoke-virtual {p1}, Landroid/graphics/Bitmap;->getWidth()I

    move-result v1

    invoke-virtual {p1}, Landroid/graphics/Bitmap;->getHeight()I

    move-result v2

    if-lez v1, :done

    if-lez v2, :done

    # hauteur d'un cadre 16:9 a largeur pleine : v3 = v1 * 9 / 16
    mul-int/lit8 v3, v1, 0x9

    div-int/lit8 v3, v3, 0x10

    if-gt v3, v2, :too_wide

    # plus haut que 16:9 : on rogne la hauteur, centre
    if-ne v3, v2, :done

    sub-int v4, v2, v3

    div-int/lit8 v4, v4, 0x2

    const/4 v5, 0x0

    move v6, v1

    move v7, v3

    goto :crop

    :too_wide
    # plus large que 16:9 : on rogne les cotes, centre
    mul-int/lit8 v3, v2, 0x10

    div-int/lit8 v3, v3, 0x9

    if-ne v3, v1, :done

    sub-int v4, v1, v3

    div-int/lit8 v4, v4, 0x2

    const/4 v5, 0x0

    move v6, v3

    move v7, v2

    :crop
    :try_start
    invoke-static {p1, v4, v5, v6, v7}, Landroid/graphics/Bitmap;->createBitmap(Landroid/graphics/Bitmap;IIII)Landroid/graphics/Bitmap;

    move-result-object v0
    :try_end
    .catch Ljava/lang/Throwable; {:try_start .. :try_end} :catch

    return-object v0

    :catch
    move-exception v0

    :done
    :null
    return-object p1
.end method
