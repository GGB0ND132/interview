import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const backend = process.env.INTERVIEW_BACKEND_URL || 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': backend } },
  preview: { proxy: { '/api': backend } },
})
