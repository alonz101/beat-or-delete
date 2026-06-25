import SwiftUI

enum Verdict: String, Codable, CaseIterable {
    case clubReady  = "CLUB READY"
    case marginal   = "MARGINAL"
    case doNotPlay  = "DO NOT PLAY"

    var color: Color {
        switch self {
        case .clubReady:  return Color(hex: "1a7a3e")
        case .marginal:   return Color(hex: "c97a00")
        case .doNotPlay:  return Color(hex: "b52b2b")
        }
    }

    var displayName: String { rawValue }
}

extension Color {
    init(hex: String) {
        let v = UInt64(hex, radix: 16) ?? 0
        let r = Double((v >> 16) & 0xFF) / 255
        let g = Double((v >> 8) & 0xFF) / 255
        let b = Double(v & 0xFF) / 255
        self.init(red: r, green: g, blue: b)
    }
}
