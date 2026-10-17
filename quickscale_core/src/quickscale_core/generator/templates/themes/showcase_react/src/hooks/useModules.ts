import type { DehydratedState } from '@tanstack/react-query'

import type {
  QuickScaleModuleApiPaths,
  QuickScaleModuleDocumentPaths,
  QuickScaleModulePaths,
  QuickScaleModules,
} from '@/quickscaleSeam'

export type QuickScaleOwnerMode = 'solo' | 'saas'

interface QuickScaleOwnerConfig {
  mode: QuickScaleOwnerMode
  currentOrgSlug: string | null
}

export type PublicSocialSurface = 'link_tree' | 'embeds'

//: Surfaces of the project-owned property portal's public pages: the catalog
//: document and one listing's detail document.
export type PublicPropertySurface = 'catalog' | 'detail'

interface QuickScalePublicPageNavigation {
  home: string
  linkTree: string
  embeds: string
}

interface QuickScalePublicSocialPageConfig {
  module: 'social'
  surface: PublicSocialSurface
  endpoint: string
  navigation: QuickScalePublicPageNavigation
}

/**
 * A prerendered project-owned public page: the route the document was
 * rendered for, plus the react-query cache state that produced its markup.
 * The boot hydrates the cache with that state and the document with
 * `hydrateRoot`, so the served HTML and the first client render agree
 * instead of the page mounting a fresh, client-side loading state.
 */
interface QuickScalePublicPropertyPageConfig {
  module: 'properties'
  surface: PublicPropertySurface
  path: string
  dehydratedState: DehydratedState
}

export type QuickScalePublicPageConfig =
  | QuickScalePublicSocialPageConfig
  | QuickScalePublicPropertyPageConfig

export interface QuickScaleConfig {
  projectName: string
  modules: QuickScaleModules
  modulePaths: QuickScaleModulePaths
  moduleApiPaths: QuickScaleModuleApiPaths
  moduleDocumentPaths: QuickScaleModuleDocumentPaths
  owner: QuickScaleOwnerConfig
  publicPage?: QuickScalePublicPageConfig
}

import { validateQuickScaleConfig } from '@/lib/validateQuickScaleSeam'

declare global {
  interface Window {
    __QUICKSCALE__?: QuickScaleConfig
  }
}

function resolveProjectConfig(): QuickScaleConfig {
  // The producer resolves the owner's org slug server-side and renders it into
  // the seam, so the theme reads the validated seam value instead of inferring
  // a slug from a module path (SA276).
  const config = validateQuickScaleConfig()

  return { ...config, owner: { ...config.owner } }
}

export function useModules(): QuickScaleModules {
  return resolveProjectConfig().modules
}

export function useProjectConfig(): QuickScaleConfig {
  return resolveProjectConfig()
}

export function useOwnerMode(): QuickScaleOwnerMode {
  return resolveProjectConfig().owner.mode
}

export function useCurrentOrgSlug(): string | null {
  return resolveProjectConfig().owner.currentOrgSlug
}

export function buildOrgPath(orgSlug: string, path = ''): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `/orgs/${orgSlug}${path ? normalizedPath : ''}`
}
