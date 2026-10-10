import { afterEach, describe, expect, it, vi } from 'vitest'

const posthogMock = { init: vi.fn(), capture: vi.fn() }

vi.mock('posthog-js', () => ({ default: posthogMock }))

// The stub must be in place before the module's dynamic import because the
// starter reads its PostHog configuration once, at module load. Every test
// establishes both keys explicitly so an ambient VITE_POSTHOG_KEY or
// VITE_POSTHOG_HOST in the developer's environment cannot change the outcome.
async function loadAnalytics() {
  return await import('@/lib/analytics')
}

afterEach(() => {
  vi.unstubAllEnvs()
  vi.resetModules()
  posthogMock.init.mockReset()
  posthogMock.capture.mockReset()
})

describe('analytics starter wiring', () => {
  it('stays dormant without a configured key', async () => {
    vi.stubEnv('VITE_POSTHOG_KEY', undefined)
    vi.stubEnv('VITE_POSTHOG_HOST', undefined)
    const { initializeAnalytics, trackSocialLinkClick } = await loadAnalytics()

    initializeAnalytics()
    trackSocialLinkClick({
      provider: ' YouTube ',
      linkId: 7,
      surface: 'link_tree',
      targetUrl: 'https://example.com/',
    })

    expect(posthogMock.init).not.toHaveBeenCalled()
    expect(posthogMock.capture).not.toHaveBeenCalled()
  })

  it('treats placeholder keys and blank keys as unconfigured', async () => {
    vi.stubEnv('VITE_POSTHOG_KEY', 'your-posthog-key')
    const placeholder = await loadAnalytics()
    placeholder.initializeAnalytics()
    expect(posthogMock.init).not.toHaveBeenCalled()

    vi.resetModules()
    vi.stubEnv('VITE_POSTHOG_KEY', '   ')
    const blank = await loadAnalytics()
    blank.initializeAnalytics()
    expect(posthogMock.init).not.toHaveBeenCalled()
  })

  it('initializes once with the default host and captures normalized link clicks', async () => {
    vi.stubEnv('VITE_POSTHOG_KEY', 'phc_real_key')
    vi.stubEnv('VITE_POSTHOG_HOST', undefined)
    const { initializeAnalytics, trackSocialLinkClick } = await loadAnalytics()

    initializeAnalytics()
    initializeAnalytics()

    expect(posthogMock.init).toHaveBeenCalledTimes(1)
    expect(posthogMock.init).toHaveBeenCalledWith('phc_real_key', {
      api_host: 'https://us.i.posthog.com',
      capture_pageview: 'history_change',
      person_profiles: 'identified_only',
    })

    trackSocialLinkClick({
      provider: ' YouTube ',
      linkId: 42,
      surface: 'embeds',
      targetUrl: 'https://example.com/shared',
    })

    expect(posthogMock.capture).toHaveBeenCalledWith('social_link_click', {
      module: 'social',
      provider: 'youtube',
      link_id: '42',
      surface: 'embeds',
      target_url: 'https://example.com/shared',
    })
  })

  it('honors an explicit PostHog host', async () => {
    vi.stubEnv('VITE_POSTHOG_KEY', 'phc_other_key')
    vi.stubEnv('VITE_POSTHOG_HOST', ' https://eu.i.posthog.com ')
    const { initializeAnalytics } = await loadAnalytics()

    initializeAnalytics()

    expect(posthogMock.init).toHaveBeenCalledWith(
      'phc_other_key',
      expect.objectContaining({ api_host: 'https://eu.i.posthog.com' }),
    )
  })
})
