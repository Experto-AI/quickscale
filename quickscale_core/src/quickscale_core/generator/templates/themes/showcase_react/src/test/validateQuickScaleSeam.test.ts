import { afterEach, describe, expect, it } from 'vitest'
import { validateQuickScaleConfig } from '@/lib/validateQuickScaleSeam'
import type { QuickScaleConfig } from '@/hooks/useModules'
import {
  SEAM_MODULE_API_PATH_KEYS,
  SEAM_MODULE_DOCUMENT_PATH_KEYS,
  SEAM_MODULE_FLAG_KEYS,
  SEAM_MODULE_PATH_KEYS,
} from '@/quickscaleSeam.keys'
import { moduleApiPaths, moduleDocumentPaths, moduleFlags, modulePaths } from '@/test/seamFixtures'

function buildValidConfig(): QuickScaleConfig {
  return {
    projectName: 'QuickScale Test Project',
    modules: moduleFlags(),
    modulePaths: modulePaths({ analytics: '/analytics/' }),
    moduleApiPaths: moduleApiPaths(),
    moduleDocumentPaths: moduleDocumentPaths(),
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
    modules: moduleFlags({ social: true }),
    modulePaths: modulePaths({ crm: '/crm/', analytics: '/analytics/' }),
    moduleApiPaths: moduleApiPaths(),
    moduleDocumentPaths: moduleDocumentPaths(),
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
    modules: moduleFlags({ social: true }),
    modulePaths: modulePaths({ crm: '/crm/', social: '/social/embeds', analytics: '/analytics/' }),
    moduleApiPaths: moduleApiPaths(),
    moduleDocumentPaths: moduleDocumentPaths(),
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
    expect(result.publicPage).toMatchObject({
      module: 'social',
      surface: 'link_tree',
      endpoint: '/_quickscale/social/',
      navigation: { home: '/', linkTree: '/social', embeds: '/social/embeds' },
    })
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

  // ── Required module keys, from the generated key manifest (SA276) ─

  it.each([...SEAM_MODULE_FLAG_KEYS])(
    'throws when required module key "%s" is missing',
    (missingKey) => {
      const config: Record<string, unknown> = JSON.parse(JSON.stringify(buildValidConfig()))
      const modules = config.modules as Record<string, unknown>
      delete modules[missingKey]
      window.__QUICKSCALE__ = config as unknown as QuickScaleConfig
      expect(() => validateQuickScaleConfig()).toThrow(new RegExp(`modules\\.${missingKey}`))
    },
  )

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
    // Set all other required keys as own booleans
    for (const key of SEAM_MODULE_FLAG_KEYS) {
      if (key !== 'auth') inheritedModules[key] = false
    }
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      modules: inheritedModules as unknown as QuickScaleConfig['modules'],
    }
    expect(() => validateQuickScaleConfig()).toThrow(/modules\.auth/)
  })

  it('throws when a required module key is inherited (no match in own or inherited value)', () => {
    const missingModules = Object.create({})
    for (const key of SEAM_MODULE_FLAG_KEYS) {
      if (key !== 'auth') missingModules[key] = false
    }
    window.__QUICKSCALE__ = {
      ...buildValidConfig(),
      modules: missingModules as unknown as QuickScaleConfig['modules'],
    }
    expect(() => validateQuickScaleConfig()).toThrow(/modules\.auth/)
  })

  it.each([true, false])(
    'throws when a required module key is inherited from prototype with boolean value %s',
    (authValue) => {
      const proto = { auth: authValue }
      const inheritedModules = Object.create(proto)
      for (const key of SEAM_MODULE_FLAG_KEYS) {
        if (key !== 'auth') inheritedModules[key] = false
      }
      window.__QUICKSCALE__ = {
        ...buildValidConfig(),
        modules: inheritedModules as unknown as QuickScaleConfig['modules'],
      }
      expect(() => validateQuickScaleConfig()).toThrow(/modules\.auth/)
    },
  )

  it('throws when a required module key is own but non-enumerable with non-boolean value', () => {
    const modules: Record<string, unknown> = {}
    // Set all other required keys normally first
    for (const key of SEAM_MODULE_FLAG_KEYS) {
      if (key !== 'auth') modules[key] = false
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
    for (const key of SEAM_MODULE_FLAG_KEYS) {
      if (key !== 'auth') modules[key] = false
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

  it.each([...SEAM_MODULE_PATH_KEYS])(
    'throws when modulePaths.%s is missing',
    (missingKey) => {
      const config: Record<string, unknown> = JSON.parse(JSON.stringify(buildValidConfig()))
      const paths = config.modulePaths as Record<string, unknown>
      delete paths[missingKey]
      window.__QUICKSCALE__ = config as unknown as QuickScaleConfig
      expect(() => validateQuickScaleConfig()).toThrow(new RegExp(`modulePaths\\.${missingKey}`))
    },
  )

  it('throws when modulePaths.crm is empty string', () => {
    window.__QUICKSCALE__ = { ...buildValidConfig(), modulePaths: modulePaths({ crm: '', analytics: '/analytics/' }) as QuickScaleConfig['modulePaths'] }
    expect(() => validateQuickScaleConfig()).toThrow(/modulePaths\.crm/)
  })

  it('throws when modulePaths.social is a number', () => {
    window.__QUICKSCALE__ = { ...buildValidConfig(), modulePaths: { ...modulePaths(), social: 42 } as unknown as QuickScaleConfig['modulePaths'] }
    expect(() => validateQuickScaleConfig()).toThrow(/modulePaths\.social/)
  })

  // ── moduleApiPaths validation ───────────────────────────────────

  it('throws when moduleApiPaths is missing', () => {
    const config: Record<string, unknown> = JSON.parse(JSON.stringify(buildValidConfig()))
    delete config.moduleApiPaths
    window.__QUICKSCALE__ = config as unknown as QuickScaleConfig
    expect(() => validateQuickScaleConfig()).toThrow(/moduleApiPaths/)
  })

  it('throws when moduleApiPaths is an array', () => {
    window.__QUICKSCALE__ = { ...buildValidConfig(), moduleApiPaths: [] as unknown as QuickScaleConfig['moduleApiPaths'] }
    expect(() => validateQuickScaleConfig()).toThrow(/moduleApiPaths/)
  })

  it.each([...SEAM_MODULE_API_PATH_KEYS])(
    'throws when moduleApiPaths.%s is missing',
    (missingKey) => {
      const config: Record<string, unknown> = JSON.parse(JSON.stringify(buildValidConfig()))
      const paths = config.moduleApiPaths as Record<string, unknown>
      delete paths[missingKey]
      window.__QUICKSCALE__ = config as unknown as QuickScaleConfig
      expect(() => validateQuickScaleConfig()).toThrow(new RegExp(`moduleApiPaths\\.${missingKey}`))
    },
  )

  it('throws when moduleApiPaths.orgs is empty string', () => {
    window.__QUICKSCALE__ = { ...buildValidConfig(), moduleApiPaths: moduleApiPaths({ orgs: '' }) as QuickScaleConfig['moduleApiPaths'] }
    expect(() => validateQuickScaleConfig()).toThrow(/moduleApiPaths\.orgs/)
  })

  it('throws when moduleApiPaths.billing is a number', () => {
    window.__QUICKSCALE__ = { ...buildValidConfig(), moduleApiPaths: { ...moduleApiPaths(), billing: 42 } as unknown as QuickScaleConfig['moduleApiPaths'] }
    expect(() => validateQuickScaleConfig()).toThrow(/moduleApiPaths\.billing/)
  })

  // ── moduleDocumentPaths validation ──────────────────────────────

  it('throws when moduleDocumentPaths is missing', () => {
    const config: Record<string, unknown> = JSON.parse(JSON.stringify(buildValidConfig()))
    delete config.moduleDocumentPaths
    window.__QUICKSCALE__ = config as unknown as QuickScaleConfig
    expect(() => validateQuickScaleConfig()).toThrow(/moduleDocumentPaths/)
  })

  it('throws when moduleDocumentPaths is an array', () => {
    window.__QUICKSCALE__ = { ...buildValidConfig(), moduleDocumentPaths: [] as unknown as QuickScaleConfig['moduleDocumentPaths'] }
    expect(() => validateQuickScaleConfig()).toThrow(/moduleDocumentPaths/)
  })

  it.each([...SEAM_MODULE_DOCUMENT_PATH_KEYS])(
    'throws when moduleDocumentPaths.%s is missing',
    (missingKey) => {
      const config: Record<string, unknown> = JSON.parse(JSON.stringify(buildValidConfig()))
      const paths = config.moduleDocumentPaths as Record<string, unknown>
      delete paths[missingKey]
      window.__QUICKSCALE__ = config as unknown as QuickScaleConfig
      expect(() => validateQuickScaleConfig()).toThrow(
        new RegExp(`moduleDocumentPaths\\.${missingKey}`),
      )
    },
  )

  it('throws when moduleDocumentPaths.blogIndex is empty string', () => {
    window.__QUICKSCALE__ = { ...buildValidConfig(), moduleDocumentPaths: moduleDocumentPaths({ blogIndex: '' }) as QuickScaleConfig['moduleDocumentPaths'] }
    expect(() => validateQuickScaleConfig()).toThrow(/moduleDocumentPaths\.blogIndex/)
  })

  it('throws when moduleDocumentPaths.blogFeed is a number', () => {
    window.__QUICKSCALE__ = { ...buildValidConfig(), moduleDocumentPaths: { ...moduleDocumentPaths(), blogFeed: 42 } as unknown as QuickScaleConfig['moduleDocumentPaths'] }
    expect(() => validateQuickScaleConfig()).toThrow(/moduleDocumentPaths\.blogFeed/)
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

  it('throws when publicPage.module is neither "social" nor "properties"', () => {
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
    expect(result.publicPage).toMatchObject({
      module: 'social',
      surface: 'link_tree',
      endpoint: '/_quickscale/social/',
    })
    expect(result.owner.mode).toBe('solo')
    expect(result.owner.currentOrgSlug).toBeNull()
    expect(result.modulePaths.crm).toBe('/crm/')
    expect(result.modulePaths.social).toBe('/social')
    expect(result.modulePaths.analytics).toBe('/analytics/')
    expect(result.moduleApiPaths.orgs).toBe('/orgs/api/')
    expect(result.moduleApiPaths.billing).toBe('/billing/api/')
  })

  it('accepts a production-shaped embeds public injector config', () => {
    window.__QUICKSCALE__ = buildPublicInjectorEmbeds()
    const result = validateQuickScaleConfig()
    expect(result.projectName).toBe('Public Social Demo')
    expect(result.publicPage).toMatchObject({
      module: 'social',
      surface: 'embeds',
      endpoint: '/_quickscale/social/embeds/',
    })
    expect(result.owner.mode).toBe('solo')
    expect(result.owner.currentOrgSlug).toBeNull()
    expect(result.modulePaths.social).toBe('/social/embeds')
  })

  it('accepts a production-shaped saas-mode config', () => {
    const config = buildValidConfig()
    config.owner = { mode: 'saas', currentOrgSlug: 'acme-corp' }
    config.modulePaths = modulePaths({
      crm: '/orgs/acme-corp/crm/',
      social: '/social',
      analytics: '/analytics/',
    })
    window.__QUICKSCALE__ = config
    const result = validateQuickScaleConfig()
    expect(result.owner.mode).toBe('saas')
    expect(result.owner.currentOrgSlug).toBe('acme-corp')
  })

  // ── Properties public page validation (SA153 (e1)) ─────────────

  /**
   * Build a config matching the prerendered project document's injector: the
   * properties publicPage carries the route and the react-query state the
   * server rendered the document with.
   */
  function buildPropertyPublicPage(
    surface: 'catalog' | 'detail',
    overrides: Record<string, unknown> = {},
  ): QuickScaleConfig {
    return {
      ...buildValidConfig(),
      publicPage: {
        module: 'properties',
        surface,
        path: surface === 'catalog' ? '/properties' : '/properties/malvarrosa-villa-001',
        dehydratedState: { mutations: [], queries: [] },
        ...overrides,
      },
    } as unknown as QuickScaleConfig
  }

  it('accepts a properties catalog public page', () => {
    window.__QUICKSCALE__ = buildPropertyPublicPage('catalog')
    const result = validateQuickScaleConfig()
    expect(result.publicPage?.module).toBe('properties')
    expect(result.publicPage?.surface).toBe('catalog')
  })

  it('accepts a properties detail public page', () => {
    window.__QUICKSCALE__ = buildPropertyPublicPage('detail')
    const result = validateQuickScaleConfig()
    expect(result.publicPage?.surface).toBe('detail')
  })

  it('throws when a properties public page surface is unsupported', () => {
    window.__QUICKSCALE__ = buildPropertyPublicPage('catalog', { surface: 'gallery' })
    expect(() => validateQuickScaleConfig()).toThrow(/publicPage\.surface/)
  })

  it('throws when a properties public page path is missing', () => {
    const config = buildPropertyPublicPage('catalog')
    delete (config.publicPage as unknown as Record<string, unknown>).path
    window.__QUICKSCALE__ = config
    expect(() => validateQuickScaleConfig()).toThrow(/publicPage\.path/)
  })

  it('throws when a properties public page path is empty', () => {
    window.__QUICKSCALE__ = buildPropertyPublicPage('detail', { path: '  ' })
    expect(() => validateQuickScaleConfig()).toThrow(/publicPage\.path/)
  })

  it('throws when a properties public page has no dehydrated state', () => {
    const config = buildPropertyPublicPage('catalog')
    delete (config.publicPage as unknown as Record<string, unknown>).dehydratedState
    window.__QUICKSCALE__ = config
    expect(() => validateQuickScaleConfig()).toThrow(/publicPage\.dehydratedState/)
  })

  it('throws when a properties dehydrated state lacks its queries array', () => {
    window.__QUICKSCALE__ = buildPropertyPublicPage('catalog', {
      dehydratedState: { mutations: [] },
    })
    expect(() => validateQuickScaleConfig()).toThrow(/publicPage\.dehydratedState/)
  })

  it('throws when a properties dehydrated state is an array', () => {
    window.__QUICKSCALE__ = buildPropertyPublicPage('catalog', {
      dehydratedState: [],
    })
    expect(() => validateQuickScaleConfig()).toThrow(/publicPage\.dehydratedState/)
  })
})
