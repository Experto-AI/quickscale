import { afterEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Header } from '@/components/layout/Header'
import { Sidebar } from '@/components/layout/Sidebar'
import { useThemeStore } from '@/stores/themeStore'
import type { QuickScaleConfig } from '@/hooks/useModules'

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
    owner: { mode: 'solo', currentOrgSlug: null },
    ...overrides,
  }
}

function renderSidebar(path = '/') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Sidebar />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

afterEach(() => {
  fetchMock.mockReset()
  delete window.__QUICKSCALE__
  document.documentElement.className = ''
  useThemeStore.setState({ theme: 'light' })
})

describe('Header', () => {
  it('toggles the document theme through the store', async () => {
    const user = userEvent.setup()
    useThemeStore.setState({ theme: 'light' })
    render(<Header />)

    const toggle = screen.getByRole('button', { name: /toggle theme/i })
    expect(toggle).toHaveTextContent('🌙')

    await user.click(toggle)

    expect(toggle).toHaveTextContent('☀️')
    expect(useThemeStore.getState().theme).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })

  it('shows the light-mode icon when the stored theme is dark', () => {
    useThemeStore.setState({ theme: 'dark' })
    render(<Header />)

    expect(screen.getByRole('button', { name: /toggle theme/i })).toHaveTextContent('☀️')
  })
})

describe('Sidebar', () => {
  it('shows every enabled module link in solo mode', () => {
    window.__QUICKSCALE__ = buildConfig({
      modules: {
        auth: true,
        blog: true,
        listings: true,
        crm: true,
        forms: true,
        storage: false,
        backups: false,
        notifications: false,
        analytics: false,
        billing: false,
        social: true,
      },
    })
    fetchMock.mockReturnValue(new Promise(() => {}))
    renderSidebar('/')

    expect(screen.queryByRole('link', { name: /organizations/i })).toBeNull()
    expect(screen.getByRole('link', { name: /^dashboard$/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /^blog$/i })).toHaveAttribute('href', '/blog')
    expect(screen.getByRole('link', { name: /^listings$/i })).toHaveAttribute('href', '/listings')
    expect(screen.getByRole('link', { name: /^crm$/i })).toHaveAttribute('href', '/crm')
    expect(screen.getByRole('link', { name: /^forms$/i })).toHaveAttribute('href', '/forms/contact')
    expect(screen.getByRole('link', { name: /^social$/i })).toHaveAttribute('href', '/social')
    expect(screen.getByRole('link', { name: /^auth$/i })).toHaveAttribute('href', '/profile')
    expect(screen.getByRole('link', { name: /^settings$/i })).toHaveAttribute('href', '/settings')

    const dashboard = screen.getByRole('link', { name: /^dashboard$/i })
    expect(dashboard.className.split(' ')).toContain('bg-sidebar-accent')
    const blog = screen.getByRole('link', { name: /^blog$/i })
    expect(blog.className.split(' ')).not.toContain('bg-sidebar-accent')
    expect(blog.className).toContain('hover:bg-sidebar-accent')
  })

  it('keeps the org-scoped workspace links while an org context is active', () => {
    window.__QUICKSCALE__ = buildConfig({
      modules: {
        auth: true,
        blog: true,
        listings: true,
        crm: false,
        forms: true,
        storage: false,
        backups: false,
        notifications: false,
        analytics: false,
        billing: false,
        social: false,
      },
      owner: { mode: 'saas', currentOrgSlug: 'acme' },
    })
    fetchMock.mockReturnValue(new Promise(() => {}))
    renderSidebar('/orgs/acme')

    expect(screen.getByRole('link', { name: /organizations/i })).toHaveAttribute('href', '/orgs')
    expect(screen.getByRole('link', { name: /^blog$/i })).toHaveAttribute('href', '/orgs/acme/blog')
    expect(screen.getByRole('link', { name: /^listings$/i })).toHaveAttribute(
      'href',
      '/orgs/acme/listings',
    )
    expect(screen.getByRole('link', { name: /^forms$/i })).toHaveAttribute(
      'href',
      '/forms/contact',
    )
    expect(screen.getByRole('link', { name: /members/i })).toHaveAttribute(
      'href',
      '/orgs/acme/members',
    )
    expect(screen.getByRole('link', { name: /org settings/i })).toHaveAttribute(
      'href',
      '/orgs/acme/settings',
    )
  })

  it('hides module links until an org context exists in saas mode', () => {
    window.__QUICKSCALE__ = buildConfig({
      modules: {
        auth: true,
        blog: true,
        listings: true,
        crm: true,
        forms: true,
        storage: false,
        backups: false,
        notifications: false,
        analytics: false,
        billing: false,
        social: true,
      },
      owner: { mode: 'saas', currentOrgSlug: null },
    })
    fetchMock.mockReturnValue(new Promise(() => {}))
    renderSidebar('/orgs')

    expect(screen.queryByRole('link', { name: /^blog$/i })).toBeNull()
    expect(screen.queryByRole('link', { name: /^listings$/i })).toBeNull()
    expect(screen.queryByRole('link', { name: /^forms$/i })).toBeNull()
    expect(screen.queryByRole('link', { name: /members/i })).toBeNull()
    expect(screen.queryByRole('link', { name: /org settings/i })).toBeNull()
    // CRM is not org-gated, and Auth/Social stay visible from their module flags.
    expect(screen.getByRole('link', { name: /^crm$/i })).toHaveAttribute('href', '/crm')
    expect(screen.getByRole('link', { name: /^auth$/i })).toHaveAttribute('href', '/profile')
    expect(screen.getByRole('link', { name: /^social$/i })).toHaveAttribute('href', '/social')
    expect(screen.getByRole('link', { name: /organizations/i })).toHaveAttribute('href', '/orgs')
  })
})
