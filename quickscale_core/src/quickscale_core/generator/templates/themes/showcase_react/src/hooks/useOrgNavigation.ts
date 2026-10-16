import { useMemo } from 'react'
import { useParams } from 'react-router-dom'
import { buildOrgPath, useCurrentOrgSlug, useOwnerMode, useProjectConfig } from '@/hooks/useModules'

function stripTrailingSlash(path: string): string {
  if (path !== '/' && path.endsWith('/')) {
    return path.slice(0, -1)
  }

  return path
}

function joinPath(basePath: string, path = ''): string {
  if (!path) {
    return stripTrailingSlash(basePath)
  }

  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${stripTrailingSlash(basePath)}${normalizedPath}`
}

export function useOrgNavigation() {
  const { orgSlug: routeOrgSlug } = useParams<{ orgSlug: string }>()
  const ownerMode = useOwnerMode()
  const fallbackOrgSlug = useCurrentOrgSlug()
  const { moduleApiPaths, moduleDocumentPaths, modulePaths } = useProjectConfig()
  const currentOrgSlug = routeOrgSlug ?? fallbackOrgSlug
  const isSaas = ownerMode === 'saas'

  return useMemo(() => {
    const hasOrgContext = Boolean(isSaas && currentOrgSlug)
    const orgBasePath = hasOrgContext && currentOrgSlug ? buildOrgPath(currentOrgSlug) : null

    return {
      isSaas,
      hasOrgContext,
      currentOrgSlug: orgBasePath ? currentOrgSlug : null,
      appPaths: {
        // Module page paths come from the seam (rule 31): the org-scoped
        // workspace mounts each module page under /orgs/<slug>/ with the
        // module's own path, never a path written here.
        orgList: '/orgs',
        orgCreate: '/orgs/new',
        dashboard: orgBasePath ?? (isSaas ? '/orgs' : '/'),
        blog: orgBasePath ? joinPath(orgBasePath, modulePaths.blog) : modulePaths.blog,
        listings: orgBasePath
          ? joinPath(orgBasePath, modulePaths.listings)
          : modulePaths.listings,
        crm: modulePaths.crm,
        forms: '/forms/contact',
        members: orgBasePath ? joinPath(orgBasePath, 'members') : '/orgs',
        settings: orgBasePath ? joinPath(orgBasePath, 'settings') : '/settings',
        profile: '/profile',
      },
      documentPaths: {
        // A module's server-rendered document keeps its own URL in every
        // mode (rule 31): the seam resolves each from the document's named
        // route, so a launcher link never points back at the SPA.
        blogIndex: moduleDocumentPaths.blogIndex,
        blogFeed: moduleDocumentPaths.blogFeed,
        listingsIndex: moduleDocumentPaths.listingsIndex,
        crmDashboard: moduleDocumentPaths.crmDashboard,
        crmApiBase: moduleApiPaths.crm,
        formsApiBase: moduleApiPaths.forms,
      },
    }
  }, [
    currentOrgSlug,
    isSaas,
    moduleApiPaths.crm,
    moduleApiPaths.forms,
    moduleDocumentPaths.blogFeed,
    moduleDocumentPaths.blogIndex,
    moduleDocumentPaths.crmDashboard,
    moduleDocumentPaths.listingsIndex,
    modulePaths.blog,
    modulePaths.crm,
    modulePaths.listings,
  ])
}
