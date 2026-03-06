#!/bin/bash
# restore.sh: Restore blessed copies of protected files before running checks
#
# Used by the PROJECT repo's CI to overwrite any local modifications to
# protected files with their blessed copies. This ensures CI always runs
# against the canonical blessed versions, regardless of what's in the branch.
#
# This script is distributed to projects and should be run early in the
# CI pipeline, before any linting, testing, or type checking.
#
# Arguments:
#   $1: Path to enforcement repo clone (required)
#   $2: Project root path (default: .)

set -euo pipefail

ENFORCEMENT_REPO="${1:?Enforcement repo path required as \$1}"
PROJECT_ROOT="${2:-.}"

# Validate enforcement repo exists
if [[ ! -d "$ENFORCEMENT_REPO" ]]; then
  echo "❌ Enforcement repo not found: $ENFORCEMENT_REPO"
  exit 1
fi

PROTECTED_FILES="$ENFORCEMENT_REPO/protected-files.txt"
BLESSED_DIR="$ENFORCEMENT_REPO/blessed"

# Validate protected-files.txt exists
if [[ ! -f "$PROTECTED_FILES" ]]; then
  echo "❌ protected-files.txt not found in enforcement repo: $PROTECTED_FILES"
  exit 1
fi

# Validate blessed directory exists
if [[ ! -d "$BLESSED_DIR" ]]; then
  echo "❌ Blessed directory not found: $BLESSED_DIR"
  exit 1
fi

# Track restoration
restored_count=0
skipped_count=0

echo "=========================================="
echo "Restoring Protected Files"
echo "=========================================="
echo "Enforcement repo: $ENFORCEMENT_REPO"
echo "Project root:     $PROJECT_ROOT"
echo "Blessed source:   $BLESSED_DIR"
echo ""

# Process each protected file
while IFS= read -r file_path; do
  # Skip empty lines and comments
  [[ -z "$file_path" || "$file_path" =~ ^# ]] && continue

  blessed_file="$BLESSED_DIR/$file_path"
  project_file="$PROJECT_ROOT/$file_path"

  # Skip if blessed copy doesn't exist yet (file not yet blessed)
  if [[ ! -f "$blessed_file" ]]; then
    echo "⚠️  SKIP: $file_path (not yet blessed)"
    ((skipped_count++))
    continue
  fi

  # Create parent directory if needed
  project_dir=$(dirname "$project_file")
  if [[ ! -d "$project_dir" ]]; then
    mkdir -p "$project_dir"
    echo "Created directory: $project_dir"
  fi

  # Copy blessed file to project
  cp "$blessed_file" "$project_file"
  echo "✓ RESTORED: $file_path"
  ((restored_count++))
done < "$PROTECTED_FILES"

echo ""
echo "=========================================="
echo "Restoration Complete"
echo "=========================================="
echo "  Restored: $restored_count"
echo "  Skipped:  $skipped_count"
echo ""

if [[ $restored_count -eq 0 && $skipped_count -eq 0 ]]; then
  echo "⚠️  No protected files found or processed"
fi

echo "✓ All blessed copies have been restored"
exit 0
