import { lazy, Suspense } from 'react'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import type { PublicSocialSurface } from '@/hooks/useModules'
import { validateQuickScaleConfig } from '@/lib/validateQuickScaleSeam'

const SocialEmbedsPublicPage = lazy(() => import('@/pages/SocialEmbedsPublicPage').then((m) => ({ default: m.SocialEmbedsPublicPage })))
const SocialLinkTreePublicPage = lazy(() => import('@/pages/SocialLinkTreePublicPage').then((m) => ({ default: m.SocialLinkTreePublicPage })))

export function renderQuickScaleRoot(surface?: PublicSocialSurface) {
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

  return (
    <BrowserRouter>
      <App />
    </BrowserRouter>
  )
}
