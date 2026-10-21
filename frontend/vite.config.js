import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In development the UI calls /api/... and Vite forwards it to the FastAPI server.
// In Docker, nginx does the same forwarding (see nginx.conf).
const proxy = { '/api': { target: process.env.VITE_PROXY_TARGET || 'http://localhost:8000', changeOrigin: true } };

export default defineConfig({
  plugins: [react()],
  preview: { port: 4173, proxy },
  server: {
    port: 5173,
    host: true,
    proxy,
  },
});
