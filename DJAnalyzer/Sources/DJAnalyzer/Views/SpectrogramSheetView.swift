import SwiftUI
import AppKit

// MARK: - Window content view

struct SpectrogramSheetView: View {
    let result: AnalysisResult

    @State private var imagePath: String? = nil
    @State private var isLoading = true
    @State private var errorMessage: String? = nil
    @State private var scale: CGFloat = 1.0
    @State private var baseScale: CGFloat = 1.0

    var body: some View {
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
                GeometryReader { geo in
                    ScrollView([.horizontal, .vertical], showsIndicators: true) {
                        Image(nsImage: img)
                            .resizable()
                            .aspectRatio(contentMode: .fit)
                            .frame(
                                width: geo.size.width * max(1, scale),
                                height: geo.size.height * max(1, scale)
                            )
                    }
                }
                .gesture(
                    MagnificationGesture()
                        .onChanged { value in scale = max(1.0, baseScale * value) }
                        .onEnded { _ in baseScale = scale }
                )
                .onTapGesture(count: 2) {
                    withAnimation(.easeOut(duration: 0.2)) { scale = 1.0; baseScale = 1.0 }
                }
                .padding(8)
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
        .task { await load() }
    }

    private func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            imagePath = try await SpectrogramService.generateFull(
                filePath: result.filePath ?? result.filename,
                duration: result.format.duration,
                humHz: result.vinyl?.humHz,
                clipTimes: result.clipTimesSec
            )
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

// MARK: - Window opener

enum SpectrogramWindow {
    // Strong references — prevents ARC from releasing windows while animations are in flight
    private static var openWindows: [ObjectIdentifier: NSWindow] = [:]

    static func open(result: AnalysisResult) {
        let view = SpectrogramSheetView(result: result)
        let controller = NSHostingController(rootView: view)
        let window = NSWindow(contentViewController: controller)
        window.title = result.filename
        window.setContentSize(NSSize(width: 960, height: 420))
        window.minSize = NSSize(width: 600, height: 280)
        window.styleMask = [.titled, .closable, .resizable, .miniaturizable]
        window.isReleasedWhenClosed = false  // ARC manages lifetime via openWindows
        window.collectionBehavior = [.fullScreenPrimary]

        let key = ObjectIdentifier(window)
        openWindows[key] = window

        NotificationCenter.default.addObserver(
            forName: NSWindow.willCloseNotification,
            object: window,
            queue: .main
        ) { _ in
            openWindows.removeValue(forKey: key)
        }

        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}
