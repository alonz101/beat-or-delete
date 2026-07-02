import SwiftUI

/// Owns the omnibox suggestion list, the highlighted index, and the keyDown monitor
/// that drives ↑/↓/Enter over the (focused) search field. Enter bumps `selectionToken`
/// so the view can react and add the highlighted track in its own @State context.
final class OmniboxController: ObservableObject {
    @Published var suggestions: [AnalysisResult] = [] {
        didSet { highlighted = suggestions.isEmpty ? nil : 0 }   // first item highlighted by default
    }
    @Published var highlighted: Int?
    @Published private(set) var selectionToken = 0

    /// True only while the History tab is on-screen. Gates the keyDown handler so a
    /// monitor that outlives a tab switch (macOS TabView `onDisappear` is unreliable)
    /// stays inert and never swallows ↑/↓/Enter app-wide.
    var isActive = false

    /// The track chosen via Enter — read by the view when `selectionToken` changes.
    private(set) var pendingSelection: AnalysisResult?
    private var monitor: Any?

    func startMonitor() {
        guard monitor == nil else { return }
        monitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            guard let self, self.isActive, !self.suggestions.isEmpty else { return event }
            switch event.keyCode {
            case 125: self.move(1);  return nil      // ↓
            case 126: self.move(-1); return nil      // ↑
            case 36, 76:                             // return / enter
                if let i = self.highlighted, self.suggestions.indices.contains(i) {
                    self.pendingSelection = self.suggestions[i]
                    self.selectionToken &+= 1
                    return nil
                }
                return event
            default: return event                    // pass typing through to the field
            }
        }
    }

    func stopMonitor() {
        if let m = monitor { NSEvent.removeMonitor(m); monitor = nil }
    }

    private func move(_ delta: Int) {
        let n = suggestions.count
        guard n > 0 else { return }
        let cur = highlighted ?? 0
        highlighted = ((cur + delta) % n + n) % n
    }
}

/// History tab — a single-column, Chrome-omnibox-style search over the SQLite cache
/// via `dj-analyze --history`. Empty box shows nothing. Typing drops a floating
/// suggestion list under the field (hover / ↑↓ to highlight, Enter or click to pick);
/// picking adds that track's full report card to this page and to the Analyze queue.
struct HistoryView: View {
    @EnvironmentObject var vm: AppViewModel
    @StateObject private var omni = OmniboxController()

    @State private var searchText = ""
    @State private var addedCards: [AnalysisResult] = []   // tracks opened into this tab
    @State private var searchTask: Task<Void, Never>?

    private let searchBarHeight: CGFloat = 44
    private let maxSuggestions = 8

    private var showDropdown: Bool {
        !searchText.trimmingCharacters(in: .whitespaces).isEmpty && !omni.suggestions.isEmpty
    }

    var body: some View {
        ZStack(alignment: .top) {
            VStack(spacing: 0) {
                header
                Divider()
                cardsArea
            }

            if showDropdown {
                suggestionsDropdown
                    .padding(.top, searchBarHeight)
                    .padding(.horizontal, 12)
                    .zIndex(10)
            }
        }
        .frame(minWidth: 560, minHeight: 460)
        .onChange(of: searchText) { _ in scheduleSearch() }
        .onChange(of: showDropdown) { show in show ? omni.startMonitor() : omni.stopMonitor() }
        .onChange(of: omni.selectionToken) { _ in
            if let r = omni.pendingSelection { addCard(r) }   // Enter on highlighted row
        }
        .onAppear { omni.isActive = true; if showDropdown { omni.startMonitor() } }
        .onDisappear { omni.isActive = false; omni.stopMonitor() }
    }

    // MARK: - Header (search field + clear)

