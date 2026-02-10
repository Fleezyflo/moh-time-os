import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
// PWA disabled temporarily to clear cached service worker issues
// import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    // PWA disabled - re-enable after clearing browser cache
  ],
  server: {
    host: true,
    port: 5173,
    proxy: {
      // Proxy /api requests to backend during development
      '/api': {
        target: 'http://localhost:8420',
        changeOrigin: true,
        secure: false,
      }
    }
  }
})
