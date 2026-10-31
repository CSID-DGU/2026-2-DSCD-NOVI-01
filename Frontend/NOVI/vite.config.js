import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 개발 중 /api/* 요청을 Django 개발 서버에 전달 (CORS 설정 불필요).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
