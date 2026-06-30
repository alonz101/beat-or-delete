import Foundation
import SwiftUI

class AppSettings: ObservableObject {
    static let shared = AppSettings()

    @AppStorage("analyzerRoot") var analyzerRoot: String = ""
    @AppStorage("pythonPathOverride") var pythonPathOverride: String = ""

    // @AppStorage can't hold a dict, so we persist a JSON string and expose a
    // computed dictionary. Source of truth for threshold overrides; thresholds.json
    // on disk is derived (written on Save).
    @AppStorage("thresholdOverridesJSON") private var thresholdOverridesJSON: String = "{}"

    var thresholdOverrides: [String: Double] {
        get {
            guard let data = thresholdOverridesJSON.data(using: .utf8),
                  let map = try? JSONDecoder().decode([String: Double].self, from: data)
            else { return [:] }
            return map
        }
        set {
            if let data = try? JSONEncoder().encode(newValue),
               let str = String(data: data, encoding: .utf8) {
                thresholdOverridesJSON = str
            } else {
                thresholdOverridesJSON = "{}"
            }
        }
    }

    var effectivePythonPath: String? {
        pythonPathOverride.isEmpty ? nil : pythonPathOverride
    }

    // MARK: - thresholds.json transport (mirrors the Python side)

    /// `~/Library/Application Support/BeatOrDelete/` — same dir the frozen
    /// `dj-analyze` resolves via `core/runtime_config.py`.
    var beatOrDeleteSupportDir: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? URL(fileURLWithPath: NSHomeDirectory())
                .appendingPathComponent("Library/Application Support")
        return base.appendingPathComponent("BeatOrDelete", isDirectory: true)
    }

    var thresholdsFileURL: URL {
        beatOrDeleteSupportDir.appendingPathComponent("thresholds.json")
    }

    /// Write ONLY the non-default overrides to thresholds.json as a flat
    /// `{CONST_NAME: number}` object. If nothing differs from defaults, write `{}`
    /// so "all defaults" == "no override" on the Python side.
    func writeThresholdsFile() {
        var nonDefault: [String: Double] = [:]
        for (name, value) in thresholdOverrides {
            if let spec = ThresholdCatalog.spec(named: name), value != spec.defaultValue {
                nonDefault[name] = value
            }
        }

        let dir = beatOrDeleteSupportDir
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)

        let options: JSONSerialization.WritingOptions = nonDefault.isEmpty ? [] : [.sortedKeys]
        guard let data = try? JSONSerialization.data(withJSONObject: nonDefault, options: options) else {
            return
        }
        try? data.write(to: thresholdsFileURL, options: .atomic)
    }

    /// Load thresholds.json (if present) into `thresholdOverrides`. @AppStorage stays
    /// the source of truth, so this is only a derived-sync helper.
    func loadThresholdsFile() {
        guard let data = try? Data(contentsOf: thresholdsFileURL),
              let map = try? JSONDecoder().decode([String: Double].self, from: data)
        else { return }
        thresholdOverrides = map.filter { ThresholdCatalog.spec(named: $0.key) != nil }
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
