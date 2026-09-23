import Capacitor
import UIKit

/// Ouvre la story Instagram ou Facebook avec le visuel généré par l'app
/// déjà en fond — la seule chose que le Clipboard API du web ne permet
/// pas de faire, d'où ce petit plugin natif plutôt qu'un simple appel JS
/// (voir la tentative retirée dans index.html, commit 246c9fe). Meta
/// documente le même mécanisme pour les deux réseaux ("Sharing to
/// Stories") : seuls le schéma d'URL et le préfixe des clés du
/// presse-papier changent.
@objc(PartageStoriesPlugin)
public class PartageStoriesPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "PartageStoriesPlugin"
    public let jsName = "PartageStories"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "partagerStory", returnType: CAPPluginReturnPromise)
    ]

    // ID de l'app Meta "Populous Social" (developers.facebook.com) —
    // sans ce parametre, l'app cible s'ouvre mais ignore le contenu du
    // presse-papier : elle n'identifie pas l'app appelante comme une
    // source autorisee a preremplir une story. Partage entre les deux
    // reseaux, c'est le meme "Populous Social" cote Meta.
    private let idAppMeta = "1008098912281717"

    private struct Reseau {
        let schema: String
        let prefixeCle: String
        let urlProfil: String
    }

    private let reseaux: [String: Reseau] = [
        "instagram": Reseau(
            schema: "instagram-stories",
            prefixeCle: "com.instagram.sharedSticker",
            urlProfil: "https://www.instagram.com/populous_officiel/"
        ),
        "facebook": Reseau(
            schema: "facebook-stories",
            prefixeCle: "com.facebook.sharedSticker",
            urlProfil: "https://www.facebook.com/profile.php?id=61594127495751"
        )
    ]

    @objc func partagerStory(_ call: CAPPluginCall) {
        guard let base64 = call.getString("image"), let data = Data(base64Encoded: base64) else {
            call.reject("Image manquante ou invalide")
            return
        }
        let reseauNom = call.getString("reseau") ?? ""
        guard let reseau = reseaux[reseauNom] else {
            call.reject("Réseau inconnu (attendu : instagram ou facebook)")
            return
        }
        guard let url = URL(string: "\(reseau.schema)://share?source_application=\(idAppMeta)") else {
            call.resolve(["ouvert": false])
            return
        }
        DispatchQueue.main.async {
            guard UIApplication.shared.canOpenURL(url) else {
                call.resolve(["ouvert": false]) // app non installée
                return
            }
            var items: [String: Any] = [
                "\(reseau.prefixeCle).backgroundImage": data,
                "\(reseau.prefixeCle).contentURL": reseau.urlProfil
            ]
            // Facebook exige en plus l'ID d'app dans le presse-papier lui
            // meme (contrairement a Instagram, ou le parametre
            // source_application de l'URL suffit) — sans cette cle,
            // l'app s'ouvre mais reste sur le fil d'actualite au lieu
            // d'ouvrir le compositeur de story.
            if reseauNom == "facebook" {
                items["\(reseau.prefixeCle).appID"] = self.idAppMeta
            }
            let options: [UIPasteboard.OptionsKey: Any] = [.expirationDate: Date().addingTimeInterval(300)]
            UIPasteboard.general.setItems([items], options: options)
            // Appel natif (pas une navigation WKWebView) : bascule
            // directement sur l'app cible, sans l'alerte "Ouvrir dans
            // X ?" de Safari qui bloquait la détection en JS.
            UIApplication.shared.open(url, options: [:]) { ouvert in
                call.resolve(["ouvert": ouvert])
            }
        }
    }
}
