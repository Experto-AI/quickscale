import path from "path"
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

function quickscaleManualChunks(id: string): string | undefined {
  const normalizedId = id.replace(/\\/g, '/')

  if (!normalizedId.includes('/node_modules/')) {
    return undefined
  }

  if (normalizedId.includes('/posthog-js/')) {
    return 'analytics'
  }

  if (normalizedId.includes('/react-router')) {
    return 'router'
  }

  if (
    normalizedId.includes('/@radix-ui/') ||
    normalizedId.includes('/lucide-react/') ||
    normalizedId.includes('/motion/') ||
    normalizedId.includes('/class-variance-authority/') ||
    normalizedId.includes('/clsx/') ||
    normalizedId.includes('/tailwind-merge/')
  ) {
    return 'ui'
  }

  if (
    normalizedId.includes('/@tanstack/') ||
    normalizedId.includes('/zustand/')
  ) {
    return 'data'
  }

  if (
    normalizedId.includes('/react-dom/') ||
    normalizedId.includes('/react/')
  ) {
    return 'react-vendor'
  }

  return 'vendor'
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/static/frontend/',
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/_quickscale': { target: 'http://localhost:8000', changeOrigin: true },
      '/admin': { target: 'http://localhost:8000', changeOrigin: true },
      '/accounts': { target: 'http://localhost:8000', changeOrigin: true },
      '/blog': { target: 'http://localhost:8000', changeOrigin: true },
      '/listings': { target: 'http://localhost:8000', changeOrigin: true },
      '/crm': { target: 'http://localhost:8000', changeOrigin: true },
      '/healthcheck': { target: 'http://localhost:8000', changeOrigin: true },
      '/static': { target: 'http://localhost:8000', changeOrigin: true },
      '/markdownx': { target: 'http://localhost:8000', changeOrigin: true },
      '/social': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: '../static/frontend',
    emptyOutDir: true,
    manifest: true,
    rollupOptions: {
      output: {
        manualChunks: quickscaleManualChunks,
        // Use consistent filenames for Django template compatibility
        entryFileNames: 'assets/[name].js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name].[ext]',
      },
    },
  },
})
