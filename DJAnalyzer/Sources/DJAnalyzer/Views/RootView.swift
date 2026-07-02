import SwiftUI

/// Top-level tab container. Keeps the Analyze screen (ContentView, filter chips and all)
/// structurally separate from the History tab so History never reads as one of the
/// All / Do Not Play / Marginal+ / Club Ready filter chips (AC-1). The shared view model
/// is passed down via the environment so both tabs (and Settings) see the same state.
struct RootView: View {
    @EnvironmentObject var vm: AppViewModel

    var body: some View {
        TabView {
            ContentView()
                .tabItem {
                    Label("Analyze", systemImage: "waveform")
                }

            HistoryView()
                .tabItem {
                    Label("History", systemImage: "clock.arrow.circlepath")
                }

            GuideView()
                .tabItem {
                    Label("Guide", systemImage: "book")
                }
        }
        .frame(minWidth: 780, minHeight: 500)
    }
}
