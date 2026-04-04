declare module 'posthog-js' {
  interface PostHogConfig {
    api_host?: string
    capture_pageview?: boolean | 'history_change'
    person_profiles?: 'always' | 'identified_only' | 'never'
  }

  interface PostHogClient {
    init(apiKey: string, config?: PostHogConfig): void
    capture(event: string, properties?: Record<string, unknown>): void
  }

  const posthog: PostHogClient
  export default posthog
}
