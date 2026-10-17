import { lazy, Suspense } from 'react'
import { BrowserRouter, StaticRouter } from 'react-router-dom'
import App from './App'
import type { PublicSocialSurface } from '@/hooks/useModules'
import { validateQuickScaleConfig } from '@/lib/validateQuickScaleSeam'

const SocialEmbedsPublicPage = lazy(() => import('@/pages/SocialEmbedsPublicPage').then((m) => ({ default: m.SocialEmbedsPublicPage })))
const SocialLinkTreePublicPage = lazy(() => import('@/pages/SocialLinkTreePublicPage').then((m) => ({ default: m.SocialLinkTreePublicPage })))

export interface QuickScaleRootRenderOptions {
  /**
   * Render the app tree at this location with `StaticRouter` instead of the
   * browser router — the SSR entry's boot for a prerendered document. The
   * client keeps `BrowserRouter`, so hydration reads the same location it
   * was rendered for.
   */
  staticLocation?: string
}

export function renderQuickScaleRoot(
  surface?: PublicSocialSurface,
  options: QuickScaleRootRenderOptions = {},
) {
  const config = validateQuickScaleConfig()
  const socialEnabled = config.modules.social

  if (surface && socialEnabled) {
    const Page = surface === 'link_tree' ? SocialLinkTreePublicPage : SocialEmbedsPublicPage
    return (
      <Suspense fallback={<div>Loading…</div>}>
        <Page />
      </Suspense>
    )
  }

  if (options.staticLocation !== undefined) {
    return (
      <StaticRouter location={options.staticLocation}>
        <App />
      </StaticRouter>
    )
  }

  return (
    <BrowserRouter>
      <App />
    </BrowserRouter>
  )
}
