import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// /api  -> Node read API (Express, :3001)
// /ing  -> Python ingestion service (FastAPI, :8000)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:3001',
      '/ing': {
        target: 'http://localhost:8020',
        rewrite: (p) => p.replace(/^\/ing/, ''),
      },
    },
  },
});
