import posthog from 'posthog-js'

const POSTHOG_DEFAULT_HOST = 'https://us.i.posthog.com'
const POSTHOG_KEY_PLACEHOLDERS = new Set(['your-posthog-key', 'your_posthog_key'])

let analyticsInitialized = false

interface AnalyticsImportMetaEnv {
  VITE_POSTHOG_KEY?: string
  VITE_POSTHOG_HOST?: string
}

interface SocialLinkClickEvent {
  provider: string
  linkId: number | string
  surface: 'link_tree' | 'embeds'
  targetUrl: string
}

const env = (import.meta as ImportMeta & { env?: AnalyticsImportMetaEnv }).env ?? {}

function resolvePosthogApiKey(): string | null {
  const candidate = env.VITE_POSTHOG_KEY?.trim() ?? ''
  if (!candidate) {
    return null
  }

  return POSTHOG_KEY_PLACEHOLDERS.has(candidate.toLowerCase()) ? null : candidate
}

function resolvePosthogHost(): string {
  return env.VITE_POSTHOG_HOST?.trim() || POSTHOG_DEFAULT_HOST
}

export function initializeAnalytics(): void {
  if (analyticsInitialized) {
    return
  }

  const apiKey = resolvePosthogApiKey()
  if (!apiKey) {
    return
  }

  posthog.init(apiKey, {
    api_host: resolvePosthogHost(),
    capture_pageview: 'history_change',
    person_profiles: 'identified_only',
  })
  analyticsInitialized = true
}

export function trackSocialLinkClick(event: SocialLinkClickEvent): void {
  if (!analyticsInitialized) {
    return
  }

  posthog.capture('social_link_click', {
    module: 'social',
    provider: event.provider.trim().toLowerCase(),
    link_id: String(event.linkId),
    surface: event.surface,
    target_url: event.targetUrl,
  })
}
