import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, createElement } from 'react'
import { fireEvent, waitFor } from '@testing-library/dom'
import { FormRenderer } from '@/components/forms/FormRenderer'
import { getCsrfToken } from '@/lib/csrf'
import { apiRequest } from '@/hooks/useApi'
import type { FormSchema } from '@/hooks/useFormSchema'

const { useFormSchemaMock } = vi.hoisted(() => ({ useFormSchemaMock: vi.fn() }))

vi.mock('@/hooks/useFormSchema', () => ({
  useFormSchema: useFormSchemaMock,
}))

const fetchMock = vi.fn()

vi.stubGlobal('fetch', fetchMock)
vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)

const runtimeProcess = (globalThis as typeof globalThis & { process?: { cwd(): string } }).process
const runningFromNoSocialDirectory = runtimeProcess?.cwd().endsWith('/no_social') ?? false
const localDependencyPath =
  import.meta.url.includes('/no_social/') && !runningFromNoSocialDirectory
    ? '../../../node_modules/react-dom/client.js'
    : '../../node_modules/react-dom/client.js'
const { createRoot } = await import(/* @vite-ignore */ new URL(localDependencyPath, import.meta.url).href)

const cookieCases = [
  {
    name: 'uses the first exact duplicate',
    cookie: 'csrftoken=first-token; csrftoken=second-token',
    expected: 'first-token',
  },
  {
    name: 'finds the token after a session cookie',
    cookie: 'sessionid=session-value; csrftoken=csrf-token',
    expected: 'csrf-token',
  },
  {
    name: 'decodes an encoded single token',
    cookie: 'csrftoken=encoded%20token%3Dvalue',
    expected: 'encoded token=value',
  },
  {
    name: 'returns an empty string without a token',
    cookie: 'sessionid=session-value',
    expected: '',
  },
  {
    name: 'does not match a near-miss cookie name',
    cookie: 'notcsrftoken=attacker-token',
    expected: '',
  },
] as const

function setCookie(cookie: string) {
  vi.spyOn(document, 'cookie', 'get').mockReturnValue(cookie)
}

function buildFormSchema(): FormSchema {
  return {
    slug: 'contact',
    title: 'Contact',
    success_message: 'Thanks for your message.',
    fields: [
      {
        name: 'message',
        field_type: 'text',
        label: 'Message',
        required: false,
        order: 0,
        layout_hint: 'full',
        options: [],
        validation_rules: {},
        is_active: true,
      },
    ],
  }
}

function requestHeaders(callIndex = 0): Headers {
  const request = fetchMock.mock.calls[callIndex]?.[1] as RequestInit | undefined
  return new Headers(request?.headers)
}

afterEach(() => {
  vi.restoreAllMocks()
  fetchMock.mockReset()
  useFormSchemaMock.mockReset()
})

describe('getCsrfToken', () => {
  it.each(cookieCases)('$name', ({ cookie, expected }) => {
    setCookie(cookie)

    expect(getCsrfToken()).toBe(expected)
  })
})

describe('CSRF request callers', () => {
  it('uses the selected token for a mutating apiRequest', async () => {
    setCookie('sessionid=session-value; csrftoken=api%20token')
    const expectedToken = getCsrfToken()
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers(),
    })

    await apiRequest('/api/example/', { method: 'POST', body: '{}' })

    expect(requestHeaders().get('X-CSRFToken')).toBe(expectedToken)
  })

  it('preserves a caller-supplied apiRequest CSRF header', async () => {
    setCookie('csrftoken=cookie-token')
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers(),
    })

    await apiRequest('/api/example/', {
      method: 'POST',
      headers: { 'X-CSRFToken': 'caller-token' },
    })

    expect(requestHeaders().get('X-CSRFToken')).toBe('caller-token')
  })

  it.each(['GET', 'HEAD'] as const)('does not add a CSRF header to %s requests', async (method) => {
    setCookie('csrftoken=cookie-token')
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers(),
    })

    await apiRequest('/api/example/', { method })

    expect(requestHeaders().has('X-CSRFToken')).toBe(false)
  })

  it('uses the same selected token for the FormRenderer POST', async () => {
    setCookie('sessionid=session-value; csrftoken=form%20token')
    const expectedToken = getCsrfToken()
    useFormSchemaMock.mockReturnValue({
      data: buildFormSchema(),
      isLoading: false,
      isError: false,
      error: null,
    })
    fetchMock.mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({}),
    })

    const container = document.createElement('div')
    document.body.append(container)
    const root = createRoot(container)

    try {
      await act(async () => {
        root.render(createElement(FormRenderer, { slug: 'contact' }))
      })
      const submitButton = container.querySelector('button')
      if (!submitButton) {
        throw new Error('FormRenderer did not render a submit button')
      }
      await act(async () => {
        fireEvent.click(submitButton)
        await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
      })

      expect(fetchMock).toHaveBeenCalledWith(
        '/api/forms/contact/submit/',
        expect.objectContaining({ method: 'POST' }),
      )
      expect(requestHeaders().get('X-CSRFToken')).toBe(expectedToken)
      expect(fetchMock.mock.calls[0]?.[1]).toEqual(
        expect.objectContaining({ body: JSON.stringify({ message: '' }) }),
      )
    } finally {
      await act(async () => {
        root.unmount()
      })
      container.remove()
    }
  })
})
