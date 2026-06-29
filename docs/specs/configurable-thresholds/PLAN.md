# PLAN: User-Configurable Thresholds (#7)

## Overview
Add a runtime override layer so DJs can tune **verdict-time** thresholds (the cutoffs
applied in `core/checks/flags.py`) without editing source. Swift writes a flat
`{CONST_NAME: value}` map of only the changed keys to
`~/Library/Application Support/BeatOrDelete/thresholds.json`. A new
`core/runtime_config.py` overlays that file on the `core/config.py` defaults and exposes
the **active** values, read at call time by `flags.py` (and by the spectral-label helper).
`core/config_hash.py` is extended to fold the active overrides into the hash, so a changed
threshold yields a distinct `verdicts` row while the `measurements` row stays shared —
the two-layer cache invariant. The FAKE_LOSSLESS / SUSPECT decision is refactored OUT of
`spectral.py` (measurement-time) into `flags.py` (verdict-time), operating on the already
stored `coverage_ratio`, so spectral coverage becomes reverdict-able; `spectral.py` still
computes and stores `coverage_ratio`, `top_freq_hz`, `suspected_origin`, rolloff, etc.
On Save, Swift writes the JSON then re-runs the existing per-track one-shot `dj-analyze`
path for every loaded file; each fresh process imports a new `CONFIG_HASH`, the cache hits
the measurement and misses the verdict, so it reverdicts on the cheap no-librosa path and
returns immediately (bounded by the cap=3 semaphore). No new pip deps (json + hashlib +
sqlite3 are stdlib).

Measurement-time thresholds (FFT size/duration, CLIP_SAMPLE_THRESHOLD, CLIP_MIN_RUN,
vinyl scoring, and the MP3 cutoff Hz used in both `spectral.py` and `flags.py`) stay fixed
in v1 — exposing them would force full re-analysis. See Open Questions.

## Waves

**Wave 1 — runtime config foundation (Python).** `core/runtime_config.py`: load + overlay
+ active-value accessor + a test-injection hook. Zero dependency on anything else; unblocks
everything downstream. Solo task.

**Wave 2 — hash + spectral refactor (Python).** Two tasks against the Wave-1 contract,
disjoint files. T-2 folds active overrides into `config_hash`. T-3 (the high-risk task)
moves the spectral verdict-label decision from `spectral.py` into `flags.py` and converts
`flags.py`'s import-bound constants to call-time active reads. T-3 must preserve
byte-identical default verdicts — guarded by a golden regression over the fixture corpus.

**Wave 3 — assembly seam (Python).** Solo task. `spectral_verdict` no longer exists in the
raw blob, so the two places that assemble the public result dict
(`analyzer.analyze_raw`, `cache._assemble`) must derive it at verdict-time via the new
`flags.classify_coverage` helper. This is the output-contract seam consumed by CSV/PDF
export and the Swift model, hence sequenced after T-3 and kept solo.

**Wave 4 — Swift UI + Save→reverdict flow.** Three tasks, disjoint files. T-5: override
map model + threshold catalog + `thresholds.json` writer/reader in `AppSettings`. T-6:
Config tab UI (grouped fields, current+default, inline validation, Reset) and the
view-model wiring so the Settings scene can reach the queue. T-7: `reverdictAll()` on the
view model that re-runs the one-shot analyze for every loaded file. `AnalyzerService.swift`
needs NO change (the frozen `dj-analyze` reads `thresholds.json` itself).

