import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

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

function applyConfig(overrides?: Record<string, unknown>) {
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
    },
    modulePaths: {
      crm: '/crm',
      social: '/social',
      analytics: '/analytics/',
    },
    owner: {
      mode: 'solo',
      currentOrgSlug: null,
    },
    ...overrides,
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
    applyConfig({ modules: { social: true } })
    // surface undefined -> renderQuickScaleRoot falls through to BrowserRouter + App
    renderWithProviders(renderQuickScaleRoot(undefined))
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })

  it('renders App via BrowserRouter when modules.social is false', () => {
    applyConfig()
    renderWithProviders(renderQuickScaleRoot('link_tree'))
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })

  it('renders App via BrowserRouter when modules.social is absent from config', () => {
    applyConfig({ modules: { auth: true } }) // social key omitted
    renderWithProviders(renderQuickScaleRoot('link_tree'))
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })

  it('renders SocialLinkTreePublicPage when social=true and surface=link_tree', async () => {
    applyConfig({ modules: { social: true } })
    renderWithProviders(renderQuickScaleRoot('link_tree'))
    expect(
      await screen.findByText('SocialLinkTreePublicPage rendered'),
    ).toBeInTheDocument()
  })

  it('renders SocialEmbedsPublicPage when social=true and surface=embeds', async () => {
    applyConfig({ modules: { social: true } })
    renderWithProviders(renderQuickScaleRoot('embeds'))
    expect(
      await screen.findByText('SocialEmbedsPublicPage rendered'),
    ).toBeInTheDocument()
  })
})
