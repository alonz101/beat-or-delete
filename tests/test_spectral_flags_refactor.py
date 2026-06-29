"""RED tests for T-3: spectral verdict-label decision moves spectral.py -> flags.py.

Target contract (NOT yet implemented):
  * core.checks.flags.classify_coverage(coverage_ratio, cfg) -> str
        "FAKE_LOSSLESS"  if coverage_ratio <  cfg.SPECTRAL_FAKE_LOSSLESS_RATIO
        "SUSPECT"        if coverage_ratio <  cfg.SPECTRAL_SUSPECT_RATIO
        "GENUINE"        otherwise   (strict < at both boundaries)
  * compute_flags reads cfg = runtime_config.active() once and derives
        sv = classify_coverage(spectral["coverage_ratio"], cfg)
    INSTEAD of reading spectral["spectral_verdict"]. Every former import-bound
    verdict-time constant becomes cfg.<NAME>.
  * core.checks.spectral.check_spectral DROPS the "spectral_verdict" key and the
    FAKE_LOSSLESS/SUSPECT decision; still returns coverage_ratio, top_freq_hz,
    suspected_origin, rolloff_cliff_pp, rolloff_shape, nyquist_hz.

Expected RED right now:
  * Section A/C: classify_coverage does not exist -> ImportError/AttributeError.
  * Section B "no spectral_verdict key" variant: current compute_flags still
    reads spectral["spectral_verdict"] -> KeyError.
  * Section E: current check_spectral still emits "spectral_verdict".
The plain golden asserts (with spectral_verdict present) and the override-driven
asserts already match current behaviour where the logic is unchanged — that is
fine; they become the regression guard after the refactor.

Type fidelity (per the realistic-numpy-data lesson): fixtures mirror the types the
REAL pipeline produces:
  * spectral coverage_ratio / top_freq_hz / nyquist_hz / rolloff_cliff_pp ->
    python float (spectral.py wraps with float()/round()).
  * integrity dB metrics -> python float; clip_events -> python int
    (integrity.py wraps with float()/int()).
  * loudness LUFS / true-peaks -> numpy.float64 (np.log10 / pyloudnorm output).
The golden EXPECTED strings below were CAPTURED from the CURRENT pre-refactor
compute_verdict run over these exact fixtures (capture-and-pin).
"""

import importlib

import numpy as np
import pytest

import core.runtime_config as runtime_config
from core.verdict import compute_verdict


# --------------------------------------------------------------------------- #
# Autouse isolation: no override leaks across tests (before AND after).
# --------------------------------------------------------------------------- #

@pytest.fixture(autouse=True)
def _reset_runtime_config():
    runtime_config.reset()
    yield
    runtime_config.reset()


def _classify_coverage():
    """Fetch the (target) helper fresh so the import error surfaces per-test."""
    flags = importlib.import_module("core.checks.flags")
    return flags.classify_coverage


# --------------------------------------------------------------------------- #
# Realistic raw-component corpus
# --------------------------------------------------------------------------- #

def _base():
    """Clean lossless FLAC -> CLUB READY. Faithful per-field types."""
    return {
        "meta": {
            "lame_header": False,
            "codec": "flac",
            "bitrate": 1_000_000,
            "bit_depth": 16,
        },
        "spectral": {
            "spectral_verdict": "GENUINE",
            "top_freq_hz": 21000.0,
            "suspected_origin": "likely genuine lossless",
            "coverage_ratio": 0.95,
            "rolloff_cliff_pp": 5.0,
            "rolloff_shape": "gradual",
            "nyquist_hz": 22050.0,
        },
        "integrity": {
            "clip_events_L": 0,
            "clip_events_R": 0,
            "clip_max_ms": 0.0,
            "dynamic_range_db": 11.5,
            "noise_floor_dbfs": -72.0,
            "dc_offset_L": 0.0001,
            "dc_offset_R": 0.0001,
            "lsb_zero_ratio": 0.10,
        },
        "loudness": {
            "loudness_lufs": np.float64(-9.8),
            "true_peak_L_dbfs": np.float64(-1.2),
            "true_peak_R_dbfs": np.float64(-1.05),
        },
        "vinyl": None,
    }


