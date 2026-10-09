import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// `npm run dev` proxies /api/* to the FastAPI backend (uvicorn on :8000 by default), stripping the /api prefix:
// the backend serves /chat, the frontend calls /api/chat. Production does the same in nginx (see README).
// Set VITE_PROXY_TARGET (e.g. in frontend/.env.local) to point the dev proxy at a backend on another port.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: env.VITE_PROXY_TARGET || 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (p) => p.replace(/^\/api/, ''),
        },
      },
    },
    build: { chunkSizeWarningLimit: 900 },
  }
})
