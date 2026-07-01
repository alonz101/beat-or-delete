import SwiftUI

/// History tab — live substring search over the SQLite cache via `dj-analyze --history`.
/// Selecting a row shows the full ReportCardView (reverdicted under current thresholds)
/// and injects the track into the Analyze queue (unless its file is missing).
struct HistoryView: View {
    @EnvironmentObject var vm: AppViewModel

    @State private var searchText = ""
    @State private var results: [AnalysisResult] = []
    @State private var selection: AnalysisResult.ID?
    @State private var searchTask: Task<Void, Never>?

    private var selectedResult: AnalysisResult? {
        results.first { $0.id == selection }
    }

    var body: some View {
        HSplitView {
            // Left: search + results list
            VStack(spacing: 0) {
                searchBar
                Divider()
                if results.isEmpty {
                    emptyResultsState
                } else {
                    List(selection: $selection) {
                        ForEach(results) { result in
                            HistoryRow(result: result)
                                .tag(result.id)
                        }
                    }
                    .listStyle(.inset)
                }
            }
            .frame(minWidth: 300, idealWidth: 340, maxWidth: 460)

            // Right: detail
            detailPane
                .frame(minWidth: 380, maxWidth: .infinity, maxHeight: .infinity)
        }
        .frame(minWidth: 780, minHeight: 500)
        .onAppear { runSearch(immediate: true) }
        .onChange(of: searchText) { _ in scheduleSearch() }
        .onChange(of: selection) { newValue in
            if let result = results.first(where: { $0.id == newValue }) {
                vm.addFromHistory(result)   // no-op when file is missing (AC-8)
            }
        }
    }

    // MARK: - Search bar

    private var searchBar: some View {
        HStack(spacing: 6) {
            Image(systemName: "magnifyingglass")
                .foregroundColor(.secondary)
            TextField("Search analyzed tracks…", text: $searchText)
                .textFieldStyle(.plain)
            if !searchText.isEmpty || !results.isEmpty {
                Button {
                    clearSearch()
                } label: {
                    Label("Clear search", systemImage: "xmark.circle.fill")
                        .labelStyle(.iconOnly)
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
                .help("Clear search")
            }
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
    }

    // MARK: - Detail pane

    @ViewBuilder
    private var detailPane: some View {
        if let result = selectedResult {
            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    if result.fileExists == false {
                        HStack(spacing: 6) {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundColor(Color(hex: "b52b2b"))
                            Text("File missing — shown from cache. Not added to Analyze; spectrogram unavailable.")
                                .font(.system(size: 11))
                                .foregroundColor(.secondary)
                        }
                        .padding(10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(Color(hex: "b52b2b").opacity(0.12))
                        .cornerRadius(6)
                    }
                    ReportCardView(result: result, spectrogramEnabled: result.fileExists != false)
                }
                .padding(16)
            }
        } else {
            VStack(spacing: 8) {
                Image(systemName: "clock.arrow.circlepath")
                    .font(.system(size: 34))
                    .foregroundColor(.secondary)
                Text("Select a track to see its report.")
                    .font(.system(size: 12))
                    .foregroundColor(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    private var emptyResultsState: some View {
        VStack(spacing: 8) {
            Image(systemName: searchText.isEmpty ? "tray" : "magnifyingglass")
                .font(.system(size: 30))
                .foregroundColor(.secondary)
            Text(searchText.isEmpty
                 ? "No analyzed tracks yet."
                 : "No tracks match “\(searchText)”.")
                .font(.system(size: 12))
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }

    // MARK: - Actions

    private func clearSearch() {
        searchTask?.cancel()
        searchText = ""
        results = []
        selection = nil
        // NOTE: does NOT touch vm.items (AC-7)
        runSearch(immediate: true)   // reload most-recent list after clearing
    }

    private func scheduleSearch() {
        runSearch(immediate: false)
    }

    /// Fetch results for the current `searchText`. `immediate == false` debounces ~150ms
    /// (keystroke path); the prior in-flight task is always cancelled first.
    private func runSearch(immediate: Bool) {
        searchTask?.cancel()
        let query = searchText
        searchTask = Task {
            if !immediate {
                try? await Task.sleep(nanoseconds: 150_000_000)   // ~150ms debounce
            }
            if Task.isCancelled { return }
            let fetched = (try? await HistoryService.search(query: query, limit: 10)) ?? []
            if Task.isCancelled { return }
            await MainActor.run {
                results = fetched
                if !fetched.contains(where: { $0.id == selection }) {
                    selection = nil
                }
            }
        }
    }
}

/// A single history result row: filename + verdict badge + analyzed date + missing marker.
private struct HistoryRow: View {
    let result: AnalysisResult

    var body: some View {
        HStack(spacing: 8) {
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    if result.fileExists == false {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.system(size: 10))
                            .foregroundColor(Color(hex: "b52b2b"))
                            .help("File missing — shown from cache")
                    }
                    Text(result.filename)
                        .font(.system(size: 12, weight: .medium))
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .foregroundColor(result.fileExists == false ? .secondary : .primary)
                }
                if let date = result.analyzedDate {
                    Text(date.formatted(date: .abbreviated, time: .shortened))
                        .font(.system(size: 10))
                        .foregroundColor(.secondary)
                }
            }
            Spacer()
            VerdictBadge(verdict: result.verdict)
        }
        .padding(.vertical, 3)
    }
}
