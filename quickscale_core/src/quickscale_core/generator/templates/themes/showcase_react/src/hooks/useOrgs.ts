import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiRequest, useApiData } from '@/hooks/useApi'
import { useProjectConfig } from '@/hooks/useModules'
import { BILLING_RESOURCE_PATHS, ORGS_RESOURCE_PATHS } from '@/quickscaleSeam.hooks'

import type {
  OrgActor,
  OrgBalanceResponse,
  OrgCreateResponse,
  OrgDetailResponse,
  OrgInvitation,
  OrgInvitationResponse,
  OrgInvitationRevokedResponse,
  OrgListResponse,
  OrgMember,
  OrgMemberResponse,
  OrgMembersResponse,
  OrgMemberRemovedResponse,
  OrgPlan,
  OrgRole,
  OrgRoleChoice,
  OrgSettingsResponse,
  OrgSubscriptionResponse,
  OrgSummary,
  OrgUser,
} from '@/quickscaleSeam.hooks'

// The payload types live in the managed hook file; the hooks re-export them
// for the org pages that already import this module.
export type {
  OrgActor,
  OrgBalanceResponse,
  OrgCreateResponse,
  OrgDetailResponse,
  OrgInvitation,
  OrgInvitationResponse,
  OrgInvitationRevokedResponse,
  OrgListResponse,
  OrgMember,
  OrgMemberResponse,
  OrgMembersResponse,
  OrgMemberRemovedResponse,
  OrgPlan,
  OrgRole,
  OrgRoleChoice,
  OrgSettingsResponse,
  OrgSubscriptionResponse,
  OrgSummary,
  OrgUser,
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
  return useApiData<OrgDetailResponse>(
    `${moduleApiPaths.orgs}${ORGS_RESOURCE_PATHS.detail(orgSlug)}`,
    ['orgs', orgSlug],
    { enabled: Boolean(orgSlug) },
  )
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
    `${moduleApiPaths.orgs}${ORGS_RESOURCE_PATHS.members(orgSlug)}`,
    ['orgs', orgSlug, 'members'],
    { enabled: Boolean(orgSlug) },
  )
}

export function useInviteOrgMember(orgSlug: string) {
  const queryClient = useQueryClient()
  const { moduleApiPaths } = useProjectConfig()

  return useMutation({
    mutationFn: (payload: { email: string; role: OrgRole }) =>
      apiRequest<OrgInvitationResponse>(
        `${moduleApiPaths.orgs}${ORGS_RESOURCE_PATHS.membersInvite(orgSlug)}`,
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
      apiRequest<OrgMemberResponse>(
        `${moduleApiPaths.orgs}${ORGS_RESOURCE_PATHS.memberRole(orgSlug, payload.membershipId)}`,
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
      apiRequest<OrgMemberRemovedResponse>(
        `${moduleApiPaths.orgs}${ORGS_RESOURCE_PATHS.memberRemove(orgSlug, payload.membershipId)}`,
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
      apiRequest<OrgInvitationRevokedResponse>(
        `${moduleApiPaths.orgs}${ORGS_RESOURCE_PATHS.invitationRevoke(orgSlug, payload.invitationId)}`,
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
      apiRequest<OrgSettingsResponse>(`${moduleApiPaths.orgs}${ORGS_RESOURCE_PATHS.settings(orgSlug)}`, {
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
    buildBillingApiPath(moduleApiPaths.billing, BILLING_RESOURCE_PATHS.subscription),
    ['orgs', orgSlug, 'billing', 'subscription'],
    { enabled: billingEnabled },
  )
  const balance = useApiData<OrgBalanceResponse>(
    buildBillingApiPath(moduleApiPaths.billing, BILLING_RESOURCE_PATHS.balance),
    ['orgs', orgSlug, 'billing', 'balance'],
    { enabled: billingEnabled },
  )

  return {
    subscription,
    balance,
  }
}
