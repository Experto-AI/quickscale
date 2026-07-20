import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from '../App'

const fetchMock = vi.fn()

vi.stubGlobal('fetch', fetchMock)

function applyRuntimeConfig(
  config: {
    modules?: Partial<Record<string, boolean>>
    owner?: { currentOrgSlug: string | null; mode: 'saas' | 'solo' }
  } = {},
) {
  window.__QUICKSCALE__ = {
    projectName: 'QuickScale Test Project',
    modules: {
      auth: false,
      blog: false,
      listings: false,
      crm: false,
      forms: false,
      storage: false,
      backups: false,
      notifications: false,
      analytics: false,
      billing: false,
      social: false,
      ...config.modules,
    },
    modulePaths: {
      crm: '/crm',
      social: '/social',
      analytics: '/analytics/',
    },
    owner: config.owner ?? {
      mode: 'solo',
      currentOrgSlug: null,
    },
  }
}

function renderWithProviders(ui: React.ReactElement, initialEntries: string[] = ['/']) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  fetchMock.mockReset()
  delete window.__QUICKSCALE__
})

describe('App', () => {
  it('renders dashboard heading', () => {
    applyRuntimeConfig()
    renderWithProviders(<App />)
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })

  it('renders the org list shell in saas mode', async () => {
    applyRuntimeConfig({
      owner: {
        mode: 'saas',
        currentOrgSlug: null,
      },
    })
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      headers: {
        get: () => 'application/json',
      },
      json: async () => ({ organizations: [] }),
    })

    renderWithProviders(<App />, ['/orgs'])

    expect(await screen.findByRole('heading', { name: /organizations/i })).toBeInTheDocument()
    expect(await screen.findByText(/no organizations yet/i)).toBeInTheDocument()
  })

  it('does not mount module routes when all runtime flags are false', async () => {
    applyRuntimeConfig()
    renderWithProviders(<App />, ['/blog'])

    expect(await screen.findByText('Dashboard')).toBeInTheDocument()
    expect(screen.queryByText(/blog/i)).not.toBeInTheDocument()
  })

  it('mounts blog route when modules.blog is true', async () => {
    applyRuntimeConfig({ modules: { blog: true } })
    renderWithProviders(<App />, ['/blog'])

    expect(await screen.findByRole('heading', { name: /blog/i })).toBeInTheDocument()
  })

  it('redirects unselected module routes to not-found fallback', async () => {
    applyRuntimeConfig()
    renderWithProviders(<App />, ['/listings'])

    expect(await screen.findByText('Dashboard')).toBeInTheDocument()
    expect(screen.queryByText(/listings/i)).not.toBeInTheDocument()
  })

  it('renders dashboard with all modules disabled', () => {
    applyRuntimeConfig()
    renderWithProviders(<App />)

    expect(screen.getByText('No Modules Installed')).toBeInTheDocument()
    expect(screen.getByText(/no modules installed yet/i)).toBeInTheDocument()
  })

  it('renders installed modules section when any module flag is true', () => {
    applyRuntimeConfig({ modules: { blog: true } })
    renderWithProviders(<App />)

    expect(screen.getByText('Installed Modules')).toBeInTheDocument()
  })

  it('does not render crm route when modules.crm is false', async () => {
    applyRuntimeConfig()
    renderWithProviders(<App />, ['/crm'])

    expect(await screen.findByText('Dashboard')).toBeInTheDocument()
    expect(screen.queryByText(/crm/i)).not.toBeInTheDocument()
  })

  it('renders settings page unconditionally at /settings', async () => {
    applyRuntimeConfig()
    renderWithProviders(<App />, ['/settings'])

    expect(await screen.findByRole('heading', { name: /settings/i })).toBeInTheDocument()
  })

  it('renders profile page unconditionally at /profile', async () => {
    applyRuntimeConfig()
    renderWithProviders(<App />, ['/profile'])

    expect(await screen.findByRole('heading', { name: /profile/i })).toBeInTheDocument()
  })
})
