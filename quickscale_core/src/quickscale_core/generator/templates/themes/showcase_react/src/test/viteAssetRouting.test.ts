import { request } from 'node:http'
import { createServer as createNetServer, type AddressInfo } from 'node:net'
import path from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { createServer, type ViteDevServer } from 'vite'

function requestStylesheet(port: number, host: string): Promise<{ body: string; status: number }> {
  return new Promise((resolve, reject) => {
    const stylesheetRequest = request(
      {
        hostname: '127.0.0.1',
        port,
        path: '/static/frontend/src/index.css',
        headers: { Host: host },
      },
      (response) => {
        let body = ''
        response.setEncoding('utf8')
        response.on('data', (chunk: string) => {
          body += chunk
        })
        response.on('end', () => {
          resolve({ body, status: response.statusCode ?? 0 })
        })
      },
    )
    stylesheetRequest.on('error', reject)
    stylesheetRequest.end()
  })
}

describe('Vite asset routing', () => {
  let server: ViteDevServer | undefined
  const originalFrontendOrigin = process.env.QUICKSCALE_FRONTEND_ORIGIN

  afterEach(async () => {
    await server?.close()
    server = undefined
    if (originalFrontendOrigin === undefined) {
      delete process.env.QUICKSCALE_FRONTEND_ORIGIN
    } else {
      process.env.QUICKSCALE_FRONTEND_ORIGIN = originalFrontendOrigin
    }
  })

  it('serves the shared token stylesheet under the configured base path', async () => {
    server = await createServer({
      configFile: path.resolve('vite.config.ts'),
      logLevel: 'silent',
      server: {
        host: '0.0.0.0',
        port: 0,
      },
    })
    await server.listen()

    const address = server.httpServer?.address()
    expect(address).not.toBeNull()
    expect(typeof address).not.toBe('string')

    const { port } = address as AddressInfo
    const response = await fetch(`http://127.0.0.1:${port}/static/frontend/src/index.css`)

    expect(response.status).toBe(200)
    expect(await response.text()).toContain('--primary:')
  })

  it('allows the exact hostname configured for a browser-visible origin', async () => {
    process.env.QUICKSCALE_FRONTEND_ORIGIN = 'https://vite.example.test'
    server = await createServer({
      configFile: path.resolve('vite.config.ts'),
      logLevel: 'silent',
      server: {
        host: '0.0.0.0',
        port: 0,
      },
    })
    await server.listen()

    const address = server.httpServer?.address()
    expect(address).not.toBeNull()
    expect(typeof address).not.toBe('string')

    const { port } = address as AddressInfo
    const allowedResponse = await requestStylesheet(port, 'vite.example.test')
    const deniedResponse = await requestStylesheet(port, 'other.example.test')

    expect(allowedResponse.status).toBe(200)
    expect(allowedResponse.body).toContain('--primary:')
    expect(deniedResponse.status).toBe(403)
  })

  it('fails explicitly when its configured port is occupied', async () => {
    const portBlocker = createNetServer()
    await new Promise<void>((resolve, reject) => {
      portBlocker.once('error', reject)
      portBlocker.listen(0, '127.0.0.1', resolve)
    })
    const blockedAddress = portBlocker.address()
    expect(blockedAddress).not.toBeNull()
    expect(typeof blockedAddress).not.toBe('string')

    try {
      const { port } = blockedAddress as AddressInfo
      server = await createServer({
        configFile: path.resolve('vite.config.ts'),
        logLevel: 'silent',
        server: {
          host: '127.0.0.1',
          port,
        },
      })

      await expect(server.listen()).rejects.toThrow(`Port ${port} is already in use`)
    } finally {
      await new Promise<void>((resolve, reject) => {
        portBlocker.close((error) => {
          if (error) {
            reject(error)
          } else {
            resolve()
          }
        })
      })
    }
  })
})
