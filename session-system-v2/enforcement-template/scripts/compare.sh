#!/bin/bash
# compare.sh: Compare project checkout against blessed copies
#
# Used by the enforcement-gate workflow to validate that protected files
# match their blessed copies in the enforcement repo.
#
# Exit code: 0 if all matched (or only not-yet-blessed), 1 if any mismatch or missing

set -euo pipefail

# Arguments
PROJECT_DIR="${1:?Project directory required as \$1}"
BLESSED_DIR="${2:-./blessed}"
PROTECTED_FILES="${3:-./protected-files.txt}"

# Validation
if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "❌ Project directory does not exist: $PROJECT_DIR"
  exit 1
fi

if [[ ! -d "$BLESSED_DIR" ]]; then
  echo "❌ Blessed directory does not exist: $BLESSED_DIR"
  exit 1
fi

if [[ ! -f "$PROTECTED_FILES" ]]; then
  echo "❌ Protected files list does not exist: $PROTECTED_FILES"
  exit 1
fi

# Counters
matched=0
mismatched=0
missing=0
not_yet_blessed=0
mismatch_list=()
missing_list=()

echo "=========================================="
echo "Protected Files Comparison"
echo "=========================================="
echo "Project: $PROJECT_DIR"
echo "Blessed: $BLESSED_DIR"
echo "Config:  $PROTECTED_FILES"
echo ""

# Read protected-files.txt and compare each file
while IFS= read -r file_path; do
  # Skip empty lines and comments
  [[ -z "$file_path" || "$file_path" =~ ^# ]] && continue

  project_file="$PROJECT_DIR/$file_path"
  blessed_file="$BLESSED_DIR/$file_path"

  echo "Checking: $file_path"

  # Check if file exists in project
  if [[ ! -f "$project_file" ]]; then
    echo "  ❌ MISSING: File does not exist in project"
    missing_list+=("$file_path")
    ((missing++))
    continue
  fi

  # Check if blessed copy exists
  if [[ ! -f "$blessed_file" ]]; then
    echo "  ⚠️  NOT-YET-BLESSED: No blessed copy in enforcement repo"
    ((not_yet_blessed++))
    continue
  fi

  # Compare files
  if diff -q "$project_file" "$blessed_file" > /dev/null 2>&1; then
    echo "  ✓ MATCH"
    ((matched++))
  else
    echo "  ❌ DIFF: File differs from blessed copy"
    mismatch_list+=("$file_path")
    ((mismatched++))
  fi
done < "$PROTECTED_FILES"

# Print summary
echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
echo "  Matched:        $matched"
echo "  Mismatched:     $mismatched"
echo "  Missing:        $missing"
echo "  Not-yet-blessed: $not_yet_blessed"
echo ""

# Print details if there are issues
if [[ $mismatched -gt 0 ]]; then
  echo "❌ MISMATCHED FILES:"
  for file in "${mismatch_list[@]}"; do
    echo "  - $file"
  done
  echo ""
fi

if [[ $missing -gt 0 ]]; then
  echo "❌ MISSING FILES:"
  for file in "${missing_list[@]}"; do
    echo "  - $file"
  done
  echo ""
fi

# Determine exit code
if [[ $mismatched -gt 0 ]] || [[ $missing -gt 0 ]]; then
  echo "❌ COMPARISON FAILED"
  exit 1
else
  echo "✓ COMPARISON PASSED (all protected files match blessed copies or are not yet blessed)"
  exit 0
fi
