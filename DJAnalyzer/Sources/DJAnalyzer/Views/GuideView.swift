import SwiftUI

/// Guide tab — a comprehensive but scannable in-app explainer: how the analysis works,
/// what each verdict / flag / metric means, and what a DJ should actually do about it.
/// Threshold numbers shown are the DEFAULTS (mirrors core/config.py via ThresholdCatalog);
/// they're adjustable in Settings → Thresholds.
struct GuideView: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                title

                howItWorks

                verdictsSection

                GuideSection("Blocking flags → DO NOT PLAY", subtitle: "A real quality problem. Try to source a better file before your set.", expanded: false) {
                    ForEach(GuideContent.blockingFlags) { FlagRow(flag: $0, tint: Verdict.doNotPlay.color) }
                }

                GuideSection("Review flags → REVIEW", subtitle: "Worth a quick listen — many are perfectly fine.", expanded: false) {
                    ForEach(GuideContent.reviewFlags) { FlagRow(flag: $0, tint: Verdict.review.color) }
                }

                GuideSection("Informational", subtitle: "Shown for awareness — these do NOT change the verdict.", expanded: false) {
                    ForEach(GuideContent.infoFlags) { FlagRow(flag: $0, tint: .secondary) }
                }

                GuideSection("The metrics, in plain language", expanded: false) {
                    ForEach(GuideContent.metrics) { MetricRow(metric: $0) }
                }

                GuideSection("What to actually look for", expanded: true) {
                    ForEach(GuideContent.practical, id: \.self) { BulletRow(text: $0) }
                }

                GuideSection("Known limitations — don't over-trust it", expanded: false) {
                    ForEach(GuideContent.limitations, id: \.self) { BulletRow(text: $0) }
                }

                thresholdsNote
            }
            .padding(20)
            .frame(maxWidth: 760, alignment: .leading)
            .frame(maxWidth: .infinity)
        }
    }

    // MARK: - Top

    private var title: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("How to read your results")
                .font(.system(size: 20, weight: .bold))
            Text("Beat or Delete checks each track's real audio quality before you play it. Here's what everything means.")
                .font(.system(size: 12))
                .foregroundColor(.secondary)
        }
    }

    private var howItWorks: some View {
        GuideCard {
            VStack(alignment: .leading, spacing: 6) {
                Label("How it works", systemImage: "cpu")
                    .font(.system(size: 13, weight: .semibold))
                Text("Fully deterministic signal analysis — no AI, no guessing. Each file is decoded, run through an FFT plus loudness, clipping, dynamic-range and vinyl checks, then scored against fixed rules. Every number you see is measured from the audio itself, so the same file always gets the same verdict.")
                    .font(.system(size: 12))
                    .foregroundColor(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    private var verdictsSection: some View {
        GuideSection("The three verdicts", expanded: true) {
            VStack(alignment: .leading, spacing: 10) {
                verdictRow(.clubReady, "Passes every threshold. Play it with confidence.")
                verdictRow(.review, "Something is worth a listen first — often just a slightly dull master or a couple of clipped peaks. Not necessarily bad.")
                verdictRow(.doNotPlay, "A blocking issue was found: a fake lossless, a low-bitrate rip, heavy clipping, or crushed dynamics. Usually a genuine problem.")
            }
        }
    }

    private func verdictRow(_ v: Verdict, _ text: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            VerdictBadge(verdict: v)
                .frame(width: 110, alignment: .leading)
            Text(text)
                .font(.system(size: 12))
                .foregroundColor(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private var thresholdsNote: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "slider.horizontal.3")
                .foregroundColor(.accentColor)
            Text("The cutoffs above are the defaults. You can tune every one of them in **Settings → Thresholds** to match your taste and genre — for example, loosening the dynamic-range rule for peak-time techno.")
                .font(.system(size: 12))
                .foregroundColor(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.accentColor.opacity(0.10))
        .cornerRadius(8)
    }
}

// MARK: - Reusable pieces

/// A collapsible titled section.
private struct GuideSection<Content: View>: View {
    let heading: String
    let subtitle: String?
    let startExpanded: Bool
    @ViewBuilder let content: () -> Content
    @State private var expanded: Bool

    init(_ heading: String, subtitle: String? = nil, expanded: Bool = false, @ViewBuilder content: @escaping () -> Content) {
        self.heading = heading
        self.subtitle = subtitle
        self.startExpanded = expanded
        self.content = content
        _expanded = State(initialValue: expanded)
    }

    var body: some View {
        DisclosureGroup(isExpanded: $expanded) {
            VStack(alignment: .leading, spacing: 12) {
                if let subtitle {
                    Text(subtitle)
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                content()
            }
            .padding(.top, 8)
            .frame(maxWidth: .infinity, alignment: .leading)
        } label: {
            Text(heading)
                .font(.system(size: 14, weight: .semibold))
        }
        .padding(14)
        .background(Color(NSColor.controlBackgroundColor))
        .cornerRadius(8)
        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color(NSColor.separatorColor), lineWidth: 1))
    }
}

private struct GuideCard<Content: View>: View {
    @ViewBuilder let content: () -> Content
    var body: some View {
        content()
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(NSColor.controlBackgroundColor))
            .cornerRadius(8)
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color(NSColor.separatorColor), lineWidth: 1))
    }
}

