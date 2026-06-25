import SwiftUI

struct SpectrogramSheetView: View {
    let result: AnalysisResult

    @State private var imagePath: String? = nil
    @State private var isLoading = true
    @State private var errorMessage: String? = nil
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            body_content
        }
        .frame(minWidth: 860, minHeight: 360)
        .background(Color(NSColor.windowBackgroundColor))
        .task { await load() }
    }

    private var header: some View {
        HStack {
            Image(systemName: "waveform")
                .foregroundColor(.secondary)
                .font(.system(size: 12))
            Text(result.filename)
                .font(.system(size: 13, weight: .semibold))
                .lineLimit(1)
                .truncationMode(.middle)
            Spacer()
            Button(action: { dismiss() }) {
                Image(systemName: "xmark.circle.fill")
                    .font(.system(size: 16))
                    .foregroundColor(.secondary)
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }

    @ViewBuilder
    private var body_content: some View {
        ZStack {
            Color(NSColor.windowBackgroundColor)
            if isLoading {
                VStack(spacing: 10) {
                    ProgressView()
                        .progressViewStyle(.circular)
                        .scaleEffect(0.8)
                    Text("Generating spectrogram…")
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                }
            } else if let path = imagePath, let img = NSImage(contentsOfFile: path) {
                ScrollView([.horizontal, .vertical]) {
                    Image(nsImage: img)
                        .resizable()
                        .scaledToFit()
                        .padding(16)
                }
            } else {
                VStack(spacing: 8) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.system(size: 24))
                        .foregroundColor(.secondary)
                    Text(errorMessage ?? "Failed to generate spectrogram")
                        .font(.system(size: 12))
                        .foregroundColor(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding()
            }
        }
    }

    private func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            imagePath = try await SpectrogramService.generateFull(
                filePath: result.filePath ?? result.filename,
                humHz: result.vinyl?.humHz,
                clipTimes: result.clipTimesSec
            )
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
