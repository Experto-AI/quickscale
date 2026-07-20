import type { QuickScaleConfig } from '@/hooks/useModules'

/**
 * Validate the window.__QUICKSCALE__ runtime seam and return the parsed config.
 *
 * Fails hard (throws Error) when the seam is missing or malformed, so every
 * load-bearing read goes through a single diagnostic boundary instead of
 * silently defaulting or producing a blank/disabled UI.
 *
 * Required fields validated:
 *   - window.__QUICKSCALE__ must exist
 *   - projectName must be a non-empty string
 *   - modules must be an object whose 11 required keys are own boolean properties
 *   - modulePaths must be an object with crm, social, analytics as non-empty strings
 *   - owner must be an object with mode ('solo'|'saas') and currentOrgSlug (string|null)
 *
 * Optional fields validated when present:
 *   - publicPage must be a well-formed object with required children;
 *     module must be 'social', surface must be 'link_tree'|'embeds',
 *     endpoint and navigation fields must be non-empty strings
 */
export function validateQuickScaleConfig(): QuickScaleConfig {
  const seam = window.__QUICKSCALE__

  if (!seam) {
    throw new Error(
      'QuickScale runtime configuration (window.__QUICKSCALE__) is missing. ' +
      'Ensure the Django template injects the config before loading the React bundle.',
    )
  }

  if (typeof seam.projectName !== 'string' || seam.projectName.trim() === '') {
    throw new Error(
      'QuickScale runtime configuration is malformed: window.__QUICKSCALE__.projectName ' +
      'must be a non-empty string.',
    )
  }

  if (!seam.modules || typeof seam.modules !== 'object' || Array.isArray(seam.modules)) {
    throw new Error(
      'QuickScale runtime configuration is malformed: window.__QUICKSCALE__.modules ' +
      'must be an object with boolean values.',
    )
  }

  // ── All required module keys must be own boolean properties ──────
  const REQUIRED_MODULE_KEYS = [
    'auth', 'blog', 'listings', 'crm', 'forms', 'storage',
    'backups', 'notifications', 'analytics', 'billing', 'social',
  ] as const

  const mods = seam.modules as unknown as Record<string, unknown>

  for (const key of REQUIRED_MODULE_KEYS) {
    if (!Object.prototype.hasOwnProperty.call(mods, key)) {
      throw new Error(
        `QuickScale runtime configuration is malformed: window.__QUICKSCALE__.modules.${key} ` +
        `is missing or inherited — all required module flags must be own boolean properties.`,
      )
    }
    if (typeof mods[key] !== 'boolean') {
      throw new Error(
        `QuickScale runtime configuration is malformed: window.__QUICKSCALE__.modules.${key} ` +
        `must be a boolean, got ${typeof mods[key]}.`,
      )
    }
  }

  // ── modulePaths (required) ──────────────────────────────────────
  if (!seam.modulePaths || typeof seam.modulePaths !== 'object' || Array.isArray(seam.modulePaths)) {
    throw new Error(
      'QuickScale runtime configuration is malformed: window.__QUICKSCALE__.modulePaths ' +
      'must be an object with string values.',
    )
  }

  const requiredModulePathFields = ['crm', 'social', 'analytics'] as const
  for (const field of requiredModulePathFields) {
    const value = (seam.modulePaths as unknown as Record<string, unknown>)[field]
    if (typeof value !== 'string' || (value as string).trim() === '') {
      throw new Error(
        `QuickScale runtime configuration is malformed: window.__QUICKSCALE__.modulePaths.${field} ` +
        `must be a non-empty string.`,
      )
    }
  }

  // ── owner (required) ────────────────────────────────────────────
  if (!seam.owner || typeof seam.owner !== 'object' || Array.isArray(seam.owner)) {
    throw new Error(
      'QuickScale runtime configuration is malformed: window.__QUICKSCALE__.owner ' +
      'must be an object with mode and currentOrgSlug.',
    )
  }

  const owner = seam.owner as unknown as Record<string, unknown>

  if (owner.mode !== 'solo' && owner.mode !== 'saas') {
    throw new Error(
      'QuickScale runtime configuration is malformed: window.__QUICKSCALE__.owner.mode ' +
      'must be "solo" or "saas".',
    )
  }

  if (owner.currentOrgSlug !== null && typeof owner.currentOrgSlug !== 'string') {
    throw new Error(
      'QuickScale runtime configuration is malformed: window.__QUICKSCALE__.owner.currentOrgSlug ' +
      'must be a string or null.',
    )
  }

  // ── publicPage (optional, strictly validated when present) ──────
  if (seam.publicPage !== undefined) {
    if (!seam.publicPage || typeof seam.publicPage !== 'object' || Array.isArray(seam.publicPage)) {
      throw new Error(
        'QuickScale runtime configuration is malformed: window.__QUICKSCALE__.publicPage ' +
        'must be an object when present.',
      )
    }

    const pp = seam.publicPage as unknown as Record<string, unknown>
    const requiredPublicFields = ['module', 'surface', 'endpoint', 'navigation'] as const

    for (const field of requiredPublicFields) {
      if (pp[field] == null || (typeof pp[field] === 'string' && (pp[field] as string).trim() === '')) {
        throw new Error(
          `QuickScale runtime configuration is malformed: window.__QUICKSCALE__.publicPage.${field} ` +
          `is required when publicPage is present.`,
        )
      }
    }

    // publicPage.module must be exactly 'social'
    if (pp.module !== 'social') {
      throw new Error(
        'QuickScale runtime configuration is malformed: window.__QUICKSCALE__.publicPage.module ' +
        'must be "social".',
      )
    }

    // publicPage.surface must be exactly 'link_tree' or 'embeds'
    if (pp.surface !== 'link_tree' && pp.surface !== 'embeds') {
      throw new Error(
        'QuickScale runtime configuration is malformed: window.__QUICKSCALE__.publicPage.surface ' +
        'must be "link_tree" or "embeds".',
      )
    }

    // publicPage.endpoint must be a non-empty string (not array/object)
    if (typeof pp.endpoint !== 'string' || (pp.endpoint as string).trim() === '') {
      throw new Error(
        'QuickScale runtime configuration is malformed: window.__QUICKSCALE__.publicPage.endpoint ' +
        'must be a non-empty string.',
      )
    }

    if (!pp.navigation || typeof pp.navigation !== 'object' || Array.isArray(pp.navigation)) {
      throw new Error(
        'QuickScale runtime configuration is malformed: window.__QUICKSCALE__.publicPage.navigation ' +
        'must be an object when publicPage is present.',
      )
    }

    const nav = pp.navigation as Record<string, unknown>
    const requiredNavFields = ['home', 'linkTree', 'embeds'] as const

    for (const field of requiredNavFields) {
      if (typeof nav[field] !== 'string' || (nav[field] as string).trim() === '') {
        throw new Error(
          `QuickScale runtime configuration is malformed: window.__QUICKSCALE__.publicPage.navigation.${field} ` +
          `must be a non-empty string when publicPage is present.`,
        )
      }
    }
  }

  return seam as QuickScaleConfig
}
