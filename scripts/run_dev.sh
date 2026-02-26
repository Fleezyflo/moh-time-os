#!/usr/bin/env bash
# DEPRECATED: Use ./scripts/dev.sh or `make dev` instead.
# This script is kept as a redirect to avoid breaking muscle memory.
echo "run_dev.sh is deprecated. Redirecting to dev.sh..."
exec "$(dirname "${BASH_SOURCE[0]}")/dev.sh" "$@"
