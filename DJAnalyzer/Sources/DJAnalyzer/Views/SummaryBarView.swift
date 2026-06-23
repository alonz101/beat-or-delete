import SwiftUI

struct SummaryBarView: View {
    let items: [FileItem]
    let onExport: () -> Void

    private var done: [AnalysisResult] {
        items.compactMap { if case .done(let r) = $0.state { return r } else { return nil } }
    }

    private var counts: [String: Int] {
        done.reduce(into: [:]) { $0[$1.verdict, default: 0] += 1 }
    }

    private var progress: Double {
        items.isEmpty ? 0 : Double(done.count) / Double(items.count)
    }

    var body: some View {
        VStack(spacing: 0) {
            if done.count < items.count {
                ProgressView(value: progress)
                    .progressViewStyle(.linear)
                    .tint(.accentColor)
                    .frame(height: 3)
            }
            HStack(spacing: 14) {
            Text("\(done.count)/\(items.count) analyzed")
                .font(.system(size: 12, weight: .medium))
                .foregroundColor(.secondary)

            Divider().frame(height: 16)

            ForEach(["CLUB READY", "CASUAL OK", "MARGINAL", "DO NOT PLAY"], id: \.self) { verdict in
                if let count = counts[verdict] {
                    HStack(spacing: 4) {
                        Circle()
                            .fill(verdictColor(verdict))
                            .frame(width: 8, height: 8)
                        Text("\(count)")
                            .font(.system(size: 12, weight: .semibold))
                        Text(verdict)
                            .font(.system(size: 11))
                            .foregroundColor(.secondary)
                    }
                }
            }

            Spacer()

            if !done.isEmpty {
                Button {
                    onExport()
                } label: {
                    Label("Export PDF + CSV", systemImage: "square.and.arrow.up")
                        .font(.system(size: 12))
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.small)
            }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
        }
        .background(Color(NSColor.windowBackgroundColor))
        .overlay(Divider(), alignment: .top)
    }

    private func verdictColor(_ verdict: String) -> Color {
        switch verdict {
        case "CLUB READY":  return Color(hex: "1a7a3e")
        case "CASUAL OK":   return Color(hex: "2e6da4")
        case "MARGINAL":    return Color(hex: "c97a00")
        case "DO NOT PLAY": return Color(hex: "b52b2b")
        default:            return .gray
        }
    }
}
