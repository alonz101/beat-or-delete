import SwiftUI

struct VerdictBadge: View {
    let verdict: String

    var color: Color {
        switch verdict {
        case "CLUB READY":  return Color(hex: "1a7a3e")
        case "CASUAL OK":   return Color(hex: "2a7a6e")
        case "MARGINAL":    return Color(hex: "c97a00")
        case "DO NOT PLAY": return Color(hex: "b52b2b")
        default:            return .gray
        }
    }

    var body: some View {
        Text(verdict)
            .font(.system(size: 11, weight: .bold, design: .monospaced))
            .foregroundColor(.white)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(color)
            .cornerRadius(4)
    }
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
