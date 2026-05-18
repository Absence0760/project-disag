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
find "$BUILD_DIR" -type d \( -name '__pycache__' -o -name '.pytest_cache' \) -prune -exec rm -rf {} +

# Defensive secret + cruft exclusions. None of these should exist
# inside disag/ or exceed/ today, but anything matching these
# patterns has no business in a deployed Lambda image — strip
# pre-emptively so a future accidental commit doesn't ride along.
# Docs (CLAUDE.md, README.md) are stripped too — operator notes are
# noise in production, not source code.
find "$BUILD_DIR" -type f \( \
    -name '.env' -o -name '.env.*' \
    -o -name '*.pem' -o -name '*.key' -o -name '*.p12' -o -name '*.pfx' \
    -o -name 'credentials' -o -name 'credentials.*' \
    -o -name 'id_rsa' -o -name 'id_ed25519' \
    -o -name 'CLAUDE.md' -o -name 'README.md' \
\) -delete

(cd "$BUILD_DIR" && zip -qr "$OUTPUT_ZIP" .)
echo "Built $OUTPUT_ZIP ($(du -h "$OUTPUT_ZIP" | cut -f1))"
