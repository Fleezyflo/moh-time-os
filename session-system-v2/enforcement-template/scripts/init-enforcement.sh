#!/bin/bash
# init-enforcement.sh: Initialize a new enforcement repo
#
# Run this script once to bootstrap a new enforcement repository with
# the required directory structure and initial configuration files.
#
# This creates:
#   - blessed/              (stores canonical copies of protected files)
#   - scripts/              (contains enforcement scripts)
#   - .github/workflows/    (contains GitHub Actions workflows)
#   - protected-files.txt   (configuration file listing protected files)
#   - README.md             (documentation)

set -euo pipefail

# Detect script location to determine repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "Initializing Enforcement Repository"
echo "=========================================="
echo "Repository root: $REPO_ROOT"
echo ""

# Create directory structure
echo "Creating directories..."

mkdir -p "$REPO_ROOT/blessed"
echo "  ✓ Created blessed/"

touch "$REPO_ROOT/blessed/.gitkeep"

mkdir -p "$REPO_ROOT/scripts"
echo "  ✓ Created scripts/"

mkdir -p "$REPO_ROOT/.github/workflows"
echo "  ✓ Created .github/workflows/"

# Create protected-files.txt if it doesn't exist
if [[ ! -f "$REPO_ROOT/protected-files.txt" ]]; then
  cat > "$REPO_ROOT/protected-files.txt" << 'EOF'
# protected-files.txt: List of files protected by the enforcement system
#
# Format:
#   - One file path per line (relative to project root)
#   - Lines starting with # are comments
#   - Empty lines are ignored
#
# When a file is added here:
#   1. Create a blessed copy: cp project/path/to/file blessed/path/to/file
#   2. The enforcement gate will enforce that project's version matches blessed
#   3. Any modifications to protected files must be blessed separately
#
# Example:
#   config/security.yaml
#   lib/core/auth.py
#   .env.production

EOF
  echo "  ✓ Created protected-files.txt"
else
  echo "  ⚠️  protected-files.txt already exists (skipped)"
fi

# Create README.md if it doesn't exist
if [[ ! -f "$REPO_ROOT/README.md" ]]; then
  cat > "$REPO_ROOT/README.md" << 'EOF'
# Enforcement Repository

This repository enforces that critical files in the project repository match
blessed (canonical) copies. See SETUP.md in the session-system-v2 template
for complete setup instructions.

## Quick Reference

- `blessed/` — Canonical copies of protected files
- `scripts/compare.sh` — Compare project files against blessed copies
- `scripts/restore.sh` — Restore blessed copies into project CI workspace
- `protected-files.txt` — Registry of protected file paths
- `.github/workflows/enforcement-gate.yml` — PR enforcement check
- `.github/workflows/bless.yml` — Admin workflow to update blessed copies
EOF
  echo "  ✓ Created README.md"
else
  echo "  ⚠️  README.md already exists (skipped)"
fi

# Create .gitignore if it doesn't exist
if [[ ! -f "$REPO_ROOT/.gitignore" ]]; then
  cat > "$REPO_ROOT/.gitignore" << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~
.DS_Store

# OS
Thumbs.db
.AppleDouble
.LSOverride
EOF
  echo "  ✓ Created .gitignore"
else
  echo "  ⚠️  .gitignore already exists (skipped)"
fi

echo ""
echo "=========================================="
echo "Initialization Complete"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Edit protected-files.txt and add the files you want to protect:"
echo "   nano $REPO_ROOT/protected-files.txt"
echo ""
echo "2. Create blessed copies of each protected file:"
echo "   cp ../project-repo/path/to/file blessed/path/to/file"
echo ""
echo "3. Commit the initial setup:"
echo "   git add blessed/ scripts/ .github/ protected-files.txt README.md"
echo "   git commit -m 'chore: initialize enforcement repo'"
echo ""
echo "4. Create GitHub secrets (see README.md Setup section):"
echo "   - PROJECT_STATUS_TOKEN"
echo ""
echo "5. Configure your project repo's CI to restore blessed copies"
echo "   and trigger the enforcement gate (see README.md)"
echo ""
echo "For detailed instructions, see: $REPO_ROOT/README.md"
