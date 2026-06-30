import SwiftUI

@MainActor
class AppViewModel: ObservableObject {
    @Published var items: [FileItem] = []
    @Published var isExporting = false
    @Published var exportMessage: String? = nil

    private let supportedExtensions = Set(["aiff", "aif", "wav", "flac", "mp3", "m4a", "aac", "ogg"])

    func addURLs(_ urls: [URL]) {
        let files = urls.flatMap { url -> [URL] in
            var isDir: ObjCBool = false
            FileManager.default.fileExists(atPath: url.path, isDirectory: &isDir)
            if isDir.boolValue {
                return (try? FileManager.default.contentsOfDirectory(
                    at: url, includingPropertiesForKeys: nil, options: .skipsHiddenFiles
                ))?.filter { supportedExtensions.contains($0.pathExtension.lowercased()) }
                .sorted { $0.lastPathComponent < $1.lastPathComponent } ?? []
            }
            return supportedExtensions.contains(url.pathExtension.lowercased()) ? [url] : []
        }

        guard !files.isEmpty else { return }

        let newItems = files.map { FileItem(url: $0) }
        items.append(contentsOf: newItems)

        for item in newItems {
            analyzeItem(item)
        }
    }

    func clearAll() {
        items = []
    }

    /// Re-run the one-shot analyze for every loaded file. Each fresh `dj-analyze`
    /// reads the new thresholds.json → new CONFIG_HASH → verdict miss → fast
    /// reverdict (cache hits the measurement, no re-FFT). Bounded by the cap=3 gate.
    func reverdictAll() {
        for item in items {
            switch item.state {
            case .done, .failed:
                analyzeItem(item)
            default:
                break
            }
        }
    }

    func exportReports() {
        let panel = NSSavePanel()
        panel.nameFieldStringValue = "dj-report"
        panel.allowedContentTypes = []
        panel.message = "Choose output location (CSV and PDF will be saved)"

        guard panel.runModal() == .OK, let url = panel.url else { return }

        let stem = url.deletingPathExtension().path
        isExporting = true
        exportMessage = "Exporting…"

        Task {
            do {
                let urls = items.compactMap { item -> URL? in
                    if case .done = item.state { return item.url } else { return nil }
                }
                guard let firstURL = urls.first else { return }
                let folder = firstURL.deletingLastPathComponent()

                let (csv, pdf) = try await AnalyzerService.runBatch(
                    folderURL: folder,
                    outputStem: stem,
                    progress: { [weak self] line in
                        Task { @MainActor in self?.exportMessage = line }
                    }
                )

                exportMessage = "Saved: \(URL(fileURLWithPath: csv).lastPathComponent) + \(URL(fileURLWithPath: pdf).lastPathComponent)"
                NSWorkspace.shared.selectFile(pdf, inFileViewerRootedAtPath: "")
            } catch {
                exportMessage = "Export failed: \(error.localizedDescription)"
            }
            isExporting = false
        }
    }

    private func analyzeItem(_ item: FileItem) {
        guard let idx = items.firstIndex(where: { $0.id == item.id }) else { return }
        items[idx].state = .analyzing

        Task {
            do {
                let result = try await AnalyzerService.analyze(fileURL: item.url)
                if let i = items.firstIndex(where: { $0.id == item.id }) {
                    items[i].state = .done(result)
                }
            } catch {
                if let i = items.firstIndex(where: { $0.id == item.id }) {
                    items[i].state = .failed(error.localizedDescription)
                }
            }
        }
    }
}
