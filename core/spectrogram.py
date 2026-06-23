import numpy as np
import librosa
import librosa.display
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import tempfile


def generate_spectrogram(path: str, duration: float = 30.0) -> str:
    """
    Generate a spectrogram PNG for the first `duration` seconds.
    Returns path to temp PNG file.
    """
    y, sr = librosa.load(path, sr=None, mono=True, duration=duration)

    fig, ax = plt.subplots(figsize=(6, 1.8), dpi=100)
    fig.patch.set_facecolor("#1a1a1a")
    ax.set_facecolor("#1a1a1a")

    D = librosa.amplitude_to_db(np.abs(librosa.stft(y, n_fft=2048)), ref=np.max)
    img = librosa.display.specshow(
        D, sr=sr, x_axis="time", y_axis="hz",
        ax=ax, cmap="magma", vmin=-80, vmax=0
    )

    ax.set_ylim(0, sr / 2)

    # Hide x-axis (time) — not useful for quality checking
    ax.xaxis.set_visible(False)

    # Y-axis: visible ticks and spine
    ax.tick_params(axis="y", colors="#aaaaaa", labelsize=7, length=3, width=0.5)
    ax.spines["left"].set_color("#555555")
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.yaxis.label.set_visible(False)

    plt.tight_layout(pad=0.2)

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    fig.savefig(tmp.name, facecolor=fig.get_facecolor())
    plt.close(fig)

    return tmp.name
