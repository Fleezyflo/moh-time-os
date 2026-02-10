#!/bin/bash
# detect_vite_url.sh
# Input: Vite log file path
# Output: http://localhost:<port>/
# Exit 1 if not found

LOGFILE="$1"
[ -z "$LOGFILE" ] && exit 1
[ ! -f "$LOGFILE" ] && exit 1

# Vite outputs: ➜  Local:   http://localhost:5173/
# Extract URL after "Local:" - handles unicode arrow and variable spacing
URL=$(grep "Local:" "$LOGFILE" 2>/dev/null | head -1 | sed -E 's/.*Local:[[:space:]]*(http:\/\/[^[:space:]]+).*/\1/')
[ -z "$URL" ] && exit 1

# Ensure trailing slash
case "$URL" in
  */) echo "$URL" ;;
  *)  echo "$URL/" ;;
esac
