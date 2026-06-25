import SwiftUI

enum QueueFilter: String, CaseIterable {
    case all       = "All"
    case doNotPlay = "Do Not Play"
    case review    = "Review"
    case clubReady = "Club Ready"
}

struct FileQueueView: View {
    @Binding var items: [FileItem]
    @State private var filter: QueueFilter = .all

    private var filtered: [FileItem] {
        switch filter {
        case .all: return items
        case .doNotPlay:
            return items.filter {
                if case .done(let r) = $0.state { return r.verdict == .doNotPlay }
                return false
            }
        case .review:
            return items.filter {
                if case .done(let r) = $0.state { return r.verdict == .review }
                return false
            }
        case .clubReady:
            return items.filter {
                if case .done(let r) = $0.state { return r.verdict == .clubReady }
                return false
            }
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 6) {
                ForEach(QueueFilter.allCases, id: \.self) { f in
                    Button(f.rawValue) { filter = f }
                        .buttonStyle(.plain)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(filter == f ? Color.accentColor.opacity(0.15) : Color.clear)
                        .foregroundColor(filter == f ? .accentColor : .secondary)
                        .cornerRadius(5)
                        .font(.system(size: 11, weight: filter == f ? .semibold : .regular))
                }
                Spacer()
                Text("\(filtered.count) / \(items.count)")
                    .font(.system(size: 11))
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 6)
            .overlay(Divider(), alignment: .bottom)

            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(filtered) { item in
                        switch item.state {
                        case .done(let result):
                            ReportCardView(result: result)
                                .contextMenu {
                                    Button("Reveal in Finder") {
                                        NSWorkspace.shared.selectFile(item.url.path, inFileViewerRootedAtPath: "")
                                    }
                                }
                        case .analyzing:
                            analyzingRow(item.url.lastPathComponent)
                        case .failed(let msg):
                            errorRow(item.url.lastPathComponent, message: msg)
                                .contextMenu {
                                    Button("Reveal in Finder") {
                                        NSWorkspace.shared.selectFile(item.url.path, inFileViewerRootedAtPath: "")
                                    }
                                }
                        case .pending:
                            pendingRow(item.url.lastPathComponent)
                        }
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
            }
        }
    }

    @ViewBuilder
    private func analyzingRow(_ name: String) -> some View {
        HStack(spacing: 10) {
            ProgressView()
                .scaleEffect(0.7)
                .frame(width: 20)
            Text(name)
                .font(.system(size: 12))
                .lineLimit(1)
                .truncationMode(.middle)
            Spacer()
            Text("Analyzing…")
                .font(.system(size: 11))
                .foregroundColor(.secondary)
        }
        .padding(10)
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color(NSColor.separatorColor), lineWidth: 1))
    }

    @ViewBuilder
    private func pendingRow(_ name: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: "clock")
                .foregroundColor(.secondary)
                .frame(width: 20)
            Text(name)
                .font(.system(size: 12))
                .foregroundColor(.secondary)
                .lineLimit(1)
                .truncationMode(.middle)
            Spacer()
        }
        .padding(10)
        .background(Color(NSColor.controlBackgroundColor).opacity(0.5))
        .cornerRadius(8)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color(NSColor.separatorColor), lineWidth: 1))
    }

    @ViewBuilder
    private func errorRow(_ name: String, message: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: "exclamationmark.triangle")
                .foregroundColor(.orange)
                .frame(width: 20)
            VStack(alignment: .leading, spacing: 2) {
                Text(name)
                    .font(.system(size: 12, weight: .medium))
                Text(message)
                    .font(.system(size: 10))
                    .foregroundColor(.secondary)
                    .lineLimit(2)
            }
            Spacer()
        }
        .padding(10)
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.orange.opacity(0.4), lineWidth: 1))
    }
}
