import SwiftUI

struct ContentView: View {
    @StateObject private var vm = AppViewModel()

    var body: some View {
        VStack(spacing: 0) {
            // Drop zone (hide once files are loaded)
            if vm.items.isEmpty {
                DropZoneView { urls in
                    vm.addURLs(urls)
                }
                .padding(20)
            } else {
                // Top toolbar
                HStack {
                    Text("Beat or Delete")
                        .font(.system(size: 13, weight: .semibold))
                    Spacer()
                    Button("Add more…") {
                        openPanel()
                    }
                    .controlSize(.small)
                    Button("Clear") {
                        vm.clearAll()
                    }
                    .controlSize(.small)
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(Color(NSColor.windowBackgroundColor))
                .overlay(Divider(), alignment: .bottom)

                FileQueueView(items: $vm.items)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)

                SummaryBarView(items: vm.items) {
                    vm.exportReports()
                }

                if let msg = vm.exportMessage {
                    Text(msg)
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                        .padding(.bottom, 6)
                }
            }
        }
        .frame(minWidth: 780, minHeight: 500)
    }

    private func openPanel() {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = true
        panel.canChooseFiles = true
        panel.canChooseDirectories = true
        if panel.runModal() == .OK {
            vm.addURLs(panel.urls)
        }
    }
}
