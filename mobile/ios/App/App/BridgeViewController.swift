import Capacitor

/// Point d'enregistrement des plugins Capacitor "locaux" (écrits dans ce
/// projet, pas installés via npm) — ils n'apparaissent pas tout seuls
/// dans Package.swift comme @capacitor/push-notifications, il faut les
/// déclarer ici. Utilisé par SceneDelegate à la place de
/// CAPBridgeViewController tel quel.
class BridgeViewController: CAPBridgeViewController {
    // Fond blanc partout tant que la page web n'est pas dessinee : sans ca,
    // le fond sombre par defaut du webview apparait pendant l'animation
    // d'ouverture (blanc -> gris fonce -> noir -> blanc), d'ou l'ouverture
    // saccadee constatee sur l'enregistrement d'ecran.
    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .white
        webView?.isOpaque = true
        webView?.backgroundColor = .white
        webView?.scrollView.backgroundColor = .white
    }

    override func capacitorDidLoad() {
        bridge?.registerPluginInstance(PartageStoriesPlugin())
    }
}
