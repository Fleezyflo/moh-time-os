#!/bin/bash

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_SYSTEM_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

# Parse arguments
if [[ $# -lt 3 ]]; then
  echo -e "${RED}Error: Missing required arguments${NC}"
  echo "Usage: bootstrap.sh <target-dir> <project-name> <owner> [--enforcement-repo <repo>] [--skip-validation]"
  echo ""
  echo "Arguments:"
  echo "  target-dir          Target directory where project will be set up"
  echo "  project-name        Name of the project"
  echo "  owner               Project owner/organization"
  echo ""
  echo "Optional flags:"
  echo "  --enforcement-repo  Enforcement repo name (default: <owner>/enforcement)"
  echo "  --skip-validation   Skip running validate_system.py at the end"
  exit 1
fi

TARGET_DIR="$1"
PROJECT_NAME="$2"
OWNER="$3"
ENFORCEMENT_REPO="${OWNER}/enforcement"
SKIP_VALIDATION=false

# Parse optional arguments
shift 3
while [[ $# -gt 0 ]]; do
  case "$1" in
    --enforcement-repo)
      ENFORCEMENT_REPO="$2"
      shift 2
      ;;
    --skip-validation)
      SKIP_VALIDATION=true
      shift
      ;;
    *)
      echo -e "${RED}Error: Unknown option '$1'${NC}"
      exit 1
      ;;
  esac
done

# Validate inputs
if [[ -z "$TARGET_DIR" || -z "$PROJECT_NAME" || -z "$OWNER" ]]; then
  echo -e "${RED}Error: Invalid inputs${NC}"
  exit 1
fi

# Resolve target directory path
TARGET_DIR="$(cd "$(dirname "$TARGET_DIR")" && pwd)/$(basename "$TARGET_DIR")"

# Check if target already has session system files
if [[ -f "$TARGET_DIR/state.json" ]] || [[ -d "$TARGET_DIR/sessions" ]]; then
  echo -e "${RED}Error: Target directory already contains session system files${NC}"
  echo "Target: $TARGET_DIR"
  echo "Please use a clean directory or remove existing session system files."
  exit 1
fi

echo -e "${GREEN}Setting up session-system-v2 for: $PROJECT_NAME${NC}"
echo "  Target: $TARGET_DIR"
echo "  Owner: $OWNER"
echo "  Enforcement Repo: $ENFORCEMENT_REPO"
echo ""

# Create target directory if it doesn't exist
if [[ ! -d "$TARGET_DIR" ]]; then
  echo -e "${YELLOW}Creating target directory...${NC}"
  mkdir -p "$TARGET_DIR"
fi

# Create directory structure
echo -e "${YELLOW}Creating directory structure...${NC}"
mkdir -p "$TARGET_DIR/sessions"
mkdir -p "$TARGET_DIR/plan"
mkdir -p "$TARGET_DIR/scripts"

touch "$TARGET_DIR/sessions/.gitkeep"
touch "$TARGET_DIR/plan/.gitkeep"

# Helper function for file copying with placeholder replacement
copy_and_replace() {
  local source="$1"
  local dest="$2"

  if [[ ! -f "$source" ]]; then
    echo -e "${RED}Error: Source file not found: $source${NC}"
    exit 1
  fi

  # Create destination directory if needed
  mkdir -p "$(dirname "$dest")"

  # Copy and replace placeholders
  sed \
    -e "s/{{PROJECT_NAME}}/$PROJECT_NAME/g" \
    -e "s/{{OWNER}}/$OWNER/g" \
    -e "s|{{ENFORCEMENT_REPO}}|$ENFORCEMENT_REPO|g" \
    "$source" > "$dest"

  echo "  ✓ $dest"
}

# Copy core template files with placeholder replacement
echo -e "${YELLOW}Copying template files...${NC}"
copy_and_replace "$SESSION_SYSTEM_ROOT/core/state.json" "$TARGET_DIR/state.json"
copy_and_replace "$SESSION_SYSTEM_ROOT/core/AGENT.md" "$TARGET_DIR/AGENT.md"
copy_and_replace "$SESSION_SYSTEM_ROOT/core/sessions/session-template.yaml" "$TARGET_DIR/sessions/session-template.yaml"
copy_and_replace "$SESSION_SYSTEM_ROOT/core/plan/phase-template.yaml" "$TARGET_DIR/plan/phase-template.yaml"
copy_and_replace "$SESSION_SYSTEM_ROOT/core/plan/index.yaml" "$TARGET_DIR/plan/index.yaml"

# Copy files without replacement needed
echo -e "${YELLOW}Copying static files...${NC}"
if [[ -f "$SESSION_SYSTEM_ROOT/core/state.schema.json" ]]; then
  cp "$SESSION_SYSTEM_ROOT/core/state.schema.json" "$TARGET_DIR/state.schema.json"
  echo "  ✓ $TARGET_DIR/state.schema.json"
fi

if [[ -f "$SESSION_SYSTEM_ROOT/core/scripts/check_state.py" ]]; then
  cp "$SESSION_SYSTEM_ROOT/core/scripts/check_state.py" "$TARGET_DIR/scripts/check_state.py"
  echo "  ✓ $TARGET_DIR/scripts/check_state.py"
fi

if [[ -f "$SESSION_SYSTEM_ROOT/core/scripts/generate_handoff.py" ]]; then
  cp "$SESSION_SYSTEM_ROOT/core/scripts/generate_handoff.py" "$TARGET_DIR/scripts/generate_handoff.py"
  echo "  ✓ $TARGET_DIR/scripts/generate_handoff.py"
fi

if [[ -f "$SESSION_SYSTEM_ROOT/core/scripts/validate_system.py" ]]; then
  cp "$SESSION_SYSTEM_ROOT/core/scripts/validate_system.py" "$TARGET_DIR/scripts/validate_system.py"
  echo "  ✓ $TARGET_DIR/scripts/validate_system.py"
fi

# Verify state.json was created and has correct structure
echo -e "${YELLOW}Verifying state.json...${NC}"
if [[ ! -f "$TARGET_DIR/state.json" ]]; then
  echo -e "${RED}Error: state.json was not created${NC}"
  exit 1
fi

# Check if Python is available and validation script exists
if [[ "$SKIP_VALIDATION" == false ]] && [[ -f "$TARGET_DIR/scripts/validate_system.py" ]]; then
  echo -e "${YELLOW}Running validation...${NC}"
  if command -v python3 &> /dev/null; then
    cd "$TARGET_DIR"
    if python3 scripts/validate_system.py; then
      echo -e "${GREEN}✓ Validation passed${NC}"
    else
      echo -e "${RED}✗ Validation failed${NC}"
      exit 1
    fi
    cd - > /dev/null
  else
    echo -e "${YELLOW}⚠ Python3 not found, skipping validation${NC}"
  fi
elif [[ "$SKIP_VALIDATION" == true ]]; then
  echo -e "${YELLOW}Skipping validation (--skip-validation flag set)${NC}"
fi

# Print next steps
echo ""
echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Edit ${TARGET_DIR}/plan/index.yaml to define your phases"
echo "  2. Create phase-*.yaml files in ${TARGET_DIR}/plan/ for each phase"
echo "  3. Set up enforcement repo:"
echo "     - See session-system-v2/docs/SETUP.md for enforcement integration"
echo "     - Link enforcement repo: $ENFORCEMENT_REPO"
echo ""
echo "To view state:"
echo "  cat ${TARGET_DIR}/state.json"
echo ""
echo "To generate handoff:"
echo "  python3 ${TARGET_DIR}/scripts/generate_handoff.py"
echo ""
