import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// In dev, the React app runs on :5173 and forwards /api calls to FastAPI on :8000.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
