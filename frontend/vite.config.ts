/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
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
