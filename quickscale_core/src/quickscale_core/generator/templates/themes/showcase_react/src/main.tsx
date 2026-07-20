import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
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

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {renderQuickScaleRoot(quickScaleConfig.publicPage?.surface)}
    </QueryClientProvider>
  </StrictMode>,
)
