# WatchPoints — points de visionnage par chaine, comptes localement, TELEPHONE.
#
# Aucune API : une minute regardee = un point, range dans des SharedPreferences
# dediees, cle = login de la chaine. Le comptage est pilote par le cycle de vie
# du lecteur : `enter()` a chaque passe de disposition (onResume, focus,
# rotation, mises en page du chat) solde les minutes entieres ecoulees, et
# `leave()` (onPause) ferme la session.
#
# `enter()` est idempotent : rappele avec la meme chaine, il ne fait que solder
# (`flush`), sans remettre le depart a zero — c'est ce qui permet de le cabler
# sur chaque passe de disposition sans perdre le temps deja couru.
.class public final Lcom/twouich/phone/WatchPoints;
.super Ljava/lang/Object;


# SharedPreferences dediees : ne touche pas aux prefs de l'app.
.field private static final PREFS:Ljava/lang/String; = "twouich_watch_points"

# Chaine en cours de comptage (null hors session) et depart en millisecondes.
.field private static channel:Ljava/lang/String;

.field private static since:J

# Temps deja couru avant une pause de lecture, rendu a la reprise. Une pause
# ne doit pas fabriquer de minute : la cadence met le temps de cote au lieu de
# le solder, et `leave()` (onPause) remet ce reliquat a zero.
.field private static carry:J


.method public constructor <init>()V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method


.method private static prefs(Landroid/content/Context;)Landroid/content/SharedPreferences;
    .locals 2

    const-string v0, "twouich_watch_points"

    const/4 v1, 0x0

    invoke-virtual {p0, v0, v1}, Landroid/content/Context;->getSharedPreferences(Ljava/lang/String;I)Landroid/content/SharedPreferences;

    move-result-object v0

    return-object v0
.end method


# Solde les minutes entieres courues et avance le depart d'autant : la seconde
# en cours n'est pas perdue, elle continue de courir.
.method private static flush(Landroid/content/Context;)V
    .locals 12

    sget-wide v2, Lcom/twouich/phone/WatchPoints;->since:J

    const-wide/16 v0, 0x0

    cmp-long v10, v2, v0

    # `if-eqz` : cmp-long rend 0 quand `since` est 0, c'est-a-dire hors session.
    if-eqz v10, :done

    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v0

    sub-long v4, v0, v2

    const-wide/32 v8, 0xea60

    div-long v6, v4, v8

    const-wide/16 v4, 0x0

    cmp-long v10, v6, v4

    # `if-lez` : rien a solder tant qu'aucune minute entiere n'est ecoulee.
    if-lez v10, :done

    long-to-int v11, v6

    invoke-static {p0}, Lcom/twouich/phone/WatchPoints;->prefs(Landroid/content/Context;)Landroid/content/SharedPreferences;

    move-result-object v0

    sget-object v1, Lcom/twouich/phone/WatchPoints;->channel:Ljava/lang/String;

    const/4 v2, 0x0

    invoke-interface {v0, v1, v2}, Landroid/content/SharedPreferences;->getInt(Ljava/lang/String;I)I

    move-result v2

    add-int/2addr v2, v11

    invoke-interface {v0}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;

    move-result-object v0

    invoke-interface {v0, v1, v2}, Landroid/content/SharedPreferences$Editor;->putInt(Ljava/lang/String;I)Landroid/content/SharedPreferences$Editor;

    move-result-object v0

    invoke-interface {v0}, Landroid/content/SharedPreferences$Editor;->apply()V

    # Trace de solde : sans elle, une pastille bloquee a 0 ne dit pas si le
    # temps n'arrive jamais ou si l'ecriture pref echoue.
    const-string v8, "Twouich"

    const-string v9, "points : solde ecrit"

    invoke-static {v8, v9}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I

    sget-wide v2, Lcom/twouich/phone/WatchPoints;->since:J

    const-wide/32 v4, 0xea60

    mul-long v4, v6, v4

    add-long v2, v2, v4

    sput-wide v2, Lcom/twouich/phone/WatchPoints;->since:J

    :done
    return-void
.end method


