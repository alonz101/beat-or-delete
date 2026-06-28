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


def _render_hum_strip(
    y: np.ndarray, sr: int, hum_hz: float, ax: plt.Axes, fig: plt.Figure
) -> None:
    """Narrow 20–200Hz line graph that makes a narrowband hum spike visible."""
    n_samples = min(len(y), sr * 10)
    spectrum = np.abs(np.fft.rfft(y[:n_samples]))
    freqs = np.fft.rfftfreq(n_samples, d=1.0 / sr)

    mask = (freqs >= 20) & (freqs <= 200)
    ax.plot(freqs[mask], spectrum[mask], color="#aaaaaa", linewidth=0.8)

    ax.axvline(hum_hz, color="#44ccff", linewidth=1.2, alpha=0.9)
    ylo, yhi = ax.get_ylim()
    ax.text(
        hum_hz + 1, ylo + (yhi - ylo) * 0.82,
        f"{hum_hz:.0f}Hz", color="#44ccff", fontsize=7, va="top",
    )

    ax.set_facecolor("#1a1a1a")
    fig.patch.set_facecolor("#1a1a1a")
    ax.set_xlim(20, 200)
    ax.tick_params(axis="both", colors="#aaaaaa", labelsize=7, length=2)
    for spine in ax.spines.values():
        spine.set_color("#555555")
    ax.spines["top"].set_visible(False)
    ax.set_xlabel("Hz (20–200)", color="#aaaaaa", fontsize=7)
    ax.yaxis.set_visible(False)


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
    y, sr = librosa.load(path, sr=None, mono=True, duration=duration)
    actual_dur = len(y) / sr

    if hum_hz:
        fig, (ax, ax_hum) = plt.subplots(
            2, 1, figsize=(14, 5), dpi=100,
            gridspec_kw={"height_ratios": [4, 1], "hspace": 0.35},
        )
    else:
        fig, ax = plt.subplots(figsize=(14, 4), dpi=100)
        ax_hum = None

    fig.patch.set_facecolor("#1a1a1a")
    ax.set_facecolor("#1a1a1a")

    D = librosa.amplitude_to_db(np.abs(librosa.stft(y, n_fft=2048)), ref=np.max)
    librosa.display.specshow(
        D, sr=sr, x_axis="time", y_axis="log",
        ax=ax, cmap="magma", vmin=-80, vmax=0,
    )
    ax.set_xlim(0, actual_dur)
    ax.tick_params(axis="y", colors="#aaaaaa", labelsize=7, length=3, width=0.5)
    ax.tick_params(axis="x", colors="#aaaaaa", labelsize=7, length=3, width=0.5)
    ax.spines["left"].set_color("#555555")
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["right"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["bottom"].set_color("#555555")
    ax.spines["bottom"].set_linewidth(0.8)
    ax.yaxis.label.set_visible(False)
    ax.xaxis.label.set_color("#aaaaaa")

    if hum_hz:
        # Y-axis margin pointer — strip below shows the actual spike
        ax.text(
            -0.04, hum_hz, f"► {hum_hz:.0f}Hz",
            transform=ax.get_yaxis_transform(),
            color="#44ccff", fontsize=7, fontweight="bold", ha="right", va="center",
        )

    for t in (clip_times_sec or []):
        if t <= actual_dur:
            ax.axvline(t, color="#ff6666", alpha=0.65, linewidth=1.0, linestyle="--")

    if hum_hz and ax_hum is not None:
        _render_hum_strip(y, sr, hum_hz, ax_hum, fig)

    plt.tight_layout(pad=0.3)
    return _save(fig)


# Back-compat alias — existing callers that import generate_spectrogram still work
generate_spectrogram = generate_thumbnail
