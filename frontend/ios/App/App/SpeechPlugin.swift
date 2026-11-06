import AVFoundation
import Capacitor
import Speech

/// "Say it" on the iPhone: Apple's own speech recognition, on the device where it can be, tuned to
/// the expected word. Tap to start, tap to stop, like the web version; it reports how loud the
/// voice is for the wave, and gives back what it heard (the server still judges it).
@objc(SpeechPlugin)
public class SpeechPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "SpeechPlugin"
    public let jsName = "Speech"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "start", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "stop", returnType: CAPPluginReturnPromise),
    ]

    private let engine = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var heard = ""
    private var stopCall: CAPPluginCall?

    @objc func start(_ call: CAPPluginCall) {
        let word = call.getString("word") ?? ""
        let locale = call.getString("locale") ?? "en-IN"
        SFSpeechRecognizer.requestAuthorization { status in
            guard status == .authorized else {
                call.reject("Speech recognition isn't allowed: turn it on in Settings", "denied")
                return
            }
            self.askForMicrophone { granted in
                guard granted else {
                    call.reject("The microphone isn't allowed: turn it on in Settings", "denied")
                    return
                }
                DispatchQueue.main.async { self.begin(call, word: word, locale: locale) }
            }
        }
    }

    @objc func stop(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            self.stopCall = call
            self.stopListening()
            self.request?.endAudio()
            // The final result usually comes within a moment; don't wait forever for it.
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) { self.finish() }
        }
    }

    private func askForMicrophone(_ done: @escaping (Bool) -> Void) {
        if #available(iOS 17.0, *) {
            AVAudioApplication.requestRecordPermission(completionHandler: done)
        } else {
            AVAudioSession.sharedInstance().requestRecordPermission(done)
        }
    }

    private func begin(_ call: CAPPluginCall, word: String, locale: String) {
        guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: locale)) ?? SFSpeechRecognizer(),
              recognizer.isAvailable else {
            call.reject("Speech recognition isn't available right now")
            return
        }
        task?.cancel()
        stopListening()
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        request.contextualStrings = [word] // a hint: rare words are heard much better
        if recognizer.supportsOnDeviceRecognition {
            request.requiresOnDeviceRecognition = true // private, and works offline
        }
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playAndRecord, mode: .measurement, options: [.duckOthers, .defaultToSpeaker])
            try session.setActive(true, options: .notifyOthersOnDeactivation)
            let input = engine.inputNode
            input.removeTap(onBus: 0)
            input.installTap(onBus: 0, bufferSize: 1024, format: input.outputFormat(forBus: 0)) { [weak self] buffer, _ in
                request.append(buffer)
                self?.reportLevel(buffer)
            }
            engine.prepare()
            try engine.start()
        } catch {
            call.reject("Couldn't start the microphone")
            return
        }
        heard = ""
        self.request = request
        task = recognizer.recognitionTask(with: request) { [weak self] result, error in
            guard let self else { return }
            if let result {
                self.heard = result.bestTranscription.formattedString
            }
            if error != nil || result?.isFinal == true {
                self.finish()
            }
        }
        call.resolve()
    }

    private func stopListening() {
        if engine.isRunning {
            engine.stop()
        }
        engine.inputNode.removeTap(onBus: 0)
    }

    /// Answers the waiting stop() with what was heard, once.
    private func finish() {
        DispatchQueue.main.async {
            guard let call = self.stopCall else { return }
            self.stopCall = nil
            call.resolve(["heard": self.heard])
            self.task?.cancel()
            self.task = nil
            self.request = nil
            try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        }
    }

    /// How loud the voice is, 0 to 1, for the wave on the button.
    private func reportLevel(_ buffer: AVAudioPCMBuffer) {
        guard let samples = buffer.floatChannelData?[0], buffer.frameLength > 0 else { return }
        var sum: Float = 0
        for i in 0..<Int(buffer.frameLength) {
            sum += samples[i] * samples[i]
        }
        let rms = sqrt(sum / Float(buffer.frameLength))
        notifyListeners("level", data: ["level": min(1, Double(rms) * 8)])
    }
}
