#!/bin/bash
# detect_uvicorn_url.sh
# Input: uvicorn log file path
# Output: http://localhost:<port> (always localhost, regardless of bound host)
# Exit 1 if not found

LOGFILE="$1"
[ -z "$LOGFILE" ] && exit 1
[ ! -f "$LOGFILE" ] && exit 1

# Match: Uvicorn running on http://<any-host>:<port>
LINE=$(grep -E "Uvicorn running on http://[^:]+:[0-9]+" "$LOGFILE" 2>/dev/null | head -1)
[ -z "$LINE" ] && exit 1

# Extract port from the URL (last colon-number sequence)
PORT=$(echo "$LINE" | sed -E 's/.*:([0-9]+).*/\1/')
[ -z "$PORT" ] && exit 1

echo "http://localhost:$PORT"