private struct FlagRow: View {
    let flag: GuideFlag
    let tint: Color

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack(spacing: 8) {
                Text(flag.name)
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .foregroundColor(.white)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(tint)
                    .cornerRadius(3)
                Text(flag.trigger)
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundColor(.secondary)
            }
            Text(flag.meaning)
                .font(.system(size: 12))
                .fixedSize(horizontal: false, vertical: true)
            Text("→ \(flag.action)")
                .font(.system(size: 11))
                .foregroundColor(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct MetricRow: View {
    let metric: GuideMetric
    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(metric.name)
                .font(.system(size: 12, weight: .semibold))
            Text(metric.explanation)
                .font(.system(size: 12))
                .foregroundColor(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

private struct BulletRow: View {
    let text: String
    var body: some View {
        HStack(alignment: .top, spacing: 6) {
            Text("•").font(.system(size: 12))
            Text(.init(text))
                .font(.system(size: 12))
                .foregroundColor(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// MARK: - Content model + data

private struct GuideFlag: Identifiable {
    let name: String
    let trigger: String
    let meaning: String
    let action: String
    var id: String { name }
}

private struct GuideMetric: Identifiable {
    let name: String
    let explanation: String
    var id: String { name }
}

private enum GuideContent {
    static let blockingFlags: [GuideFlag] = [
        .init(name: "FAKE_LOSSLESS", trigger: "coverage < 85% of Nyquist",
              meaning: "A lossless container (FLAC/ALAC/WAV) that was actually transcoded from a lossy source — e.g. an MP3 re-wrapped as FLAC. You get MP3 quality in a lossless-sized file.",
              action: "Find the real lossless or original; this file is no better than the MP3 it came from."),
        .init(name: "LOW_QUALITY_MP3", trigger: "lossy, ceiling < 19 kHz",
              meaning: "A low-bitrate lossy file (≈192 kbps or less). The top end is missing.",
              action: "Source a 320 kbps or lossless copy — this will sound dull on a club system."),
        .init(name: "CLIPPING", trigger: "> 20 events or longest > 100 ms",
              meaning: "The waveform is pinned at digital maximum and flat-topping, which is audible distortion.",
              action: "Get a cleaner master — clipping is harsh and loud on big speakers."),
        .init(name: "OVER_COMPRESSED", trigger: "dynamic range < 4 dB",
              meaning: "Almost no difference between the loud and quiet parts — a brickwalled master with no punch.",
              action: "Check it's not crushed. Note: legit peak-time techno can trip this (see limitations)."),
    ]

    static let reviewFlags: [GuideFlag] = [
        .init(name: "FAKE_320", trigger: "declares 320, ceiling 19–20.5 kHz",
              meaning: "Claims 320 kbps but the frequency ceiling looks like 256 kbps — likely upscaled.",
              action: "Treat as a 256 rip; fine in a pinch, not audiophile."),
        .init(name: "SUSPECT_LOSSLESS", trigger: "coverage 85–92% of Nyquist",
              meaning: "Borderline coverage — could be a gentle low-pass or a genuine but dull master.",
              action: "Give it a listen; check the spectrogram for a hard cliff."),
        .init(name: "LAME_CONFIRMED", trigger: "LAME header in lossless container",
              meaning: "A LAME (MP3 encoder) fingerprint was found inside a lossless file — strong hint it was an MP3.",
              action: "Verify the source; likely a transcode."),
        .init(name: "MINOR_CLIPPING", trigger: "3–20 clip events",
              meaning: "A handful of clipped peaks. Usually inaudible, but worth a glance.",
              action: "Probably fine; listen if it's a key track."),
        .init(name: "LOW_DYNAMIC_RANGE", trigger: "dynamic range 4–6 dB",
              meaning: "Compressed, but not fully crushed.",
              action: "Fine for most club use; judge by ear."),
        .init(name: "HIGH_NOISE_FLOOR", trigger: "noise floor > -45 dBFS",
              meaning: "Audible hiss or hum in the quiet parts.",
              action: "Listen on headphones; may be a noisy rip."),
        .init(name: "HUM", trigger: "50/60 Hz spike (vinyl only)",
              meaning: "Mains hum from a turntable/ground loop on a vinyl rip.",
              action: "Fine to play; a cleaner rip would remove it."),
    ]

    static let infoFlags: [GuideFlag] = [
        .init(name: "FAKE_24BIT", trigger: "LSB-zero ratio > 95%",
              meaning: "Declared 24-bit but the lowest bits are all zero — it's really 16-bit padded out.",
              action: "Harmless; just not 'true' 24-bit."),
        .init(name: "WOW_FLUTTER", trigger: "> 0.15% (vinyl only)",
              meaning: "Pitch wobble from a turntable or tape.",
              action: "Character, not a defect — your call."),
        .init(name: "PEAK_HOT", trigger: "sample peak > -0.03 dBFS",
              meaning: "Riding right up to full scale.",
              action: "Watch your gain / limiter headroom."),
        .init(name: "LOUDNESS_LOW", trigger: "< -18 LUFS",
              meaning: "Quieter than club norm.",
              action: "You'll ride the channel gain up."),
        .init(name: "LOUDNESS_HOT", trigger: "> -6 LUFS",
              meaning: "A very loud master.",
              action: "Back the gain off to match your other tracks."),
    ]

    static let metrics: [GuideMetric] = [
        .init(name: "Spectral coverage", explanation: "How much of the available frequency range actually carries sound, as a % of Nyquist (half the sample rate). Real lossless fills ~100%; lossy files and transcodes roll off early. The single best 'is this really lossless?' tell."),
        .init(name: "Top frequency", explanation: "The highest frequency with real energy. A hard cliff near 16 kHz means MP3; ~20 kHz means full-range."),
        .init(name: "Loudness (LUFS)", explanation: "Perceived loudness averaged over the whole track. The club sweet spot is roughly -18 to -6 LUFS."),
        .init(name: "Dynamic range", explanation: "The spread between the loud and quiet sections, in dB. More range = more punch; very low = brickwalled."),
        .init(name: "Noise floor", explanation: "The level of the quietest part (dBFS). Lower is cleaner; a high floor means audible hiss or hum."),
        .init(name: "Clipping", explanation: "Samples pinned at digital maximum. A few are fine; many or long runs mean audible distortion."),
        .init(name: "Wow & flutter", explanation: "Pitch instability — a vinyl/tape artifact. Measured with a zero-crossing proxy, so wide-pitch music can false-positive."),
        .init(name: "True / sample peak", explanation: "The loudest single sample. Near 0 dBFS is hot and risks inter-sample overs on playback."),
    ]

    static let practical: [String] = [
        "**Trust CLUB READY.** It cleared every check — cue it up.",
        "**On REVIEW, open the card and read the reason, then listen.** Most REVIEW tracks are totally playable — a slightly dull master or a couple of clipped peaks.",
        "**On DO NOT PLAY, treat it as real.** It's almost always a fake lossless or a low-bitrate rip. Try to source a better file before the set.",
        "**Use the Full Spectrogram button** to see the frequency cliff with your own eyes — a sharp horizontal line across the top is the tell-tale sign of a lossy transcode.",
        "**Check loudness across your set,** not just per track — matching LUFS keeps your gain riding sane.",
    ]

    static let limitations: [String] = [
        "**OVER_COMPRESSED** (< 4 dB) can misfire on legit peak-time techno and loud EDM — trust your ears there.",
        "**Wow & flutter** uses a zero-crossing proxy, so music with a wide pitch range can false-positive.",
        "**True peak** is the sample peak, not a true inter-sample peak (no oversampling) — treat 'hot' as a nudge, not gospel.",
        "**Vinyl detection** can false-positive on digital files that carry hum from studio gear.",
    ]
}
