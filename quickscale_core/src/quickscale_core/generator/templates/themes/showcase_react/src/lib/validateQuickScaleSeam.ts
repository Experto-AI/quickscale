import type { QuickScaleConfig } from '@/hooks/useModules'
import {
  SEAM_MODULE_API_PATH_KEYS,
  SEAM_MODULE_DOCUMENT_PATH_KEYS,
  SEAM_MODULE_FLAG_KEYS,
  SEAM_MODULE_PATH_KEYS,
} from '@/quickscaleSeam.keys'

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
 *   - modules must carry an own boolean flag for every module key
 *   - modulePaths must carry a non-empty string for every module path key
 *   - moduleApiPaths must carry a non-empty string for every API-base key
 *   - moduleDocumentPaths must carry a non-empty string for every document-path key
 *   - owner must be an object with mode ('solo'|'saas') and currentOrgSlug (string|null)
 *
 * The key sets are the generated seam key manifest's
 * (`frontend/src/quickscaleSeam.keys.ts`), rendered from the shipped module
 * set beside the generated declaration (`frontend/src/quickscaleSeam.d.ts`),
 * so this validator requires every entry without holding a module list of its
 * own (SA276).
 *
 * Optional fields validated when present:
 *   - publicPage must be a well-formed object whose module selects its shape:
 *     a social page requires module 'social', surface 'link_tree'|'embeds',
 *     and non-empty endpoint and navigation fields; a prerendered project
 *     public page requires module 'properties', surface 'catalog'|'detail',
 *     a non-empty path, and a dehydratedState carrying the react-query
 *     mutations and queries arrays the cache hydration reads.
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

  // ── All required module flags must be own boolean properties ────
  const mods = seam.modules as unknown as Record<string, unknown>

  for (const key of SEAM_MODULE_FLAG_KEYS) {
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

  for (const field of SEAM_MODULE_PATH_KEYS) {
    const value = (seam.modulePaths as unknown as Record<string, unknown>)[field]
    if (typeof value !== 'string' || value.trim() === '') {
      throw new Error(
        `QuickScale runtime configuration is malformed: window.__QUICKSCALE__.modulePaths.${field} ` +
        `must be a non-empty string.`,
      )
    }
  }

  // ── moduleApiPaths (required) ───────────────────────────────────
  if (
    !seam.moduleApiPaths ||
    typeof seam.moduleApiPaths !== 'object' ||
    Array.isArray(seam.moduleApiPaths)
  ) {
    throw new Error(
      'QuickScale runtime configuration is malformed: window.__QUICKSCALE__.moduleApiPaths ' +
      'must be an object with string values.',
    )
  }

  for (const field of SEAM_MODULE_API_PATH_KEYS) {
    const value = (seam.moduleApiPaths as unknown as Record<string, unknown>)[field]
    if (typeof value !== 'string' || value.trim() === '') {
      throw new Error(
        `QuickScale runtime configuration is malformed: window.__QUICKSCALE__.moduleApiPaths.${field} ` +
        `must be a non-empty string.`,
      )
    }
  }

  // ── moduleDocumentPaths (required) ──────────────────────────────
  if (
    !seam.moduleDocumentPaths ||
    typeof seam.moduleDocumentPaths !== 'object' ||
    Array.isArray(seam.moduleDocumentPaths)
  ) {
    throw new Error(
      'QuickScale runtime configuration is malformed: window.__QUICKSCALE__.moduleDocumentPaths ' +
      'must be an object with string values.',
    )
  }

  for (const field of SEAM_MODULE_DOCUMENT_PATH_KEYS) {
    const value = (seam.moduleDocumentPaths as unknown as Record<string, unknown>)[field]
    if (typeof value !== 'string' || value.trim() === '') {
      throw new Error(
        `QuickScale runtime configuration is malformed: window.__QUICKSCALE__.moduleDocumentPaths.${field} ` +
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

    if (pp.module === 'social') {
      const requiredPublicFields = ['module', 'surface', 'endpoint', 'navigation'] as const

      for (const field of requiredPublicFields) {
        if (pp[field] == null || (typeof pp[field] === 'string' && (pp[field] as string).trim() === '')) {
          throw new Error(
            `QuickScale runtime configuration is malformed: window.__QUICKSCALE__.publicPage.${field} ` +
            `is required when publicPage is present.`,
          )
        }
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
    } else if (pp.module === 'properties') {
      // publicPage.surface must be exactly 'catalog' or 'detail'
      if (pp.surface !== 'catalog' && pp.surface !== 'detail') {
        throw new Error(
          'QuickScale runtime configuration is malformed: window.__QUICKSCALE__.publicPage.surface ' +
          'must be "catalog" or "detail" for a properties public page.',
        )
      }

      // publicPage.path must be the document's own non-empty route
      if (typeof pp.path !== 'string' || (pp.path as string).trim() === '') {
        throw new Error(
          'QuickScale runtime configuration is malformed: window.__QUICKSCALE__.publicPage.path ' +
          'must be a non-empty string for a properties public page.',
        )
      }

      // publicPage.dehydratedState carries the react-query state the document
      // was rendered with: an object with the mutations and queries arrays the
      // cache hydration reads.
      if (
        !pp.dehydratedState ||
        typeof pp.dehydratedState !== 'object' ||
        Array.isArray(pp.dehydratedState)
      ) {
        throw new Error(
          'QuickScale runtime configuration is malformed: window.__QUICKSCALE__.publicPage.dehydratedState ' +
          'must be an object with mutations and queries arrays.',
        )
      }

      const dehydrated = pp.dehydratedState as Record<string, unknown>
      if (!Array.isArray(dehydrated.queries) || !Array.isArray(dehydrated.mutations)) {
        throw new Error(
          'QuickScale runtime configuration is malformed: window.__QUICKSCALE__.publicPage.dehydratedState ' +
          'must be an object with mutations and queries arrays.',
        )
      }
    } else {
      throw new Error(
        'QuickScale runtime configuration is malformed: window.__QUICKSCALE__.publicPage.module ' +
        'must be "social" or "properties".',
      )
    }
  }

  return seam as QuickScaleConfig
}
