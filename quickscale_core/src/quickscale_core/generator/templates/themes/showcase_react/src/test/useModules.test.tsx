import { afterEach, describe, expect, it } from 'vitest'
import { renderHook } from '@testing-library/react'
import {
  buildOrgPath,
  useCurrentOrgSlug,
  useModules,
  useOwnerMode,
  useProjectConfig,
} from '@/hooks/useModules'
import type { QuickScaleConfig } from '@/hooks/useModules'

function buildConfig(overrides: Partial<QuickScaleConfig> = {}): QuickScaleConfig {
  return {
    projectName: 'QuickScale Test Project',
    modules: {
      auth: true,
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
    owner: {
      mode: 'solo',
      currentOrgSlug: null,
    },
    ...overrides,
  }
}

afterEach(() => {
  delete window.__QUICKSCALE__
})

describe('useModules config readers', () => {
  it('reads the module flags and owner mode from the runtime config', () => {
    window.__QUICKSCALE__ = buildConfig({ owner: { mode: 'saas', currentOrgSlug: null } })

    const modules = renderHook(() => useModules())
    expect(modules.result.current.auth).toBe(true)
    expect(modules.result.current.blog).toBe(false)

    const mode = renderHook(() => useOwnerMode())
    expect(mode.result.current).toBe('saas')

    const config = renderHook(() => useProjectConfig())
    expect(config.result.current.projectName).toBe('QuickScale Test Project')
  })

  it('returns the owner slug when the runtime config carries one', () => {
    window.__QUICKSCALE__ = buildConfig({
      owner: { mode: 'saas', currentOrgSlug: 'acme' },
    })

    const { result } = renderHook(() => useCurrentOrgSlug())

    expect(result.current).toBe('acme')
  })

  it('infers the current org slug from the org-scoped CRM path', () => {
    window.__QUICKSCALE__ = buildConfig({
      modulePaths: {
        crm: '/orgs/acme%20co/crm/api/',
        social: '/social',
        analytics: '/analytics/',
      },
      owner: { mode: 'saas', currentOrgSlug: null },
    })

    const { result } = renderHook(() => useCurrentOrgSlug())

    expect(result.current).toBe('acme co')
  })

  it('returns null when the CRM path is not org-scoped', () => {
    window.__QUICKSCALE__ = buildConfig({
      modulePaths: { crm: '/crm', social: '/social', analytics: '/analytics/' },
    })

    const { result } = renderHook(() => useCurrentOrgSlug())

    expect(result.current).toBeNull()
  })
})

describe('buildOrgPath', () => {
  it('builds an org base path without a sub-path', () => {
    expect(buildOrgPath('acme')).toBe('/orgs/acme')
    expect(buildOrgPath('acme', '')).toBe('/orgs/acme')
  })

  it('joins relative and absolute sub-paths under the org base', () => {
    expect(buildOrgPath('acme', 'settings')).toBe('/orgs/acme/settings')
    expect(buildOrgPath('acme', '/settings')).toBe('/orgs/acme/settings')
  })
})
