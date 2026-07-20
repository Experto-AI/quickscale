// DORMANT: Listings module surface. Inert unless modules.listings is true at runtime. React.lazy-loaded, tree-shaken when unused. Safe to leave dormant.
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Store, ExternalLink, Filter, Grid } from 'lucide-react'
import { useOrgNavigation } from '@/hooks/useOrgNavigation'

export function ListingsPage() {
  const { documentPaths } = useOrgNavigation()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Listings</h1>
          <p className="text-muted-foreground">
            Generic listings with filtering for marketplace verticals
          </p>
        </div>
        <Button asChild>
          <a href={documentPaths.listingsIndex} target="_blank" rel="noopener noreferrer">
            <Store className="mr-2 h-4 w-4" /> View Listings
            <ExternalLink className="ml-1 h-3 w-3" />
          </a>
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <Grid className="mb-1 h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-base">All Listings</CardTitle>
            <CardDescription>Browse and search through all available listings</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" size="sm" asChild>
              <a href={documentPaths.listingsIndex}>
                Browse <ExternalLink className="ml-1 h-3 w-3" />
              </a>
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <Filter className="mb-1 h-5 w-5 text-muted-foreground" />
            <CardTitle className="text-base">Manage Listings</CardTitle>
            <CardDescription>Create and manage listings from Django Admin</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" size="sm" asChild>
              <a
                href="/admin/quickscale_modules_listings/"
                target="_blank"
                rel="noopener noreferrer"
              >
                Open Admin <ExternalLink className="ml-1 h-3 w-3" />
              </a>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
