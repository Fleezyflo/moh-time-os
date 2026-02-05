\
#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-.}"
bash "$ROOT/scripts/verify_step6_component_library.sh" "$ROOT"
bash "$ROOT/scripts/verify_step7_data_access_layer.sh" "$ROOT"
