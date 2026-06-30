import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var vm: AppViewModel
    @ObservedObject private var settings = AppSettings.shared

    // General tab
    @State private var pythonFieldText = ""

    // Thresholds tab — string drafts keyed by const name, for inline validation
    @State private var draft: [String: String] = [:]

    var body: some View {
        TabView {
            generalTab
                .tabItem { Text("General") }

            thresholdsTab
                .tabItem { Text("Thresholds") }
        }
        .frame(width: 560)
        .onAppear {
            pythonFieldText = settings.pythonPathOverride
            initDrafts()
        }
    }

    // MARK: - General tab

    private var generalTab: some View {
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
                Button("Save") { saveGeneral() }
                    .controlSize(.small)
                    .keyboardShortcut(.return)
            }
        }
        .padding(20)
    }

    private func saveGeneral() {
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

    // MARK: - Thresholds tab

    private var thresholdsTab: some View {
        VStack(spacing: 0) {
            Form {
                ForEach(ThresholdCatalog.categories, id: \.self) { category in
                    Section {
                        ForEach(ThresholdCatalog.all.filter { $0.category == category }) { spec in
                            thresholdRow(spec)
                        }
                    } header: {
                        Text(category)
                    }
                }
            }

            Divider()

            HStack {
                Spacer()
                Button("Reset to Defaults") { resetThresholds() }
                    .controlSize(.small)
                Button("Save") { saveThresholds() }
                    .controlSize(.small)
                    .keyboardShortcut(.return)
                    .disabled(anyInvalid)
            }
            .padding(12)
        }
        .padding(8)
    }

    @ViewBuilder
    private func thresholdRow(_ spec: ThresholdSpec) -> some View {
        let invalid = isInvalid(spec)
        VStack(alignment: .leading, spacing: 2) {
            HStack {
                Text(spec.label)
                    .frame(width: 230, alignment: .leading)
                TextField(
                    "",
                    text: Binding(
                        get: { draft[spec.name] ?? format(spec.defaultValue) },
                        set: { draft[spec.name] = $0 }
                    )
                )
                .frame(width: 90)
                .multilineTextAlignment(.trailing)
                .font(.system(size: 12, design: .monospaced))
                .foregroundColor(invalid ? .red : .primary)
                Text("default \(format(spec.defaultValue))")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            if invalid {
                Text(validationMessage(spec))
                    .font(.caption2)
                    .foregroundColor(.red)
            }
        }
    }

    // MARK: - Validation

    private func parsed(_ name: String) -> Double? {
        guard let raw = draft[name] else {
            // No draft yet → fall back to default (always valid).
            return ThresholdCatalog.spec(named: name)?.defaultValue
        }
        return Double(raw.trimmingCharacters(in: .whitespaces))
    }

    private func isInvalid(_ spec: ThresholdSpec) -> Bool {
        guard let value = parsed(spec.name) else { return true }
        if let other = spec.lessThan, let otherValue = parsed(other), !(value < otherValue) {
            return true
        }
        if let other = spec.greaterThan, let otherValue = parsed(other), !(value > otherValue) {
            return true
        }
        return false
    }

    private func validationMessage(_ spec: ThresholdSpec) -> String {
        if parsed(spec.name) == nil { return "Enter a number" }
        if let other = spec.lessThan {
            return "Must be less than \(ThresholdCatalog.spec(named: other)?.label ?? other)"
        }
        if let other = spec.greaterThan {
            return "Must be greater than \(ThresholdCatalog.spec(named: other)?.label ?? other)"
        }
        return "Invalid value"
    }

    private var anyInvalid: Bool {
        ThresholdCatalog.all.contains { isInvalid($0) }
    }

    // MARK: - Actions

    private func initDrafts() {
        let overrides = settings.thresholdOverrides
        var next: [String: String] = [:]
        for spec in ThresholdCatalog.all {
            next[spec.name] = format(overrides[spec.name] ?? spec.defaultValue)
        }
        draft = next
    }

    private func saveThresholds() {
        guard !anyInvalid else { return }
        var values: [String: Double] = [:]
        for spec in ThresholdCatalog.all {
            if let value = parsed(spec.name) {
                values[spec.name] = value
            }
        }
        settings.thresholdOverrides = values        // writeThresholdsFile emits only non-defaults
        settings.writeThresholdsFile()
        vm.reverdictAll()
    }

    private func resetThresholds() {
        var next: [String: String] = [:]
        for spec in ThresholdCatalog.all {
            next[spec.name] = format(spec.defaultValue)
        }
        draft = next
        settings.thresholdOverrides = [:]
        settings.writeThresholdsFile()              // writes {}
        vm.reverdictAll()
    }

    // MARK: - Formatting

    private func format(_ value: Double) -> String {
        if value == value.rounded() && abs(value) < 1e15 {
            return String(Int(value))
        }
        return String(value)
    }
}
