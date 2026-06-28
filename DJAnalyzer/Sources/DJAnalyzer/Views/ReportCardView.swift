import SwiftUI

struct ReportCardView: View {
    let result: AnalysisResult

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            // Header
            HStack(alignment: .center) {
                Text(result.filename)
                    .font(.system(size: 13, weight: .semibold))
                    .lineLimit(1)
                    .truncationMode(.middle)
                Spacer()
                VerdictBadge(verdict: result.verdict)
            }

            // Verdict reasons (red — drive the verdict)
            if !result.verdictReasons.isEmpty {
                VStack(alignment: .leading, spacing: 2) {
                    ForEach(result.verdictReasons, id: \.self) { reason in
                        HStack(alignment: .top, spacing: 4) {
                            Text("•")
                            Text(reason)
                        }
                        .font(.system(size: 11))
                        .foregroundColor(Color(hex: "aa3333"))
                    }
                }
            }

            // Info reasons (yellow — informational only, don't affect verdict)
            if !result.infoReasons.isEmpty {
                VStack(alignment: .leading, spacing: 2) {
                    ForEach(result.infoReasons, id: \.self) { reason in
                        HStack(alignment: .top, spacing: 4) {
                            Text("•")
                            Text(reason)
                        }
                        .font(.system(size: 11))
                        .foregroundColor(Color(hex: "b09030"))
                    }
                }
            }

            // Stats grid
            HStack(alignment: .top, spacing: 16) {
                statsSection("FORMAT", items: [
                    ("Codec", result.format.codec),
                    ("Sample rate", formatSampleRate(result.format.sampleRate)),
                    ("Bit depth", result.format.bitDepth > 0 ? "\(result.format.bitDepth)-bit" : "n/a"),
                    ("Bitrate", result.format.isLossless ? "lossless" : (result.format.bitrate > 0 ? "\(result.format.bitrate / 1000)kbps" : "n/a")),
                    ("Duration", formatDuration(result.format.duration)),
                ])
                statsSection("AUTHENTICITY", items: [
                    ("Spectral coverage", String(format: "%.1f%%", result.authenticity.spectralCoverageRatio * 100)),
                    ("Top freq", String(format: "%.1f kHz", result.authenticity.topFreqHz / 1000)),
                    ("Verdict", result.authenticity.spectralVerdict),
                    ("Origin", result.authenticity.suspectedOrigin),
                    ("LAME header", result.authenticity.lameHeader ? "YES" : "no"),
                ])
                statsSection("PLAYABILITY", items: [
                    ("Clip events L/R", "\(result.playability.clipEventsL) / \(result.playability.clipEventsR)"),
                    ("Peak", formatPeak(result.playability.peakDbfs)),
                    ("Loudness", String(format: "%.2f LUFS", result.playability.loudnessLufs)),
                    ("Dyn. range", String(format: "%.1f dB", result.playability.dynamicRangeDb)),
                    ("Noise floor", String(format: "%.1f dBFS", result.playability.noiseFloorDbfs)),
                ])
            }

            // Vinyl info
            if let vinyl = result.vinyl, vinyl.vinylRip {
                HStack(spacing: 10) {
                    Image(systemName: "circle.fill")
                        .font(.system(size: 6))
                        .foregroundColor(Color(hex: "a07840"))
                    Text("VINYL RIP")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundColor(Color(hex: "a07840"))
                    if let grade = vinyl.vinylGrade {
                        Text("— \(grade)")
                            .font(.system(size: 9))
                            .foregroundColor(.secondary)
                    }
                    if let wf = vinyl.wowFlutterWrms {
                        Text("W&F: \(String(format: "%.3f", wf))%")
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundColor(.secondary)
                    }
                    if result.clickCount > 0 {
                        Text("\(result.clickCount) click(s)")
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundColor(.secondary)
                    }
                }
            }

            // Spectrogram: on-demand only. Card thumbnails were removed — rendering
            // one spectrogram process per card (each ~300MB–1GB of librosa/matplotlib)
            // caused unbounded concurrent spawns and OOM. The full spectrogram opens
            // in its own window, one at a time, on user request.
            HStack {
                Spacer()
                Button {
                    SpectrogramWindow.open(result: result)
                } label: {
                    Label("Full Spectrogram", systemImage: "waveform.circle")
                        .font(.system(size: 10, weight: .medium))
                }
                .buttonStyle(.plain)
                .foregroundColor(.accentColor)
            }

            // Flags
            if !result.flags.isEmpty {
                HStack(spacing: 6) {
                    ForEach(result.flags, id: \.self) { flag in
                        Text(flag)
                            .font(.system(size: 9, weight: .medium, design: .monospaced))
                            .foregroundColor(.secondary)
                            .padding(.horizontal, 5)
                            .padding(.vertical, 2)
                            .overlay(
                                RoundedRectangle(cornerRadius: 3)
                                    .stroke(Color.secondary.opacity(0.4), lineWidth: 1)
                            )
                    }
                }
            }
        }
        .padding(12)
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(Color(NSColor.separatorColor), lineWidth: 1)
        )
    }

    private func formatDuration(_ seconds: Double) -> String {
        let total = Int(seconds)
        return String(format: "%d:%02d", total / 60, total % 60)
    }

    private func formatSampleRate(_ hz: Int) -> String {
        let khz = Double(hz) / 1000.0
        return khz.truncatingRemainder(dividingBy: 1) == 0 ? "\(Int(khz)) kHz" : String(format: "%.1f kHz", khz)
    }

    private func formatPeak(_ dbfs: Double) -> String {
        let s = String(format: "%.2f", dbfs)
        return (s == "-0.00" ? "0.00" : s) + " dBFS"
    }

    @ViewBuilder
    private func statsSection(_ title: String, items: [(String, String)]) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title)
                .font(.system(size: 9, weight: .bold))
                .foregroundColor(.secondary)
                .padding(.bottom, 1)
            ForEach(items, id: \.0) { label, value in
                HStack(alignment: .top, spacing: 0) {
                    Text(label)
                        .font(.system(size: 10))
                        .foregroundColor(.secondary)
                        .frame(width: 90, alignment: .leading)
                    Text(value)
                        .font(.system(size: 10, weight: .medium))
                        .lineLimit(1)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
