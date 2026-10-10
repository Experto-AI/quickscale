import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useThemeStore } from '@/stores/themeStore'

describe('theme store', () => {
  beforeEach(() => {
    document.documentElement.className = ''
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('applies and persists an explicit theme on the document root', () => {
    useThemeStore.getState().setTheme('dark')

    expect(useThemeStore.getState().theme).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    expect(document.documentElement.classList.contains('light')).toBe(false)
    const persisted = JSON.parse(localStorage.getItem('theme-storage') ?? '{}') as {
      state?: { theme?: string }
    }
    expect(persisted.state?.theme).toBe('dark')
  })

  it('toggles between light and dark in both directions', () => {
    useThemeStore.setState({ theme: 'light' })
    useThemeStore.getState().toggleTheme()
    expect(useThemeStore.getState().theme).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)

    useThemeStore.getState().toggleTheme()
    expect(useThemeStore.getState().theme).toBe('light')
    expect(document.documentElement.classList.contains('light')).toBe(true)
    expect(document.documentElement.classList.contains('dark')).toBe(false)
  })

  it('rehydrates a persisted theme onto the document root', async () => {
    vi.resetModules()
    localStorage.setItem('theme-storage', JSON.stringify({ state: { theme: 'dark' }, version: 0 }))

    const freshModule = await import('@/stores/themeStore')

    expect(freshModule.useThemeStore.getState().theme).toBe('dark')
    expect(document.documentElement.classList.contains('dark')).toBe(true)
    // Keep later assertions on the static store deterministic.
    useThemeStore.setState({ theme: 'light' })
  })

  it('keeps the default theme when persisted state is unreadable', async () => {
    vi.resetModules()
    localStorage.setItem('theme-storage', '{not json')

    const freshModule = await import('@/stores/themeStore')

    expect(freshModule.useThemeStore.getState().theme).toBe('light')
    useThemeStore.setState({ theme: 'light' })
  })
})
