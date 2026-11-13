import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  build: {
    // The hub server serves the built app from here (see backend/fms/main.py).
    outDir: '../backend/fms/static',
    emptyOutDir: true,
    // The app is served from the hub's own disk (and later cached on the phone),
    // not downloaded over the internet, so a ~180 KB gzipped core is fine.
    chunkSizeWarningLimit: 800,
  },
  server: {
    port: 5173,
    // During development the API runs separately: `uv run python -m fms`.
    proxy: { '/api': 'http://127.0.0.1:8765' },
  },
  test: { environment: 'node' },
});
