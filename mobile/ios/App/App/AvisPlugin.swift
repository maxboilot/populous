import Capacitor
import StoreKit

/// Invite native "Donnez votre avis" (SKStoreReviewController) — Apple décide
/// elle-même si le popup s'affiche vraiment (limite système : 3 fois max par
/// appareil sur 365 jours, aucun moyen de le savoir côté app), donc le JS
/// choisit juste un bon MOMENT pour le suggérer (voir demanderAvis() dans
/// index.html), pas si Apple l'affiche réellement.
@objc(AvisPlugin)
public class AvisPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "AvisPlugin"
    public let jsName = "Avis"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "demander", returnType: CAPPluginReturnPromise)
    ]

    @objc func demander(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            if let scene = self.bridge?.viewController?.view.window?.windowScene {
                SKStoreReviewController.requestReview(in: scene)
            }
            call.resolve()
        }
    }
}
