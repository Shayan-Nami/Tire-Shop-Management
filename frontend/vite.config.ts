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
            if (id.includes('node_modules')) {
              // Match package directories exactly; a bare 'react' substring also captures lucide-react.
              if (/[\\/]node_modules[\\/](react-router|react-router-dom)[\\/]/.test(id)) {
                return 'react-router';
              }
              if (/[\\/]node_modules[\\/](react|react-dom|scheduler)[\\/]/.test(id)) {
                return 'react-core';
              }
              if (/[\\/]node_modules[\\/]axios[\\/]/.test(id)) {
                return 'axios';
              }
            }
          },
        }
      }
    }
  }
})