def _corpus():
    """Return ordered dict {name: raw} spanning every verdict path.

    Invariant: each item's spectral['spectral_verdict'] equals
    classify_coverage(spectral['coverage_ratio']) at DEFAULT thresholds, so the
    OLD (read spectral_verdict) and NEW (derive from coverage_ratio) paths agree.
    """
    items = {}

    # 1. clean lossless -> CLUB READY
    items["clean_lossless"] = _base()

    # 2. FAKE_LOSSLESS (coverage 0.80 < 0.85) -> DO NOT PLAY
    r = _base()
    r["spectral"].update(
        spectral_verdict="FAKE_LOSSLESS",
        coverage_ratio=0.80,
        top_freq_hz=17600.0,
        suspected_origin="MP3 ~192kbps",
        rolloff_cliff_pp=22.0,
        rolloff_shape="cliff",
    )
    items["fake_lossless"] = r

    # 3. SUSPECT lossless (coverage 0.88) non-vinyl -> SUSPECT_LOSSLESS -> REVIEW
    r = _base()
    r["spectral"].update(
        spectral_verdict="SUSPECT",
        coverage_ratio=0.88,
        top_freq_hz=19400.0,
        suspected_origin="MP3 ~256-320kbps",
        rolloff_cliff_pp=18.0,
        rolloff_shape="cliff",
    )
    items["suspect_lossless"] = r

    # 4. SUSPECT lossless on a CONFIRMED VINYL rip w/ gradual rolloff -> info only
    r = _base()
    r["spectral"].update(
        spectral_verdict="SUSPECT",
        coverage_ratio=0.88,
        top_freq_hz=19400.0,
        suspected_origin="likely genuine lossless",
        rolloff_cliff_pp=6.0,
        rolloff_shape="gradual",
    )
    r["integrity"]["noise_floor_dbfs"] = -52.0
    r["vinyl"] = {
        "vinyl_rip": True,
        "vinyl_grade": "GOOD",
        "wow_flutter_wrms": np.float64(0.08),
        "hum_hz": None,
        "hum_db": None,
    }
    items["suspect_vinyl_gradual"] = r

    # 5. lossy LOW_QUALITY_MP3 (top_freq < 19000) -> DO NOT PLAY
    r = _base()
    r["meta"].update(codec="mp3", bitrate=320_000)
    r["spectral"].update(
        spectral_verdict="FAKE_LOSSLESS",
        coverage_ratio=0.72,
        top_freq_hz=16000.0,
        suspected_origin="MP3 ~128kbps or lower",
        rolloff_cliff_pp=25.0,
        rolloff_shape="cliff",
    )
    items["low_quality_mp3"] = r

    # 6. FAKE_320 (declares 320k, ceiling 19k-20.5k) -> REVIEW
    r = _base()
    r["meta"].update(codec="mp3", bitrate=320_000)
    r["spectral"].update(
        spectral_verdict="SUSPECT",
        coverage_ratio=0.90,
        top_freq_hz=20000.0,
        suspected_origin="MP3 ~256-320kbps",
        rolloff_cliff_pp=17.0,
        rolloff_shape="cliff",
    )
    items["fake_320"] = r

    # 7. CLIPPING blocking (45 events) -> DO NOT PLAY
    r = _base()
    r["integrity"].update(clip_events_L=40, clip_events_R=5, clip_max_ms=12.0)
    items["clipping_blocking"] = r

    # 8. MINOR_CLIPPING (10 events) -> REVIEW
    r = _base()
    r["integrity"].update(clip_events_L=5, clip_events_R=5, clip_max_ms=0.0)
    items["clipping_marginal"] = r

    # 9. OVER_COMPRESSED (DR 3.0 < 4) -> DO NOT PLAY
    r = _base()
    r["integrity"]["dynamic_range_db"] = 3.0
    items["over_compressed"] = r

    # 10. LOW_DYNAMIC_RANGE (DR 5.0) -> REVIEW
    r = _base()
    r["integrity"]["dynamic_range_db"] = 5.0
    items["low_dynamic_range"] = r

    # 11. HIGH_NOISE_FLOOR (-40 > -45) -> REVIEW
    r = _base()
    r["integrity"]["noise_floor_dbfs"] = -40.0
    items["high_noise_floor"] = r

    # 12. VINYL rip with strong HUM -> REVIEW
    r = _base()
    r["integrity"]["noise_floor_dbfs"] = -50.0
    r["vinyl"] = {
        "vinyl_rip": True,
        "vinyl_grade": "GOOD",
        "wow_flutter_wrms": np.float64(0.20),
        "hum_hz": 60.0,
        "hum_db": np.float64(30.0),
    }
    items["vinyl_hum"] = r

    # 13. FAKE_24BIT informational -> CLUB READY
    r = _base()
    r["meta"]["bit_depth"] = 24
    r["integrity"]["lsb_zero_ratio"] = 0.98
    items["fake_24bit"] = r

    # 14. LOUDNESS_HOT informational -> CLUB READY
    r = _base()
    r["loudness"]["loudness_lufs"] = np.float64(-4.0)
    items["loudness_hot"] = r

    # 15. LOUDNESS_LOW informational -> CLUB READY
    r = _base()
    r["loudness"]["loudness_lufs"] = np.float64(-20.0)
    items["loudness_low"] = r

    # 16. PEAK_HOT informational -> CLUB READY
    r = _base()
    r["loudness"].update(true_peak_L_dbfs=np.float64(-0.01),
                         true_peak_R_dbfs=np.float64(-0.02))
    items["peak_hot"] = r

    # 17. DC_OFFSET flag (informational to verdict) -> CLUB READY
    r = _base()
    r["integrity"].update(dc_offset_L=0.01, dc_offset_R=0.0001)
    items["dc_offset"] = r

    return items


