import { Link } from 'react-router-dom'
import { Building2, Plus, Users } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { OrgStatePanel } from '@/components/orgs/OrgStatePanel'
import { getApiErrorMessage } from '@/hooks/useApi'
import { useOrgNavigation } from '@/hooks/useOrgNavigation'
import { useOrgs } from '@/hooks/useOrgs'
import { buildOrgPath } from '@/hooks/useModules'

export function OrgListPage() {
  const { appPaths } = useOrgNavigation()
  const orgsQuery = useOrgs()

  if (orgsQuery.isError) {
    return (
      <OrgStatePanel
        actionHref={appPaths.orgCreate}
        actionLabel="Create an organization"
        description={getApiErrorMessage(
          orgsQuery.error,
          'Your organizations could not be loaded right now.',
        )}
        icon={Building2}
        title="Unable to load organizations"
      />
    )
  }

  const organizations = orgsQuery.data?.organizations ?? []

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Organizations</h1>
          <p className="mt-1 text-muted-foreground">
            Pick a workspace to open its org-scoped dashboard, members, settings, and module pages.
          </p>
        </div>
        <Button asChild>
          <Link to={appPaths.orgCreate}>
            <Plus className="mr-2 h-4 w-4" />
            Create organization
          </Link>
        </Button>
      </div>

      {orgsQuery.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Card key={index} className="animate-pulse">
              <CardHeader>
                <div className="h-5 w-40 rounded bg-muted" />
                <div className="h-4 w-56 rounded bg-muted" />
              </CardHeader>
              <CardContent>
                <div className="h-9 w-32 rounded bg-muted" />
              </CardContent>
            </Card>
          ))}
        </div>
      ) : organizations.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {organizations.map((organization) => (
            <Card key={organization.id} className="h-full">
              <CardHeader>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <CardTitle className="text-lg">{organization.name}</CardTitle>
                    <CardDescription className="mt-1">/{organization.slug}</CardDescription>
                  </div>
                  {organization.role_label && (
                    <Badge variant="secondary">{organization.role_label}</Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Users className="h-4 w-4" />
                  {organization.is_personal
                    ? 'Personal workspace'
                    : 'Shared organization workspace'}
                </div>
                <Button asChild className="w-full justify-between">
                  <Link to={buildOrgPath(organization.slug)}>
                    Open workspace
                    <Building2 className="h-4 w-4" />
                  </Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>No organizations yet</CardTitle>
            <CardDescription>
              Create your first organization to unlock org-scoped dashboards, members, settings, and
              billing.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link to={appPaths.orgCreate}>
                <Plus className="mr-2 h-4 w-4" />
                Create your first organization
              </Link>
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
