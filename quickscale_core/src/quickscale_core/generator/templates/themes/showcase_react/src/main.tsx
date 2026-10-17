import { StrictMode } from 'react'
import { createRoot, hydrateRoot } from 'react-dom/client'
import { hydrate, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import { initializeAnalytics } from '@/lib/analytics'
import { validateQuickScaleConfig } from '@/lib/validateQuickScaleSeam'
import { renderQuickScaleRoot } from './renderQuickScaleRoot'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: 1,
    },
  },
})

const rootElement = document.getElementById('root')

if (rootElement == null) {
  throw new Error('QuickScale could not find the React root element')
}

initializeAnalytics()

// Validate the runtime seam at boot before any rendering.
// This ensures a missing/malformed window.__QUICKSCALE__ produces a clear
// diagnostic (throw) rather than silently rendering a blank or disabled UI.
const quickScaleConfig = validateQuickScaleConfig()
const publicPage = quickScaleConfig.publicPage

// A prerendered document arrives with the react-query state its markup was
// rendered from; seeding the cache before the first render keeps hydration
// aligned with the served HTML, and hydrateRoot adopts that markup instead of
// replacing it with a fresh client tree.
if (publicPage?.module === 'properties') {
  hydrate(queryClient, publicPage.dehydratedState)
}

const tree = (
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {renderQuickScaleRoot(publicPage?.module === 'social' ? publicPage.surface : undefined)}
    </QueryClientProvider>
  </StrictMode>
)

if (publicPage?.module === 'properties') {
  hydrateRoot(rootElement, tree)
} else {
  createRoot(rootElement).render(tree)
}