def _call(raw):
    return compute_verdict(
        raw["meta"], raw["spectral"], raw["integrity"],
        raw["loudness"], raw["vinyl"],
    )


# --------------------------------------------------------------------------- #
# Golden expected outputs — CAPTURED from current pre-refactor compute_verdict
# over the exact fixtures above (see _corpus()). Pinned byte-for-byte.
# --------------------------------------------------------------------------- #

EXPECTED = {
    'clean_lossless': {'verdict': 'CLUB READY', 'flags': [], 'reasons': [], 'info_reasons': []},
    'fake_lossless': {'verdict': 'DO NOT PLAY', 'flags': ['FAKE_LOSSLESS'], 'reasons': ['lossless container but spectral ceiling at 17600Hz (80.0% of Nyquist) — transcoded from MP3 ~192kbps'], 'info_reasons': []},
    'suspect_lossless': {'verdict': 'REVIEW', 'flags': ['SUSPECT_LOSSLESS'], 'reasons': ['spectral coverage only 88.0% of Nyquist — possible lossy transcode'], 'info_reasons': []},
    'suspect_vinyl_gradual': {'verdict': 'CLUB READY', 'flags': ['VINYL_RIP'], 'reasons': [], 'info_reasons': ['spectral coverage 88.0% of Nyquist — consistent with natural vinyl HF rolloff']},
    'low_quality_mp3': {'verdict': 'DO NOT PLAY', 'flags': ['LOW_QUALITY_MP3'], 'reasons': ['spectral ceiling at 16000Hz — audio quality ≤192kbps, not suitable for club use'], 'info_reasons': []},
    'fake_320': {'verdict': 'REVIEW', 'flags': ['FAKE_320'], 'reasons': ['declared 320kbps but spectral ceiling at 20000Hz — actual quality ~256kbps'], 'info_reasons': []},
    'clipping_blocking': {'verdict': 'DO NOT PLAY', 'flags': ['CLIPPING'], 'reasons': ['45 clipping events detected — longest 12.0ms'], 'info_reasons': []},
    'clipping_marginal': {'verdict': 'REVIEW', 'flags': ['MINOR_CLIPPING'], 'reasons': ['10 minor clipping events'], 'info_reasons': []},
    'over_compressed': {'verdict': 'DO NOT PLAY', 'flags': ['OVER_COMPRESSED'], 'reasons': ['dynamic range 3.0dB — severely over-compressed'], 'info_reasons': []},
    'low_dynamic_range': {'verdict': 'REVIEW', 'flags': ['LOW_DYNAMIC_RANGE'], 'reasons': [], 'info_reasons': []},
    'high_noise_floor': {'verdict': 'REVIEW', 'flags': ['HIGH_NOISE_FLOOR'], 'reasons': ['noise floor at -40.0dBFS — audible hiss at club volume'], 'info_reasons': []},
    'vinyl_hum': {'verdict': 'REVIEW', 'flags': ['VINYL_RIP', 'WOW_FLUTTER', 'HUM'], 'reasons': ['60Hz hum at 30dB above floor — audible at club volume'], 'info_reasons': ['estimated wow & flutter 0.20% (proxy measurement — improving in future version)']},
    'fake_24bit': {'verdict': 'CLUB READY', 'flags': ['FAKE_24BIT'], 'reasons': [], 'info_reasons': ['declared 24-bit but LSBs are all zero — likely upsampled from 16-bit']},
    'loudness_hot': {'verdict': 'CLUB READY', 'flags': ['LOUDNESS_HOT'], 'reasons': [], 'info_reasons': ['loudness -4.0 LUFS — louder than typical club master']},
    'loudness_low': {'verdict': 'CLUB READY', 'flags': ['LOUDNESS_LOW'], 'reasons': [], 'info_reasons': ['loudness -20.0 LUFS — crank the gain, but watch headroom']},
    'peak_hot': {'verdict': 'CLUB READY', 'flags': ['PEAK_HOT'], 'reasons': [], 'info_reasons': ['peak at -0.01 dBFS — headroom tight, ease up on gain when mixing']},
    'dc_offset': {'verdict': 'CLUB READY', 'flags': ['DC_OFFSET'], 'reasons': [], 'info_reasons': []},
}


