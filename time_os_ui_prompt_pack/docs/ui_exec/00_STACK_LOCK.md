# 00_STACK_LOCK — Time OS UI

## Framework
- **Build Tool:** Vite 7.3.1
- **UI Library:** React 19.2.4
- **Language:** TypeScript 5.9.3
- **Styling:** Tailwind CSS 4.1.18
- **Routing:** TanStack Router 1.158.1
- **PWA:** vite-plugin-pwa 1.2.0
- **Package Manager:** pnpm 10.28.2

## Design Requirements
- **Mobile-first:** Responsive layouts, touch-friendly (44px tap targets)
- **PWA:** Standalone display, offline caching, installable
- **Cross-platform:** iOS Safari, Android Chrome, Desktop

## Commands
```bash
# Install dependencies
pnpm install

# Development server (http://localhost:5173)
pnpm dev

# Production build
pnpm build

# Preview production build
pnpm preview
```

## Directory Structure
```
time-os-ui/
├── index.html
├── vite.config.ts          # Vite + PWA config
├── postcss.config.js       # Tailwind v4
├── tsconfig.json
├── src/
│   ├── main.tsx            # Entry point
│   ├── router.tsx          # TanStack Router routes
│   ├── index.css           # Tailwind + base styles
│   ├── components/         # Reusable UI components
│   ├── lib/                # Data access, types, utilities
│   ├── fixtures/           # Contract-shaped mock data
│   └── routes/             # Route components (if split)
├── public/
│   ├── pwa-192x192.png
│   └── pwa-512x512.png
└── dist/                   # Build output
```

## Routes Implemented
| Route | Component | Status |
|-------|-----------|--------|
| `/` | Snapshot (Control Room) | ✓ Placeholder |
| `/clients` | Clients Portfolio | ✓ Placeholder |
| `/clients/$clientId` | Client Detail | ✓ Placeholder |
| `/team` | Team Portfolio | ✓ Placeholder |
| `/team/$id` | Team Member Detail | ✓ Placeholder |
| `/intersections` | Intersections | ✓ Placeholder |
| `/issues` | Issues Inbox | ✓ Placeholder |
| `/fix-data` | Fix Data Center | ✓ Placeholder |

## PWA Configuration
- **Display:** standalone
- **Theme color:** #0f172a
- **Offline:** Workbox precaching for static assets
- **API caching:** NetworkFirst strategy for /api/* routes

## Verified
- `pnpm dev` → serves on http://localhost:5173 ✓
- `pnpm build` → builds in 722ms, PWA files generated ✓

---

LOCKED: 2026-02-05
