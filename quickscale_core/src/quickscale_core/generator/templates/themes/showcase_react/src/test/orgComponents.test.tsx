import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Building2, Info } from 'lucide-react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { OrgStatePanel } from '@/components/orgs/OrgStatePanel'
import { OrgSwitcher } from '@/components/orgs/OrgSwitcher'
import type { QuickScaleConfig } from '@/hooks/useModules'
import { moduleFlags, modulePaths, moduleApiPaths } from '@/test/seamFixtures'

const fetchMock = vi.fn()

vi.stubGlobal('fetch', fetchMock)

class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn()
  Element.prototype.hasPointerCapture = vi.fn(() => false)
  Element.prototype.releasePointerCapture = vi.fn()
  vi.stubGlobal('ResizeObserver', ResizeObserverStub)
})

afterAll(() => {
  vi.unstubAllGlobals()
})

function buildConfig(mode: 'solo' | 'saas', currentOrgSlug: string | null = null): QuickScaleConfig {
  return {
    projectName: 'QuickScale Test Project',
    modules: moduleFlags(),
    modulePaths: modulePaths({ analytics: '/analytics/' }),
    moduleApiPaths: moduleApiPaths(),
    owner: { mode, currentOrgSlug },
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

function LocationProbe() {
  const location = useLocation()
  return <span data-testid="location">{location.pathname}</span>
}

function renderSwitcher() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/orgs']}>
        <OrgSwitcher />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  fetchMock.mockReset()
  delete window.__QUICKSCALE__
})

describe('OrgStatePanel', () => {
  it('renders the title, description, and action link', () => {
    render(
      <MemoryRouter>
        <OrgStatePanel
          actionHref="/orgs/new"
          actionLabel="Create an organization"
          description="Nothing to see yet."
          icon={Building2}
          title="Unable to load organizations"
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('Unable to load organizations')).toBeInTheDocument()
    expect(screen.getByText('Nothing to see yet.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /create an organization/i })).toHaveAttribute(
      'href',
      '/orgs/new',
    )
  })

  it('renders a provided icon component', () => {
    const { container } = render(
      <MemoryRouter>
        <OrgStatePanel
          actionHref="/orgs/new"
          actionLabel="Create"
          description="Copy"
          icon={Info}
          title="Title"
        />
      </MemoryRouter>,
    )

    expect(container.querySelector('svg')).not.toBeNull()
  })
})

describe('OrgSwitcher', () => {
  it('renders nothing outside saas mode', () => {
    window.__QUICKSCALE__ = buildConfig('solo')
    const { container } = renderSwitcher()

    expect(container.querySelector('[class*="space-y-3"]')).toBeNull()
    expect(screen.queryByRole('combobox')).toBeNull()
    expect(screen.queryByText(/organization/i)).toBeNull()
  })

  it('shows the loading state while organizations load', () => {
    window.__QUICKSCALE__ = buildConfig('saas')
    fetchMock.mockReturnValue(new Promise(() => {}))
    renderSwitcher()

    expect(screen.getByText('Loading organizations...')).toBeInTheDocument()
  })

  it('invites the first organization when the list is empty', async () => {
    window.__QUICKSCALE__ = buildConfig('saas')
    fetchMock.mockResolvedValue(jsonResponse(200, { organizations: [] }))
    renderSwitcher()

    const create = await screen.findByRole('link', { name: /create your first organization/i })
    expect(create).toHaveAttribute('href', '/orgs/new')
    expect(screen.queryByText(/choose an organization to unlock/i)).toBeNull()
  })

  it('lists organizations and switches to the chosen one', async () => {
    window.__QUICKSCALE__ = buildConfig('saas')
    fetchMock.mockResolvedValue(
      jsonResponse(200, {
        organizations: [
          { id: '1', name: 'Acme Inc', slug: 'acme', is_personal: false },
          { id: '2', name: 'Beta Co', slug: 'beta', is_personal: false },
        ],
      }),
    )
    renderSwitcher()

    const user = userEvent.setup()
    await user.click(await screen.findByRole('combobox'))
    expect(await screen.findByRole('option', { name: 'Acme Inc' })).toBeInTheDocument()
    expect(screen.getByText(/choose an organization to unlock/i)).toBeInTheDocument()

    await user.click(screen.getByRole('option', { name: 'Beta Co' }))

    expect(screen.getByTestId('location')).toHaveTextContent('/orgs/beta')
  })

  it('hides the unlock note once an organization is current', async () => {
    window.__QUICKSCALE__ = buildConfig('saas', 'acme')
    fetchMock.mockResolvedValue(
      jsonResponse(200, {
        organizations: [{ id: '1', name: 'Acme Inc', slug: 'acme', is_personal: false }],
      }),
    )
    renderSwitcher()

    const user = userEvent.setup()
    await user.click(await screen.findByRole('combobox'))
    expect(await screen.findByRole('option', { name: 'Acme Inc' })).toBeInTheDocument()
    expect(screen.queryByText(/choose an organization to unlock/i)).toBeNull()
  })
})