# =========================================================================== #
# Section A — classify_coverage unit tests (define the new function)
# =========================================================================== #

def test_classify_coverage_fake_lossless_default():
    cc = _classify_coverage()
    assert cc(0.80, runtime_config.active()) == "FAKE_LOSSLESS"


def test_classify_coverage_suspect_default():
    cc = _classify_coverage()
    assert cc(0.88, runtime_config.active()) == "SUSPECT"


def test_classify_coverage_genuine_default():
    cc = _classify_coverage()
    assert cc(0.95, runtime_config.active()) == "GENUINE"


def test_classify_coverage_lower_boundary_is_suspect():
    # strict < : exactly 0.85 is NOT < 0.85 -> falls through to SUSPECT
    cc = _classify_coverage()
    assert cc(0.85, runtime_config.active()) == "SUSPECT"


def test_classify_coverage_upper_boundary_is_genuine():
    # strict < : exactly 0.92 is NOT < 0.92 -> GENUINE
    cc = _classify_coverage()
    assert cc(0.92, runtime_config.active()) == "GENUINE"


def test_classify_coverage_override_fake_lossless_ratio():
    cc = _classify_coverage()
    runtime_config.set_overrides({"SPECTRAL_FAKE_LOSSLESS_RATIO": 0.90})
    assert cc(0.88, runtime_config.active()) == "FAKE_LOSSLESS"


# =========================================================================== #
# Section B — GOLDEN REGRESSION (AC-7)
# =========================================================================== #

@pytest.mark.parametrize("name", list(_corpus().keys()))
def test_golden_verdict_matches_pinned(name):
    """Default config: compute_verdict output is byte-identical to the pinned
    pre-refactor golden for every corpus item."""
    raw = _corpus()[name]
    assert _call(raw) == EXPECTED[name]


