import { createHash } from 'node:crypto';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

import react from '@vitejs/plugin-react';
import type { Plugin } from 'vite';
import { defineConfig } from 'vitest/config';

const pkg = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf-8'));

function listFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? listFiles(path) : [path];
  });
}

/**
 * Emits sw.js: the service worker from sw/sw-template.js plus the exact list of files
 * in this build, so the whole app can be kept on the phone and opened offline.
 */
function serviceWorker(): Plugin {
  return {
    name: 'fms-service-worker',
    apply: 'build',
    enforce: 'post',
    generateBundle(_options, bundle) {
      const publicDir = join(import.meta.dirname, 'public');
      const files = [
        ...Object.keys(bundle),
        ...listFiles(publicDir).map((f) => relative(publicDir, f).split(sep).join('/')),
      ]
        // Every browser we support reads .woff2, so skip the older .woff copies.
        .filter((f) => !f.endsWith('.map') && !f.endsWith('.woff') && f !== 'sw.js')
        .map((f) => `/${f}`);
      const precache = ['/', ...new Set(files)].sort();
      const version = createHash('sha256').update(precache.join('\n')).digest('hex').slice(0, 12);
      const source = readFileSync(join(import.meta.dirname, 'sw', 'sw-template.js'), 'utf-8')
        .replace('__VERSION__', JSON.stringify(`${pkg.version}-${version}`))
        .replace('__PRECACHE__', JSON.stringify(precache, null, 2));
      this.emitFile({ type: 'asset', fileName: 'sw.js', source });
    },
  };
}

export default defineConfig({
  plugins: [react(), serviceWorker()],
  define: { __APP_VERSION__: JSON.stringify(pkg.version) },
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
