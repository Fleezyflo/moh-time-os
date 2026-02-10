#!/bin/bash
# Ripgrep guardrails - check for forbidden patterns

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "Checking for forbidden patterns..."

# Pattern 1: Direct writes to legacy inbox_items table
echo -n "  INSERT INTO inbox_items... "
RESULT=$(rg -c 'INSERT\s+INTO\s+inbox_items\s*\(' lib/ --glob '*.py' --glob '!*test*' --glob '!*migration*' --glob '!*safety*' 2>/dev/null || true)
if [ -n "$RESULT" ]; then
    echo "❌ FOUND"
    exit 1
else
    echo "✅ OK"
fi

echo -n "  UPDATE inbox_items SET... "
RESULT=$(rg -c 'UPDATE\s+inbox_items\s+SET' lib/ --glob '*.py' --glob '!*test*' --glob '!*migration*' --glob '!*safety*' 2>/dev/null || true)
if [ -n "$RESULT" ]; then
    echo "❌ FOUND"
    exit 1
else
    echo "✅ OK"
fi

echo ""
echo "✅ No forbidden patterns found"
exit 0
