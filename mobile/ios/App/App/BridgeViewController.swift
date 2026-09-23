import Capacitor

/// Point d'enregistrement des plugins Capacitor "locaux" (écrits dans ce
/// projet, pas installés via npm) — ils n'apparaissent pas tout seuls
/// dans Package.swift comme @capacitor/push-notifications, il faut les
/// déclarer ici. Utilisé par SceneDelegate à la place de
/// CAPBridgeViewController tel quel.
class BridgeViewController: CAPBridgeViewController {
    override func capacitorDidLoad() {
        bridge?.registerPluginInstance(InstagramSharePlugin())
    }
}