# Ouvre (ou poursuit) la session de comptage pour `channel`.
.method public static enter(Landroid/content/Context;Ljava/lang/String;)V
    .locals 4

    if-eqz p0, :done

    if-eqz p1, :done

    invoke-virtual {p1}, Ljava/lang/String;->length()I

    move-result v0

    # `if-eqz` : longueur nulle -> pas de chaine, rien a compter.
    if-eqz v0, :done

    invoke-static {p0}, Lcom/twouich/phone/WatchPoints;->flush(Landroid/content/Context;)V

    sget-object v0, Lcom/twouich/phone/WatchPoints;->channel:Ljava/lang/String;

    invoke-virtual {p1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z

    move-result v0

    # `if-nez` : equals != 0 (meme chaine) -> on garde la session et on sort.
    # Mesure du 23/10 : avec `if-eqz`, c'etait l'inverse — chaque passe de
    # disposition REMETTAIT le depart a maintenant, et le compteur restait
    # definitivement a 0. Polarite Dalvik, encore (§3 d'AGENTS.md).
    if-nez v0, :done

    sput-object p1, Lcom/twouich/phone/WatchPoints;->channel:Ljava/lang/String;

    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v0

    sput-wide v0, Lcom/twouich/phone/WatchPoints;->since:J

    const-wide/16 v0, 0x0

    sput-wide v0, Lcom/twouich/phone/WatchPoints;->carry:J

    const-string v2, "Twouich"

    const-string v3, "points : session ouverte"

    invoke-static {v2, v3}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I

    :done
    return-void
.end method


# Met le compteur en accord avec l'etat de lecture. En pause, le temps couru
# passe dans `carry` et `since` revient a zero : plus aucune minute ne se
# solde tant que la video est arretee. A la reprise, `since` repart en arriere
# de `carry`, donc le reliquat est rendu sans etre invente.
.method public static setPlaying(Landroid/content/Context;Z)V
    .locals 6

    sget-wide v2, Lcom/twouich/phone/WatchPoints;->since:J

    const-wide/16 v0, 0x0

    cmp-long v4, v2, v0

    # `if-eqz` : p1 faux (0) -> branche de pause. Un `if-nez` inversait
    # pause et lecture, donc le compteur se figeait des le premier tir
    # (mesure du 24/10 : `lecture en cours` suivi de `pause lecture`).
    if-eqz p1, :paused

    # Deja en cours : rien a rendre.
    if-nez v4, :done

    sget-object v4, Lcom/twouich/phone/WatchPoints;->channel:Ljava/lang/String;

    # Sans chaine, il n'y a pas de session a reprendre.
    if-eqz v4, :done

    sget-wide v2, Lcom/twouich/phone/WatchPoints;->carry:J

    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v0

    sub-long v2, v0, v2

    sput-wide v2, Lcom/twouich/phone/WatchPoints;->since:J

    const-wide/16 v2, 0x0

    sput-wide v2, Lcom/twouich/phone/WatchPoints;->carry:J

    const-string v2, "Twouich"

    const-string v3, "points : reprise lecture"

    invoke-static {v2, v3}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I

    return-void

    :paused
    # Deja en pause : le temps est deja mis de cote.
    if-eqz v4, :done

    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v0

    sget-wide v2, Lcom/twouich/phone/WatchPoints;->since:J

    sub-long v0, v0, v2

    sput-wide v0, Lcom/twouich/phone/WatchPoints;->carry:J

    const-wide/16 v0, 0x0

    sput-wide v0, Lcom/twouich/phone/WatchPoints;->since:J

    const-string v2, "Twouich"

    const-string v3, "points : pause lecture"

    invoke-static {v2, v3}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I

    :done
    return-void
.end method


# Solde la session en cours sans l'ouvrir ni la fermer : c'est le geste de la
# cadence (rafraichir l'etiquette chaque minute), jamais un redemarrage.
.method public static tick(Landroid/content/Context;)V
    .locals 0

    invoke-static {p0}, Lcom/twouich/phone/WatchPoints;->flush(Landroid/content/Context;)V

    return-void
.end method


# Ferme la session (lecteur en pause) : solde le temps couru.
.method public static leave(Landroid/content/Context;)V
    .locals 2

    invoke-static {p0}, Lcom/twouich/phone/WatchPoints;->flush(Landroid/content/Context;)V

    const/4 v0, 0x0

    sput-object v0, Lcom/twouich/phone/WatchPoints;->channel:Ljava/lang/String;

    const-wide/16 v0, 0x0

    sput-wide v0, Lcom/twouich/phone/WatchPoints;->since:J

    sput-wide v0, Lcom/twouich/phone/WatchPoints;->carry:J

    return-void
.end method


# Cle du choix : « @ » ne peut pas commencer un login Twitch, donc elle ne peut
# pas ecraser le compteur d'une chaine (pas de champ dedie : smali n'en a pas
# besoin et un champ mort se relit comme une intention).
# La pastille est-elle masquee par choix ? Defaut : affichee (false).
.method public static hidden(Landroid/content/Context;)Z
    .locals 3

    const/4 v1, 0x0

    # Sans contexte, on ne masque pas : un appel defectueux ne doit pas faire
    # disparaitre l'affichage, seulement le laisser tel qu'il est.
    if-eqz p0, :answer

    invoke-static {p0}, Lcom/twouich/phone/WatchPoints;->prefs(Landroid/content/Context;)Landroid/content/SharedPreferences;

    move-result-object v0

    const-string v2, "@badge_hidden"

    invoke-interface {v0, v2, v1}, Landroid/content/SharedPreferences;->getBoolean(Ljava/lang/String;Z)Z

    move-result v1

    :answer
    return v1
.end method


# Enregistre le choix : une ecriture par appui, pas une par minute.
.method public static setHidden(Landroid/content/Context;Z)V
    .locals 4

    if-eqz p0, :done

    invoke-static {p0}, Lcom/twouich/phone/WatchPoints;->prefs(Landroid/content/Context;)Landroid/content/SharedPreferences;

    move-result-object v0

    invoke-interface {v0}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;

    move-result-object v1

    const-string v2, "@badge_hidden"

    invoke-interface {v1, v2, p1}, Landroid/content/SharedPreferences$Editor;->putBoolean(Ljava/lang/String;Z)Landroid/content/SharedPreferences$Editor;

    move-result-object v1

    invoke-interface {v1}, Landroid/content/SharedPreferences$Editor;->apply()V

    # Une ligne par choix : elle dit au journal si la pastille a disparu par
    # preference ou pour une autre raison.
    if-eqz p1, :visible

    const-string v2, "points : pastille masquee (choix)"

    goto :trace

    :visible
    const-string v2, "points : pastille affichee (choix)"

    :trace
    const-string v3, "Twouich"

    invoke-static {v3, v2}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I

    :done
    return-void
.end method


# Masque la pastille et ne trace QUE le passage visible -> masquee : la cadence
# repasse toutes les 15 s, une ligne par passage remplirait le journal. La
# raison vient de l'appelant (chaine inconnue, choix, incrustation).
.method public static hide(Landroid/view/View;Ljava/lang/String;)V
    .locals 3

    if-eqz p0, :done

    invoke-virtual {p0}, Landroid/view/View;->getVisibility()I

    move-result v0

    const/16 v1, 0x8

    invoke-virtual {p0, v1}, Landroid/view/View;->setVisibility(I)V

    # `if-nez` : deja masquee (non nul) -> rien de neuf a dire.
    if-nez v0, :done

    const-string v1, "Twouich"

    invoke-static {v1, p1}, Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I

    :done
    return-void
.end method


# Bascule le choix et renvoie le nouvel etat (true = masquee).
.method public static toggle(Landroid/content/Context;)Z
    .locals 2

    invoke-static {p0}, Lcom/twouich/phone/WatchPoints;->hidden(Landroid/content/Context;)Z

    move-result v0

    const/4 v1, 0x1

    # `if-eqz` : visible (0) -> on masque, v1 reste 1. Deja masquee -> on
    # affiche (v1 = 0). Inverser ces deux cas rendrait le bouton inoperant.
    if-eqz v0, :apply

    const/4 v1, 0x0

    :apply
    invoke-static {p0, v1}, Lcom/twouich/phone/WatchPoints;->setHidden(Landroid/content/Context;Z)V

    return v1
.end method


.method public static points(Landroid/content/Context;Ljava/lang/String;)I
    .locals 3

    if-eqz p0, :zero

    if-eqz p1, :zero

    invoke-static {p0}, Lcom/twouich/phone/WatchPoints;->prefs(Landroid/content/Context;)Landroid/content/SharedPreferences;

    move-result-object v0

    const/4 v1, 0x0

    invoke-interface {v0, p1, v1}, Landroid/content/SharedPreferences;->getInt(Ljava/lang/String;I)I

    move-result v0

    return v0

    :zero
    const/4 v0, 0x0

    return v0
.end method


# Etiquette de la pastille ("0 pt", "1 pt", "12 pts"), ou null quand aucune
# chaine n'est connue : le lecteur s'en sert pour masquer la vue. Le zero est
# affiche — une pastille qui n'apparait qu'apres la premiere minute se lit comme
# une fonctionnalite absente.
.method public static label(Landroid/content/Context;Ljava/lang/String;)Ljava/lang/String;
    .locals 5

    if-eqz p1, :none

    invoke-virtual {p1}, Ljava/lang/String;->length()I

    move-result v1

    # `if-eqz` : longueur nulle -> pas de chaine, la pastille se masque.
    if-eqz v1, :none

    invoke-static {p0, p1}, Lcom/twouich/phone/WatchPoints;->points(Landroid/content/Context;Ljava/lang/String;)I

    move-result v0

    new-instance v1, Ljava/lang/StringBuilder;

    invoke-direct {v1}, Ljava/lang/StringBuilder;-><init>()V

    invoke-virtual {v1, v0}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    const-string v2, " pt"

    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    const/4 v3, 0x1

    # `if-le` : 0 et 1 restent au singulier (« 0 pt », « 1 pt »), le pluriel
    # commence a 2. Un `if-gt` — polarite inverse, mesuree a l'ecran le 23/10 —
    # affichait « 0 pts » et aurait donne « 2 pt ».
    if-le v0, v3, :no_plural

    const-string v2, "s"

    invoke-virtual {v1, v2}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    :no_plural
    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    return-object v0

    :none
    const/4 v0, 0x0

    return-object v0
.end method