## Tasks
| # | Wave | File | What | Touches AC |
|---|------|------|------|------------|
| T-1 | 1 | `core/runtime_config.py` (new, **Python**) | Load `thresholds.json`, coerce override values to each default's type, filter to known UPPERCASE primitive config keys. Expose `active()` (cached snapshot of defaults overlaid with overrides), `load_overrides()`, plus `set_overrides()` / `reset()` test hooks and a monkeypatchable `_overrides_path()`. | AC-2, AC-8, AC-9, AC-10 |
| T-2 | 2 | `core/config_hash.py` (edit, **Python**) | Fold active overrides into the hash: take the UPPERCASE-primitive defaults dict, overlay `load_overrides()` (only keys that exist as defaults), hash sorted `repr`. No file → identical hash to today. | AC-4, AC-8 |
| T-3 | 2 | `core/checks/spectral.py` + `core/checks/flags.py` (edit, **Python**, HIGH RISK) | Remove the FAKE_LOSSLESS/SUSPECT/GENUINE decision and `spectral_verdict` key from `spectral.py`. Add `flags.classify_coverage(coverage_ratio, cfg)`. In `flags.py` read all configurable thresholds from `runtime_config.active()` at call time; keep `SPECTRAL_MP3_192/320_CUTOFF_HZ` as fixed `core.config` imports (shared with spectral, not exposed v1). Byte-identical defaults — golden regression. | AC-7, AC-8 |
| T-4 | 3 | `core/analyzer.py` + `core/cache.py` (edit, **Python**, solo) | Both `analyze_raw`'s assembled dict and `cache._assemble` set `authenticity.spectral_verdict` via `flags.classify_coverage(spectral_coverage, runtime_config.active())` instead of reading `spectral["spectral_verdict"]`. Confirm `reverdict.py` needs no change. | AC-3, AC-4, AC-7, AC-9 |
| T-5 | 4 | `AppSettings.swift` (edit) + `ThresholdCatalog.swift` (new, **Swift**) | Add `thresholdOverrides: [String:Double]` (persisted), a static catalog (name, label, category, default, optional paired-bound partner), and `writeThresholdsFile()` / `loadThresholdsFile()` to `~/Library/Application Support/BeatOrDelete/thresholds.json` (write only non-default keys; delete file or write `{}` on full reset). | AC-1, AC-2, AC-5, AC-6 |
| T-6 | 4 | `SettingsView.swift` + `DJAnalyzerApp.swift` + `ContentView.swift` (edit, **Swift**) | Config tab (TabView) listing catalog grouped by category, each row: editable field + current value + default; inline numeric + min<max validation; Save (disabled while invalid) → write file then trigger reverdict; Reset to Defaults. Inject the shared `AppViewModel` into both the WindowGroup and Settings scenes so Save can reverdict. | AC-1, AC-5, AC-6 |
| T-7 | 4 | `AppViewModel.swift` (edit, **Swift**) | `reverdictAll()`: for every loaded item, re-set `.analyzing` and re-run `AnalyzerService.analyze` (cache hits measurement, misses verdict → fast reverdict), update badges/reasons in place. Make the instance reachable from the Settings scene (shared/injected). | AC-3, AC-5 |

## Interface contracts

### T-1 `core/runtime_config.py` (the runtime config layer)
```python
import json
from pathlib import Path
from types import SimpleNamespace
import core.config as _config

_CACHE: SimpleNamespace | None = None          # process-lifetime snapshot

def _overrides_path() -> Path:                  # monkeypatched by tests
    return Path.home() / "Library" / "Application Support" / "BeatOrDelete" / "thresholds.json"

def _defaults() -> dict:                        # UPPERCASE primitive constants only
    return {k: v for k, v in vars(_config).items()
            if k == k.upper() and not k.startswith("_")
            and isinstance(v, (int, float, str, bool))}

def load_overrides() -> dict:
    """Read overrides file → {NAME: value}; only keys present in defaults; each value
    COERCED to type(default) so repr is stable (JSON 4 vs 4.0). Missing/corrupt file → {}.
    Never raises to callers. Not cached (config_hash calls this directly)."""
    ...

def active() -> SimpleNamespace:
    """Cached snapshot: defaults overlaid with load_overrides(). Attribute access:
    active().CLIP_BLOCKING_EVENTS. Cached for the process; rebuilt after set_overrides/reset."""
    ...

def set_overrides(d: dict) -> None: ...   # test hook: inject without touching disk; busts cache
def reset() -> None: ...                   # test hook: clear cache → next active() re-reads file
```
- AC-8: no file → `load_overrides()=={}` → `active()` equals defaults exactly.
- `flags.py` calls `cfg = runtime_config.active()` once at the top of `compute_flags`.
- Caching is correct because each `dj-analyze` process reads one fixed file; cross-process
  config change happens by re-spawn (Save). Tests change config mid-process via
  `set_overrides()` / `reset()`.

