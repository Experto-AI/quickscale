import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  apiRequest,
  getApiErrorMessage,
  getApiFieldErrors,
} from '@/hooks/useApi'

const fetchMock = vi.fn()

vi.stubGlobal('fetch', fetchMock)

function jsonResponse(status: number, payload: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => payload,
  } as Response
}

describe('QuickScale API error parsing', () => {
  beforeEach(() => {
    fetchMock.mockReset()
  })

  it('derives an actionable message and fields from the one QuickScale error shape', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(400, {
        error: {
          code: 'validation_error',
          message: 'Invalid input.',
          fields: { name: ['This field is required.'] },
        },
      }),
    )

    const error = await apiRequest('/orgs/api/', {
      method: 'POST',
      body: '{}',
    }).catch((caught: unknown) => caught)

    expect(error).toBeInstanceOf(ApiError)
    expect(getApiErrorMessage(error)).toBe('This field is required.')
    expect(getApiFieldErrors(error)).toEqual({
      name: ['This field is required.'],
    })
  })

  it('keeps an actionable message for a validation failure shown only as a message', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(400, {
        error: {
          code: 'validation_error',
          message: 'Invalid input.',
          fields: {
            non_field_errors: ['You cannot remove the last owner.'],
          },
        },
      }),
    )

    const error = await apiRequest('/orgs/api/acme/members/1/remove/', {
      method: 'POST',
      body: '{}',
    }).catch((caught: unknown) => caught)

    expect(getApiErrorMessage(error)).toBe('You cannot remove the last owner.')
  })

  it('reads a non-validation error without fields', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(403, {
        error: { code: 'permission_denied', message: 'Forbidden' },
      }),
    )

    const error = await apiRequest('/orgs/api/').catch(
      (caught: unknown) => caught,
    )

    expect(getApiErrorMessage(error)).toBe('Forbidden')
    expect(getApiFieldErrors(error)).toEqual({})
  })

  it('still reads the pre-convention string and field shapes', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(400, { error: 'Invalid JSON payload' }),
    )
    const stringError = await apiRequest('/forms/api/example/').catch(
      (caught: unknown) => caught,
    )
    expect(getApiErrorMessage(stringError)).toBe('Invalid JSON payload')

    fetchMock.mockResolvedValue(
      jsonResponse(400, { errors: { title: ['This field is required.'] } }),
    )
    const fieldsError = await apiRequest('/forms/api/example/').catch(
      (caught: unknown) => caught,
    )
    expect(getApiFieldErrors(fieldsError)).toEqual({
      title: ['This field is required.'],
    })
  })

  it('falls back to the status text for an unshaped error body', async () => {
    fetchMock.mockResolvedValue(
      jsonResponse(500, { detail: 'Server exploded' }),
    )

    const error = await apiRequest('/api/example/').catch(
      (caught: unknown) => caught,
    )

    expect(getApiErrorMessage(error)).toBe('API Error: 500')
  })
})
