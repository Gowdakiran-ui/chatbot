import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// `npm run dev` proxies /api/* to the FastAPI backend (uvicorn on :8000), stripping the /api prefix:
// the backend serves /chat, the frontend calls /api/chat. Production does the same in nginx (see README).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, '') } },
  },
  build: { chunkSizeWarningLimit: 900 },
})
