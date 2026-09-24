import UIKit
import Capacitor
import UserNotifications

class SceneDelegate: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?

    func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options connectionOptions: UIScene.ConnectionOptions) {
        guard let windowScene = scene as? UIWindowScene else { return }

        window = UIWindow(windowScene: windowScene)
        window?.backgroundColor = .white
        window?.rootViewController = BridgeViewController() // enregistre InstagramSharePlugin, voir ce fichier
        window?.makeKeyAndVisible()

        SceneDelegateProxy.shared.scene(scene, willConnectTo: session, options: connectionOptions)
    }

    func scene(_ scene: UIScene, openURLContexts URLContexts: Set<UIOpenURLContext>) {
        SceneDelegateProxy.shared.scene(scene, openURLContexts: URLContexts)
    }

    func scene(_ scene: UIScene, continue userActivity: NSUserActivity) {
        SceneDelegateProxy.shared.scene(scene, continue: userActivity)
    }

    // Pastille rouge des notifications (aps.badge = 1, cf. notifier_push.py) :
    // remise à zéro dès que l'app devient active, et bannières retirées du
    // centre de notifications. Ici et non dans AppDelegate : l'app utilise
    // les scènes (UIApplicationSceneManifest), donc
    // applicationDidBecomeActive n'est jamais appelé.
    func sceneDidBecomeActive(_ scene: UIScene) {
        if #available(iOS 16.0, *) {
            UNUserNotificationCenter.current().setBadgeCount(0)
        } else {
            UIApplication.shared.applicationIconBadgeNumber = 0
        }
        UNUserNotificationCenter.current().removeAllDeliveredNotifications()
    }
}
