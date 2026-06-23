import Foundation

struct AudioFormat: Codable {
    let container: String
    let codec: String
    let sampleRate: Int
    let bitDepth: Int
    let bitrate: Int
    let duration: Double
    let channels: Int

    enum CodingKeys: String, CodingKey {
        case container, codec
        case sampleRate = "sample_rate"
        case bitDepth = "bit_depth"
        case bitrate, duration, channels
    }
}

struct Authenticity: Codable {
    let lameHeader: Bool
    let spectralCoverageRatio: Double
    let topFreqHz: Double
    let nyquistHz: Double
    let spectralVerdict: String
    let suspectedOrigin: String
    let lsbZeroRatio: Double

    enum CodingKeys: String, CodingKey {
        case lameHeader = "lame_header"
        case spectralCoverageRatio = "spectral_coverage_ratio"
        case topFreqHz = "top_freq_hz"
        case nyquistHz = "nyquist_hz"
        case spectralVerdict = "spectral_verdict"
        case suspectedOrigin = "suspected_origin"
        case lsbZeroRatio = "lsb_zero_ratio"
    }
}

struct Playability: Codable {
    let clipEventsL: Int
    let clipEventsR: Int
    let clipMaxMs: Double
    let peakDbfs: Double
    let loudnessLufs: Double
    let truePeakLDbfs: Double
    let truePeakRDbfs: Double
    let dynamicRangeDb: Double
    let noiseFloorDbfs: Double
    let dcOffsetL: Double
    let dcOffsetR: Double

    enum CodingKeys: String, CodingKey {
        case clipEventsL = "clip_events_L"
        case clipEventsR = "clip_events_R"
        case clipMaxMs = "clip_max_ms"
        case peakDbfs = "peak_dbfs"
        case loudnessLufs = "loudness_lufs"
        case truePeakLDbfs = "true_peak_L_dbfs"
        case truePeakRDbfs = "true_peak_R_dbfs"
        case dynamicRangeDb = "dynamic_range_db"
        case noiseFloorDbfs = "noise_floor_dbfs"
        case dcOffsetL = "dc_offset_L"
        case dcOffsetR = "dc_offset_R"
    }
}

struct VinylInfo: Codable {
    let vinylRip: Bool
    let wowFlutterWrms: Double?
    let humHz: Double?
    let vinylGrade: String?
    let crackleCount: Int?

    enum CodingKeys: String, CodingKey {
        case vinylRip = "vinyl_rip"
        case wowFlutterWrms = "wow_flutter_wrms"
        case humHz = "hum_hz"
        case vinylGrade = "vinyl_grade"
        case crackleCount = "crackle_count"
    }
}

struct AnalysisResult: Codable, Identifiable {
    var id: String { filePath ?? filename }
    let filename: String
    let filePath: String?
    let format: AudioFormat
    let authenticity: Authenticity
    let playability: Playability
    let vinyl: VinylInfo?
    let clickCount: Int
    let flags: [String]
    let verdict: Verdict
    let verdictReasons: [String]
    let spectrogramPath: String?

    enum CodingKeys: String, CodingKey {
        case filename, format, authenticity, playability, vinyl, flags, verdict
        case filePath = "file_path"
        case clickCount = "click_count"
        case verdictReasons = "verdict_reasons"
        case spectrogramPath = "spectrogram_path"
    }
}

enum AnalysisState {
    case pending
    case analyzing
    case done(AnalysisResult)
    case failed(String)
}

struct FileItem: Identifiable {
    let id = UUID()
    let url: URL
    var state: AnalysisState = .pending
}
