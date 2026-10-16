import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { moduleFlags, modulePaths, moduleApiPaths, moduleDocumentPaths } from '@/test/seamFixtures'

// Mock lazy-loaded social page modules so they resolve synchronously in tests.
vi.mock('@/pages/SocialEmbedsPublicPage', () => ({
  SocialEmbedsPublicPage: function MockEmbedsPage() {
    return <div>SocialEmbedsPublicPage rendered</div>
  },
}))
vi.mock('@/pages/SocialLinkTreePublicPage', () => ({
  SocialLinkTreePublicPage: function MockLinkTreePage() {
    return <div>SocialLinkTreePublicPage rendered</div>
  },
}))

import { renderQuickScaleRoot } from '../renderQuickScaleRoot'

/**
 * Build a config matching the production template injector shape from
 * templates/index.html.j2 — the standard app shell config.
 */
function applyConfig(overrides?: Record<string, unknown>) {
  window.__QUICKSCALE__ = {
    projectName: 'QuickScale Test Project',
    modules: moduleFlags(),
    modulePaths: modulePaths({ analytics: '/analytics/' }),
    moduleApiPaths: moduleApiPaths(),
    moduleDocumentPaths: moduleDocumentPaths(),
    owner: {
      mode: 'solo',
      currentOrgSlug: null,
    },
    ...overrides,
  }
}

/**
 * Build a config matching the production public social injector from
 * templates/social/link_tree.html.j2 — a minimal config only sufficing
 * for a public social page (no org context, no extra module paths).
 */
function applyPublicInjectorConfig(surface: 'link_tree' | 'embeds') {
  window.__QUICKSCALE__ = {
    projectName: 'Public Social Demo',
    modules: moduleFlags({ social: true }),
    modulePaths: modulePaths({ crm: '/crm/', social: surface === 'link_tree' ? '/social' : '/social/embeds', analytics: '/analytics/' }),
    moduleApiPaths: moduleApiPaths(),
    moduleDocumentPaths: moduleDocumentPaths(),
    owner: {
      mode: 'solo',
      currentOrgSlug: null,
    },
    publicPage: {
      module: 'social',
      surface,
      endpoint: surface === 'link_tree' ? '/_quickscale/social/' : '/_quickscale/social/embeds/',
      navigation: {
        home: '/',
        linkTree: '/social',
        embeds: '/social/embeds',
      },
    },
  }
}

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)
}

afterEach(() => {
  vi.clearAllMocks()
  delete window.__QUICKSCALE__
})

describe('renderQuickScaleRoot', () => {
  it('renders App via BrowserRouter when surface is absent', () => {
    applyConfig()
    window.__QUICKSCALE__!.modules.social = true
    // surface undefined -> renderQuickScaleRoot falls through to BrowserRouter + App
    renderWithProviders(renderQuickScaleRoot(undefined))
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })

  it('renders App via BrowserRouter when modules.social is false', () => {
    applyConfig()
    renderWithProviders(renderQuickScaleRoot('link_tree'))
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })

  it('throws when required module keys are absent from config', () => {
    // With declaration-backed validation, a sparse modules object must throw
    applyConfig({ modules: { auth: true } as unknown as Record<string, unknown> })
    expect(() => renderWithProviders(renderQuickScaleRoot('link_tree'))).toThrow(/modules\.blog/)
  })

  it('renders SocialLinkTreePublicPage when social=true and surface=link_tree', async () => {
    applyConfig()
    window.__QUICKSCALE__!.modules.social = true
    renderWithProviders(renderQuickScaleRoot('link_tree'))
    expect(
      await screen.findByText('SocialLinkTreePublicPage rendered'),
    ).toBeInTheDocument()
  })

  it('renders SocialEmbedsPublicPage when social=true and surface=embeds', async () => {
    applyConfig()
    window.__QUICKSCALE__!.modules.social = true
    renderWithProviders(renderQuickScaleRoot('embeds'))
    expect(
      await screen.findByText('SocialEmbedsPublicPage rendered'),
    ).toBeInTheDocument()
  })

  // ── Production-shaped public injector boot tests (SA107-TEST-001) ─

  it('boots and renders link tree from production link_tree.html.j2 injector shape', async () => {
    applyPublicInjectorConfig('link_tree')
    renderWithProviders(renderQuickScaleRoot('link_tree'))
    expect(
      await screen.findByText('SocialLinkTreePublicPage rendered'),
    ).toBeInTheDocument()
  })

  it('boots and renders embeds from production embeds.html.j2 injector shape', async () => {
    applyPublicInjectorConfig('embeds')
    renderWithProviders(renderQuickScaleRoot('embeds'))
    expect(
      await screen.findByText('SocialEmbedsPublicPage rendered'),
    ).toBeInTheDocument()
  })

  it('falls back to App when public injector config lacks publicPage', async () => {
    // Same shape as public injectors but without publicPage — exercises
    // the fallback path where renderQuickScaleRoot receives undefined surface.
    applyPublicInjectorConfig('link_tree')
    delete window.__QUICKSCALE__!.publicPage
    renderWithProviders(renderQuickScaleRoot(undefined))
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })
})
