import { afterEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SocialLinkTreePublicPage } from '@/pages/SocialLinkTreePublicPage'
import type { QuickScaleConfig } from '@/hooks/useModules'
import type { SocialLinkTreePayload } from '@/hooks/usePublicSocialSurface'
import { moduleFlags, modulePaths, moduleApiPaths } from '@/test/seamFixtures'

const analyticsMock = vi.hoisted(() => ({ trackSocialLinkClick: vi.fn() }))

vi.mock('@/lib/analytics', () => ({
  trackSocialLinkClick: analyticsMock.trackSocialLinkClick,
}))

const fetchMock = vi.fn()

vi.stubGlobal('fetch', fetchMock)

function buildProjectConfig(): QuickScaleConfig {
  return {
    projectName: 'Public Social Demo',
    modules: moduleFlags({ social: true }),
    modulePaths: modulePaths({ analytics: '/analytics/' }),
    moduleApiPaths: moduleApiPaths(),
    owner: { mode: 'solo', currentOrgSlug: null },
    publicPage: {
      module: 'social',
      surface: 'link_tree',
      endpoint: '/_quickscale/social/',
      navigation: { home: '/', linkTree: '/social', embeds: '/social/embeds' },
    },
  }
}

function renderPage() {
  window.__QUICKSCALE__ = buildProjectConfig()
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <SocialLinkTreePublicPage />
    </QueryClientProvider>,
  )
}

function buildPayload(overrides: Partial<SocialLinkTreePayload> = {}): SocialLinkTreePayload {
  return {
    module: 'social',
    surface: 'link_tree',
    status: 'enabled',
    enabled: true,
    public_path: '/social',
    integration_base_path: '/_quickscale/social/',
    integration_embeds_path: '/_quickscale/social/embeds/',
    provider_allowlist: ['youtube'],
    embed_provider_allowlist: ['youtube'],
    error: null,
    layout_variant: 'list',
    links_per_page: 24,
    total_links: 0,
    links: [],
    ...overrides,
  }
}

afterEach(() => {
  fetchMock.mockReset()
  analyticsMock.trackSocialLinkClick.mockReset()
  delete window.__QUICKSCALE__
})

describe('social link-tree page states', () => {
  it('renders the loading shell while the payload is pending', () => {
    fetchMock.mockReturnValue(new Promise(() => {}))
    renderPage()

    expect(screen.getByText('Loading curated links')).toBeInTheDocument()
    expect(screen.getByText('Syncing…')).toBeInTheDocument()
    expect(screen.getAllByText('Loading').length).toBeGreaterThan(0)
  })

  it('renders a grid layout with one destination and a shared source URL', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () =>
        buildPayload({
          layout_variant: 'grid',
          total_links: 1,
          links: [
            {
              id: 5,
              title: 'One link',
              description: '',
              provider_name: 'YouTube',
              provider_display_name: 'YouTube',
              url: 'https://example.com/one',
              source_url: 'https://example.com/one',
              display_order: 1,
            },
          ],
        }),
    })

    const { container } = renderPage()

    expect(await screen.findByText('One link')).toBeInTheDocument()
    expect(screen.getAllByText('Grid layout').length).toBeGreaterThan(0)
    expect(screen.getByText('1 published destination')).toBeInTheDocument()
    expect(
      screen.getByText('A curated public destination rendered through the managed social contract.'),
    ).toBeInTheDocument()
    expect(screen.queryByText(/^Source:/)).toBeNull()
    expect(container.querySelector('.sm\\:grid-cols-2')).not.toBeNull()

    fireEvent.click(screen.getByRole('link', { name: 'Visit One link' }))

    expect(analyticsMock.trackSocialLinkClick).toHaveBeenCalledWith({
      provider: 'YouTube',
      linkId: 5,
      surface: 'link_tree',
      targetUrl: 'https://example.com/one',
    })
  })

  it('renders the list layout for a multi-link payload', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () =>
        buildPayload({
          layout_variant: 'list',
          total_links: 2,
          links: [
            {
              id: 6,
              title: 'First',
              description: 'First destination.',
              provider_name: 'youtube',
              provider_display_name: 'YouTube',
              url: 'https://example.com/first',
              source_url: 'https://example.com/first',
              display_order: 1,
            },
            {
              id: 7,
              title: 'Second',
              description: 'Second destination.',
              provider_name: 'youtube',
              provider_display_name: 'YouTube',
              url: 'https://example.com/second',
              source_url: 'https://example.com/second',
              display_order: 2,
            },
          ],
        }),
    })

    const { container } = renderPage()

    expect(await screen.findByText('First')).toBeInTheDocument()
    expect(screen.getAllByText('List layout').length).toBeGreaterThan(0)
    expect(screen.getByText('2 published destinations')).toBeInTheDocument()
    expect(container.querySelector('.grid-cols-1')).not.toBeNull()
  })

  it('renders the managed error state from an in-contract payload', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () =>
        buildPayload({
          status: 'error',
          enabled: false,
          error: 'Managed social contract reported an error.',
        }),
    })

    renderPage()

    expect(await screen.findByText('Social configuration needs attention')).toBeInTheDocument()
    expect(screen.getAllByText('Managed social contract reported an error.').length).toBeGreaterThan(
      0,
    )
  })
})
