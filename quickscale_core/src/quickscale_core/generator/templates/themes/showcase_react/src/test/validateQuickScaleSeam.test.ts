import { afterEach, describe, expect, it } from 'vitest'
import { validateQuickScaleConfig } from '@/lib/validateQuickScaleSeam'
import type { QuickScaleConfig } from '@/hooks/useModules'

function buildValidConfig(): QuickScaleConfig {
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
    owner: {
      mode: 'solo',
      currentOrgSlug: null,
    },
  }
}

/**
 * Build a config that mirrors the public injector shape in
 * templates/social/link_tree.html.j2 — a minimal config with all
 * required fields that a Django-owned public social page provides.
 */
function buildPublicInjectorLinkTree(): QuickScaleConfig {
  return {
    projectName: 'Public Social Demo',
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
      social: true,
    },
    modulePaths: {
      crm: '/crm/',
      social: '/social',
      analytics: '/analytics/',
    },
    owner: {
      mode: 'solo',
      currentOrgSlug: null,
    },
    publicPage: {
      module: 'social',
      surface: 'link_tree',
      endpoint: '/_quickscale/social/',
      navigation: {
        home: '/',
        linkTree: '/social',
        embeds: '/social/embeds',
      },
    },
  }
}

/**
 * Build a config that mirrors the public injector shape in
 * templates/social/embeds.html.j2.
 */
function buildPublicInjectorEmbeds(): QuickScaleConfig {
  return {
    projectName: 'Public Social Demo',
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
      social: true,
    },
    modulePaths: {
      crm: '/crm/',
      social: '/social/embeds',
      analytics: '/analytics/',
    },
    owner: {
      mode: 'solo',
      currentOrgSlug: null,
    },
    publicPage: {
      module: 'social',
      surface: 'embeds',
      endpoint: '/_quickscale/social/embeds/',
      navigation: {
        home: '/',
        linkTree: '/social',
        embeds: '/social/embeds',
      },
    },
  }
}

afterEach(() => {
  delete window.__QUICKSCALE__
})

