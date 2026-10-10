import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiRequest, useApiData } from '@/hooks/useApi'
import { useProjectConfig } from '@/hooks/useModules'

export type OrgRole = 'viewer' | 'member' | 'admin' | 'owner'

export interface OrgSummary {
  id: string
  name: string
  slug: string
  is_personal: boolean
  role?: OrgRole
  role_label?: string
  member_count?: number
}

export interface OrgActor {
  role: OrgRole | null
  is_owner_like: boolean
}

export interface OrgDetailResponse {
  organization: OrgSummary
  actor: OrgActor
}

export interface OrgListResponse {
  organizations: OrgSummary[]
}

export interface OrgCreateResponse {
  organization: OrgSummary
  next_url: string
  billing_pricing_url: string | null
}

export interface OrgUser {
  id: string
  username: string
  email: string
  display_name: string
}

export interface OrgMember {
  id: number
  role: OrgRole
  role_label: string
  joined_at: string
  user: OrgUser
}

export interface OrgInvitation {
  id: string
  email: string
  role: OrgRole
  role_label: string
  expires_at: string
}

export interface OrgRoleChoice {
  value: OrgRole
  label: string
}

export interface OrgMembersResponse {
  organization: OrgSummary
  actor: OrgActor
  members: OrgMember[]
  pending_invitations: OrgInvitation[]
  role_choices: OrgRoleChoice[]
}

export interface OrgSettingsResponse {
  organization: OrgSummary
}

export interface OrgBalanceResponse {
  balance: number
  updated_at: string | null
}

export interface OrgPlan {
  name: string
  slug: string
  credits_per_period: number
  price_cents: number
  currency: string
  billing_interval: string
}

export interface OrgSubscriptionResponse {
  plan: OrgPlan
  status: string
  checkout_expires_at: string | null
  current_period_start: string | null
  current_period_end: string | null
}

function buildOrgApiPath(orgsApiBase: string, orgSlug: string, path = ''): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${orgsApiBase}${orgSlug}${path ? normalizedPath : '/'}`
}

function buildBillingApiPath(billingApiBase: string, path: string): string {
  const normalizedBase = billingApiBase.endsWith('/')
    ? billingApiBase.slice(0, -1)
    : billingApiBase
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${normalizedBase}${normalizedPath}`
}

function invalidateOrgQueries(queryClient: ReturnType<typeof useQueryClient>, orgSlug: string) {
  return Promise.all([
    queryClient.invalidateQueries({ queryKey: ['orgs'] }),
    queryClient.invalidateQueries({ queryKey: ['orgs', orgSlug] }),
    queryClient.invalidateQueries({ queryKey: ['orgs', orgSlug, 'members'] }),
  ])
}

export function isOrgAdminLike(actor: OrgActor | null | undefined): boolean {
  if (!actor) {
    return false
  }

  return actor.is_owner_like || actor.role === 'admin' || actor.role === 'owner'
}

export function useOrgs() {
  const { moduleApiPaths } = useProjectConfig()
  return useApiData<OrgListResponse>(moduleApiPaths.orgs, ['orgs'])
}

export function useOrg(orgSlug: string) {
  const { moduleApiPaths } = useProjectConfig()
  return useApiData<OrgDetailResponse>(buildOrgApiPath(moduleApiPaths.orgs, orgSlug), ['orgs', orgSlug], {
    enabled: Boolean(orgSlug),
  })
}

export function useCreateOrg() {
  const queryClient = useQueryClient()
  const { moduleApiPaths } = useProjectConfig()

  return useMutation({
    mutationFn: (payload: { name: string }) =>
      apiRequest<OrgCreateResponse>(moduleApiPaths.orgs, {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['orgs'] })
    },
  })
}

export function useOrgMembers(orgSlug: string) {
  const { moduleApiPaths } = useProjectConfig()
  return useApiData<OrgMembersResponse>(
    buildOrgApiPath(moduleApiPaths.orgs, orgSlug, 'members'),
    ['orgs', orgSlug, 'members'],
    { enabled: Boolean(orgSlug) },
  )
}

export function useInviteOrgMember(orgSlug: string) {
  const queryClient = useQueryClient()
  const { moduleApiPaths } = useProjectConfig()

  return useMutation({
    mutationFn: (payload: { email: string; role: OrgRole }) =>
      apiRequest<{ invitation: OrgInvitation }>(
        buildOrgApiPath(moduleApiPaths.orgs, orgSlug, 'members/invite'),
        {
          method: 'POST',
          body: JSON.stringify(payload),
        },
      ),
    onSuccess: async () => {
      await invalidateOrgQueries(queryClient, orgSlug)
    },
  })
}

export function useUpdateOrgMemberRole(orgSlug: string) {
  const queryClient = useQueryClient()
  const { moduleApiPaths } = useProjectConfig()

  return useMutation({
    mutationFn: (payload: { membershipId: number; role: OrgRole }) =>
      apiRequest<{ member: OrgMember }>(
        buildOrgApiPath(moduleApiPaths.orgs, orgSlug, `members/${payload.membershipId}/role`),
        {
          method: 'POST',
          body: JSON.stringify({ role: payload.role }),
        },
      ),
    onSuccess: async () => {
      await invalidateOrgQueries(queryClient, orgSlug)
    },
  })
}

export function useRemoveOrgMember(orgSlug: string) {
  const queryClient = useQueryClient()
  const { moduleApiPaths } = useProjectConfig()

  return useMutation({
    mutationFn: (payload: { membershipId: number }) =>
      apiRequest<{ status: 'removed'; member_id: number }>(
        buildOrgApiPath(moduleApiPaths.orgs, orgSlug, `members/${payload.membershipId}/remove`),
        {
          method: 'POST',
        },
      ),
    onSuccess: async () => {
      await invalidateOrgQueries(queryClient, orgSlug)
    },
  })
}

export function useRevokeOrgInvitation(orgSlug: string) {
  const queryClient = useQueryClient()
  const { moduleApiPaths } = useProjectConfig()

  return useMutation({
    mutationFn: (payload: { invitationId: string }) =>
      apiRequest<{ status: 'revoked'; invitation_id: string }>(
        buildOrgApiPath(moduleApiPaths.orgs, orgSlug, `members/invitations/${payload.invitationId}/revoke`),
        {
          method: 'POST',
        },
      ),
    onSuccess: async () => {
      await invalidateOrgQueries(queryClient, orgSlug)
    },
  })
}

export function useUpdateOrgSettings(orgSlug: string) {
  const queryClient = useQueryClient()
  const { moduleApiPaths } = useProjectConfig()

  return useMutation({
    mutationFn: (payload: { name: string; slug: string }) =>
      apiRequest<OrgSettingsResponse>(buildOrgApiPath(moduleApiPaths.orgs, orgSlug, 'settings'), {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    onSuccess: async () => {
      await invalidateOrgQueries(queryClient, orgSlug)
    },
  })
}

export function useOrgBilling(orgSlug: string, enabled = true) {
  const billingEnabled = enabled && Boolean(orgSlug)
  const { moduleApiPaths } = useProjectConfig()

  const subscription = useApiData<OrgSubscriptionResponse>(
    buildBillingApiPath(moduleApiPaths.billing, 'subscription/'),
    ['orgs', orgSlug, 'billing', 'subscription'],
    { enabled: billingEnabled },
  )
  const balance = useApiData<OrgBalanceResponse>(
    buildBillingApiPath(moduleApiPaths.billing, 'balance/'),
    ['orgs', orgSlug, 'billing', 'balance'],
    { enabled: billingEnabled },
  )

  return {
    subscription,
    balance,
  }
}
