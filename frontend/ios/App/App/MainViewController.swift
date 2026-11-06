import Capacitor

/// The app's web view, with our own native plugins added.
class MainViewController: CAPBridgeViewController {
    override open func capacitorDidLoad() {
        bridge?.registerPluginInstance(SpeechPlugin())
    }
}
