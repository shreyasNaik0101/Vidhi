import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Local dev proxies to the running backends:
//   /api -> Node read API (Express, :3001)
//   /ing -> Python ingestion service (FastAPI, :8030)
// The GitHub Pages build (npm run build:static) sets VITE_STATIC=1 and serves
// everything from a baked dataset, so no backend is needed there. BASE_PATH lets
// the same build target a project page (/Vidhi/) or a root/custom domain (/).
export default defineConfig({
  base: process.env.BASE_PATH || '/',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:3001',
      '/ing': {
        target: 'http://localhost:8030',
        rewrite: (p) => p.replace(/^\/ing/, ''),
      },
    },
  },
});
