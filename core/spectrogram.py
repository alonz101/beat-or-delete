import numpy as np
import librosa
import librosa.display
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import tempfile


def _render(
    path: str,
    duration: float,
    fig_size: tuple[float, float],
    y_axis: str = "hz",
    show_xaxis: bool = False,
) -> tuple[plt.Figure, plt.Axes, int, float]:
    y, sr = librosa.load(path, sr=None, mono=True, duration=duration)
    actual_duration = len(y) / sr

    fig, ax = plt.subplots(figsize=fig_size, dpi=100)
    fig.patch.set_facecolor("#1a1a1a")
    ax.set_facecolor("#1a1a1a")

    D = librosa.amplitude_to_db(np.abs(librosa.stft(y, n_fft=2048)), ref=np.max)
    librosa.display.specshow(
        D, sr=sr,
        x_axis="time" if show_xaxis else None,
        y_axis=y_axis,
        ax=ax, cmap="magma", vmin=-80, vmax=0,
    )

    if y_axis == "hz":
        ax.set_ylim(0, sr / 2)

    ax.tick_params(axis="y", colors="#aaaaaa", labelsize=7, length=3, width=0.5)
    ax.spines["left"].set_color("#555555")
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.yaxis.label.set_visible(False)

    if show_xaxis:
        ax.tick_params(axis="x", colors="#aaaaaa", labelsize=7, length=3, width=0.5)
        ax.spines["bottom"].set_color("#555555")
        ax.spines["bottom"].set_linewidth(0.8)
        ax.spines["bottom"].set_visible(True)
        ax.xaxis.label.set_color("#aaaaaa")
        ax.set_xlim(0, actual_duration)
    else:
        ax.xaxis.set_visible(False)
        ax.spines["bottom"].set_visible(False)

    return fig, ax, sr, actual_duration


def _save(fig: plt.Figure) -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    fig.savefig(tmp.name, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)
    return tmp.name


def generate_thumbnail(path: str, duration: float = 30.0) -> str:
    fig, ax, sr, _ = _render(path, duration, (6, 1.8), y_axis="hz", show_xaxis=False)
    plt.tight_layout(pad=0.2)
    return _save(fig)


def generate_full(
    path: str,
    duration: float = 600.0,
    hum_hz: float | None = None,
    clip_times_sec: list[float] | None = None,
) -> str:
    fig, ax, sr, actual_dur = _render(path, duration, (14, 4), y_axis="log", show_xaxis=True)

    if hum_hz:
        # Short pointer at left edge only (2% width) — doesn't cover content
        ax.axhline(hum_hz, xmin=0, xmax=0.02, color="#44ccff", linewidth=1.5)
        # Label in the Y axis margin
        ax.text(
            -0.04, hum_hz,
            f"► {hum_hz:.0f}Hz",
            transform=ax.get_yaxis_transform(),
            color="#44ccff",
            fontsize=7,
            fontweight="bold",
            ha="right",
            va="center",
        )

    # Clip markers within the rendered audio window
    for t in (clip_times_sec or []):
        if t <= actual_dur:
            ax.axvline(t, color="#ff6666", alpha=0.65, linewidth=1.0, linestyle="--")

    plt.tight_layout(pad=0.3)
    return _save(fig)


# Back-compat alias — existing callers that import generate_spectrogram still work
generate_spectrogram = generate_thumbnail
