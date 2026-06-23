import Foundation
import SwiftUI

class AppSettings: ObservableObject {
    static let shared = AppSettings()

    @AppStorage("analyzerRoot") var analyzerRoot: String = ""
    @AppStorage("pythonPathOverride") var pythonPathOverride: String = ""

    var effectivePythonPath: String? {
        pythonPathOverride.isEmpty ? nil : pythonPathOverride
    }

    var resolvedAnalyzerRoot: String {
        if !analyzerRoot.isEmpty { return analyzerRoot }
        // Default: sibling of the .app bundle, or cwd
        if let bundlePath = Bundle.main.bundlePath as String? {
            let candidate = URL(fileURLWithPath: bundlePath)
                .deletingLastPathComponent()
                .appendingPathComponent("analyzer")
                .path
            if FileManager.default.fileExists(atPath: candidate) { return candidate }
        }
        return FileManager.default.currentDirectoryPath
    }
}
