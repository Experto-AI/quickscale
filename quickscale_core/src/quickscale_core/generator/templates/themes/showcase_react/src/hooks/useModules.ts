interface QuickScaleModules {
  auth: boolean
  blog: boolean
  listings: boolean
  crm: boolean
  forms: boolean
  storage: boolean
  backups: boolean
  notifications: boolean
  analytics: boolean
  billing: boolean
  social: boolean
}

interface QuickScaleModulePaths {
  crm: string
  social: string
  analytics: string
}

export type QuickScaleOwnerMode = 'solo' | 'saas'

interface QuickScaleOwnerConfig {
  mode: QuickScaleOwnerMode
  currentOrgSlug: string | null
}

export type PublicSocialSurface = 'link_tree' | 'embeds'

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
  owner: QuickScaleOwnerConfig
  publicPage?: QuickScalePublicPageConfig
}

import { validateQuickScaleConfig } from '@/lib/validateQuickScaleSeam'

declare global {
  interface Window {
    __QUICKSCALE__?: QuickScaleConfig
  }
}

function inferCurrentOrgSlug(config: QuickScaleConfig): string | null {
  if (config.owner.currentOrgSlug) {
    return config.owner.currentOrgSlug
  }

  const crmPath = (config.modulePaths as { crm?: string }).crm
  if (crmPath) {
    const match = crmPath.match(/^\/orgs\/([^/]+)\/crm(\/|$)/)
    if (match) {
      return decodeURIComponent(match[1])
    }
  }

  return null
}

function resolveProjectConfig(): QuickScaleConfig {
  const config = validateQuickScaleConfig()

  return {
    ...config,
    owner: {
      ...config.owner,
      currentOrgSlug: inferCurrentOrgSlug(config),
    },
  }
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
