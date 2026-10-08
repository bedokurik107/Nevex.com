import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  base: "/Nevex.com/",
  plugins: [react(), tailwindcss()],
  server: { host: true, proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } } },
})
