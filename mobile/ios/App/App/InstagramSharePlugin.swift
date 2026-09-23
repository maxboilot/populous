import Capacitor
import UIKit

/// Ouvre Instagram Stories avec le visuel généré par l'app déjà en fond
/// de la story — la seule chose que le Clipboard API du web ne permet
/// pas de faire, d'où ce petit plugin natif plutôt qu'un simple appel JS
/// (voir la tentative retirée dans index.html, commit 246c9fe).
@objc(InstagramSharePlugin)
public class InstagramSharePlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "InstagramSharePlugin"
    public let jsName = "InstagramShare"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "partagerStory", returnType: CAPPluginReturnPromise)
    ]

    // Clé privée qu'Instagram lit pour préremplir le fond d'une story,
    // documentée par Meta ("Sharing to Other Apps" côté iOS) — c'est
    // exactement pour écrire dans cette case précise que ce plugin
    // existe, un UIPasteboard classique (ou le Clipboard API web) ne
    // suffit pas.
    private let cleFondStory = "com.instagram.sharedSticker.backgroundImage"

    @objc func partagerStory(_ call: CAPPluginCall) {
        guard let base64 = call.getString("image"), let data = Data(base64Encoded: base64) else {
            call.reject("Image manquante ou invalide")
            return
        }
        guard let url = URL(string: "instagram-stories://share") else {
            call.resolve(["ouvert": false])
            return
        }
        DispatchQueue.main.async {
            guard UIApplication.shared.canOpenURL(url) else {
                call.resolve(["ouvert": false]) // Instagram non installé
                return
            }
            let items: [String: Any] = [self.cleFondStory: data]
            let options: [UIPasteboard.OptionsKey: Any] = [.expirationDate: Date().addingTimeInterval(300)]
            UIPasteboard.general.setItems([items], options: options)
            // Appel natif (pas une navigation WKWebView) : bascule
            // directement sur Instagram, sans l'alerte "Ouvrir dans
            // Instagram ?" de Safari qui bloquait la détection en JS.
            UIApplication.shared.open(url, options: [:]) { ouvert in
                call.resolve(["ouvert": ouvert])
            }
        }
    }
}