describe('validateQuickScaleConfig', () => {
  it('returns the config for a well-formed seam', () => {
    const config = buildValidConfig()
    window.__QUICKSCALE__ = config

    const result = validateQuickScaleConfig()
    expect(result.projectName).toBe('QuickScale Test Project')
    expect(result.modules.auth).toBe(false)
    expect(result.modules.social).toBe(false)
    expect(result.owner.mode).toBe('solo')
  })

  it('returns the config when publicPage is absent (optional)', () => {
    const config = buildValidConfig()
    // publicPage is already absent in buildValidConfig
    window.__QUICKSCALE__ = config

    const result = validateQuickScaleConfig()
    expect(result.projectName).toBe('QuickScale Test Project')
    // Should not throw — publicPage is optional
  })

  it('returns the config when publicPage is present and well-formed', () => {
    const config = buildValidConfig()
    config.modules.social = true
    config.publicPage = {
      module: 'social',
      surface: 'link_tree',
      endpoint: '/_quickscale/social/',
      navigation: {
        home: '/',
        linkTree: '/social',
        embeds: '/social/embeds',
      },
    }
    window.__QUICKSCALE__ = config

    const result = validateQuickScaleConfig()
    expect(result.publicPage?.surface).toBe('link_tree')
    expect(result.publicPage?.navigation.home).toBe('/')
  })

  it('throws when window.__QUICKSCALE__ is missing', () => {
    // window.__QUICKSCALE__ already deleted in afterEach
    expect(() => validateQuickScaleConfig()).toThrow(/window\.__QUICKSCALE__/)
  })

  it('throws when window.__QUICKSCALE__ is null', () => {
    window.__QUICKSCALE__ = null as unknown as QuickScaleConfig
    expect(() => validateQuickScaleConfig()).toThrow(/window\.__QUICKSCALE__/)
  })

  it('throws when projectName is missing', () => {
    window.__QUICKSCALE__ = { ...buildValidConfig(), projectName: '' as string }
    expect(() => validateQuickScaleConfig()).toThrow(/projectName/)
  })

  it('throws when projectName is empty string', () => {
    window.__QUICKSCALE__ = { ...buildValidConfig(), projectName: '' }
    expect(() => validateQuickScaleConfig()).toThrow(/projectName/)
  })

  it('throws when projectName is only whitespace', () => {
    window.__QUICKSCALE__ = { ...buildValidConfig(), projectName: '   ' }
    expect(() => validateQuickScaleConfig()).toThrow(/projectName/)
  })

  it('throws when modules is missing', () => {
    const config: Record<string, unknown> = JSON.parse(JSON.stringify(buildValidConfig()))
    delete config.modules
    window.__QUICKSCALE__ = config as unknown as QuickScaleConfig
    expect(() => validateQuickScaleConfig()).toThrow(/modules/)
  })

  it('throws when modules is an array', () => {
    window.__QUICKSCALE__ = { ...buildValidConfig(), modules: [] as unknown as QuickScaleConfig['modules'] }
    expect(() => validateQuickScaleConfig()).toThrow(/modules/)
  })

  it('throws when a module value is not a boolean (string)', () => {
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      modules: { ...buildValidConfig().modules, auth: 'yes' as unknown as boolean },
    }
    expect(() => validateQuickScaleConfig()).toThrow(/modules\.auth/)
  })

  it('throws when a module value is not a boolean (number)', () => {
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      modules: { ...buildValidConfig().modules, blog: 1 as unknown as boolean },
    }
    expect(() => validateQuickScaleConfig()).toThrow(/modules\.blog/)
  })

  // ── Required module keys (SA107-CR-002) ───────────────────────────

  const REQUIRED_KEYS = [
    'auth', 'blog', 'listings', 'crm', 'forms', 'storage',
    'backups', 'notifications', 'analytics', 'billing', 'social',
  ] as const

  it.each(REQUIRED_KEYS)('throws when required module key "%s" is missing', (missingKey) => {
    const config: Record<string, unknown> = JSON.parse(JSON.stringify(buildValidConfig()))
    const modules = config.modules as Record<string, unknown>
    delete modules[missingKey]
    window.__QUICKSCALE__ = config as unknown as QuickScaleConfig
    expect(() => validateQuickScaleConfig()).toThrow(new RegExp(`modules\\.${missingKey}`))
  })

  it('throws when modules has only a subset of required keys', () => {
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      modules: { auth: false, social: true } as unknown as QuickScaleConfig['modules'],
    }
    expect(() => validateQuickScaleConfig()).toThrow(/modules\.blog/)
  })

  // ── Inherited / non-enumerable required flags (SA107-CR-002) ────

  it('throws when a required module key is inherited from prototype with non-boolean value', () => {
    const proto = { auth: 'not-a-boolean' }
    const inheritedModules = Object.create(proto)
    // Set all other 10 required keys as own booleans
    for (const key of ['blog', 'listings', 'crm', 'forms', 'storage', 'backups', 'notifications', 'analytics', 'billing', 'social']) {
      inheritedModules[key] = false
    }
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      modules: inheritedModules as unknown as QuickScaleConfig['modules'],
    }
    expect(() => validateQuickScaleConfig()).toThrow(/modules\.auth/)
  })

  it('throws when a required module key is inherited (no match in own or inherited value)', () => {
    const proto = {}
    const missingModules = Object.create(proto)
    for (const key of ['blog', 'listings', 'crm', 'forms', 'storage', 'backups', 'notifications', 'analytics', 'billing', 'social']) {
      missingModules[key] = false
    }
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      modules: missingModules as unknown as QuickScaleConfig['modules'],
    }
    expect(() => validateQuickScaleConfig()).toThrow(/modules\.auth/)
  })

  it.each([true, false])('throws when a required module key is inherited from prototype with boolean value %s', (authValue) => {
    const proto = { auth: authValue }
    const inheritedModules = Object.create(proto)
    for (const key of ['blog', 'listings', 'crm', 'forms', 'storage', 'backups', 'notifications', 'analytics', 'billing', 'social']) {
      inheritedModules[key] = false
    }
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      modules: inheritedModules as unknown as QuickScaleConfig['modules'],
    }
    expect(() => validateQuickScaleConfig()).toThrow(/modules\.auth/)
  })

  it('throws when a required module key is own but non-enumerable with non-boolean value', () => {
    const modules: Record<string, unknown> = {}
    // Set all other required keys normally first
    for (const key of ['blog', 'listings', 'crm', 'forms', 'storage', 'backups', 'notifications', 'analytics', 'billing', 'social']) {
      modules[key] = false
    }
    // Set auth as non-enumerable non-boolean — preserves hasOwnProperty but hides from Object.entries
    Object.defineProperty(modules, 'auth', {
      value: 'non-enumerable-string',
      enumerable: false,
      writable: true,
      configurable: true,
    })
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      modules: modules as unknown as QuickScaleConfig['modules'],
    }
    expect(() => validateQuickScaleConfig()).toThrow(/modules\.auth/)
  })

  it('throws when a required module key is own but non-enumerable with non-boolean value (number)', () => {
    const modules: Record<string, unknown> = {}
    for (const key of ['blog', 'listings', 'crm', 'forms', 'storage', 'backups', 'notifications', 'analytics', 'billing', 'social']) {
      modules[key] = false
    }
    Object.defineProperty(modules, 'auth', {
      value: 42,
      enumerable: false,
      writable: true,
      configurable: true,
    })
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      modules: modules as unknown as QuickScaleConfig['modules'],
    }
    expect(() => validateQuickScaleConfig()).toThrow(/modules\.auth/)
  })

  it('throws when publicPage.endpoint is missing', () => {
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      publicPage: {
        module: 'social',
        surface: 'link_tree',
        navigation: { home: '/', linkTree: '/social', embeds: '/social/embeds' },
      } as QuickScaleConfig['publicPage'],
    }
    expect(() => validateQuickScaleConfig()).toThrow(/publicPage\.endpoint/)
  })

  it('throws when publicPage.navigation.home is missing', () => {
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      publicPage: {
        module: 'social',
        surface: 'embeds',
        endpoint: '/_quickscale/social/embeds/',
        navigation: { linkTree: '/social', embeds: '/social/embeds' },
      } as QuickScaleConfig['publicPage'],
    }
    expect(() => validateQuickScaleConfig()).toThrow(/navigation\.home/)
  })

  it('throws when publicPage.navigation.embeds is empty string', () => {
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      publicPage: {
        module: 'social',
        surface: 'embeds',
        endpoint: '/_quickscale/social/embeds/',
        navigation: { home: '/', linkTree: '/social', embeds: '' },
      } as QuickScaleConfig['publicPage'],
    }
    expect(() => validateQuickScaleConfig()).toThrow(/navigation\.embeds/)
  })

  // ── modulePaths validation (SA107-CR-002) ─────────────────────

  it('throws when modulePaths is missing', () => {
    const config: Record<string, unknown> = JSON.parse(JSON.stringify(buildValidConfig()))
    delete config.modulePaths
    window.__QUICKSCALE__ = config as unknown as QuickScaleConfig
    expect(() => validateQuickScaleConfig()).toThrow(/modulePaths/)
  })

  it('throws when modulePaths is an array', () => {
    window.__QUICKSCALE__ = { ...buildValidConfig(), modulePaths: [] as unknown as QuickScaleConfig['modulePaths'] }
    expect(() => validateQuickScaleConfig()).toThrow(/modulePaths/)
  })

  it('throws when modulePaths.crm is missing', () => {
    const mp = { social: '/social', analytics: '/analytics/' }
    window.__QUICKSCALE__ = { ...buildValidConfig(), modulePaths: mp as QuickScaleConfig['modulePaths'] }
    expect(() => validateQuickScaleConfig()).toThrow(/modulePaths\.crm/)
  })

  it('throws when modulePaths.crm is empty string', () => {
    window.__QUICKSCALE__ = { ...buildValidConfig(), modulePaths: { crm: '', social: '/social', analytics: '/analytics/' } as QuickScaleConfig['modulePaths'] }
    expect(() => validateQuickScaleConfig()).toThrow(/modulePaths\.crm/)
  })

  it('throws when modulePaths.social is a number', () => {
    window.__QUICKSCALE__ = { ...buildValidConfig(), modulePaths: { crm: '/crm', social: 42, analytics: '/analytics/' } as unknown as QuickScaleConfig['modulePaths'] }
    expect(() => validateQuickScaleConfig()).toThrow(/modulePaths\.social/)
  })

  // ── owner validation (SA107-CR-002) ───────────────────────────

  it('throws when owner is missing', () => {
    const config: Record<string, unknown> = JSON.parse(JSON.stringify(buildValidConfig()))
    delete config.owner
    window.__QUICKSCALE__ = config as unknown as QuickScaleConfig
    expect(() => validateQuickScaleConfig()).toThrow(/owner/)
  })

  it('throws when owner is an array', () => {
    window.__QUICKSCALE__ = { ...buildValidConfig(), owner: [] as unknown as QuickScaleConfig['owner'] }
    expect(() => validateQuickScaleConfig()).toThrow(/owner/)
  })

  it('throws when owner.mode is neither solo nor saas', () => {
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      owner: { mode: 'enterprise', currentOrgSlug: null } as unknown as QuickScaleConfig['owner'],
    }
    expect(() => validateQuickScaleConfig()).toThrow(/owner\.mode/)
  })

  it('throws when owner.currentOrgSlug is a boolean', () => {
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      owner: { mode: 'solo', currentOrgSlug: true } as unknown as QuickScaleConfig['owner'],
    }
    expect(() => validateQuickScaleConfig()).toThrow(/currentOrgSlug/)
  })

  it('throws when owner.currentOrgSlug is a number', () => {
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      owner: { mode: 'solo', currentOrgSlug: 123 } as unknown as QuickScaleConfig['owner'],
    }
    expect(() => validateQuickScaleConfig()).toThrow(/currentOrgSlug/)
  })

  it('accepts owner.currentOrgSlug as a string', () => {
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      owner: { mode: 'saas', currentOrgSlug: 'my-org' },
    }
    const result = validateQuickScaleConfig()
    expect(result.owner.currentOrgSlug).toBe('my-org')
  })

  // ── publicPage enum/type strict validation (SA107-CR-002) ─────

  it('throws when publicPage.module is not "social"', () => {
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      publicPage: {
        module: 'blog',
        surface: 'link_tree',
        endpoint: '/_quickscale/social/',
        navigation: { home: '/', linkTree: '/social', embeds: '/social/embeds' },
      } as unknown as QuickScaleConfig['publicPage'],
    }
    expect(() => validateQuickScaleConfig()).toThrow(/publicPage\.module/)
  })

  it('throws when publicPage.surface is an unsupported string', () => {
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      publicPage: {
        module: 'social',
        surface: 'gallery',
        endpoint: '/_quickscale/social/',
        navigation: { home: '/', linkTree: '/social', embeds: '/social/embeds' },
      } as unknown as QuickScaleConfig['publicPage'],
    }
    expect(() => validateQuickScaleConfig()).toThrow(/publicPage\.surface/)
  })

  it('throws when publicPage.surface is a number', () => {
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      publicPage: {
        module: 'social',
        surface: 3,
        endpoint: '/_quickscale/social/',
        navigation: { home: '/', linkTree: '/social', embeds: '/social/embeds' },
      } as unknown as QuickScaleConfig['publicPage'],
    }
    expect(() => validateQuickScaleConfig()).toThrow(/publicPage\.surface/)
  })

  it('throws when publicPage.endpoint is an array', () => {
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      publicPage: {
        module: 'social',
        surface: 'link_tree',
        endpoint: [],
        navigation: { home: '/', linkTree: '/social', embeds: '/social/embeds' },
      } as unknown as QuickScaleConfig['publicPage'],
    }
    expect(() => validateQuickScaleConfig()).toThrow(/publicPage\.endpoint/)
  })

  it('throws when publicPage.endpoint is a number', () => {
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      publicPage: {
        module: 'social',
        surface: 'link_tree',
        endpoint: 42,
        navigation: { home: '/', linkTree: '/social', embeds: '/social/embeds' },
      } as unknown as QuickScaleConfig['publicPage'],
    }
    expect(() => validateQuickScaleConfig()).toThrow(/publicPage\.endpoint/)
  })

  // ── Production-shaped public injector configs (SA107-TEST-001) ─

  it('accepts a production-shaped link_tree public injector config', () => {
    window.__QUICKSCALE__ = buildPublicInjectorLinkTree()
    const result = validateQuickScaleConfig()
    expect(result.projectName).toBe('Public Social Demo')
    expect(result.publicPage?.surface).toBe('link_tree')
    expect(result.publicPage?.endpoint).toBe('/_quickscale/social/')
    expect(result.owner.mode).toBe('solo')
    expect(result.owner.currentOrgSlug).toBeNull()
    expect(result.modulePaths.crm).toBe('/crm/')
    expect(result.modulePaths.social).toBe('/social')
    expect(result.modulePaths.analytics).toBe('/analytics/')
  })

  it('accepts a production-shaped embeds public injector config', () => {
    window.__QUICKSCALE__ = buildPublicInjectorEmbeds()
    const result = validateQuickScaleConfig()
    expect(result.projectName).toBe('Public Social Demo')
    expect(result.publicPage?.surface).toBe('embeds')
    expect(result.publicPage?.endpoint).toBe('/_quickscale/social/embeds/')
    expect(result.owner.mode).toBe('solo')
    expect(result.owner.currentOrgSlug).toBeNull()
    expect(result.modulePaths.social).toBe('/social/embeds')
  })

  it('accepts a production-shaped saas-mode config', () => {
    const config = buildValidConfig()
    config.owner = { mode: 'saas', currentOrgSlug: 'acme-corp' }
    config.modulePaths = { crm: '/orgs/acme-corp/crm/', social: '/social', analytics: '/analytics/' }
    window.__QUICKSCALE__ = config
    const result = validateQuickScaleConfig()
    expect(result.owner.mode).toBe('saas')
    expect(result.owner.currentOrgSlug).toBe('acme-corp')
  })
})
