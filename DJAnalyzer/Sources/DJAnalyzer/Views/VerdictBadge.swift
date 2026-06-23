import SwiftUI

struct VerdictBadge: View {
    let verdict: Verdict

    var body: some View {
        Text(verdict.displayName)
            .font(.system(size: 11, weight: .bold, design: .monospaced))
            .foregroundColor(.white)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(verdict.color)
            .cornerRadius(4)
    }
}
