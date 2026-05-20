"""Django URL surface for the QuickScale organizations module."""

from django.urls import path

from .views import (
    MemberListView,
    InviteView,
    OrgCreateView,
    OrgDashboardView,
    OrgInvitationAcceptView,
    OrgListView,
    OrgSettingsView,
    RevokeInvitationView,
)

urlpatterns = [
    path("", OrgDashboardView.as_view(), name="org-home"),
    path("orgs/", OrgListView.as_view(), name="org-index"),
    path("orgs/new/", OrgCreateView.as_view(), name="org-new"),
    path(
        "orgs/invitations/<uuid:token>/accept/",
        OrgInvitationAcceptView.as_view(),
        name="org-invitation-accept",
    ),
    path("orgs/<slug:org_slug>/", OrgDashboardView.as_view(), name="org-detail"),
    path(
        "orgs/<slug:org_slug>/members/",
        MemberListView.as_view(),
        name="org-members",
    ),
    path(
        "orgs/<slug:org_slug>/members/invite/",
        InviteView.as_view(),
        name="org-members-invite",
    ),
    path(
        "orgs/<slug:org_slug>/members/invitations/<uuid:invitation_id>/revoke/",
        RevokeInvitationView.as_view(),
        name="org-members-invitation-revoke",
    ),
    path(
        "orgs/<slug:org_slug>/settings/",
        OrgSettingsView.as_view(),
        name="org-settings",
    ),
]
