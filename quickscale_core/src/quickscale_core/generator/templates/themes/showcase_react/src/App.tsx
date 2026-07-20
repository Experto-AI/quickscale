import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from '@/components/layout/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { NotFound } from '@/pages/NotFound'
import { ProfilePage } from '@/pages/ProfilePage'
import { SettingsPage } from '@/pages/SettingsPage'
import { buildOrgPath, useCurrentOrgSlug, useModules, useOwnerMode } from '@/hooks/useModules'

const BlogPage = lazy(() => import('@/pages/BlogPage').then((m) => ({ default: m.BlogPage })))
const CrmPage = lazy(() => import('@/pages/CrmPage').then((m) => ({ default: m.CrmPage })))
const ListingsPage = lazy(() => import('@/pages/ListingsPage').then((m) => ({ default: m.ListingsPage })))
const FormsPage = lazy(() => import('@/pages/FormsPage').then((m) => ({ default: m.FormsPage })))
const OrgCreatePage = lazy(() => import('@/pages/orgs/OrgCreatePage').then((m) => ({ default: m.OrgCreatePage })))
const OrgDashboardPage = lazy(() => import('@/pages/orgs/OrgDashboardPage').then((m) => ({ default: m.OrgDashboardPage })))
const OrgLayout = lazy(() => import('@/pages/orgs/OrgLayout').then((m) => ({ default: m.OrgLayout })))
const OrgListPage = lazy(() => import('@/pages/orgs/OrgListPage').then((m) => ({ default: m.OrgListPage })))
const OrgMembersPage = lazy(() => import('@/pages/orgs/OrgMembersPage').then((m) => ({ default: m.OrgMembersPage })))
const OrgSettingsPage = lazy(() => import('@/pages/orgs/OrgSettingsPage').then((m) => ({ default: m.OrgSettingsPage })))

function LegacySaasRedirect({ path = '' }: { path?: string }) {
  const currentOrgSlug = useCurrentOrgSlug()

  return <Navigate to={currentOrgSlug ? buildOrgPath(currentOrgSlug, path) : '/orgs'} replace />
}

function App() {
  const ownerMode = useOwnerMode()
  const currentOrgSlug = useCurrentOrgSlug()
  const modules = useModules()

  if (ownerMode === 'saas') {
    const defaultOrgDestination = currentOrgSlug ? buildOrgPath(currentOrgSlug) : '/orgs'

    return (
      <Suspense fallback={<div>Loading…</div>}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Navigate to={defaultOrgDestination} replace />} />
            <Route path="/orgs" element={<OrgListPage />} />
            <Route path="/orgs/new" element={<OrgCreatePage />} />
            <Route path="/orgs/:orgSlug" element={<OrgLayout />}>
              <Route index element={<OrgDashboardPage />} />
              {modules.blog && <Route path="blog" element={<BlogPage />} />}
              {modules.listings && <Route path="listings" element={<ListingsPage />} />}
              <Route path="members" element={<OrgMembersPage />} />
              <Route path="settings" element={<OrgSettingsPage />} />
            </Route>
            {modules.crm && <Route path="/crm" element={<CrmPage />} />}
            <Route path="/profile" element={<ProfilePage />} />
            {modules.blog && <Route path="/blog" element={<LegacySaasRedirect path="blog" />} />}
            {modules.listings && <Route path="/listings" element={<LegacySaasRedirect path="listings" />} />}
            {modules.forms && <Route path="/forms" element={<FormsPage />} />}
            {modules.forms && <Route path="/forms/:slug" element={<FormsPage />} />}
            <Route path="/settings" element={<LegacySaasRedirect path="settings" />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </Suspense>
    )
  }

  return (
    <Suspense fallback={<div>Loading…</div>}>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Dashboard />} />
          {modules.blog && <Route path="/blog" element={<BlogPage />} />}
          {modules.listings && <Route path="/listings" element={<ListingsPage />} />}
          {modules.crm && <Route path="/crm" element={<CrmPage />} />}
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/settings" element={<SettingsPage />} />
          {modules.forms && <Route path="/forms" element={<FormsPage />} />}
          {modules.forms && <Route path="/forms/:slug" element={<FormsPage />} />}
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  )
}

export default App
