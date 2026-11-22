import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In dev, the React app runs on :5173 and forwards /api calls to FastAPI on :8000.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // 127.0.0.1 rather than localhost: on Windows 'localhost' tries IPv6 first (+2s per call)
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
