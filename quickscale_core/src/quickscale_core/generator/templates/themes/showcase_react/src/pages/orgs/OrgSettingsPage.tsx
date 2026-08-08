import { useState } from 'react'
import { Save, ShieldAlert } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { getApiErrorMessage, getApiFieldErrors } from '@/hooks/useApi'
import { buildOrgPath } from '@/hooks/useModules'
import { useOrgNavigation } from '@/hooks/useOrgNavigation'
import { isOrgAdminLike, useUpdateOrgSettings } from '@/hooks/useOrgs'
import { OrgStatePanel } from '@/components/orgs/OrgStatePanel'
import { useOrgPageContext } from './OrgLayout'

export function OrgSettingsPage() {
  const { actor, organization } = useOrgPageContext()
  const { appPaths, currentOrgSlug } = useOrgNavigation()
  const updateSettingsMutation = useUpdateOrgSettings(currentOrgSlug ?? '')
  const [globalError, setGlobalError] = useState<string | null>(null)
  const [name, setName] = useState(organization.name)
  const [saved, setSaved] = useState(false)
  const [slug, setSlug] = useState(organization.slug)
  const fieldErrors = getApiFieldErrors(updateSettingsMutation.error)
  const canManageSettings = isOrgAdminLike(actor)

  // Reset the draft fields when we switch to a different organization.
  // Adjusting state during render is React's documented alternative to a
  // reset-on-prop-change effect: it re-renders before anything is painted,
  // where an effect would flash the previous org's values first.
  const [syncedOrg, setSyncedOrg] = useState(organization)
  if (syncedOrg.name !== organization.name || syncedOrg.slug !== organization.slug) {
    setSyncedOrg(organization)
    setName(organization.name)
    setSlug(organization.slug)
  }

  if (!canManageSettings) {
    return (
      <OrgStatePanel
        actionHref={appPaths.dashboard}
        actionLabel="Back to organization"
        description="Only organization admins and owners can change org metadata."
        icon={ShieldAlert}
        title="Settings access restricted"
      />
    )
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setGlobalError(null)
    setSaved(false)

    try {
      const response = await updateSettingsMutation.mutateAsync({ name, slug })
      setSaved(true)

      if (currentOrgSlug && response.organization.slug !== currentOrgSlug) {
        window.location.assign(buildOrgPath(response.organization.slug, 'settings'))
      }
    } catch (error) {
      const errors = getApiFieldErrors(error)
      if (!errors.name?.length && !errors.slug?.length) {
        setGlobalError(getApiErrorMessage(error))
      }
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Organization settings</h1>
        <p className="mt-1 text-muted-foreground">
          Update the display name and slug for {organization.name}. Slug changes move every
          org-aware URL.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>General</CardTitle>
          <CardDescription>
            Changes are saved through `/api/orgs/:slug/settings/`. Slug changes require a full
            document reload to land on the new canonical URL.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="org-name">Organization name</Label>
              <Input
                id="org-name"
                value={name}
                onChange={(event) => {
                  setName(event.target.value)
                  setSaved(false)
                  setGlobalError(null)
                }}
              />
              {fieldErrors.name?.[0] && (
                <p className="text-sm text-destructive">{fieldErrors.name[0]}</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="org-slug">Organization slug</Label>
              <Input
                id="org-slug"
                value={slug}
                onChange={(event) => {
                  setSlug(event.target.value)
                  setSaved(false)
                  setGlobalError(null)
                }}
                autoCapitalize="none"
                autoCorrect="off"
              />
              {fieldErrors.slug?.[0] && (
                <p className="text-sm text-destructive">{fieldErrors.slug[0]}</p>
              )}
              <p className="text-sm text-muted-foreground">
                Existing bookmarks and deep links will need the new slug after this change.
              </p>
            </div>

            {fieldErrors.non_field_errors?.[0] && (
              <div className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                {fieldErrors.non_field_errors[0]}
              </div>
            )}

            {globalError && (
              <div className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                {globalError}
              </div>
            )}

            {saved && !globalError && (
              <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">
                Organization settings saved.
              </div>
            )}

            <Button type="submit" disabled={updateSettingsMutation.isPending}>
              <Save className="mr-2 h-4 w-4" />
              {updateSettingsMutation.isPending ? 'Saving...' : 'Save changes'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
