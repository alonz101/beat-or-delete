import Foundation
import SwiftUI

class AppSettings: ObservableObject {
    static let shared = AppSettings()

    @AppStorage("analyzerRoot") var analyzerRoot: String = "/Users/alonzigerman/personal/analyzer"
    @AppStorage("pythonPathOverride") var pythonPathOverride: String = ""

    var effectivePythonPath: String? {
        pythonPathOverride.isEmpty ? nil : pythonPathOverride
    }
}