### T-2 `core/config_hash.py` (overrides folded in)
```python
import hashlib
import core.config as _config
import core.runtime_config as _rc

def compute_config_hash() -> str:
    values = {k: v for k, v in vars(_config).items()
              if k == k.upper() and not k.startswith("_")
              and isinstance(v, (int, float, str, bool))}
    values.update({k: v for k, v in _rc.load_overrides().items() if k in values})
    items = sorted(f"{k}={v!r}" for k, v in values.items())
    return hashlib.sha256("\n".join(items).encode()).hexdigest()

CONFIG_HASH: str = compute_config_hash()   # module-load-time
```
- AC-8: empty overrides → identical string → identical hash to today (existing
  `test_config_hash.py` reference test still passes **provided the test env has no file** —
  test plan adds a fixture that points `_overrides_path()` at an empty temp dir).
- Type coercion in `load_overrides` is what guarantees an override equal to the default
  collapses to the same `repr` (so "set to default value" == "no override" for the hash).

### T-3 `core/checks/spectral.py` + `core/checks/flags.py` (spectral → flags refactor)
`spectral.py` return dict: **drop** `"spectral_verdict"`; drop the
`SPECTRAL_FAKE_LOSSLESS_RATIO` / `SPECTRAL_SUSPECT_RATIO` imports and lines 38–43. Keep
`coverage_ratio` rounded to 4 exactly as today (constraint #2 says classify on the
already-stored ratio — see Open Question 4 on the rounding boundary). Everything else
(`top_freq_hz`, `suspected_origin`, rolloff, `nyquist_hz`) unchanged.

