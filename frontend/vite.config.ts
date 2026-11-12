import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': {
          target: env.VITE_API_PROXY_TARGET?.trim() || 'http://127.0.0.1:8000',
          changeOrigin: true,
          secure: false,
        }
      }
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks(id: string) {
            const normalized = id.replace(/\\/g, '/');
            if (normalized.includes('node_modules')) {
              if (normalized.includes('node_modules/react-router')) {
                return 'react-router';
              }
              if (
                normalized.includes('node_modules/react/') ||
                normalized.includes('node_modules/react-dom/') ||
                normalized.includes('node_modules/scheduler/')
              ) {
                return 'react-core';
              }
              if (normalized.includes('node_modules/axios/')) {
                return 'axios';
              }
            }
          },
        }
      }
    }
  }
})
