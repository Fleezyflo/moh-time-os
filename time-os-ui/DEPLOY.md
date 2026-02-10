# Time OS UI - Deployment Guide

## Prerequisites

- Node.js >= 18
- npm >= 9
- Python 3.10+ (for API server)

## Environment Variables

### Frontend (Vite)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_BASE_URL` | No | `/api/control-room` | Backend API base URL |

Create a `.env.local` file for local overrides (not committed to git):

```bash
VITE_API_BASE_URL=http://localhost:8000/api/control-room
```

### Backend (FastAPI)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_PATH` | No | `./time_os.db` | SQLite database path |
| `PORT` | No | `8000` | Server port |

## Local Development

### 1. Install Dependencies

```bash
# Frontend
cd time-os-ui
npm install

# Backend
cd ../api
pip install -r requirements.txt
```

### 2. Start Backend

```bash
cd api
python server.py
# Server runs at http://localhost:8000
```

### 3. Start Frontend (Dev Mode)

```bash
cd time-os-ui
npm run dev
# Opens at http://localhost:5173
```

## Production Build

### 1. Build Frontend

```bash
cd time-os-ui
npm run build
```

Output: `dist/` directory with static assets.

### 2. Validate Build

```bash
# Run tests
npm test

# Type check
npm run typecheck

# Lint
npm run lint
```

### 3. Deploy Static Assets

The `dist/` folder contains:
- `index.html` - Main entry point
- `assets/` - JS/CSS bundles (hashed filenames)
- `sw.js` - Service worker for PWA
- `manifest.webmanifest` - PWA manifest

Deploy these files to any static hosting:
- Nginx
- Cloudflare Pages
- Vercel
- AWS S3 + CloudFront

### 4. Configure Reverse Proxy

Example Nginx config:

```nginx
server {
    listen 80;
    server_name timeos.example.com;

    # Frontend static files
    location / {
        root /var/www/time-os-ui/dist;
        try_files $uri $uri/ /index.html;
    }

    # API proxy
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Validation Checklist

Before deploying, verify:

- [ ] `npm run build` completes without errors
- [ ] `npm test` passes all tests
- [ ] `npm run typecheck` reports no type errors
- [ ] No hardcoded localhost URLs in build output
- [ ] Environment variables are set correctly
- [ ] API health check responds: `GET /api/control-room/health`
- [ ] PWA manifest loads correctly
- [ ] Service worker registers

## CI/CD Integration

For automated builds, run:

```bash
npm ci                # Clean install
npm run typecheck     # Type check
npm run lint          # Lint check
npm test              # Run tests
npm run build         # Production build
```

All commands must exit with code 0 for a valid build.
