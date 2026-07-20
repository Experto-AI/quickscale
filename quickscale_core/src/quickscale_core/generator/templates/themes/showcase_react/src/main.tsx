import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import { initializeAnalytics } from '@/lib/analytics'
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

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {renderQuickScaleRoot(window.__QUICKSCALE__?.publicPage?.surface)}
    </QueryClientProvider>
  </StrictMode>,
)
