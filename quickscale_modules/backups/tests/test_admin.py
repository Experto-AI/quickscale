"""Tests for backups module admin configuration."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import patch

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import FileResponse, HttpRequest
from django.test import Client, RequestFactory
from django.urls import reverse

from quickscale_modules_backups.admin import BackupArtifactAdmin, BackupPolicyAdmin
from quickscale_modules_backups.models import BackupArtifact, BackupPolicy

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser


def _policy_admin() -> BackupPolicyAdmin:
    """Return the registered policy admin with a concrete type."""
    return cast(BackupPolicyAdmin, admin.site._registry[BackupPolicy])


def _artifact_admin() -> BackupArtifactAdmin:
    """Return the registered artifact admin with a concrete type."""
    return cast(BackupArtifactAdmin, admin.site._registry[BackupArtifact])


def _attach_messages(request: HttpRequest) -> None:
    """Attach session-backed message storage to a factory request."""
    session_middleware = SessionMiddleware(lambda response: response)
    session_middleware.process_request(request)
    request.session.save()
    setattr(request, "_messages", FallbackStorage(request))


@pytest.mark.django_db
class TestAdminRegistration:
    """Admin registration coverage for the backups module."""

    def test_policy_model_is_registered(self) -> None:
        assert admin.site.is_registered(BackupPolicy)

    def test_artifact_model_is_registered(self) -> None:
        assert admin.site.is_registered(BackupArtifact)


@pytest.mark.django_db
class TestBackupPolicyAdmin:
    """Tests for policy admin actions and singleton behavior."""

    def test_has_add_permission_is_disabled_even_without_existing_policy(
        self,
        superuser: AbstractBaseUser,
    ) -> None:
        policy_admin = _policy_admin()
        request = RequestFactory().get("/admin/")
        request.user = superuser

        assert policy_admin.has_add_permission(request) is False

    def test_policy_snapshot_fields_are_all_read_only(
        self,
        backup_policy: BackupPolicy,
        superuser: AbstractBaseUser,
    ) -> None:
        policy_admin = _policy_admin()
        request = RequestFactory().get("/admin/")
        request.user = superuser

        readonly_fields = policy_admin.get_readonly_fields(request, backup_policy)
        model_field_names = [field.name for field in BackupPolicy._meta.fields]

        assert set(model_field_names).issubset(set(readonly_fields))
        assert "authoritative_source_notice" in readonly_fields
        assert "command_driven_notice" in readonly_fields
        assert "restore_notice" in readonly_fields

    def test_has_delete_permission_is_disabled(
        self,
        backup_policy: BackupPolicy,
        superuser: AbstractBaseUser,
    ) -> None:
        policy_admin = _policy_admin()
        request = RequestFactory().get("/admin/")
        request.user = superuser

        assert policy_admin.has_delete_permission(request, backup_policy) is False

    def test_change_view_is_read_only_and_explains_authoritative_source(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
    ) -> None:
        response = admin_client.get(
            reverse(
                "admin:quickscale_modules_backups_backuppolicy_change",
                args=[backup_policy.pk],
            )
        )

        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert "quickscale apply" in content
        assert "read-only snapshot" in content
        assert 'name="_save"' not in content
        assert 'class="deletelink"' not in content

    def test_policy_changelist_exposes_operator_buttons(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
    ) -> None:
        response = admin_client.get(
            reverse("admin:quickscale_modules_backups_backuppolicy_changelist")
        )

        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert "Create backup now" in content
        assert "Prune expired backups" in content
        assert (
            reverse("admin:quickscale_modules_backups_backuppolicy_create") in content
        )
        assert reverse("admin:quickscale_modules_backups_backuppolicy_prune") in content

    @pytest.mark.parametrize(
        ("url_name", "patched_symbol"),
        [
            (
                "admin:quickscale_modules_backups_backuppolicy_create",
                "quickscale_modules_backups.admin.create_backup",
            ),
            (
                "admin:quickscale_modules_backups_backuppolicy_prune",
                "quickscale_modules_backups.admin.prune_expired_backups",
            ),
        ],
    )
    def test_operator_endpoints_ignore_get_requests(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        url_name: str,
        patched_symbol: str,
    ) -> None:
        with patch(patched_symbol) as mocked_operation:
            response = admin_client.get(reverse(url_name))

        assert response.status_code == 302
        assert response.url == reverse(
            "admin:quickscale_modules_backups_backuppolicy_changelist"
        )
        mocked_operation.assert_not_called()

    def test_create_backup_now_reports_success(
        self,
        backup_policy: BackupPolicy,
        superuser: AbstractBaseUser,
    ) -> None:
        policy_admin = _policy_admin()
        request = RequestFactory().post("/admin/")
        request.user = superuser
        _attach_messages(request)

        fake_artifact = BackupArtifact(
            filename="db-project-local-20260326T120000Z.json",
            checksum_sha256="abc",
            size_bytes=1,
            backup_format="json",
            database_engine="django.db.backends.sqlite3",
            database_name="test.sqlite3",
        )

        with patch(
            "quickscale_modules_backups.admin.create_backup", return_value=fake_artifact
        ):
            policy_admin.create_backup_now(request, BackupPolicy.objects.all())

    def test_create_backup_now_button_runs_from_custom_operator_endpoint(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
    ) -> None:
        fake_artifact = BackupArtifact(
            filename="db-project-local-20260326T120000Z.json",
            checksum_sha256="abc",
            size_bytes=1,
            backup_format="json",
            database_engine="django.db.backends.sqlite3",
            database_name="test.sqlite3",
        )

        with patch(
            "quickscale_modules_backups.admin.create_backup", return_value=fake_artifact
        ) as mocked_create:
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_create"),
                follow=True,
            )

        assert response.status_code == 200
        mocked_create.assert_called_once()
        assert [message.message for message in get_messages(response.wsgi_request)] == [
            "Created backup artifact db-project-local-20260326T120000Z.json"
        ]

    def test_prune_expired_backups_action_runs_from_admin_changelist(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
    ) -> None:
        changelist_url = reverse(
            "admin:quickscale_modules_backups_backuppolicy_changelist"
        )

        with patch(
            "quickscale_modules_backups.admin.prune_expired_backups",
            return_value=2,
        ) as mocked_prune:
            response = admin_client.post(
                changelist_url,
                {
                    "action": "prune_expired_backups_now",
                    admin.helpers.ACTION_CHECKBOX_NAME: [str(backup_policy.pk)],
                    "index": 0,
                },
                follow=True,
            )

        assert response.status_code == 200
        mocked_prune.assert_called_once_with()
        assert [message.message for message in get_messages(response.wsgi_request)] == [
            "Pruned 2 expired backup artifact(s)."
        ]

    def test_prune_expired_backups_button_runs_from_custom_operator_endpoint(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
    ) -> None:
        with patch(
            "quickscale_modules_backups.admin.prune_expired_backups",
            return_value=2,
        ) as mocked_prune:
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_prune"),
                follow=True,
            )

        assert response.status_code == 200
        mocked_prune.assert_called_once_with()
        assert [message.message for message in get_messages(response.wsgi_request)] == [
            "Pruned 2 expired backup artifact(s)."
        ]


@pytest.mark.django_db
class TestBackupArtifactAdmin:
    """Tests for artifact admin actions and download handling."""

    def test_nonstaff_user_is_denied_artifact_changelist(self) -> None:
        user = get_user_model().objects.create_user(
            username="backups-operator",
            email="backups-operator@example.com",
            password="operatorpass123",
        )
        client = Client()
        client.force_login(user)

        response = client.get(
            reverse("admin:quickscale_modules_backups_backupartifact_changelist")
        )

        assert response.status_code == 302
        assert response.url.startswith(reverse("admin:login"))

    def test_change_view_renders_download_link(
        self,
        admin_client: Client,
        backup_artifact: BackupArtifact,
    ) -> None:
        response = admin_client.get(
            reverse(
                "admin:quickscale_modules_backups_backupartifact_change",
                args=[backup_artifact.pk],
            )
        )

        assert response.status_code == 200
        assert "Download" in response.content.decode("utf-8")

    def test_metadata_pretty_escapes_embedded_html(
        self,
        backup_artifact: BackupArtifact,
    ) -> None:
        backup_artifact.metadata_json = {
            "danger": "<script>alert('xss')</script>",
            "note": "safe",
        }

        artifact_admin = _artifact_admin()

        rendered = artifact_admin.metadata_pretty(backup_artifact)

        assert rendered.startswith("<pre>")
        assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in rendered
        assert "<script>alert('xss')</script>" not in rendered

    def test_validate_selected_backups_updates_status(
        self,
        backup_artifact: BackupArtifact,
        superuser: AbstractBaseUser,
    ) -> None:
        backup_artifact.checksum_sha256 = hashlib.sha256(
            Path(backup_artifact.local_path).read_bytes()
        ).hexdigest()
        backup_artifact.save(update_fields=["checksum_sha256", "updated_at"])

        artifact_admin = _artifact_admin()
        request = RequestFactory().post("/admin/")
        request.user = superuser
        _attach_messages(request)

        artifact_admin.validate_selected_backups(
            request,
            BackupArtifact.objects.filter(pk=backup_artifact.pk),
        )

        backup_artifact.refresh_from_db()
        assert backup_artifact.status == BackupArtifact.STATUS_VALIDATED

    def test_download_view_streams_local_file(
        self,
        backup_artifact: BackupArtifact,
        superuser: AbstractBaseUser,
    ) -> None:
        artifact_admin = _artifact_admin()
        request = RequestFactory().get("/admin/")
        request.user = superuser

        response = artifact_admin.download_view(request, backup_artifact.pk)

        assert isinstance(response, FileResponse)
        assert response.status_code == 200

    def test_nonstaff_user_is_denied_download_view(
        self,
        backup_artifact: BackupArtifact,
    ) -> None:
        user = get_user_model().objects.create_user(
            username="backups-reader",
            email="backups-reader@example.com",
            password="readerpass123",
        )
        client = Client()
        client.force_login(user)

        response = client.get(
            reverse(
                "admin:quickscale_modules_backups_backupartifact_download",
                args=[backup_artifact.pk],
            )
        )

        assert response.status_code == 302
        assert response.url.startswith(reverse("admin:login"))

    def test_download_link_is_unavailable_for_deleted_artifact(
        self,
        backup_artifact: BackupArtifact,
    ) -> None:
        backup_artifact.status = BackupArtifact.STATUS_DELETED
        backup_artifact.save(update_fields=["status", "updated_at"])

        artifact_admin = _artifact_admin()

        assert artifact_admin.download_link(backup_artifact) == "Unavailable"

    def test_download_link_is_unavailable_when_local_file_is_missing(
        self,
        backup_artifact: BackupArtifact,
    ) -> None:
        Path(backup_artifact.local_path).unlink()

        artifact_admin = _artifact_admin()

        assert artifact_admin.download_link(backup_artifact) == "Unavailable"

    def test_download_view_redirects_deleted_artifact_without_resolving_path(
        self,
        backup_artifact: BackupArtifact,
        superuser: AbstractBaseUser,
    ) -> None:
        backup_artifact.status = BackupArtifact.STATUS_DELETED
        backup_artifact.save(update_fields=["status", "updated_at"])

        artifact_admin = _artifact_admin()
        request = RequestFactory().get("/admin/")
        request.user = superuser
        _attach_messages(request)

        with patch("quickscale_modules_backups.admin.download_backup_path") as mocked:
            response = artifact_admin.download_view(request, backup_artifact.pk)

        assert response.status_code == 302
        assert response.url == reverse(
            "admin:quickscale_modules_backups_backupartifact_change",
            args=[backup_artifact.pk],
        )
        mocked.assert_not_called()

    def test_download_view_redirects_missing_file_without_resolving_path(
        self,
        backup_artifact: BackupArtifact,
        superuser: AbstractBaseUser,
    ) -> None:
        Path(backup_artifact.local_path).unlink()

        artifact_admin = _artifact_admin()
        request = RequestFactory().get("/admin/")
        request.user = superuser
        _attach_messages(request)

        with patch("quickscale_modules_backups.admin.download_backup_path") as mocked:
            response = artifact_admin.download_view(request, backup_artifact.pk)

        assert response.status_code == 302
        assert response.url == reverse(
            "admin:quickscale_modules_backups_backupartifact_change",
            args=[backup_artifact.pk],
        )
        mocked.assert_not_called()

    def test_delete_model_removes_local_file(
        self,
        backup_artifact: BackupArtifact,
        superuser: AbstractBaseUser,
    ) -> None:
        artifact_admin = _artifact_admin()
        request = RequestFactory().post("/admin/")
        request.user = superuser
        local_path = Path(backup_artifact.local_path)

        artifact_admin.delete_model(request, backup_artifact)

        assert not local_path.exists()
        assert not BackupArtifact.objects.filter(pk=backup_artifact.pk).exists()
