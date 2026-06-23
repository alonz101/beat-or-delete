import SwiftUI

struct SettingsView: View {
    @ObservedObject private var settings = AppSettings.shared
    @State private var pythonFieldText = ""

    var body: some View {
        Form {
            Section {
                HStack {
                    TextField("Leave empty to auto-detect", text: $pythonFieldText)
                        .font(.system(size: 12, design: .monospaced))
                    Button("Browse…") { pickPython() }
                        .controlSize(.small)
                }
                Text("Override Python binary. Auto-detect walks ~/.pyenv/versions for librosa.")
                    .font(.caption)
                    .foregroundColor(.secondary)
            } header: {
                Text("Python Override (optional)")
            }

            HStack {
                Spacer()
                Button("Reset to Defaults") {
                    pythonFieldText = ""
                }
                .controlSize(.small)
                Button("Save") { save() }
                    .controlSize(.small)
                    .keyboardShortcut(.return)
            }
        }
        .padding(20)
        .frame(width: 520)
        .onAppear {
            pythonFieldText = settings.pythonPathOverride
        }
    }

    private func save() {
        settings.pythonPathOverride = pythonFieldText.trimmingCharacters(in: .whitespaces)
    }

    private func pickPython() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.prompt = "Select Python binary"
        if panel.runModal() == .OK, let url = panel.url {
            pythonFieldText = url.path
        }
    }
}
