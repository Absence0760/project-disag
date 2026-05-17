#!/usr/bin/env bash
# Package the Lambda handler + the disag and exceed packages into a zip
# that Terraform uploads. boto3 is already in the Lambda runtime, and
# the rest of the code is pure stdlib (see project root CLAUDE.md), so
# this is a plain zip — no pip install, no Docker.
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$BACKEND_DIR/../.." && pwd)"
BUILD_DIR="$BACKEND_DIR/build"
OUTPUT_ZIP="$BACKEND_DIR/lambda.zip"

rm -rf "$BUILD_DIR" "$OUTPUT_ZIP"
mkdir -p "$BUILD_DIR"

cp "$BACKEND_DIR/handler.py" "$BUILD_DIR/"
cp -r "$ROOT_DIR/disag" "$BUILD_DIR/"
cp -r "$ROOT_DIR/exceed" "$BUILD_DIR/"

# Strip the Tk-dependent GUI modules from the Lambda image. The
# runtime has no display server, the gui.py imports `tkinter`, and
# bundling them just bloats the cold-start unpack.
rm -f "$BUILD_DIR/disag/gui.py" "$BUILD_DIR/exceed/gui.py"
find "$BUILD_DIR" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$BUILD_DIR" -type d -name '.pytest_cache' -prune -exec rm -rf {} +

(cd "$BUILD_DIR" && zip -qr "$OUTPUT_ZIP" .)
echo "Built $OUTPUT_ZIP ($(du -h "$OUTPUT_ZIP" | cut -f1))"
