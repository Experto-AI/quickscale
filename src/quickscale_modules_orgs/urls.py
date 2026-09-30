"""Django URL surface for the QuickScale organizations module.

The module's mount (``orgs/``) is declared only in the manifest's
``url_includes`` wiring projection; every pattern here is module-relative and
every route name is snake_case without the module name, under the
``quickscale_orgs`` application namespace (Module Conventions rule 7).
"""

from django.urls import path

from .debug_views import DebugAsOrgView, ExitDebugModeView
from .views import (
    OrgApiDetailView,
    OrgApiInviteView,
    OrgApiListCreateView,
    OrgApiMemberRemoveView,
    OrgApiMemberRoleView,
    OrgApiMembersView,
    OrgApiRevokeInvitationView,
    OrgApiSettingsView,
    MemberListView,
    InviteView,
    OrgCreateView,
    OrgDashboardView,
    OrgInvitationAcceptView,
    OrgListView,
    OrgSettingsView,
    RevokeInvitationView,
)

app_name = "quickscale_orgs"

urlpatterns = [
    path("", OrgListView.as_view(), name="index"),
    path("new/", OrgCreateView.as_view(), name="new"),
    path(
        "invitations/<uuid:token>/accept/",
        OrgInvitationAcceptView.as_view(),
        name="invitation_accept",
    ),
    # Root-level debug exit (reachable without an org slug).
    path(
        "debug/exit/",
        ExitDebugModeView.as_view(),
        name="debug_exit_root",
    ),
    path("api/", OrgApiListCreateView.as_view(), name="api_list_create"),
    path("api/<slug:org_slug>/", OrgApiDetailView.as_view(), name="api_detail"),
    path(
        "api/<slug:org_slug>/members/",
        OrgApiMembersView.as_view(),
        name="api_members",
    ),
    path(
        "api/<slug:org_slug>/members/invite/",
        OrgApiInviteView.as_view(),
        name="api_members_invite",
    ),
    path(
        "api/<slug:org_slug>/members/<int:membership_id>/role/",
        OrgApiMemberRoleView.as_view(),
        name="api_members_role",
    ),
    path(
        "api/<slug:org_slug>/members/<int:membership_id>/remove/",
        OrgApiMemberRemoveView.as_view(),
        name="api_members_remove",
    ),
    path(
        "api/<slug:org_slug>/members/invitations/<uuid:invitation_id>/revoke/",
        OrgApiRevokeInvitationView.as_view(),
        name="api_members_invitation_revoke",
    ),
    path(
        "api/<slug:org_slug>/settings/",
        OrgApiSettingsView.as_view(),
        name="api_settings",
    ),
    # VIEW-AS debug routes — placed before the catch-all slug route
    # so they are matched before /orgs/<slug:org_slug>/ captures them.
    path(
        "<slug:org_slug>/debug/view-as/",
        DebugAsOrgView.as_view(),
        name="debug_view_as",
    ),
    path(
        "<slug:org_slug>/debug/exit/",
        ExitDebugModeView.as_view(),
        name="debug_exit",
    ),
    path("<slug:org_slug>/", OrgDashboardView.as_view(), name="detail"),
    path(
        "<slug:org_slug>/members/",
        MemberListView.as_view(),
        name="members",
    ),
    path(
        "<slug:org_slug>/members/invite/",
        InviteView.as_view(),
        name="members_invite",
    ),
    path(
        "<slug:org_slug>/members/invitations/<uuid:invitation_id>/revoke/",
        RevokeInvitationView.as_view(),
        name="members_invitation_revoke",
    ),
    path(
        "<slug:org_slug>/settings/",
        OrgSettingsView.as_view(),
        name="settings",
    ),
]
