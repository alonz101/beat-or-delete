import SwiftUI
import UniformTypeIdentifiers

struct DropZoneView: View {
    let onFiles: ([URL]) -> Void
    @State private var isTargeted = false

    private let supportedTypes: [UTType] = [
        .audio, .folder, .directory,
        UTType(filenameExtension: "aiff") ?? .audio,
        UTType(filenameExtension: "aif")  ?? .audio,
        UTType(filenameExtension: "flac") ?? .audio,
        UTType(filenameExtension: "mp3")  ?? .audio,
        UTType(filenameExtension: "wav")  ?? .audio,
        UTType(filenameExtension: "m4a")  ?? .audio,
    ]

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 12)
                .strokeBorder(
                    isTargeted ? Color.accentColor : Color(NSColor.separatorColor),
                    style: StrokeStyle(lineWidth: 2, dash: [6, 4])
                )
                .background(
                    RoundedRectangle(cornerRadius: 12)
                        .fill(isTargeted
                            ? Color.accentColor.opacity(0.07)
                            : Color(NSColor.controlBackgroundColor))
                )

            VStack(spacing: 10) {
                Image(systemName: "waveform.badge.plus")
                    .font(.system(size: 36))
                    .foregroundColor(isTargeted ? .accentColor : .secondary)
                Text("Drop audio files or a folder")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundColor(isTargeted ? .accentColor : .primary)
                Text("AIFF · WAV · FLAC · MP3 · M4A")
                    .font(.system(size: 11))
                    .foregroundColor(.secondary)

                Button("Or choose files…") {
                    openPanel()
                }
                .buttonStyle(.bordered)
                .font(.system(size: 12, weight: .medium))
                .padding(.top, 4)
            }
        }
        .frame(maxWidth: .infinity)
        .frame(height: 160)
        .onDrop(of: supportedTypes, isTargeted: $isTargeted) { providers in
            loadDropped(providers)
            return true
        }
    }

    private func openPanel() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = true
        panel.canChooseFiles = true
        panel.canChooseDirectories = true
        panel.allowedContentTypes = [.audio, .folder]
        if panel.runModal() == .OK {
            onFiles(panel.urls)
        }
    }

    private func loadDropped(_ providers: [NSItemProvider]) {
        var urls: [URL] = []
        let group = DispatchGroup()

        for provider in providers {
            group.enter()
            provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier) { item, _ in
                defer { group.leave() }
                if let data = item as? Data,
                   let url = URL(dataRepresentation: data, relativeTo: nil) {
                    urls.append(url)
                }
            }
        }

        group.notify(queue: .main) {
            onFiles(urls)
        }
    }
}
