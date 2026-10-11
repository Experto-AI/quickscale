import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from '../App'
import type { QuickScaleConfig } from '@/hooks/useModules'

// Lazy route modules resolve to synchronous stubs so every route decision in
// App.tsx executes without pulling the real pages into the test.
vi.mock('@/pages/BlogPage', () => ({ BlogPage: () => <div>blog route stub</div> }))
vi.mock('@/pages/CrmPage', () => ({ CrmPage: () => <div>crm route stub</div> }))
vi.mock('@/pages/ListingsPage', () => ({ ListingsPage: () => <div>listings route stub</div> }))
vi.mock('@/pages/FormsPage', () => ({ FormsPage: () => <div>forms route stub</div> }))
vi.mock('@/pages/orgs/OrgCreatePage', () => ({ OrgCreatePage: () => <div>org create stub</div> }))
vi.mock('@/pages/orgs/OrgDashboardPage', () => ({
  OrgDashboardPage: () => <div>org dashboard stub</div>,
}))
vi.mock('@/pages/orgs/OrgLayout', async () => {
  const { Outlet } = await import('react-router-dom')
  return { OrgLayout: () => <Outlet /> }
})
vi.mock('@/pages/orgs/OrgListPage', () => ({ OrgListPage: () => <div>org list stub</div> }))
vi.mock('@/pages/orgs/OrgMembersPage', () => ({ OrgMembersPage: () => <div>org members stub</div> }))
vi.mock('@/pages/orgs/OrgSettingsPage', () => ({
  OrgSettingsPage: () => <div>org settings stub</div>,
}))

const fetchMock = vi.fn()

vi.stubGlobal('fetch', fetchMock)

function buildConfig(overrides: Partial<QuickScaleConfig> = {}): QuickScaleConfig {
  return {
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
    },
    modulePaths: {
      crm: '/crm',
      social: '/social',
      analytics: '/analytics/',
    },
    moduleApiPaths: {
      orgs: '/orgs/api/',
      billing: '/billing/api/',
      crm: '/crm/api/',
      forms: '/forms/api/',
    },
    owner: { mode: 'solo', currentOrgSlug: null },
    ...overrides,
  }
}

function allModulesOn(): QuickScaleConfig['modules'] {
  return {
    auth: true,
    blog: true,
    listings: true,
    crm: true,
    forms: true,
    storage: true,
    backups: true,
    notifications: true,
    analytics: true,
    billing: true,
    social: true,
  }
}

function LocationProbe() {
  const location = useLocation()
  return <span data-testid="location">{location.pathname}</span>
}

function renderApp(path: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <App />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  fetchMock.mockReset()
  delete window.__QUICKSCALE__
})

describe('App solo routing', () => {
  it('renders the dashboard at the root', () => {
    window.__QUICKSCALE__ = buildConfig()
    renderApp('/')

    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })

  it('renders module routes when their flags are on and the fallback when they are off', async () => {
    window.__QUICKSCALE__ = buildConfig({ modules: allModulesOn() })
    const { unmount } = renderApp('/blog')
    expect(await screen.findByText('blog route stub')).toBeInTheDocument()
    unmount()

    renderApp('/listings')
    expect(await screen.findByText('listings route stub')).toBeInTheDocument()

    renderApp('/crm')
    expect(await screen.findByText('crm route stub')).toBeInTheDocument()

    renderApp('/forms/contact')
    expect(await screen.findByText('forms route stub')).toBeInTheDocument()

    window.__QUICKSCALE__ = buildConfig()
    renderApp('/blog')
    expect(await screen.findByText('Page Not Found')).toBeInTheDocument()
  })

  it('renders the unconditional pages and the not-found fallback', async () => {
    window.__QUICKSCALE__ = buildConfig()
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ status: 'ok' }),
    } as Response)

    const { unmount } = renderApp('/profile')
    expect(await screen.findByText(/profile & authentication/i)).toBeInTheDocument()
    unmount()

    renderApp('/settings')
    expect(await screen.findByText('System Status')).toBeInTheDocument()

    renderApp('/does-not-exist')
    expect(await screen.findByText('Page Not Found')).toBeInTheDocument()
  })
})

describe('App saas routing', () => {
  it('redirects the root to the current organization dashboard', async () => {
    window.__QUICKSCALE__ = buildConfig({
      modules: allModulesOn(),
      owner: { mode: 'saas', currentOrgSlug: 'acme' },
    })
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ organizations: [] }),
    } as Response)

    renderApp('/')

    expect(await screen.findByText('org dashboard stub')).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/orgs/acme')
  })

  it('redirects the root to the org list without a current organization', async () => {
    window.__QUICKSCALE__ = buildConfig({
      modules: allModulesOn(),
      owner: { mode: 'saas', currentOrgSlug: null },
    })
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ organizations: [] }),
    } as Response)

    renderApp('/')

    expect(await screen.findByText('org list stub')).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/orgs')
  })

  it('maps legacy module and settings routes into the org workspace', async () => {
    window.__QUICKSCALE__ = buildConfig({
      modules: allModulesOn(),
      owner: { mode: 'saas', currentOrgSlug: 'acme' },
    })
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ organizations: [] }),
    } as Response)

    const blog = renderApp('/blog')
    expect(await screen.findByText('blog route stub')).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/orgs/acme/blog')
    blog.unmount()

    const listings = renderApp('/listings')
    expect(await screen.findByText('listings route stub')).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/orgs/acme/listings')
    listings.unmount()

    const settings = renderApp('/settings')
    expect(await screen.findByText('org settings stub')).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/orgs/acme/settings')
    settings.unmount()

    renderApp('/crm')
    expect(await screen.findByText('crm route stub')).toBeInTheDocument()
  })

  it('sends legacy routes to the org list without a current organization', async () => {
    window.__QUICKSCALE__ = buildConfig({
      modules: allModulesOn(),
      owner: { mode: 'saas', currentOrgSlug: null },
    })
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ organizations: [] }),
    } as Response)

    renderApp('/blog')

    expect(await screen.findByText('org list stub')).toBeInTheDocument()
    expect(screen.getByTestId('location')).toHaveTextContent('/orgs')
  })

  it('renders the org create, members, and settings pages', async () => {
    window.__QUICKSCALE__ = buildConfig({
      modules: allModulesOn(),
      owner: { mode: 'saas', currentOrgSlug: 'acme' },
    })
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ organizations: [] }),
    } as Response)

    const { unmount } = renderApp('/orgs/new')
    expect(await screen.findByText('org create stub')).toBeInTheDocument()
    unmount()

    renderApp('/orgs/acme/members')
    expect(await screen.findByText('org members stub')).toBeInTheDocument()

    renderApp('/orgs/acme/settings')
    expect(await screen.findByText('org settings stub')).toBeInTheDocument()
  })
})
