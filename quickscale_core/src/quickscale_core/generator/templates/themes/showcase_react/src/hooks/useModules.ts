import type {
  QuickScaleModuleApiPaths,
  QuickScaleModuleDocumentPaths,
  QuickScaleModulePaths,
  QuickScaleModules,
} from '@/quickscaleSeam'
import type { PublicSocialSurface } from '@/quickscaleSeam.hooks'

export type QuickScaleOwnerMode = 'solo' | 'saas'

interface QuickScaleOwnerConfig {
  mode: QuickScaleOwnerMode
  currentOrgSlug: string | null
}

// The social surface union lives in the managed hook file; re-export it for
// the root dispatcher and shell that import this module.
export type { PublicSocialSurface }

interface QuickScalePublicPageNavigation {
  home: string
  linkTree: string
  embeds: string
}

interface QuickScalePublicPageConfig {
  module: 'social'
  surface: PublicSocialSurface
  endpoint: string
  navigation: QuickScalePublicPageNavigation
}

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
