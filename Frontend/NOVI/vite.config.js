import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        // 요청 호스트를 localhost:5173으로 유지해 Django CSRF의 Origin 검사와 일치시킵니다.
        changeOrigin: false,
      },
    },
  },
})
