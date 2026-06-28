# Classification thresholds — all verdict/flag cutoffs live here.

# --- Spectral ---
SPECTRAL_ANALYSIS_DURATION = 60.0
SPECTRAL_FFT_SIZE = 4096
SPECTRAL_ACTIVE_BIN_FLOOR_DB = -80.0
SPECTRAL_FAKE_LOSSLESS_RATIO = 0.85   # < this → FAKE_LOSSLESS
SPECTRAL_SUSPECT_RATIO = 0.92         # < this → SUSPECT / SUSPECT_LOSSLESS
SPECTRAL_MP3_128_CUTOFF_HZ = 17_000
SPECTRAL_MP3_192_CUTOFF_HZ = 19_000
SPECTRAL_MP3_320_CUTOFF_HZ = 20_500
SPECTRAL_MUSIC_CEILING_HZ = 22_050  # cap effective Nyquist for files with sr > 44100
SPECTRAL_CLIFF_FLOOR_HZ = 12_000    # start scanning for cutoff cliff above this frequency
SPECTRAL_CLIFF_HARD_PP = 15.0       # frame-occupancy drop (pp) in 1kHz window → hard MP3 cutoff

# --- Bitrate ---
BITRATE_320_THRESHOLD = 310_000   # claims 320kbps if bitrate >= this
BITRATE_192_THRESHOLD = 190_000   # claims ~192kbps if bitrate >= this

# --- Integrity ---
CLIP_SAMPLE_THRESHOLD = 0.9999          # |sample| >= this is at ceiling
CLIP_MIN_RUN = 2                        # consecutive ceiling samples → one event
CLIP_BLOCKING_EVENTS = 20              # total events > this → CLIPPING (blocking)
CLIP_MARGINAL_EVENTS = 3               # total events > this → MINOR_CLIPPING
CLIP_BLOCKING_MS = 100.0               # OR longest event > this ms → CLIPPING
CLIP_MARGINAL_MS = 10.0                # OR longest event > this ms → MINOR_CLIPPING
LSB_ZERO_RATIO_FAKE_24BIT = 0.95       # > this on 24-bit file → FAKE_24BIT
DYNAMIC_RANGE_BLOCKING_DB = 4.0        # < this → OVER_COMPRESSED (blocking)
DYNAMIC_RANGE_MARGINAL_DB = 6.0        # < this → LOW_DYNAMIC_RANGE
NOISE_FLOOR_MARGINAL_DBFS = -45.0      # > this → HIGH_NOISE_FLOOR
DC_OFFSET_THRESHOLD = 0.005

# --- Loudness ---
TRUE_PEAK_HOT_DBFS = -0.03    # > this → PEAK_HOT
LUFS_CLUB_MIN = -18.0         # outside [-18, -6] → CASUAL OK
LUFS_CLUB_MAX = -6.0

# --- Vinyl ---
VINYL_NOISE_GATE_DBFS = -58.0          # hard gate: file must have noise > this
VINYL_ELEVATED_NOISE_DBFS = -55.0      # scoring: noise > this → +2
VINYL_MIN_SCORE = 4                    # score must reach this to confirm vinyl rip
VINYL_CLICK_MANY = 3                   # clicks >= this → +2 score
VINYL_CLICK_FEW = 2                    # clicks >= this → +1 score
VINYL_HUM_SCORE = 3                    # hum detected → +this score
VINYL_WOW_FLUTTER_FLAG = 0.15          # > this → WOW_FLUTTER flag (display only)
VINYL_HUM_STRONG_DB = 25.0             # hum spike > this dB above local floor → HUM flag (REVIEW)
VINYL_GRADE_NOISE_POOR_DBFS = -45.0
VINYL_GRADE_NOISE_ACCEPTABLE_DBFS = -55.0
VINYL_GRADE_CLICK_POOR = 20
