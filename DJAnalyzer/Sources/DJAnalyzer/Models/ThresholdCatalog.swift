import Foundation

// MUST stay in sync with core/config.py
// Each spec's `name` is the EXACT Python constant; `defaultValue` mirrors core/config.py.
// (CI parity grep is out of scope here — this comment is the contract anchor.)

struct ThresholdSpec: Identifiable {
    var id: String { name }
    let name: String          // EXACT python const, e.g. "DYNAMIC_RANGE_BLOCKING_DB"
    let label: String         // human label
    let category: String
    let defaultValue: Double
    let lessThan: String?     // if set, this field's value must be < the named field's value
    let greaterThan: String?  // if set, this field's value must be > the named field's value

    init(
        _ name: String,
        _ label: String,
        _ category: String,
        _ defaultValue: Double,
        lessThan: String? = nil,
        greaterThan: String? = nil
    ) {
        self.name = name
        self.label = label
        self.category = category
        self.defaultValue = defaultValue
        self.lessThan = lessThan
        self.greaterThan = greaterThan
    }
}

enum ThresholdCatalog {
    static let all: [ThresholdSpec] = [
        // --- Spectral ---
        ThresholdSpec("SPECTRAL_FAKE_LOSSLESS_RATIO", "Fake-lossless coverage floor", "Spectral", 0.85,
                      lessThan: "SPECTRAL_SUSPECT_RATIO"),
        ThresholdSpec("SPECTRAL_SUSPECT_RATIO", "Suspect coverage floor", "Spectral", 0.92),

        // --- Clipping ---
        ThresholdSpec("CLIP_BLOCKING_EVENTS", "Clipping events → blocking", "Clipping", 20),
        ThresholdSpec("CLIP_MARGINAL_EVENTS", "Clipping events → review", "Clipping", 3,
                      lessThan: "CLIP_BLOCKING_EVENTS"),
        ThresholdSpec("CLIP_BLOCKING_MS", "Longest clip ms → blocking", "Clipping", 100),
        ThresholdSpec("CLIP_MARGINAL_MS", "Longest clip ms → review", "Clipping", 10,
                      lessThan: "CLIP_BLOCKING_MS"),

        // --- Dynamics ---
        ThresholdSpec("DYNAMIC_RANGE_BLOCKING_DB", "Dynamic range dB → blocking", "Dynamics", 4,
                      lessThan: "DYNAMIC_RANGE_MARGINAL_DB"),
        ThresholdSpec("DYNAMIC_RANGE_MARGINAL_DB", "Dynamic range dB → review", "Dynamics", 6),

        // --- Loudness ---
        ThresholdSpec("LUFS_CLUB_MIN", "LUFS club min", "Loudness", -18,
                      lessThan: "LUFS_CLUB_MAX"),
        ThresholdSpec("LUFS_CLUB_MAX", "LUFS club max", "Loudness", -6),
        ThresholdSpec("TRUE_PEAK_HOT_DBFS", "True-peak hot dBFS", "Loudness", -0.03),

        // --- Integrity ---
        ThresholdSpec("NOISE_FLOOR_MARGINAL_DBFS", "Noise floor dBFS → review", "Integrity", -45),
        ThresholdSpec("DC_OFFSET_THRESHOLD", "DC offset threshold", "Integrity", 0.005),
        ThresholdSpec("LSB_ZERO_RATIO_FAKE_24BIT", "Fake-24bit LSB-zero ratio", "Integrity", 0.95),

        // --- Authenticity ---
        ThresholdSpec("BITRATE_320_THRESHOLD", "Declared-320 bitrate floor", "Authenticity", 310000),

        // --- Vinyl ---
        ThresholdSpec("VINYL_WOW_FLUTTER_FLAG", "Wow & flutter flag %", "Vinyl", 0.15),
        ThresholdSpec("VINYL_HUM_STRONG_DB", "Hum strong dB → review", "Vinyl", 25),
    ]

    static func spec(named name: String) -> ThresholdSpec? {
        all.first { $0.name == name }
    }

    /// Categories in stable insertion order (first appearance in `all`).
    static var categories: [String] {
        var seen = Set<String>()
        var ordered: [String] = []
        for spec in all where !seen.contains(spec.category) {
            seen.insert(spec.category)
            ordered.append(spec.category)
        }
        return ordered
    }
}
