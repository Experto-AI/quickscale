import type { IncomingMessage } from 'node:http'
import { isIP, type Socket } from 'node:net'
import path from 'path'
import { defineConfig, loadEnv, type Plugin } from 'vite'
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

  if (normalizedId.includes('/@tanstack/') || normalizedId.includes('/zustand/')) {
    return 'data'
  }

  if (normalizedId.includes('/react-dom/') || normalizedId.includes('/react/')) {
    return 'react-vendor'
  }

  return 'vendor'
}

function quickscaleCanonicalHostname(hostname: string): boolean {
  const unbracketedHostname =
    hostname.startsWith('[') && hostname.endsWith(']') ? hostname.slice(1, -1) : hostname
  if (isIP(unbracketedHostname)) {
    return true
  }

  return hostname.split('.').every((label) => /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))
}

function quickscaleFrontendHostPort(configuredPort: string | undefined): number {
  configuredPort = configuredPort?.trim() || '5173'
  const hostPort = Number(configuredPort)
  if (
    !/^[1-9]\d{0,4}$/.test(configuredPort) ||
    !Number.isInteger(hostPort) ||
    hostPort < 1 ||
    hostPort > 65535
  ) {
    throw new Error('QUICKSCALE_FRONTEND_HOST_PORT must be between 1 and 65535')
  }
  return hostPort
}

function quickscaleFrontendOrigin(
  configuredOrigin: string | undefined,
  frontendHostPort: number,
): URL {
  const originText = configuredOrigin?.trim() || `http://localhost:${frontendHostPort}`

  let origin: URL
  try {
    origin = new URL(originText)
  } catch {
    throw new Error('QUICKSCALE_FRONTEND_ORIGIN must be an HTTP(S) origin')
  }

  if (
    !['http:', 'https:'].includes(origin.protocol) ||
    origin.username ||
    origin.password ||
    origin.pathname !== '/' ||
    origin.search ||
    origin.hash ||
    origin.port === '0' ||
    !quickscaleCanonicalHostname(origin.hostname) ||
    ![origin.origin, `${origin.origin}/`].includes(originText)
  ) {
    throw new Error('QUICKSCALE_FRONTEND_ORIGIN must be an HTTP(S) origin')
  }

  return origin
}

function quickscaleExactHostAllowed(requestHost: string | undefined, frontendOrigin: URL): boolean {
  return requestHost === frontendOrigin.host
}

function quickscaleExactHostPlugin(frontendOrigin: URL): Plugin {
  return {
    name: 'quickscale-exact-host',
    apply: 'serve',
    configureServer(server) {
      const rejectHost = (request: IncomingMessage): boolean => {
        const requestHosts = request.headersDistinct.host
        return (
          requestHosts?.length !== 1 || !quickscaleExactHostAllowed(requestHosts[0], frontendOrigin)
        )
      }

      server.middlewares.use((request, response, next) => {
        if (!rejectHost(request)) {
          next()
          return
        }

        response.writeHead(403, { 'Content-Type': 'text/plain' })
        response.end(`Blocked request. Expected Host: ${frontendOrigin.host}`)
      })

      server.httpServer?.prependListener('upgrade', (request: IncomingMessage, socket: Socket) => {
        if (!rejectHost(request)) {
          return
        }

        socket.write('HTTP/1.1 403 Forbidden\r\nConnection: close\r\nContent-Length: 0\r\n\r\n')
        socket.destroy()
      })
    },
  }
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const environment = {
    ...loadEnv(mode, path.resolve(__dirname, '..'), ''),
    ...process.env,
  }
  const frontendHostPort = quickscaleFrontendHostPort(environment.QUICKSCALE_FRONTEND_HOST_PORT)
  const frontendOrigin = quickscaleFrontendOrigin(
    environment.QUICKSCALE_FRONTEND_ORIGIN,
    frontendHostPort,
  )
  const frontendAllowedHosts = [frontendOrigin.hostname]

  return {
    plugins: [quickscaleExactHostPlugin(frontendOrigin), react()],
    base: '/static/frontend/',
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5173,
      strictPort: true,
      allowedHosts: frontendAllowedHosts,
      proxy: {
        '/_quickscale': { target: 'http://localhost:8000', changeOrigin: true },
        '/admin': { target: 'http://localhost:8000', changeOrigin: true },
        '/accounts': { target: 'http://localhost:8000', changeOrigin: true },
        '/blog': { target: 'http://localhost:8000', changeOrigin: true },
        '/listings': { target: 'http://localhost:8000', changeOrigin: true },
        '/crm': { target: 'http://localhost:8000', changeOrigin: true },
        '/healthcheck': { target: 'http://localhost:8000', changeOrigin: true },
        '^/static(?:$|/(?!frontend(?:/|$)))': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
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
  }
})
