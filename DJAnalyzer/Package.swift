// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "DJAnalyzer",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "DJAnalyzer",
            path: "Sources/DJAnalyzer",
            exclude: ["Info.plist"]
        )
    ]
)
