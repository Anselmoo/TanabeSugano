import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/TanabeSugano/',
  build: {
    outDir: '../docs',
    emptyOutDir: true,
  },
  publicDir: 'public',
})
