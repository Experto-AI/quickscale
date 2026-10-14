import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  isOrgAdminLike,
  useCreateOrg,
  useInviteOrgMember,
  useOrg,
  useOrgBilling,
  useOrgMembers,
  useOrgs,
  useRemoveOrgMember,
  useRevokeOrgInvitation,
  useUpdateOrgMemberRole,
  useUpdateOrgSettings,
} from '@/hooks/useOrgs'
import { moduleFlags, modulePaths, moduleApiPaths } from '@/test/seamFixtures'

const fetchMock = vi.fn()

vi.stubGlobal('fetch', fetchMock)

beforeEach(() => {
  window.__QUICKSCALE__ = {
    projectName: 'useOrgs Test',
    modules: moduleFlags({ billing: true }),
    modulePaths: modulePaths({ analytics: '/analytics/' }),
    moduleApiPaths: moduleApiPaths(),
    owner: { mode: 'solo', currentOrgSlug: null },
  }
})

function jsonResponse(status: number, payload: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => payload,
  } as Response
}

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

afterEach(() => {
  fetchMock.mockReset()
})

describe('org query hooks', () => {
  it('loads the org list from the org API', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { organizations: [] }))

    const { result } = renderHook(() => useOrgs(), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(fetchMock).toHaveBeenCalledWith('/orgs/api/', expect.anything())
  })

  it('loads one org by slug and skips the request without a slug', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { organization: {}, actor: {} }))

    const { result } = renderHook(() => useOrg('acme'), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(fetchMock).toHaveBeenCalledWith('/orgs/api/acme/', expect.anything())

    fetchMock.mockClear()
    const disabled = renderHook(() => useOrg(''), { wrapper: createWrapper() })
    expect(disabled.result.current.fetchStatus).toBe('idle')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('loads org members and skips the request without a slug', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { members: [] }))

    const { result } = renderHook(() => useOrgMembers('acme'), { wrapper: createWrapper() })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(fetchMock).toHaveBeenCalledWith('/orgs/api/acme/members', expect.anything())

    fetchMock.mockClear()
    const disabled = renderHook(() => useOrgMembers(''), { wrapper: createWrapper() })
    expect(disabled.result.current.fetchStatus).toBe('idle')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('loads subscription and balance while billing is enabled', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, {}))

    const { result } = renderHook(() => useOrgBilling('acme'), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.subscription.isSuccess).toBe(true))
    expect(fetchMock).toHaveBeenCalledWith('/billing/api/subscription/', expect.anything())
    expect(fetchMock).toHaveBeenCalledWith('/billing/api/balance/', expect.anything())
  })

  it('skips billing requests when billing is disabled or no slug is present', async () => {
    const disabled = renderHook(() => useOrgBilling('acme', false), { wrapper: createWrapper() })
    expect(disabled.result.current.subscription.fetchStatus).toBe('idle')
    expect(disabled.result.current.balance.fetchStatus).toBe('idle')
    expect(fetchMock).not.toHaveBeenCalled()

    const noSlug = renderHook(() => useOrgBilling(''), { wrapper: createWrapper() })
    expect(noSlug.result.current.subscription.fetchStatus).toBe('idle')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})

describe('org mutation hooks', () => {
  it('creates an organization with a JSON body', async () => {
    fetchMock.mockResolvedValue(jsonResponse(201, { organization: { id: '1' } }))

    const { result } = renderHook(() => useCreateOrg(), { wrapper: createWrapper() })
    result.current.mutate({ name: 'Acme' })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(fetchMock).toHaveBeenCalledWith(
      '/orgs/api/',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ name: 'Acme' }) }),
    )
  })

  it('invites a member through the members invite endpoint', async () => {
    fetchMock.mockResolvedValue(jsonResponse(201, { invitation: {} }))

    const { result } = renderHook(() => useInviteOrgMember('acme'), { wrapper: createWrapper() })
    result.current.mutate({ email: 'new@example.com', role: 'member' })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(fetchMock).toHaveBeenCalledWith(
      '/orgs/api/acme/members/invite',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ email: 'new@example.com', role: 'member' }),
      }),
    )
  })

  it('updates a member role through the membership endpoint', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { member: {} }))

    const { result } = renderHook(() => useUpdateOrgMemberRole('acme'), {
      wrapper: createWrapper(),
    })
    result.current.mutate({ membershipId: 7, role: 'admin' })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(fetchMock).toHaveBeenCalledWith(
      '/orgs/api/acme/members/7/role',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ role: 'admin' }) }),
    )
  })

  it('removes a member through the remove endpoint', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { status: 'removed', member_id: 7 }))

    const { result } = renderHook(() => useRemoveOrgMember('acme'), { wrapper: createWrapper() })
    result.current.mutate({ membershipId: 7 })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(fetchMock).toHaveBeenCalledWith(
      '/orgs/api/acme/members/7/remove',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('revokes an invitation through the revoke endpoint', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { status: 'revoked', invitation_id: 'abc' }))

    const { result } = renderHook(() => useRevokeOrgInvitation('acme'), {
      wrapper: createWrapper(),
    })
    result.current.mutate({ invitationId: 'abc' })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(fetchMock).toHaveBeenCalledWith(
      '/orgs/api/acme/members/invitations/abc/revoke',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('updates org settings with the new name and slug', async () => {
    fetchMock.mockResolvedValue(jsonResponse(200, { organization: {} }))

    const { result } = renderHook(() => useUpdateOrgSettings('acme'), {
      wrapper: createWrapper(),
    })
    result.current.mutate({ name: 'Acme Inc', slug: 'acme-inc' })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(fetchMock).toHaveBeenCalledWith(
      '/orgs/api/acme/settings',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ name: 'Acme Inc', slug: 'acme-inc' }),
      }),
    )
  })
})

describe('isOrgAdminLike', () => {
  it('treats owners, owner-like actors, and admins as admin-like', () => {
    expect(isOrgAdminLike(null)).toBe(false)
    expect(isOrgAdminLike(undefined)).toBe(false)
    expect(isOrgAdminLike({ role: 'viewer', is_owner_like: false })).toBe(false)
    expect(isOrgAdminLike({ role: 'admin', is_owner_like: false })).toBe(true)
    expect(isOrgAdminLike({ role: 'owner', is_owner_like: false })).toBe(true)
    expect(isOrgAdminLike({ role: 'member', is_owner_like: true })).toBe(true)
  })
})