`flags.py`:
```python
import core.runtime_config as runtime_config
from core.config import SPECTRAL_MP3_192_CUTOFF_HZ, SPECTRAL_MP3_320_CUTOFF_HZ  # FIXED, not exposed

def classify_coverage(coverage_ratio: float, cfg) -> str:
    if coverage_ratio < cfg.SPECTRAL_FAKE_LOSSLESS_RATIO:
        return "FAKE_LOSSLESS"
    if coverage_ratio < cfg.SPECTRAL_SUSPECT_RATIO:
        return "SUSPECT"
    return "GENUINE"

def compute_flags(meta, spectral, integrity, loudness, vinyl=None):
    cfg = runtime_config.active()
    sv = classify_coverage(spectral["coverage_ratio"], cfg)   # replaces spectral["spectral_verdict"]
    ...  # every former import-bound constant becomes cfg.<NAME>
```
Configurable set read via `cfg.` (constraint #1): `BITRATE_320_THRESHOLD`,
`BITRATE_192_THRESHOLD` (currently imported but unused in flags — expose for forward-compat,
note it), `LSB_ZERO_RATIO_FAKE_24BIT`, `CLIP_BLOCKING_EVENTS`, `CLIP_MARGINAL_EVENTS`,
`CLIP_BLOCKING_MS`, `CLIP_MARGINAL_MS`, `DYNAMIC_RANGE_BLOCKING_DB`,
`DYNAMIC_RANGE_MARGINAL_DB`, `NOISE_FLOOR_MARGINAL_DBFS`, `DC_OFFSET_THRESHOLD`,
`TRUE_PEAK_HOT_DBFS`, `LUFS_CLUB_MIN`, `LUFS_CLUB_MAX`, `VINYL_WOW_FLUTTER_FLAG`,
`VINYL_HUM_STRONG_DB`, plus `SPECTRAL_FAKE_LOSSLESS_RATIO`, `SPECTRAL_SUSPECT_RATIO`.
`SPECTRAL_MP3_192/320_CUTOFF_HZ` stay as plain `core.config` imports so they remain
identical to `spectral.py`'s `_classify_cutoff` (NOT user-configurable in v1).

### T-4 assembly seam (`analyzer.analyze_raw` + `cache._assemble`)
Both build `authenticity.spectral_verdict`. Replace
`"spectral_verdict": spectral["spectral_verdict"]` with:
```python
import core.checks.flags as flags
import core.runtime_config as runtime_config
...
"spectral_verdict": flags.classify_coverage(spectral["coverage_ratio"], runtime_config.active()),
```
- This makes the displayed label reflect active thresholds (consistent with the verdict),
  on both fresh-analyze and reverdict-from-cache paths.
- The raw blob no longer carries `spectral_verdict`; `reverdict_from_raw` → `compute_verdict`
  → `compute_flags` reads `coverage_ratio` (present in all raws, old and new). No change to
  `reverdict.py` — confirm in test.
- `csv_writer.py` / `pdf_writer.py` read `authenticity["spectral_verdict"]` from the
  assembled dict — still present, no change.

### T-5 Swift transport (`AppSettings` + `ThresholdCatalog`)
```swift
struct ThresholdSpec {
    let name: String      // EXACT python const name, e.g. "DYNAMIC_RANGE_BLOCKING_DB"
    let label: String     // "Over-compressed (dB)"
    let category: String  // "Spectral" | "Clipping" | "Dynamics" | "Loudness" | "Vinyl"
    let defaultValue: Double
    let pairedMaxOf: String?   // if set, this field must be < the named field (min<max)
}
enum ThresholdCatalog { static let all: [ThresholdSpec] = [ ... ] }  // mirrors core/config.py

extension AppSettings {
    // persisted JSON-encoded map of NON-default overrides only
    var thresholdOverrides: [String: Double] { get set }
    func writeThresholdsFile()   // ~/Library/Application Support/BeatOrDelete/thresholds.json
    func loadThresholdsFile()
}
```
Write only keys that differ from `defaultValue`; Reset clears the map and writes `{}` (or
removes the file). Defaults are duplicated Swift-side — see Open Question 2.

### T-7 Save → reverdict (`AppViewModel`)
```swift
func reverdictAll() {
    for item in items where item.isAnalyzed {   // .done or .failed
        analyzeItem(item)   // existing one-shot path; cache hits measurement, reverdicts
    }
}
```
Save (T-6) calls `AppSettings.shared.writeThresholdsFile()` THEN
`appViewModel.reverdictAll()`. Bounded by the existing cap=3 `AsyncSemaphore`.

## Test plan per task

**T-1 (`runtime_config`)** — pytest, monkeypatch `_overrides_path()` to a temp dir.
- No file present → `load_overrides()=={}`, `active()` attributes equal `core.config` values.
- File `{"DYNAMIC_RANGE_BLOCKING_DB": 3.0}` → `active().DYNAMIC_RANGE_BLOCKING_DB==3.0`,
  all other attrs unchanged.
- Type coercion: JSON `{"CLIP_BLOCKING_EVENTS": 25}` (int default) and
  `{"LUFS_CLUB_MIN": -20}` (float default) coerce to `int`/`float` so `repr` is stable.
- Unknown key in file (e.g. `"BOGUS": 1`) is ignored (not in defaults).
- Corrupt / empty / non-dict JSON → `{}`, no raise.
- `set_overrides({...})` then `active()` reflects it without disk; `reset()` re-reads file.

**T-2 (`config_hash`)** — pytest.
- No overrides (temp empty path) → hash equals the independent reference over
  `vars(core.config)` (keeps existing `test_config_hash.py` green; add the temp-path fixture).
- `set_overrides({"DYNAMIC_RANGE_BLOCKING_DB": 3.0})` → `compute_config_hash()` differs.
- Override set to the default value → hash equals the no-override hash (coercion proof).
- Override on a non-existent / non-primitive key → no effect.

**T-3 (spectral + flags refactor)** — pytest, realistic numpy-dtype raw blobs (per
[[tests-use-realistic-numpy-data]]); use `set_overrides` to flip thresholds.
- `classify_coverage`: ratios `0.80→FAKE_LOSSLESS`, `0.88→SUSPECT`, `0.95→GENUINE` at
  defaults; override `SPECTRAL_FAKE_LOSSLESS_RATIO=0.90` flips `0.88→FAKE_LOSSLESS`.
- **GOLDEN REGRESSION (AC-7):** for every existing audio fixture, assert
  `compute_verdict(...)` output (verdict, flags, reasons, info_reasons) is byte-identical
  before vs after the refactor at default config. Build the "before" golden from current
  `main` (or a captured JSON snapshot). Prove no fixture flips on the rounding boundary
  (Open Question 4).
- `compute_flags` honors a clip-events override (e.g. `CLIP_BLOCKING_EVENTS=5` turns a
  10-event file from MINOR_CLIPPING → CLIPPING) and a LUFS-window override.
- `spectral.py` output dict no longer contains `spectral_verdict`; still has
  `coverage_ratio`, `top_freq_hz`, `suspected_origin`, rolloff, `nyquist_hz`.

**T-4 (assembly seam)** — pytest with temp HOME + temp DB (mirror `test_cache.py`).
- AC-4: analyze a fixture; `set_overrides` a verdict-time threshold so `CONFIG_HASH`
  differs; `get_or_analyze` again → new `verdicts` row, SAME `measurements` row, analyze/FFT
  counter unchanged (monkeypatch `core.analyzer.analyze_raw` counter).
- AC-7: assembled `authenticity.spectral_verdict` equals `classify_coverage(coverage,active())`
  on both fresh and reverdict paths; with defaults equals the pre-refactor value for fixtures.
- Reverdict from a raw blob lacking `spectral_verdict` succeeds (proves no dependency).
- AC-9: CLI (`python core/analyzer.py f`) and `batch.run_batch` honor an injected override
  (write a real temp `thresholds.json`, assert verdict changes vs no file).

**T-5 (`AppSettings` + catalog)** — Swift unit test.
- `writeThresholdsFile()` writes only non-default keys; round-trips via `loadThresholdsFile()`.
- Reset → file is `{}` / removed.
- Every `ThresholdSpec.name` matches a `core/config.py` constant (a CI grep/parity check —
  see Open Question 2).

**T-6 (Config tab UI)** — manual + lightweight view-model validation tests.
- AC-1: tab lists catalog grouped by category with current value + default shown.
- AC-6: non-numeric or min≥max (paired bounds, e.g. `LUFS_CLUB_MIN` ≥ `LUFS_CLUB_MAX`,
  `DYNAMIC_RANGE_BLOCKING_DB` ≥ `DYNAMIC_RANGE_MARGINAL_DB`) → inline error, Save disabled.
- AC-5: Reset to Defaults restores values and reverdicts loaded files.

**T-7 (`reverdictAll`)** — manual GUI verification is REQUIRED
(per [[verify-real-path-before-claiming-done]]): load files, edit a threshold, Save, observe
badges/reasons update with NO FFT (e.g. tail the cache / confirm sub-second turnaround),
and AC-4 holds (measurements untouched). Do not substitute an isolated binary test.

**End-to-end (AC-2, AC-3, AC-8):** edit + Save → `thresholds.json` present and survives
restart; with the file deleted, behavior identical to defaults.

## Open questions — RESOLVED (2026-06-29)
- Q1: **DECIDED — keep `SPECTRAL_MP3_192/320_CUTOFF_HZ` fixed in v1.** Coverage ratios are the configurable spectral knob; MP3 cutoff Hz stay shared/fixed.
- Q2: **DECIDED — hardcode Swift catalog + CI parity grep** against `core/config.py`. No build-time JSON emit.
- Q3: **DECIDED — drop `BITRATE_192_THRESHOLD`** from the configurable set (no flag reads it).
- Q4: **DECIDED — rely on the golden regression.** Add an exact `coverage_ratio` key only if a fixture actually flips on the round-4 boundary.
- Q5: **DECIDED — N one-shot spawns on Save acceptable v1** (cap=3 bounds it; each is a fast cache-hit reverdict). In-process batch reverdict is a possible later optimization.
- Q6: **DECIDED — `AppViewModel` becomes a shared instance** injected into both WindowGroup + Settings scenes (T-6 owns the injection).
