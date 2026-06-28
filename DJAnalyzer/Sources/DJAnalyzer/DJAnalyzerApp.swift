import SwiftUI

/// Shuts down the persistent analyzer on app termination so the long-lived
/// `dj-analyze --serve` child is never orphaned (AC-8).
final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationWillTerminate(_ notification: Notification) {
        // Block briefly so the actor's shutdown (send {"cmd":"shutdown"} + terminate)
        // actually runs before the process exits. Timeout guards against any hang.
        // MUST be Task.detached: applicationWillTerminate is @MainActor, and a plain
        // Task would inherit main-actor isolation — it could never run while we block
        // the main thread on the semaphore (deadlock until timeout, child orphaned).
        let done = DispatchSemaphore(value: 0)
        Task.detached {
            await AnalyzerService.shutdown()
            done.signal()
        }
        _ = done.wait(timeout: .now() + 2)
    }
}

@main
struct DJAnalyzerApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .windowStyle(.titleBar)
        .windowToolbarStyle(.unified)
        .commands {
            CommandGroup(replacing: .newItem) {}
        }

        Settings {
            SettingsView()
        }
    }
}
