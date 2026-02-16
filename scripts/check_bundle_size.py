#!/usr/bin/env python3
"""
Check frontend bundle size limits.

Ensures bundles don't grow unbounded.
"""

import subprocess
import sys
from pathlib import Path

UI_DIR = Path("time-os-ui")
DIST_DIR = UI_DIR / "dist"

# Size limits in KB
MAX_JS_BUNDLE = 600  # Main JS bundle
MAX_CSS_BUNDLE = 100  # Main CSS bundle
MAX_TOTAL = 800  # Total assets


def get_file_sizes() -> dict[str, int]:
    """Get sizes of built assets in KB."""
    sizes = {}

    if not DIST_DIR.exists():
        return sizes

    assets_dir = DIST_DIR / "assets"
    if not assets_dir.exists():
        assets_dir = DIST_DIR

    for file in assets_dir.rglob("*"):
        if file.is_file():
            size_kb = file.stat().st_size // 1024
            ext = file.suffix.lower()

            if ext == ".js":
                sizes["js"] = sizes.get("js", 0) + size_kb
            elif ext == ".css":
                sizes["css"] = sizes.get("css", 0) + size_kb
            else:
                sizes["other"] = sizes.get("other", 0) + size_kb

    sizes["total"] = sum(sizes.values())
    return sizes


def build_if_needed() -> bool:
    """Build the UI if dist doesn't exist."""
    if DIST_DIR.exists():
        return True

    try:
        result = subprocess.run(
            ["pnpm", "run", "build"],
            capture_output=True,
            text=True,
            cwd=UI_DIR,
            timeout=120,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def main() -> int:
    """Main entry point."""
    if not UI_DIR.exists():
        print("✅ No UI directory found.")
        return 0

    # Get sizes (build if needed)
    sizes = get_file_sizes()

    if not sizes:
        print("⚠️ No dist directory. Run 'pnpm build' first.")
        return 1  # BLOCKING

    violations = []

    if sizes.get("js", 0) > MAX_JS_BUNDLE:
        violations.append(f"  JS bundle: {sizes['js']}KB (max {MAX_JS_BUNDLE}KB)")

    if sizes.get("css", 0) > MAX_CSS_BUNDLE:
        violations.append(f"  CSS bundle: {sizes['css']}KB (max {MAX_CSS_BUNDLE}KB)")

    if sizes.get("total", 0) > MAX_TOTAL:
        violations.append(f"  Total: {sizes['total']}KB (max {MAX_TOTAL}KB)")

    print(
        f"📦 Bundle sizes: JS={sizes.get('js', 0)}KB, CSS={sizes.get('css', 0)}KB, Total={sizes.get('total', 0)}KB"
    )

    if violations:
        print("\n⚠️ BUNDLE SIZE EXCEEDED:")
        print("\n".join(violations))
        print("\nOptimize imports, use code splitting, remove unused deps.")
        # Warning only
        return 1 if violations else 0  # BLOCKING

    print("✅ Bundle sizes within limits.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
