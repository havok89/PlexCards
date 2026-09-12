import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'fs';
import path from 'path';

let appVersion = '0.9.0-pre';
try {
  const candidates = [
    path.resolve(__dirname, '../VERSION'),
    path.resolve(__dirname, '../../VERSION'),
    '/app/VERSION'
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) {
      const v = fs.readFileSync(p, 'utf-8').trim();
      if (v) {
        appVersion = v;
        break;
      }
    }
  }
} catch {
  // fallback
}

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(appVersion)
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true
  }
});
