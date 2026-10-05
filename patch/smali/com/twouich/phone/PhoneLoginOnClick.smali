# Leanback ne fait du titre d'en-tête (« Login to use the app ») qu'un libellé :
# le seul accès à la connexion est un menu d'actions que la télécommande ouvre
# et que le doigt n'atteint pas (mesuré le 05/10/2026 sur le Xiaomi 24095PCADG :
# tap, appui long et touche MENU ouvrent tous autre chose, et aucune entrée
# « Login (Preferred) / (Web) / with Turbo » n'apparaît). Ce listener est posé
# sur ce libellé par `MainFragment.twouichPhoneLoginBind()` — et uniquement là.
#
# Il ne connaît que le fragment : toute la décision (mode téléphone, session
# existante) est prise dans `MainFragment.twouichPhoneLogin()`, qui réutilise le
# chemin de connexion déjà livré par l'amont (`s4()` → AltLoginV2Activity). Rien
# n'est réimplémenté ici, et rien ne l'est pour la TV.
.class public Lcom/twouich/phone/PhoneLoginOnClick;
.super Ljava/lang/Object;
.implements Landroid/view/View$OnClickListener;

.field public final a:Lcom/s0und/s0undtv/fragments/MainFragment;

.method public constructor <init>(Lcom/s0und/s0undtv/fragments/MainFragment;)V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    iput-object p1, p0, Lcom/twouich/phone/PhoneLoginOnClick;->a:Lcom/s0und/s0undtv/fragments/MainFragment;
    return-void
.end method

.method public onClick(Landroid/view/View;)V
    .locals 1

    iget-object v0, p0, Lcom/twouich/phone/PhoneLoginOnClick;->a:Lcom/s0und/s0undtv/fragments/MainFragment;

    if-eqz v0, :twouich_login_click_done

    invoke-virtual {v0, p1}, Lcom/s0und/s0undtv/fragments/MainFragment;->twouichPhoneLogin(Landroid/view/View;)V

    :twouich_login_click_done
    return-void
.end method