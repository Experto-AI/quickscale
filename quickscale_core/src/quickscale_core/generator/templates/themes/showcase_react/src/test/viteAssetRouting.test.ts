import { request } from 'node:http'
import { connect as connectNet, createServer as createNetServer, type AddressInfo } from 'node:net'
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { afterEach, describe, expect, it } from 'vitest'
import { createServer, loadEnv, type ViteDevServer } from 'vite'

function requestStylesheet(port: number, host?: string): Promise<{ body: string; status: number }> {
  return new Promise((resolve, reject) => {
    const stylesheetRequest = request(
      {
        hostname: '127.0.0.1',
        port,
        path: '/static/frontend/src/index.css',
        ...(host === undefined ? { setHost: false } : { headers: { Host: host } }),
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

function requestUpgrade(port: number, host: string): Promise<number> {
  return new Promise((resolve, reject) => {
    const upgradeRequest = request({
      hostname: '127.0.0.1',
      port,
      path: '/static/frontend/',
      headers: {
        Connection: 'Upgrade',
        Host: host,
        'Sec-WebSocket-Key': 'dGhlIHNhbXBsZSBub25jZQ==',
        'Sec-WebSocket-Version': '13',
        Upgrade: 'websocket',
      },
    })
    upgradeRequest.on('response', (response) => {
      resolve(response.statusCode ?? 0)
    })
    upgradeRequest.on('upgrade', (response, socket) => {
      socket.destroy()
      resolve(response.statusCode ?? 101)
    })
    upgradeRequest.on('error', reject)
    upgradeRequest.end()
  })
}

function requestRaw(port: number, requestText: string): Promise<number> {
  return new Promise((resolve, reject) => {
    const socket = connectNet({ host: '127.0.0.1', port }, () => {
      socket.write(requestText)
    })
    socket.setTimeout(5_000, () => {
      socket.destroy()
      reject(new Error('Timed out waiting for raw HTTP response'))
    })
    socket.once('data', (chunk: Buffer) => {
      const statusMatch = chunk.toString('utf8').match(/^HTTP\/1\.1 (\d{3})/)
      socket.destroy()
      if (!statusMatch) {
        reject(new Error(`Invalid raw HTTP response: ${chunk.toString('utf8')}`))
        return
      }
      resolve(Number(statusMatch[1]))
    })
    socket.once('error', reject)
  })
}

async function readOptionalFile(filePath: string): Promise<Buffer | undefined> {
  try {
    return await readFile(filePath)
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') {
      return undefined
    }
    throw error
  }
}

function withFrontendOrigin(environment: Buffer | undefined, origin: string): string {
  const text = environment?.toString('utf8') ?? ''
  const assignment = `QUICKSCALE_FRONTEND_ORIGIN=${origin}`
  if (/^QUICKSCALE_FRONTEND_ORIGIN=.*$/m.test(text)) {
    return text.replace(/^QUICKSCALE_FRONTEND_ORIGIN=.*$/m, assignment)
  }
  const separator = text && !text.endsWith('\n') ? '\n' : ''
  return `${text}${separator}${assignment}\n`
}

describe('Vite asset routing', () => {
  let server: ViteDevServer | undefined
  const originalFrontendOrigin = process.env.QUICKSCALE_FRONTEND_ORIGIN
  const originalFrontendHostPort = process.env.QUICKSCALE_FRONTEND_HOST_PORT

  afterEach(async () => {
    await server?.close()
    server = undefined
    if (originalFrontendOrigin === undefined) {
      delete process.env.QUICKSCALE_FRONTEND_ORIGIN
    } else {
      process.env.QUICKSCALE_FRONTEND_ORIGIN = originalFrontendOrigin
    }
    if (originalFrontendHostPort === undefined) {
      delete process.env.QUICKSCALE_FRONTEND_HOST_PORT
    } else {
      process.env.QUICKSCALE_FRONTEND_HOST_PORT = originalFrontendHostPort
    }
  })

  it('enforces the derived default Host for HTTP and WebSocket requests', async () => {
    delete process.env.QUICKSCALE_FRONTEND_ORIGIN
    delete process.env.QUICKSCALE_FRONTEND_HOST_PORT
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
    const response = await requestStylesheet(port, 'localhost:5173')

    expect(response.status).toBe(200)
    expect(response.body).toContain('--primary:')

    expect((await requestStylesheet(port)).status).toBe(400)
    expect((await requestStylesheet(port, `127.0.0.1:${port}`)).status).toBe(403)

    const duplicateHttpHosts = [
      'GET /static/frontend/src/index.css HTTP/1.1',
      'Host: localhost:5173',
      'Host: evil.example.test',
      'Connection: close',
      '',
      '',
    ].join('\r\n')
    expect(await requestRaw(port, duplicateHttpHosts)).toBe(403)

    const missingUpgradeHost = [
      'GET /static/frontend/ HTTP/1.1',
      'Connection: Upgrade',
      'Upgrade: websocket',
      'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==',
      'Sec-WebSocket-Version: 13',
      '',
      '',
    ].join('\r\n')
    expect(await requestRaw(port, missingUpgradeHost)).toBe(403)

    const duplicateUpgradeHosts = [
      'GET /static/frontend/ HTTP/1.1',
      'Host: localhost:5173',
      'Host: evil.example.test',
      'Connection: Upgrade',
      'Upgrade: websocket',
      'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==',
      'Sec-WebSocket-Version: 13',
      '',
      '',
    ].join('\r\n')
    expect(await requestRaw(port, duplicateUpgradeHosts)).toBe(403)
    expect(await requestUpgrade(port, `127.0.0.1:${port}`)).toBe(403)
  })

  it('derives the exact Host from a remapped browser-facing port', async () => {
    delete process.env.QUICKSCALE_FRONTEND_ORIGIN
    process.env.QUICKSCALE_FRONTEND_HOST_PORT = '45173'
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
    expect((await requestStylesheet(port, 'localhost:45173')).status).toBe(200)
    expect((await requestStylesheet(port, 'localhost:5173')).status).toBe(403)
  })

  it.each([
    ['is absent', undefined],
    [
      'already has a nonblank origin',
      'KEEP_ME=yes\nQUICKSCALE_FRONTEND_ORIGIN=https://old.example.test\n',
    ],
  ] as const)(
    'loads the exact browser-visible hostname when the root environment %s',
    async (_description, initialRootEnvironment) => {
      delete process.env.QUICKSCALE_FRONTEND_ORIGIN
      const isolatedProjectRoot = await mkdtemp(
        path.join(tmpdir(), 'quickscale-vite-root-environment-'),
      )
      const rootEnvironmentPath = path.join(isolatedProjectRoot, '.env')

      try {
        if (initialRootEnvironment !== undefined) {
          await writeFile(rootEnvironmentPath, initialRootEnvironment)
        }

        const originalRootEnvironment = await readOptionalFile(rootEnvironmentPath)
        const configuredRootEnvironment = withFrontendOrigin(
          originalRootEnvironment,
          'https://vite.example.test',
        )
        await writeFile(rootEnvironmentPath, configuredRootEnvironment)

        const loadedRootEnvironment = loadEnv('development', isolatedProjectRoot, '')
        process.env.QUICKSCALE_FRONTEND_ORIGIN = loadedRootEnvironment.QUICKSCALE_FRONTEND_ORIGIN
        const viteConfigSource = await readFile(path.resolve('vite.config.ts'), 'utf8')
        expect(viteConfigSource).toContain("loadEnv(mode, path.resolve(__dirname, '..'), '')")

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

        expect(allowedResponse.status).toBe(200)
        expect(allowedResponse.body).toContain('--primary:')

        for (const deniedHost of [
          'other.example.test',
          'localhost',
          '127.0.0.1',
          `127.0.0.1:${port}`,
          'vite.example.test:443',
          '%76ite.example.test',
        ]) {
          const deniedResponse = await requestStylesheet(port, deniedHost)
          expect(deniedResponse.status, `Host ${String(deniedHost)}`).toBe(403)
        }

        const missingHostResponse = await requestStylesheet(port)
        expect(missingHostResponse.status).toBe(400)
        const duplicateHttpHosts = [
          'GET /static/frontend/src/index.css HTTP/1.1',
          'Host: vite.example.test',
          'Host: evil.example.test',
          'Connection: close',
          '',
          '',
        ].join('\r\n')
        expect(await requestRaw(port, duplicateHttpHosts)).toBe(403)

        const duplicateUpgradeHosts = [
          'GET /static/frontend/ HTTP/1.1',
          'Host: vite.example.test',
          'Host: evil.example.test',
          'Connection: Upgrade',
          'Upgrade: websocket',
          'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==',
          'Sec-WebSocket-Version: 13',
          '',
          '',
        ].join('\r\n')
        expect(await requestRaw(port, duplicateUpgradeHosts)).toBe(403)

        for (const deniedUpgradeHost of [
          'localhost',
          'vite.example.test:443',
          '%76ite.example.test',
        ]) {
          expect(await requestUpgrade(port, deniedUpgradeHost)).toBe(403)
        }
      } finally {
        await rm(isolatedProjectRoot, { recursive: true, force: true })
      }
    },
  )

  it.each([
    ['an optional trailing slash', 'https://vite.example.test/', 'vite.example.test'],
    ['a canonical IPv4 address and port', 'http://127.0.0.1:45173', '127.0.0.1:45173'],
  ])('accepts %s', async (_description, configuredOrigin, configuredHost) => {
    process.env.QUICKSCALE_FRONTEND_ORIGIN = configuredOrigin
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

    const response = await requestStylesheet((address as AddressInfo).port, configuredHost)
    expect(response.status).toBe(200)
    expect(response.body).toContain('--primary:')
  })

  it.each([
    'https://vite.example.test?',
    'https://vite.example.test#',
    'http://127.1',
    'http://2130706433',
    'http://0x7f000001',
    'http://0x7f.0.0.1',
    'http://0177.0.0.1',
    'http://127.0.0.0x1',
    'http://localhost:0',
    'http://é.example',
    'http://exa mple.test',
  ])('rejects a non-canonical root environment origin %s', async (configuredOrigin) => {
    process.env.QUICKSCALE_FRONTEND_ORIGIN = configuredOrigin

    await expect(
      createServer({
        configFile: path.resolve('vite.config.ts'),
        logLevel: 'silent',
      }),
    ).rejects.toThrow('QUICKSCALE_FRONTEND_ORIGIN must be an HTTP(S) origin')
  })

  it.each([
    '0',
    '-1',
    '+5173',
    '05173',
    '65536',
    '999999999999999999999999999999999999',
    'not-a-port',
  ])('rejects an invalid browser-facing host port %s', async (configuredPort) => {
    delete process.env.QUICKSCALE_FRONTEND_ORIGIN
    process.env.QUICKSCALE_FRONTEND_HOST_PORT = configuredPort

    await expect(
      createServer({
        configFile: path.resolve('vite.config.ts'),
        logLevel: 'silent',
      }),
    ).rejects.toThrow('QUICKSCALE_FRONTEND_HOST_PORT must be between 1 and 65535')
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
