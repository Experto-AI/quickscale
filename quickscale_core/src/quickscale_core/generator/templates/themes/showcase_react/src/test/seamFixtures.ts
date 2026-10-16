/**
 * Seam fixture builders for the theme's tests.
 *
 * Every seam key set a fixture carries derives from the generated key
 * manifest (`quickscaleSeam.keys.ts`), so a module that joins the shipped set
 * extends these fixtures without an edit here.
 */
import type {
  QuickScaleModuleApiPaths,
  QuickScaleModuleDocumentPaths,
  QuickScaleModulePaths,
  QuickScaleModules,
} from '@/quickscaleSeam'
import {
  SEAM_MODULE_API_PATH_KEYS,
  SEAM_MODULE_DOCUMENT_PATH_KEYS,
  SEAM_MODULE_FLAG_KEYS,
  SEAM_MODULE_PATH_KEYS,
} from '@/quickscaleSeam.keys'

const ALL_MODULE_FLAGS = Object.fromEntries(
  SEAM_MODULE_FLAG_KEYS.map((key) => [key, false] as const),
) as unknown as QuickScaleModules

const ALL_MODULE_PATHS = Object.fromEntries(
  SEAM_MODULE_PATH_KEYS.map((key) => [key, `/${key}`] as const),
) as unknown as QuickScaleModulePaths

const ALL_MODULE_API_PATHS = Object.fromEntries(
  SEAM_MODULE_API_PATH_KEYS.map((key) => [key, `/${key}/api/`] as const),
) as unknown as QuickScaleModuleApiPaths

//: The shipped documents' default paths, so a test reads a real destination;
//: a key a future module adds falls back to the generic `/<key>/` shape.
const DOCUMENT_PATH_DEFAULTS: Partial<Record<string, string>> = {
  blogIndex: '/blog/',
  blogFeed: '/blog/feed/',
  listingsIndex: '/listings/',
  crmDashboard: '/crm/dashboard/',
}

const ALL_MODULE_DOCUMENT_PATHS = Object.fromEntries(
  SEAM_MODULE_DOCUMENT_PATH_KEYS.map(
    (key) => [key, DOCUMENT_PATH_DEFAULTS[key] ?? `/${key}/`] as const,
  ),
) as unknown as QuickScaleModuleDocumentPaths

export function moduleFlags(
  overrides: Partial<QuickScaleModules> = {},
): QuickScaleModules {
  return { ...ALL_MODULE_FLAGS, ...overrides }
}

export function moduleFlagsOn(
  overrides: Partial<QuickScaleModules> = {},
): QuickScaleModules {
  const allOn = Object.fromEntries(
    SEAM_MODULE_FLAG_KEYS.map((key) => [key, true] as const),
  ) as unknown as QuickScaleModules

  return { ...allOn, ...overrides }
}

export function modulePaths(
  overrides: Partial<QuickScaleModulePaths> = {},
): QuickScaleModulePaths {
  return { ...ALL_MODULE_PATHS, ...overrides }
}

export function moduleApiPaths(
  overrides: Partial<QuickScaleModuleApiPaths> = {},
): QuickScaleModuleApiPaths {
  return { ...ALL_MODULE_API_PATHS, ...overrides }
}

export function moduleDocumentPaths(
  overrides: Partial<QuickScaleModuleDocumentPaths> = {},
): QuickScaleModuleDocumentPaths {
  return { ...ALL_MODULE_DOCUMENT_PATHS, ...overrides }
}
