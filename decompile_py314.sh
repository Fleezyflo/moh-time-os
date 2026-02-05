#!/usr/bin/env bash
set -euo pipefail

PYC="${1:?Usage: $0 /path/to/file.cpython-314.pyc}"
OUT="${2:-./depyo_out}"

mkdir -p "$OUT"

npx -y depyo@latest \
  --basedir "$OUT" \
  --raw-spacing \
  --asm \
  --dump \
  "$PYC"

echo "OK: depyo output in: $OUT"
