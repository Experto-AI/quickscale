import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SettingsPage } from '@/pages/SettingsPage'
import type { QuickScaleConfig } from '@/hooks/useModules'
import { moduleFlags, modulePaths, moduleApiPaths, moduleDocumentPaths } from '@/test/seamFixtures'

const fetchMock = vi.fn()

vi.stubGlobal('fetch', fetchMock)

function buildConfig(modules: Partial<QuickScaleConfig['modules']> = {}): QuickScaleConfig {
  return {
    projectName: 'QuickScale Test Project',
    modules: moduleFlags({ ...modules }),
    modulePaths: modulePaths({ analytics: '/analytics/' }),
    moduleApiPaths: moduleApiPaths(),
    moduleDocumentPaths: moduleDocumentPaths(),
    owner: { mode: 'solo', currentOrgSlug: null },
  }
}

function jsonResponse(status: number, payload: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => payload,
  } as Response
}

function renderSettings(modules: Partial<QuickScaleConfig['modules']> = {}) {
  window.__QUICKSCALE__ = buildConfig(modules)
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <SettingsPage />
    </QueryClientProvider>,
  )
}

afterEach(() => {
  fetchMock.mockReset()
  delete window.__QUICKSCALE__
})

describe('SettingsPage', () => {
  it('shows the backend as checking while the health request runs', () => {
    fetchMock.mockReturnValue(new Promise(() => {}))
    renderSettings()

    expect(screen.getByText('Checking...')).toBeInTheDocument()
  })

  it('shows the backend online and lists the enabled module badges', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { status: 'ok' }))
    renderSettings({ blog: true, crm: true })

    expect(await screen.findByText('Online')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/healthcheck/', expect.anything())
    expect(screen.getByText('blog')).toBeInTheDocument()
    expect(screen.getByText('crm')).toBeInTheDocument()
    expect(screen.queryByText('No modules installed')).toBeNull()
  })

  it('shows the backend offline and the empty module state', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    renderSettings()

    expect(await screen.findByText('Offline')).toBeInTheDocument()
    expect(screen.getByText('No modules installed')).toBeInTheDocument()
  })
})
