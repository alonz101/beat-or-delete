#!/usr/bin/env bash
# build_app.sh — builds DJAnalyzer.app
# Run from repo root: bash build/build_app.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$REPO_ROOT/build"
DIST_DIR="$BUILD_DIR/dist"
APP_NAME="BeatOrDelete"
APP_BUNDLE="$BUILD_DIR/$APP_NAME.app"
PYTHON="$HOME/.pyenv/versions/3.11.9/bin/python3"
PYINSTALLER="$HOME/.pyenv/versions/3.11.9/bin/pyinstaller"

echo "==> Phase 1: Freeze Python executables"
cd "$REPO_ROOT"
"$PYINSTALLER" build/analyzer.spec     --distpath "$DIST_DIR" --workpath "$BUILD_DIR/work" --noconfirm --log-level WARN
"$PYINSTALLER" build/batch.spec        --distpath "$DIST_DIR" --workpath "$BUILD_DIR/work" --noconfirm --log-level WARN
"$PYINSTALLER" build/spectrogram.spec  --distpath "$DIST_DIR" --workpath "$BUILD_DIR/work" --noconfirm --log-level WARN
echo "    dj-analyze:     $(du -sh "$DIST_DIR/dj-analyze" | cut -f1)"
echo "    dj-batch:       $(du -sh "$DIST_DIR/dj-batch" | cut -f1)"
echo "    dj-spectrogram: $(du -sh "$DIST_DIR/dj-spectrogram" | cut -f1)"

echo "==> Phase 2: Build Swift binary"
cd "$REPO_ROOT/DJAnalyzer"
swift build -c release 2>&1 | grep -E "error:|warning:|Build complete" || true
SWIFT_BIN=".build/release/DJAnalyzer"
if [ ! -f "$SWIFT_BIN" ]; then
    echo "ERROR: Swift build failed — binary not found at $SWIFT_BIN"
    exit 1
fi

echo "==> Phase 3: Assemble .app bundle"
rm -rf "$APP_BUNDLE"
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"

# Swift binary
cp "$SWIFT_BIN" "$APP_BUNDLE/Contents/MacOS/$APP_NAME"

# Info.plist
cp "Sources/DJAnalyzer/Info.plist" "$APP_BUNDLE/Contents/Info.plist"

# App icon
mkdir -p "$APP_BUNDLE/Contents/Resources"
cp "$BUILD_DIR/AppIcon.icns" "$APP_BUNDLE/Contents/Resources/AppIcon.icns"

# Frozen Python executable bundles (onedir mode — no extraction delay at runtime)
cp -R "$DIST_DIR/dj-analyze"     "$APP_BUNDLE/Contents/Resources/dj-analyze"
cp -R "$DIST_DIR/dj-batch"       "$APP_BUNDLE/Contents/Resources/dj-batch"
cp -R "$DIST_DIR/dj-spectrogram" "$APP_BUNDLE/Contents/Resources/dj-spectrogram"

echo "==> Done: $APP_BUNDLE"
echo ""
echo "Bundle size: $(du -sh "$APP_BUNDLE" | cut -f1)"
echo ""
echo "To run: open $APP_BUNDLE"
echo ""
echo "To codesign (requires Apple Developer account):"
echo "  codesign --deep --force --sign \"Developer ID Application: <Your Name>\" $APP_BUNDLE"
