import { Link } from 'react-router-dom'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useOrgNavigation } from '@/hooks/useOrgNavigation'
import { isOrgAdminLike } from '@/hooks/useOrgs'
import { useOrgPageContext } from './OrgLayout'

export function OrgDashboardPage() {
  const { actor, organization } = useOrgPageContext()
  const { appPaths } = useOrgNavigation()
  const canManageOrganization = isOrgAdminLike(actor)
  const actorRoleLabel =
    organization.role_label ?? (actor.is_owner_like ? 'Owner-like access' : null)

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-3xl font-bold tracking-tight">{organization.name}</h1>
            {actorRoleLabel && <Badge variant="secondary">{actorRoleLabel}</Badge>}
          </div>
          <p className="mt-2 text-muted-foreground">
            Org-aware dashboard for /{organization.slug} with membership data loaded from the
            new SaaS contract.
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {organization.member_count === 1
              ? '1 member'
              : `${organization.member_count ?? 0} members`}{' '}
            currently belong to this organization.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {canManageOrganization && (
            <Button variant="outline" asChild>
              <Link to={appPaths.members}>Manage members</Link>
            </Button>
          )}
          {canManageOrganization && (
            <Button variant="outline" asChild>
              <Link to={appPaths.settings}>Org settings</Link>
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Your access</CardTitle>
            <CardDescription>
              The org detail API remains the source of truth for role and owner-like access.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{actorRoleLabel ?? 'Viewer'}</div>
            <p className="mt-2 text-sm text-muted-foreground">
              {actor.is_owner_like
                ? 'You have owner-level access for billing and membership changes.'
                : canManageOrganization
                  ? 'You can manage members and organization settings.'
                  : 'You can view the workspace but admin surfaces stay restricted.'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Quick links</CardTitle>
            <CardDescription>
              Switch between the org-aware membership and settings surfaces from this dashboard.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            <Button variant="outline" className="w-full justify-start" asChild>
              <Link to={appPaths.members}>Members</Link>
            </Button>
            <Button variant="outline" className="w-full justify-start" asChild>
              <Link to={appPaths.settings}>Settings</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
