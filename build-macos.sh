#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"
ARCH="$(uname -m)"
case "$ARCH" in
  arm64) SUFFIX="AppleSilicon" ;;
  x86_64) SUFFIX="Intel" ;;
  *) echo "Unsupported macOS architecture: $ARCH" >&2; exit 1 ;;
esac

rm -rf build "release-macos/$SUFFIX" assets/ChineseCap.iconset assets/ChineseCap.icns
mkdir -p assets/ChineseCap.iconset "release-macos/$SUFFIX"

for SIZE in 16 32 128 256 512; do
  sips -z "$SIZE" "$SIZE" assets/ChineseCap.png --out "assets/ChineseCap.iconset/icon_${SIZE}x${SIZE}.png" >/dev/null
  DOUBLE=$((SIZE * 2))
  sips -z "$DOUBLE" "$DOUBLE" assets/ChineseCap.png --out "assets/ChineseCap.iconset/icon_${SIZE}x${SIZE}@2x.png" >/dev/null
done
iconutil -c icns assets/ChineseCap.iconset -o assets/ChineseCap.icns

"$PYTHON_BIN" -m PyInstaller --noconfirm --clean --windowed --name ChineseCap \
  --icon assets/ChineseCap.icns --add-data "assets/ChineseCap.png:." \
  --distpath "release-macos/$SUFFIX" \
  --collect-all faster_whisper --collect-all ctranslate2 --collect-all sherpa_onnx \
  --collect-all onnxruntime --collect-all opencc --collect-all tokenizers \
  --collect-all yt_dlp --collect-all yt_dlp_ejs --copy-metadata huggingface-hub main.py

APP="release-macos/$SUFFIX/ChineseCap.app"
codesign --deep --force --sign - "$APP"
"$APP/Contents/MacOS/ChineseCap" --smoke-test "release-macos/$SUFFIX/smoke.json"

STAGE="release-macos/$SUFFIX/dmg"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
cp README.md "$STAGE/使用說明.md"
cp THIRD_PARTY.md "$STAGE/THIRD_PARTY.md"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "ChineseCap" -srcfolder "$STAGE" -ov -format UDZO \
  "release-macos/ChineseCap-macOS-$SUFFIX.dmg"
echo "Created release-macos/ChineseCap-macOS-$SUFFIX.dmg"
