/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    // Installable on phones ("Add to Home Screen"). The service worker caches the app's own files
    // for fast start-up; /api is never cached, so scores and questions always come from the server.
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'apple-touch-icon.png'],
      manifest: {
        name: 'Vocab Sensei',
        short_name: 'Vocab Sensei',
        description: 'Learn the words of your next read before you read them.',
        theme_color: '#0969da',
        background_color: '#fafaf7',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
      workbox: { navigateFallbackDenylist: [/^\/api\//] },
    }),
  ],
  server: {
    // Forward API calls to the FastAPI dev server, so the app always calls relative /api URLs.
    proxy: { '/api': 'http://localhost:8000' },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    env: { TZ: 'UTC' }, // same results on every machine (the quiz sends the browser's time zone)
    restoreMocks: true,
  },
})
