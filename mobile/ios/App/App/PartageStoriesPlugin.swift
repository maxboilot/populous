import Capacitor
import UIKit
import Photos

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
        CAPPluginMethod(name: "partagerStory", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "partagerLinkedIn", returnType: CAPPluginReturnPromise)
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

    /// LinkedIn n'a pas d'API publique pour precharger une image dans son
    /// compositeur, et son champ de texte n'accepte pas le collage d'image
    /// (constate sur iPhone). Voie fiable : l'image est enregistree dans
    /// Photos (a ajouter avec l'icone photo du post), le texte est copie
    /// dans le presse-papier, et on ouvre LinkedIn (lien universel : l'app
    /// si elle est installee, sinon Safari).
    @objc func partagerLinkedIn(_ call: CAPPluginCall) {
        guard let base64 = call.getString("image"), let data = Data(base64Encoded: base64),
              let image = UIImage(data: data) else {
            call.reject("Image manquante ou invalide")
            return
        }
        let texte = call.getString("texte") ?? ""
        var composants = URLComponents(string: "https://www.linkedin.com/feed/")!
        composants.queryItems = [
            URLQueryItem(name: "shareActive", value: "true"),
            URLQueryItem(name: "text", value: texte)
        ]
        guard let url = composants.url else {
            call.resolve(["ouvert": false, "app": false, "photo": false])
            return
        }
        PHPhotoLibrary.requestAuthorization(for: .addOnly) { statut in
            let autorise = (statut == .authorized || statut == .limited)
            let ouvrir = { (photoEnregistree: Bool) in
                DispatchQueue.main.async {
                    let options: [UIPasteboard.OptionsKey: Any] = [.expirationDate: Date().addingTimeInterval(600)]
                    UIPasteboard.general.setItems([["public.utf8-plain-text": texte]], options: options)
                    UIApplication.shared.open(url, options: [.universalLinksOnly: true]) { dansApp in
                        if dansApp {
                            call.resolve(["ouvert": true, "app": true, "photo": photoEnregistree])
                        } else {
                            UIApplication.shared.open(url, options: [:]) { ouvert in
                                call.resolve(["ouvert": ouvert, "app": false, "photo": photoEnregistree])
                            }
                        }
                    }
                }
            }
            guard autorise else { ouvrir(false); return }
            PHPhotoLibrary.shared().performChanges({
                PHAssetCreationRequest.creationRequestForAsset(from: image)
            }) { ok, _ in ouvrir(ok) }
        }
    }
}
