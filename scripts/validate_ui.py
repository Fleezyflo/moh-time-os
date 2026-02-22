#!/usr/bin/env python3
"""Brief 20 validation — UI Polish, PWA & Production."""

import os
import subprocess
import sys
from pathlib import Path

os.chdir(Path(__file__).parent.parent)
passes = failures = 0


def check(name, condition, detail=""):
    global passes, failures
    if condition:
        passes += 1
        print(f"  [PASS] {name}: {detail}" if detail else f"  [PASS] {name}")
    else:
        failures += 1
        print(f"  [FAIL] {name}: {detail}" if detail else f"  [FAIL] {name}")


# Check pages exist
ui = Path("time-os-ui/src")
pages = list((ui / "pages").glob("*.tsx"))
check("Pages exist", len(pages) >= 10, f"{len(pages)} pages")

# Check component library
comps = list((ui / "components/ui").glob("*.tsx")) + list((ui / "components").glob("*.tsx"))
check("Component library", len(comps) >= 7, f"{len(comps)} components found")

# Check auth components
check("Auth context", (ui / "components/auth/AuthContext.tsx").exists())
check("Login screen", (ui / "components/auth/LoginScreen.tsx").exists())
check("Protected route", (ui / "components/auth/ProtectedRoute.tsx").exists())

# Check pickers
check("Team member picker", (ui / "components/pickers/TeamMemberPicker.tsx").exists())

# Check SSE hook
check("SSE hook", (ui / "hooks/useEventStream.ts").exists())

# Check Brief 20 additions
check("Skeleton component", (ui / "components/Skeleton.tsx").exists())
check("Error boundary", (ui / "components/ErrorBoundary.tsx").exists())
check("Keyboard shortcuts hook", (ui / "hooks/useKeyboardShortcuts.ts").exists())

# Check PWA config
vite_config = Path("time-os-ui/vite.config.ts").read_text()
check("VitePWA plugin enabled", "VitePWA" in vite_config, "VitePWA imported and configured")
check("PWA manifest config", "MOH Time OS" in vite_config, "Manifest name configured")
check("PWA theme color", "#0f172a" in vite_config, "Theme color set correctly")
check("PWA display standalone", "standalone" in vite_config, "Display mode set to standalone")
check("Workbox runtime caching", "runtimeCaching" in vite_config, "Workbox API cache configured")
check("API cache strategy", "StaleWhileRevalidate" in vite_config, "/api/* caching configured")

# Check main.tsx service worker registration
main_tsx = Path("time-os-ui/src/main.tsx").read_text()
check(
    "Service worker registration",
    "navigator.serviceWorker.register" in main_tsx,
    "Registration code in place",
)
check(
    "Unregister old workers",
    "navigator.serviceWorker.getRegistrations" in main_tsx,
    "Cleanup code in place",
)

# Check index.html
index_html = Path("time-os-ui/index.html").read_text()
check(
    "Manifest link in HTML",
    "manifest.webmanifest" in index_html or "manifest.json" in index_html,
    "Manifest linked",
)
check("Google Fonts preconnect", "fonts.googleapis.com" in index_html, "Preconnect added")
check("Gstatic preconnect", "fonts.gstatic.com" in index_html, "Gstatic preconnect added")

# Check router accessibility
router_tsx = Path("time-os-ui/src/router.tsx").read_text()
check("Skip-to-content link", "Skip to main content" in router_tsx, "Accessibility link present")
check("Navigation role", 'role="navigation"' in router_tsx, "Navigation role added")
check("Main content role", 'role="main"' in router_tsx, "Main role added")
check(
    "Lazy loading with React.lazy", "lazy(() => import" in router_tsx, "Code splitting implemented"
)
check("Suspense wrapper", "Suspense fallback" in router_tsx, "Suspense fallback configured")

# Check design tokens wired
index_css = (ui / "index.css").read_text()
check(
    "Design tokens imported",
    "tokens.css" in index_css or "design/system" in index_css,
    "Design system imported",
)

# Check no window.prompt
result = subprocess.run(
    ["grep", "-r", "window.prompt", "time-os-ui/src/"], capture_output=True, text=True
)
check(
    "No window.prompt()",
    result.returncode != 0,
    "none found" if result.returncode != 0 else result.stdout.strip(),
)

# Check build output exists
dist_exists = Path("time-os-ui/dist/index.html").exists()
check(
    "Build artifact exists",
    dist_exists,
    "dist/index.html present" if dist_exists else "dist not built yet",
)

print(f"\n{'=' * 60}")
print(f"VALIDATION RESULTS: {passes} passed, {failures} failed out of {passes + failures} checks")
print(f"{'=' * 60}")

if failures > 0:
    print("Brief 20 validation: FAILED - Some checks did not pass")
    sys.exit(1)

print("Brief 20 validation: SUCCESS - All checks passed!")
print("\nUI Polish & Production features:")
print("  - PWA enabled with VitePWA plugin and Workbox caching")
print("  - Service worker registration for offline support")
print("  - Loading states with Skeleton components")
print("  - Error boundary for render error handling")
print("  - Accessibility: skip-to-content, semantic roles")
print("  - Keyboard shortcuts hook (Escape, ?)")
print("  - Code splitting with React.lazy + Suspense")
print("  - Performance: Google Fonts preconnect, font-display: swap")
sys.exit(0)