    private var header: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
                .foregroundColor(.secondary)
            TextField("Search analyzed tracks…", text: $searchText)
                .textFieldStyle(.plain)
                .font(.system(size: 13))
            if !searchText.isEmpty {
                Button {
                    searchText = ""
                    omni.suggestions = []
                } label: {
                    Image(systemName: "xmark.circle.fill").foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
                .help("Clear text")
            }
            if !addedCards.isEmpty {
                Button("Clear") { clearHistory() }
                    .help("Remove all tracks from the History tab (leaves the Analyze tab untouched)")
            }
        }
        .padding(.horizontal, 12)
        .frame(height: searchBarHeight)
    }

    // MARK: - Suggestions dropdown (Chrome-omnibox style)

    private var suggestionsDropdown: some View {
        let items = Array(omni.suggestions.prefix(maxSuggestions).enumerated())
        return VStack(spacing: 0) {
            ForEach(items, id: \.element.id) { index, result in
                SuggestionRow(result: result, isHighlighted: omni.highlighted == index)
                    .contentShape(Rectangle())
                    .onHover { inside in if inside { omni.highlighted = index } }
                    .onTapGesture { addCard(result) }
                if index != items.count - 1 { Divider() }
            }
        }
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(Color(NSColor.separatorColor), lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.25), radius: 12, y: 6)
    }

    // MARK: - Cards area (added tracks stack)

    @ViewBuilder
    private var cardsArea: some View {
        if addedCards.isEmpty {
            VStack(spacing: 8) {
                Image(systemName: "clock.arrow.circlepath")
                    .font(.system(size: 34))
                    .foregroundColor(.secondary)
                Text("Search a previously analyzed track, then pick it to open its report here.")
                    .font(.system(size: 12))
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 360)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .padding()
        } else {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    ForEach(addedCards) { result in
                        VStack(alignment: .leading, spacing: 6) {
                            if result.fileExists == false {
                                HStack(spacing: 6) {
                                    Image(systemName: "exclamationmark.triangle.fill")
                                        .foregroundColor(Color(hex: "b52b2b"))
                                    Text("File missing — shown from cache. Not added to Analyze; spectrogram unavailable.")
                                        .font(.system(size: 11))
                                        .foregroundColor(.secondary)
                                }
                                .padding(8)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .background(Color(hex: "b52b2b").opacity(0.12))
                                .cornerRadius(6)
                            }
                            ReportCardView(result: result, spectrogramEnabled: result.fileExists != false)
                        }
                    }
                }
                .padding(16)
            }
        }
    }

    // MARK: - Actions

    /// Add a searched track: opens its card in this tab (dedup, newest on top) and
    /// injects it into the Analyze queue. Closes the dropdown.
    private func addCard(_ result: AnalysisResult) {
        vm.addFromHistory(result)                 // no-op when file missing (AC-8)
        addedCards.removeAll { $0.id == result.id }
        addedCards.insert(result, at: 0)
        searchText = ""
        omni.suggestions = []
        searchTask?.cancel()
    }

    /// Clear the History tab's opened cards + search. Never touches `vm.items` (AC-7).
    private func clearHistory() {
        searchTask?.cancel()
        searchText = ""
        omni.suggestions = []
        addedCards = []
    }

    private func scheduleSearch() {
        searchTask?.cancel()
        let query = searchText.trimmingCharacters(in: .whitespaces)
        guard !query.isEmpty else { omni.suggestions = []; return }   // empty box → no suggestions
        searchTask = Task {
            try? await Task.sleep(nanoseconds: 150_000_000)           // ~150ms debounce
            if Task.isCancelled { return }
            let fetched = (try? await HistoryService.search(query: query, limit: maxSuggestions)) ?? []
            if Task.isCancelled { return }
            await MainActor.run {
                // Guard against an out-of-order response for stale text.
                if searchText.trimmingCharacters(in: .whitespaces) == query {
                    omni.suggestions = fetched
                }
            }
        }
    }
}

/// A compact omnibox suggestion row: filename + analyzed date + verdict badge (+ missing marker).
private struct SuggestionRow: View {
    let result: AnalysisResult
    let isHighlighted: Bool

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: result.fileExists == false ? "exclamationmark.triangle.fill" : "waveform")
                .font(.system(size: 11))
                .foregroundColor(result.fileExists == false ? Color(hex: "b52b2b") : .secondary)
                .frame(width: 16)
            Text(result.filename)
                .font(.system(size: 12, weight: .medium))
                .lineLimit(1)
                .truncationMode(.middle)
                .foregroundColor(result.fileExists == false ? .secondary : .primary)
            if let date = result.analyzedDate {
                Text(date.formatted(date: .abbreviated, time: .omitted))
                    .font(.system(size: 10))
                    .foregroundColor(.secondary)
            }
            Spacer()
            VerdictBadge(verdict: result.verdict)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 7)
        .background(isHighlighted ? Color.accentColor.opacity(0.20) : Color.clear)
        .contentShape(Rectangle())
    }
}
