import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'VITE_')
  const target = env.VITE_API_TARGET || 'http://127.0.0.1:8000'
  const port = Number(env.VITE_DEV_PORT || 5173)
  return { plugins: [react()], server: { host: '127.0.0.1', port, proxy: { '/api': target, '/a2a': target } } }
})