@pytest.mark.parametrize("name", list(_corpus().keys()))
def test_golden_verdict_without_spectral_verdict_key(name):
    """Dependency-removal proof: the SAME inputs minus the spectral_verdict key
    must still reproduce the pinned golden — i.e. the verdict is derived from
    coverage_ratio alone. RED today: current compute_flags reads
    spectral['spectral_verdict'] -> KeyError."""
    raw = _corpus()[name]
    del raw["spectral"]["spectral_verdict"]
    assert _call(raw) == EXPECTED[name]


# =========================================================================== #
# Section C — Rounding boundary (Open Question 4)
# =========================================================================== #

def test_rounding_boundary_classifies_on_stored_rounded_value():
    # spectral.py stores coverage_ratio = round(ratio, 4) as a python float.
    # This pins the POST-REFACTOR semantics: classification runs on the STORED
    # rounded value with strict <. 0.8500 is NOT < 0.85 -> SUSPECT.
    # The golden corpus deliberately avoids sub-0.0001 boundary precision so no
    # fixture flips on this rounding decision.
    cc = _classify_coverage()
    assert cc(0.8500, runtime_config.active()) == "SUSPECT"


# =========================================================================== #
# Section D — Overrides drive the verdict (configurability)
# =========================================================================== #

def test_clip_blocking_override_flips_to_do_not_play():
    raw = _corpus()["clipping_marginal"]   # 10 total clip events
    # Default: 10 > CLIP_MARGINAL_EVENTS(3) but not > CLIP_BLOCKING_EVENTS(20)
    assert _call(raw)["verdict"] == "REVIEW"
    assert "MINOR_CLIPPING" in _call(raw)["flags"]

    runtime_config.set_overrides({"CLIP_BLOCKING_EVENTS": 5})
    flipped = _call(_corpus()["clipping_marginal"])
    assert flipped["verdict"] == "DO NOT PLAY"
    assert "CLIPPING" in flipped["flags"]
    assert "MINOR_CLIPPING" not in flipped["flags"]


def test_lufs_min_override_adds_loudness_low():
    # A -14 LUFS file: clean under defaults (LUFS_CLUB_MIN = -18).
    raw = _base()
    raw["loudness"]["loudness_lufs"] = np.float64(-14.0)
    base = _call(raw)
    assert "LOUDNESS_LOW" not in base["flags"]
    assert base["verdict"] == "CLUB READY"

    runtime_config.set_overrides({"LUFS_CLUB_MIN": -12.0})
    raw2 = _base()
    raw2["loudness"]["loudness_lufs"] = np.float64(-14.0)
    flipped = _call(raw2)
    assert "LOUDNESS_LOW" in flipped["flags"]
    assert any("LUFS" in m for m in flipped["info_reasons"])


# =========================================================================== #
# Section E — spectral.py output contract (real, unmocked analysis)
# =========================================================================== #

def test_check_spectral_drops_verdict_keeps_measurements(tmp_path):
    """Run the REAL check_spectral on a synthesized WAV (no mocks). After T-3 the
    returned dict must NOT contain 'spectral_verdict' but must keep coverage_ratio,
    top_freq_hz, suspected_origin, rolloff_cliff_pp, rolloff_shape, nyquist_hz.
    RED today: current check_spectral still emits 'spectral_verdict'."""
    sf = pytest.importorskip("soundfile")
    pytest.importorskip("librosa")
    from core.checks.spectral import check_spectral

    sr = 44100
    t = np.linspace(0, 2.0, int(sr * 2.0), endpoint=False)
    # broadband-ish content so active bins are found
    sig = 0.1 * np.sin(2 * np.pi * 1000 * t) + 0.02 * np.random.randn(t.size)
    wav = tmp_path / "synth.wav"
    sf.write(str(wav), sig.astype(np.float32), sr)

    out = check_spectral(str(wav), analysis_duration=2.0)

    assert "spectral_verdict" not in out, "spectral_verdict must move to flags.py"
    for key in ("coverage_ratio", "top_freq_hz", "suspected_origin",
                "rolloff_cliff_pp", "rolloff_shape", "nyquist_hz"):
        assert key in out, f"check_spectral must still return {key!r}"
