import { lazy, StrictMode, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App'
import { initializeAnalytics } from '@/lib/analytics'
import type { PublicSocialSurface } from '@/hooks/useModules'

const SocialEmbedsPublicPage = lazy(() => import('@/pages/SocialEmbedsPublicPage').then((m) => ({ default: m.SocialEmbedsPublicPage })))
const SocialLinkTreePublicPage = lazy(() => import('@/pages/SocialLinkTreePublicPage').then((m) => ({ default: m.SocialLinkTreePublicPage })))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
})

function renderQuickScaleRoot(surface?: PublicSocialSurface) {
  const config = window.__QUICKSCALE__
  const socialEnabled = config?.modules?.social ?? false

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

const rootElement = document.getElementById('root')

if (rootElement == null) {
  throw new Error('QuickScale could not find the React root element')
}

initializeAnalytics()

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {renderQuickScaleRoot(window.__QUICKSCALE__?.publicPage?.surface)}
    </QueryClientProvider>
  </StrictMode>,
)
