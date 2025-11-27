import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  define: {
    BASE_URL: JSON.stringify(process.env.BASE_URL || ''),
    TOKEN: JSON.stringify(process.env.TOKEN || ''),
    MOBILE: false,
  },
  plugins: [react()],
})
