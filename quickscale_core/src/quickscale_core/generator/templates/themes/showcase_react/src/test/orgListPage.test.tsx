import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { OrgListPage } from '@/pages/orgs/OrgListPage'
import type { QuickScaleConfig } from '@/hooks/useModules'

const fetchMock = vi.fn()

vi.stubGlobal('fetch', fetchMock)

function buildConfig(): QuickScaleConfig {
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
    owner: { mode: 'saas', currentOrgSlug: null },
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

function renderPage() {
  window.__QUICKSCALE__ = buildConfig()
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <OrgListPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  fetchMock.mockReset()
  delete window.__QUICKSCALE__
})

describe('OrgListPage', () => {
  it('renders the loading skeleton cards while the org list loads', () => {
    fetchMock.mockReturnValue(new Promise(() => {}))
    const { container } = renderPage()

    expect(container.querySelectorAll('.animate-pulse')).toHaveLength(3)
  })

  it('renders the state panel when the org list request fails', async () => {
    fetchMock.mockResolvedValue(jsonResponse(500, { error: { code: 'server_error' } }))
    renderPage()

    expect(await screen.findByText('Unable to load organizations')).toBeInTheDocument()
    expect(screen.getByText('API Error: 500')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /create an organization/i })).toHaveAttribute(
      'href',
      '/orgs/new',
    )
  })

  it('renders each organization with its role and workspace entry points', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(200, {
        organizations: [
          {
            id: '1',
            name: 'Personal Space',
            slug: 'personal-space',
            is_personal: true,
          },
          {
            id: '2',
            name: 'Acme Inc',
            slug: 'acme',
            is_personal: false,
            role_label: 'Admin',
          },
        ],
      }),
    )
    renderPage()

    expect(await screen.findByText('Personal Space')).toBeInTheDocument()
    expect(screen.getByText('Personal workspace')).toBeInTheDocument()
    expect(screen.getByText('Acme Inc')).toBeInTheDocument()
    expect(screen.getByText('/acme')).toBeInTheDocument()
    expect(screen.getByText('Shared organization workspace')).toBeInTheDocument()
    expect(screen.getByText('Admin')).toBeInTheDocument()

    const openLinks = screen.getAllByRole('link', { name: /open workspace/i })
    expect(openLinks[0]).toHaveAttribute('href', '/orgs/personal-space')
    expect(openLinks[1]).toHaveAttribute('href', '/orgs/acme')
  })

  it('renders the empty state when no organizations exist', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { organizations: [] }))
    renderPage()

    expect(await screen.findByText('No organizations yet')).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /create your first organization/i }),
    ).toHaveAttribute('href', '/orgs/new')
  })
})
