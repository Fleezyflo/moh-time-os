#!/usr/bin/env bash
# ============================================
# GIT COMMIT WRAPPER - BLOCKS --no-verify
# ============================================
# Install: git config alias.commit '!bash scripts/git-commit-wrapper.sh'
# Or add to shell: alias git='function _git(){ if [[ "$1" == "commit" && "$*" == *"--no-verify"* ]]; then echo "❌ --no-verify is DISABLED in this repo"; return 1; fi; command git "$@"; }; _git'

for arg in "$@"; do
    if [[ "$arg" == "--no-verify" ]] || [[ "$arg" == "-n" ]]; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  ❌ --no-verify is DISABLED in this repo"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "Pre-commit hooks are mandatory. Fix the issues."
        echo "Even if bypassed, pre-push and GitHub will block you."
        echo ""
        exit 1
    fi
done

exec git commit "$@"
