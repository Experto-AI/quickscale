import { afterEach, describe, expect, it } from 'vitest'
import { renderHook } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { useOrgNavigation } from '@/hooks/useOrgNavigation'
import type { QuickScaleConfig } from '@/hooks/useModules'
import { moduleFlags, modulePaths, moduleApiPaths, moduleDocumentPaths } from '@/test/seamFixtures'

function buildConfig(overrides: Partial<QuickScaleConfig> = {}): QuickScaleConfig {
  return {
    projectName: 'QuickScale Test Project',
    modules: moduleFlags({ blog: true, listings: true, forms: true }),
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

function wrapperFor(path: string) {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/orgs/:orgSlug/*" element={<>{children}</>} />
          <Route path="*" element={<>{children}</>} />
        </Routes>
      </MemoryRouter>
    )
  }
}

afterEach(() => {
  delete window.__QUICKSCALE__
})

describe('useOrgNavigation', () => {
  it('keeps the solo workspace on project-root paths', () => {
    window.__QUICKSCALE__ = buildConfig()

    const { result } = renderHook(() => useOrgNavigation(), {
      wrapper: wrapperFor('/dashboard'),
    })

    expect(result.current.isSaas).toBe(false)
    expect(result.current.hasOrgContext).toBe(false)
    expect(result.current.currentOrgSlug).toBeNull()
    expect(result.current.appPaths).toMatchObject({
      orgList: '/orgs',
      orgCreate: '/orgs/new',
      dashboard: '/',
      blog: '/blog',
      listings: '/listings',
      crm: '/crm',
      forms: '/forms/contact',
      members: '/orgs',
      settings: '/settings',
    })
    expect(result.current.documentPaths).toMatchObject({
      blogIndex: '/blog/',
      blogFeed: '/blog/feed/',
      listingsIndex: '/listings/',
      crmDashboard: '/crm/dashboard/',
      crmApiBase: '/crm/api/',
      formsApiBase: '/forms/api/',
    })
  })

  it('routes saas workspaces without an org context to the org list', () => {
    window.__QUICKSCALE__ = buildConfig({
      owner: { mode: 'saas', currentOrgSlug: null },
    })

    const { result } = renderHook(() => useOrgNavigation(), {
      wrapper: wrapperFor('/'),
    })

    expect(result.current.isSaas).toBe(true)
    expect(result.current.hasOrgContext).toBe(false)
    expect(result.current.currentOrgSlug).toBeNull()
    expect(result.current.appPaths.dashboard).toBe('/orgs')
    expect(result.current.appPaths.blog).toBe('/blog')
    expect(result.current.appPaths.members).toBe('/orgs')
    expect(result.current.appPaths.settings).toBe('/settings')
  })

  it('builds org-scoped paths from the owner slug fallback', () => {
    window.__QUICKSCALE__ = buildConfig({
      owner: { mode: 'saas', currentOrgSlug: 'acme' },
    })

    const { result } = renderHook(() => useOrgNavigation(), {
      wrapper: wrapperFor('/orgs'),
    })

    expect(result.current.hasOrgContext).toBe(true)
    expect(result.current.currentOrgSlug).toBe('acme')
    expect(result.current.appPaths).toMatchObject({
      dashboard: '/orgs/acme',
      blog: '/orgs/acme/blog',
      listings: '/orgs/acme/listings',
      members: '/orgs/acme/members',
      settings: '/orgs/acme/settings',
    })
    // A module's server-rendered document keeps its own URL in saas mode
    // too; only the SPA page paths move under the org prefix.
    expect(result.current.documentPaths).toMatchObject({
      blogIndex: '/blog/',
      blogFeed: '/blog/feed/',
      listingsIndex: '/listings/',
    })
  })

  it('prefers the route org slug over the owner fallback', () => {
    window.__QUICKSCALE__ = buildConfig({
      owner: { mode: 'saas', currentOrgSlug: 'fallback-org' },
    })

    const { result } = renderHook(() => useOrgNavigation(), {
      wrapper: wrapperFor('/orgs/route-org/dashboard'),
    })

    expect(result.current.currentOrgSlug).toBe('route-org')
    expect(result.current.appPaths.dashboard).toBe('/orgs/route-org')
    expect(result.current.appPaths.settings).toBe('/orgs/route-org/settings')
  })

  it('follows non-default seam paths for module pages and documents', () => {
    window.__QUICKSCALE__ = buildConfig({
      modulePaths: modulePaths({ blog: '/journal', listings: '/catalog' }),
      moduleDocumentPaths: moduleDocumentPaths({
        blogIndex: '/journal/archive/',
        blogFeed: '/journal/archive/feed/',
        listingsIndex: '/catalog/all/',
        crmDashboard: '/crm/overview/',
      }),
    })

    const { result } = renderHook(() => useOrgNavigation(), {
      wrapper: wrapperFor('/dashboard'),
    })

    // Both path families come from their own seam table, never from a
    // literal or from each other.
    expect(result.current.appPaths.blog).toBe('/journal')
    expect(result.current.appPaths.listings).toBe('/catalog')
    expect(result.current.documentPaths.blogIndex).toBe('/journal/archive/')
    expect(result.current.documentPaths.blogFeed).toBe('/journal/archive/feed/')
    expect(result.current.documentPaths.listingsIndex).toBe('/catalog/all/')
    expect(result.current.documentPaths.crmDashboard).toBe('/crm/overview/')
  })

  it('composes the saas workspace members from the seam page paths', () => {
    window.__QUICKSCALE__ = buildConfig({
      modulePaths: modulePaths({ blog: '/journal', listings: '/catalog' }),
      owner: { mode: 'saas', currentOrgSlug: 'acme' },
    })

    const { result } = renderHook(() => useOrgNavigation(), {
      wrapper: wrapperFor('/orgs/acme'),
    })

    expect(result.current.appPaths.blog).toBe('/orgs/acme/journal')
    expect(result.current.appPaths.listings).toBe('/orgs/acme/catalog')
    // The document destinations keep the module's own document URLs.
    expect(result.current.documentPaths.blogIndex).toBe('/blog/')
    expect(result.current.documentPaths.listingsIndex).toBe('/listings/')
  })
})
