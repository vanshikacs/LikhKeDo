import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // AudioWorklet modules must be real files: some browsers refuse data: URLs in addModule()
    assetsInlineLimit: (file: string) => (file.includes('worklet') ? false : undefined),
  },
  server: { host: true },
})
