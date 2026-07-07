"""Tests for backups module admin configuration."""

from __future__ import annotations

import hashlib
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.conf import settings
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.http import FileResponse, HttpRequest
from django.test import Client, RequestFactory
from django.urls import reverse

from quickscale_modules_backups.admin import (
    BackupArtifactAdmin,
    BackupPolicyAdmin,
    BackupPolicyRestoreForm,
)
from quickscale_modules_backups.models import (
    BackupArtifact,
    BackupPolicy,
    BackupSnapshot,
)
from quickscale_modules_backups.services import (
    BackupError,
    BackupRestoreBlocked,
    RestoreResult,
    StagedAdminRestoreUpload,
)

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


def _place_artifact_in_authoritative_root(artifact: BackupArtifact) -> Path:
    """Move one artifact file into the configured authoritative backup root."""
    root = Path(str(getattr(settings, "QUICKSCALE_BACKUPS_LOCAL_DIRECTORY", "")))
    if not root.is_absolute():
        root = Path(getattr(settings, "BASE_DIR", Path.cwd())) / root
    root.mkdir(parents=True, exist_ok=True)

    source_path = Path(artifact.local_path)
    target_path = root / artifact.filename
    target_path.write_bytes(source_path.read_bytes())
    artifact.local_path = str(target_path)
    artifact.checksum_sha256 = hashlib.sha256(target_path.read_bytes()).hexdigest()
    artifact.size_bytes = target_path.stat().st_size
    artifact.save(
        update_fields=["local_path", "checksum_sha256", "size_bytes", "updated_at"]
    )
    return target_path


def _make_staff_user(username: str, *permission_codenames: str) -> AbstractBaseUser:
    """Create a staff user with the requested backups-model permissions."""
    user = get_user_model().objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="staffpass123",
        is_staff=True,
    )
    if permission_codenames:
        permissions = [
            Permission.objects.get(
                content_type__app_label="quickscale_modules_backups",
                codename=codename,
            )
            for codename in permission_codenames
        ]
        user.user_permissions.add(*permissions)
    return user


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
        assert "Restore backup" in content
        assert "Prune expired backups" in content
        assert (
            reverse("admin:quickscale_modules_backups_backuppolicy_create") in content
        )
        assert (
            reverse("admin:quickscale_modules_backups_backuppolicy_restore") in content
        )
        assert reverse("admin:quickscale_modules_backups_backuppolicy_prune") in content

    def test_policy_changelist_hides_change_only_controls_for_view_only_user(
        self,
        backup_policy: BackupPolicy,
    ) -> None:
        del backup_policy
        user = _make_staff_user(
            "backups-staff-policy-view-only",
            "view_backuppolicy",
        )
        client = Client()
        client.force_login(user)

        response = client.get(
            reverse("admin:quickscale_modules_backups_backuppolicy_changelist")
        )

        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert "Create backup now" not in content
        assert "Prune expired backups" not in content
        assert "Restore backup" in content
        assert (
            reverse("admin:quickscale_modules_backups_backuppolicy_restore") in content
        )

    def test_restore_page_renders_guarded_local_restore_workflow(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        del backup_policy
        response = admin_client.get(
            reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
            {"artifact_id": str(postgresql_backup_artifact.pk)},
        )

        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert "Restore backup artifact" in content
        assert "Dry-run validation" in content
        assert "Restore backup" in content
        assert postgresql_backup_artifact.filename in content
        assert postgresql_backup_artifact.local_path in content
        assert "Selected artifact:" in content
        assert "Eligible local artifacts" in content
        assert "Uploaded backup file" in content
        assert "remote-only artifacts" in content

    @pytest.mark.parametrize(
        ("permission_codenames", "expect_artifact_inventory"),
        [
            (("view_backuppolicy",), False),
            (("view_backuppolicy", "view_backupartifact"), True),
        ],
    )
    def test_restore_page_artifact_inventory_follows_artifact_view_permission(
        self,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
        permission_codenames: tuple[str, ...],
        expect_artifact_inventory: bool,
    ) -> None:
        del backup_policy
        user = _make_staff_user(
            f"backups-staff-restore-matrix-{'-'.join(permission_codenames)}",
            *permission_codenames,
        )
        client = Client()
        client.force_login(user)

        response = client.get(
            reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
            {"artifact_id": str(postgresql_backup_artifact.pk)},
        )

        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert "Restore backup artifact" in content
        assert "Uploaded backup file" in content
        if expect_artifact_inventory:
            assert postgresql_backup_artifact.filename in content
            assert postgresql_backup_artifact.local_path in content
            assert "Eligible local artifacts" in content
            assert "Selected artifact:" in content
            assert "Restore source" in content
        else:
            assert postgresql_backup_artifact.filename not in content
            assert postgresql_backup_artifact.local_path not in content
            assert "Eligible local artifacts" not in content
            assert "Selected artifact:" not in content
            assert "Restore source" not in content
            assert (
                "Recorded local artifacts are hidden on this page because your current"
                in content
            )

    def test_restore_submission_rejects_recorded_artifact_mode_without_artifact_permission(
        self,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        user = _make_staff_user(
            "backups-staff-restore-change-no-artifact-view",
            "change_backuppolicy",
        )
        client = Client()
        client.force_login(user)

        with patch(
            "quickscale_modules_backups.admin.restore_backup_artifact"
        ) as mocked_restore:
            response = client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "source_mode": BackupPolicyRestoreForm.SOURCE_MODE_RECORDED_ARTIFACT,
                    "artifact_id": str(postgresql_backup_artifact.pk),
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "dry_run",
                },
            )

        assert response.status_code == 200
        mocked_restore.assert_not_called()
        assert (
            "Recorded local artifacts are unavailable for your current permissions."
            in response.content.decode("utf-8")
        )

    def test_restore_page_routes_uploaded_file_through_trusted_admin_service(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        del backup_policy
        uploaded_file = SimpleUploadedFile(
            "operator-upload.dump",
            b"PGDMP\x01\x0e\x00trusted upload bytes",
        )

        with (
            patch(
                "quickscale_modules_backups.admin.restore_admin_uploaded_backup",
                return_value=RestoreResult(
                    executed=False,
                    dry_run=True,
                    message="Restore validation completed successfully (dry run).",
                ),
            ) as mocked_uploaded_restore,
            patch(
                "quickscale_modules_backups.admin.restore_backup_artifact"
            ) as mocked_recorded_restore,
        ):
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "source_mode": BackupPolicyRestoreForm.SOURCE_MODE_UPLOADED_FILE,
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "dry_run",
                    "uploaded_file": uploaded_file,
                },
                follow=True,
            )

        assert response.status_code == 200
        mocked_recorded_restore.assert_not_called()
        assert mocked_uploaded_restore.call_count == 1
        args, kwargs = mocked_uploaded_restore.call_args
        assert args[0].name == "operator-upload.dump"
        assert kwargs == {
            "confirmation": postgresql_backup_artifact.filename,
            "dry_run": True,
        }
        assert [message.message for message in get_messages(response.wsgi_request)] == [
            "Restore validation completed successfully (dry run)."
        ]

    def test_restore_page_denies_staff_user_without_backups_permissions(
        self,
    ) -> None:
        user = get_user_model().objects.create_user(
            username="backups-staff-no-restore-access",
            email="backups-staff-no-restore-access@example.com",
            password="staffpass123",
            is_staff=True,
        )
        client = Client()
        client.force_login(user)

        response = client.get(
            reverse("admin:quickscale_modules_backups_backuppolicy_restore")
        )

        assert response.status_code == 403

    def test_restore_submission_denies_staff_user_without_change_permission(
        self,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        user = get_user_model().objects.create_user(
            username="backups-staff-no-restore-change",
            email="backups-staff-no-restore-change@example.com",
            password="staffpass123",
            is_staff=True,
        )
        client = Client()
        client.force_login(user)

        with patch(
            "quickscale_modules_backups.admin.restore_backup_artifact"
        ) as mocked_restore:
            response = client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "artifact_id": str(postgresql_backup_artifact.pk),
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "dry_run",
                },
            )

        assert response.status_code == 403
        mocked_restore.assert_not_called()

    @pytest.mark.parametrize(
        ("label", "url_name", "patched_symbol", "needs_artifact"),
        [
            (
                "create",
                "admin:quickscale_modules_backups_backuppolicy_create",
                "quickscale_modules_backups.admin.create_backup",
                False,
            ),
            (
                "prune",
                "admin:quickscale_modules_backups_backuppolicy_prune",
                "quickscale_modules_backups.admin.prune_expired_backups",
                False,
            ),
            (
                "download",
                "admin:quickscale_modules_backups_backupartifact_download",
                "quickscale_modules_backups.admin.download_backup_path",
                True,
            ),
        ],
    )
    def test_direct_operator_urls_deny_staff_user_without_required_permissions(
        self,
        backup_artifact: BackupArtifact,
        label: str,
        url_name: str,
        patched_symbol: str,
        needs_artifact: bool,
    ) -> None:
        user = _make_staff_user(
            f"backups-staff-{label}-direct-url-view-only",
            "view_backuppolicy",
        )
        client = Client()
        client.force_login(user)

        if needs_artifact:
            url = reverse(url_name, args=[backup_artifact.pk])
        else:
            url = reverse(url_name)

        with patch(patched_symbol) as mocked_operation:
            response = client.get(url)

        assert response.status_code == 403
        mocked_operation.assert_not_called()

    @pytest.mark.parametrize(
        ("action_name", "patched_symbol"),
        [
            (
                "create_backup_now",
                "quickscale_modules_backups.admin.create_backup",
            ),
            (
                "prune_expired_backups_now",
                "quickscale_modules_backups.admin.prune_expired_backups",
            ),
        ],
    )
    def test_changelist_actions_deny_view_only_user_without_change_permission(
        self,
        backup_policy: BackupPolicy,
        action_name: str,
        patched_symbol: str,
    ) -> None:
        user = _make_staff_user(
            f"backups-staff-{action_name}-action-view-only",
            "view_backuppolicy",
        )
        client = Client()
        client.force_login(user)

        with patch(patched_symbol) as mocked_operation:
            response = client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_changelist"),
                {
                    "action": action_name,
                    admin.helpers.ACTION_CHECKBOX_NAME: [str(backup_policy.pk)],
                    "index": 0,
                },
            )

        assert response.status_code == 403
        mocked_operation.assert_not_called()

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

    def test_restore_notice_mentions_file_mode_without_broadening_admin_surface(
        self,
        backup_policy: BackupPolicy,
    ) -> None:
        policy_admin = _policy_admin()

        notice = policy_admin.restore_notice(backup_policy)

        assert "--file PATH" in notice
        assert "exact filename" in notice
        assert "Remote-only artifacts are never materialized through admin" in notice

    def test_restore_page_reports_confirmation_failure(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        del backup_policy
        response = admin_client.post(
            reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
            {
                "artifact_id": str(postgresql_backup_artifact.pk),
                "confirmation": f"{postgresql_backup_artifact.filename}-wrong",
                "operation": "dry_run",
            },
        )

        assert response.status_code == 200
        assert (
            "Confirmation must exactly match the backup filename."
            in response.content.decode("utf-8")
        )

    @pytest.mark.parametrize(
        ("artifact_kind", "expected_error"),
        [
            (
                "remote_only",
                "Admin restore only supports row-backed local artifacts already present on disk.",
            ),
            (
                "missing_local",
                "The selected local backup artifact is no longer present on disk, and admin restore will not materialize remote-only artifacts.",
            ),
        ],
    )
    def test_restore_page_rejects_ineligible_local_restore_submissions(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
        artifact_kind: str,
        expected_error: str,
    ) -> None:
        del backup_policy
        if artifact_kind == "remote_only":
            postgresql_backup_artifact.local_path = ""
            postgresql_backup_artifact.storage_target = (
                BackupArtifact.STORAGE_TARGET_PRIVATE_REMOTE
            )
            postgresql_backup_artifact.remote_key = (
                "private/backups/remote-artifact.dump"
            )
            postgresql_backup_artifact.save(
                update_fields=[
                    "local_path",
                    "storage_target",
                    "remote_key",
                    "updated_at",
                ]
            )
        else:
            Path(postgresql_backup_artifact.local_path).unlink()

        with patch(
            "quickscale_modules_backups.admin.restore_backup_artifact"
        ) as mocked_restore:
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "artifact_id": str(postgresql_backup_artifact.pk),
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                },
            )

        assert response.status_code == 200
        mocked_restore.assert_not_called()
        assert expected_error in response.content.decode("utf-8")

    def test_restore_page_dispatches_restore_asynchronously(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        """SA20: Admin-triggered restore is dispatched async via subprocess.

        The artifact should transition to STATUS_RESTORING immediately, and the
        management command is invoked in the background. The admin returns to the
        changelist with an initiation message instead of blocking on the restore.
        """
        del backup_policy

        with patch(
            "quickscale_modules_backups.services.subprocess.Popen",
            return_value=MagicMock(),
        ) as mocked_popen:
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "artifact_id": str(postgresql_backup_artifact.pk),
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                },
                follow=True,
            )

        assert response.status_code == 200
        postgresql_backup_artifact.refresh_from_db()
        assert postgresql_backup_artifact.status == BackupArtifact.STATUS_RESTORING
        assert postgresql_backup_artifact.restore_started_at is not None
        assert postgresql_backup_artifact.restore_error == ""

        mocked_popen.assert_called_once()
        popen_args = mocked_popen.call_args[0][0]
        assert "backups_restore" in popen_args
        assert str(postgresql_backup_artifact.pk) in popen_args
        assert "--confirm" in popen_args
        assert postgresql_backup_artifact.filename in popen_args
        # CR-SA20-006: admin dispatch always includes --local-only
        assert "--local-only" in popen_args

        assert [message.message for message in get_messages(response.wsgi_request)] == [
            (
                "Restore has been initiated in the background. Check the artifact's "
                "status for progress or errors."
            ),
        ]

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

    def test_create_backup_now_button_reports_backup_errors(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
    ) -> None:
        with patch(
            "quickscale_modules_backups.admin.create_backup",
            side_effect=BackupError(
                "Required executable 'pg_dump' is not installed in this runtime."
            ),
        ) as mocked_create:
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_create"),
                follow=True,
            )

        assert response.status_code == 200
        mocked_create.assert_called_once()
        assert [message.message for message in get_messages(response.wsgi_request)] == [
            "Backup creation failed: Required executable 'pg_dump' is not installed in this runtime."
        ]

    def test_prune_operator_endpoint_allows_staff_user_with_change_permission(
        self,
        backup_policy: BackupPolicy,
    ) -> None:
        del backup_policy
        user = _make_staff_user(
            "backups-staff-prune-custom-url-change",
            "change_backuppolicy",
        )
        client = Client()
        client.force_login(user)

        with patch(
            "quickscale_modules_backups.admin.prune_expired_backups",
            return_value=2,
        ) as mocked_prune:
            response = client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_prune"),
                follow=True,
            )

        assert response.status_code == 200
        mocked_prune.assert_called_once_with()
        assert [message.message for message in get_messages(response.wsgi_request)] == [
            "Pruned 2 expired backup artifact(s)."
        ]

    def test_create_backup_action_allows_staff_user_with_change_permission(
        self,
        backup_policy: BackupPolicy,
    ) -> None:
        user = _make_staff_user(
            "backups-staff-create-action-change",
            "change_backuppolicy",
        )
        client = Client()
        client.force_login(user)
        fake_artifact = BackupArtifact(
            filename="db-project-local-20260326T120000Z.json",
            checksum_sha256="abc",
            size_bytes=1,
            backup_format="json",
            database_engine="django.db.backends.sqlite3",
            database_name="test.sqlite3",
        )

        with patch(
            "quickscale_modules_backups.admin.create_backup",
            return_value=fake_artifact,
        ) as mocked_create:
            response = client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_changelist"),
                {
                    "action": "create_backup_now",
                    admin.helpers.ACTION_CHECKBOX_NAME: [str(backup_policy.pk)],
                    "index": 0,
                },
                follow=True,
            )

        assert response.status_code == 200
        mocked_create.assert_called_once_with(initiated_by=user, trigger="admin")
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

    # ------------------------------------------------------------------
    # SA20 regression: uploaded-file restore through trusted seam
    # ------------------------------------------------------------------

    def test_restore_page_dispatches_uploaded_restore_through_trusted_seam(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
        postgresql_artifact_file: Path,
    ) -> None:
        """SA20: Uploaded-file restore dispatch routes through the trusted seam.

        The uploaded content goes through the shared staging + trusted resolver
        (not inline candidate selection).  The dispatch uses the artifact-id path
        (not --file) and persists STATUS_RESTORING only after successful spawn.
        """
        del backup_policy
        content = postgresql_artifact_file.read_bytes()
        uploaded_file = SimpleUploadedFile(
            postgresql_backup_artifact.filename,
            content,
        )

        staged = StagedAdminRestoreUpload(
            local_path=postgresql_artifact_file,
            checksum_sha256=postgresql_backup_artifact.checksum_sha256,
            size_bytes=postgresql_backup_artifact.size_bytes,
        )

        with (
            patch(
                ("quickscale_modules_backups.services._stage_admin_restore_upload"),
                return_value=staged,
            ) as mocked_stage,
            patch(
                (
                    "quickscale_modules_backups.services."
                    "_resolve_admin_uploaded_restore_artifact"
                ),
                return_value=postgresql_backup_artifact,
            ) as mocked_resolve,
            patch(
                "quickscale_modules_backups.services.subprocess.Popen",
                return_value=MagicMock(),
            ) as mocked_popen,
        ):
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "source_mode": BackupPolicyRestoreForm.SOURCE_MODE_UPLOADED_FILE,
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                    "uploaded_file": uploaded_file,
                },
                follow=True,
            )

        assert response.status_code == 200
        mocked_stage.assert_called_once()
        mocked_resolve.assert_called_once_with(
            checksum_sha256=postgresql_backup_artifact.checksum_sha256,
            size_bytes=postgresql_backup_artifact.size_bytes,
        )
        postgresql_backup_artifact.refresh_from_db()
        assert postgresql_backup_artifact.status == BackupArtifact.STATUS_RESTORING
        assert postgresql_backup_artifact.restore_started_at is not None
        assert postgresql_backup_artifact.restore_error == ""

        mocked_popen.assert_called_once()
        popen_args = mocked_popen.call_args[0][0]
        assert "backups_restore" in popen_args
        assert str(postgresql_backup_artifact.pk) in popen_args
        assert "--file" not in popen_args  # artifact-id, not --file
        assert "--confirm" in popen_args
        assert postgresql_backup_artifact.filename in popen_args
        # CR-SA20-006: admin dispatch always includes --local-only
        assert "--local-only" in popen_args

        assert [message.message for message in get_messages(response.wsgi_request)] == [
            (
                "Restore has been initiated in the background. Check the "
                "artifact's status for progress or errors."
            ),
        ]

    def test_restore_page_rejects_uploaded_file_with_no_matching_artifact(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
    ) -> None:
        """SA20: Uploaded file with no matching artifact by checksum+size raises."""
        del backup_policy
        uploaded_file = SimpleUploadedFile(
            "unknown.dump",
            b"no artifact anywhere has this checksum",
        )

        with patch(
            "quickscale_modules_backups.admin.restore_backup_artifact"
        ) as mocked_restore:
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "source_mode": BackupPolicyRestoreForm.SOURCE_MODE_UPLOADED_FILE,
                    "confirmation": "unknown.dump",
                    "operation": "restore",
                    "uploaded_file": uploaded_file,
                },
            )

        assert response.status_code == 200
        mocked_restore.assert_not_called()
        assert "does not match any recorded authoritative" in response.content.decode(
            "utf-8"
        )

    def test_restore_uploaded_file_rejects_artifact_with_status_restoring(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
        postgresql_artifact_file: Path,
    ) -> None:
        """CR-SA20-REV-001: Uploaded-file restore rejects already-RESTORING artifacts.

        Parity regression matching the recorded-artifact branch's
        _get_admin_restore_ineligible_reason guard.
        """
        del backup_policy
        content = postgresql_artifact_file.read_bytes()
        uploaded_file = SimpleUploadedFile(
            postgresql_backup_artifact.filename,
            content,
        )

        staged = StagedAdminRestoreUpload(
            local_path=postgresql_artifact_file,
            checksum_sha256=postgresql_backup_artifact.checksum_sha256,
            size_bytes=postgresql_backup_artifact.size_bytes,
        )

        # Set the artifact to STATUS_RESTORING so the uploaded-file guard
        # fires before copy or Popen.
        postgresql_backup_artifact.status = BackupArtifact.STATUS_RESTORING
        postgresql_backup_artifact.save(update_fields=["status", "updated_at"])

        with (
            patch(
                ("quickscale_modules_backups.services._stage_admin_restore_upload"),
                return_value=staged,
            ),
            patch(
                (
                    "quickscale_modules_backups.services."
                    "_resolve_admin_uploaded_restore_artifact"
                ),
                return_value=postgresql_backup_artifact,
            ),
            patch(
                "quickscale_modules_backups.services.subprocess.Popen",
            ) as mocked_popen,
        ):
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "source_mode": (BackupPolicyRestoreForm.SOURCE_MODE_UPLOADED_FILE),
                    "confirmation": (postgresql_backup_artifact.filename),
                    "operation": "restore",
                    "uploaded_file": uploaded_file,
                },
            )

        assert response.status_code == 200
        mocked_popen.assert_not_called()
        postgresql_backup_artifact.refresh_from_db()
        # Status must still be STATUS_RESTORING — unchanged by the rejected
        # attempt (the guard fires before the dispatch code transitions it).
        assert postgresql_backup_artifact.status == BackupArtifact.STATUS_RESTORING
        assert (
            "This backup artifact is currently being restored."
            in response.content.decode("utf-8")
        )

    # ------------------------------------------------------------------
    # SA20 regression: spawn-failure rollback (no stranded STATUS_RESTORING)
    # ------------------------------------------------------------------

    def test_restore_page_does_not_strand_status_restoring_on_spawn_failure(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        """SA20: When subprocess.Popen raises, STATUS_RESTORING is not persisted."""
        del backup_policy
        original_status = postgresql_backup_artifact.status

        with patch(
            "quickscale_modules_backups.services.subprocess.Popen",
            side_effect=OSError("manage.py not found"),
        ) as mocked_popen:
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "artifact_id": str(postgresql_backup_artifact.pk),
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                },
            )

        assert response.status_code == 200
        postgresql_backup_artifact.refresh_from_db()
        assert postgresql_backup_artifact.status == original_status
        assert postgresql_backup_artifact.restore_started_at is None
        assert "Failed to initiate background restore" in response.content.decode(
            "utf-8"
        )
        mocked_popen.assert_called_once()

    def test_restore_page_cleanly_reports_uploaded_spawn_failure(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
        postgresql_artifact_file: Path,
    ) -> None:
        """SA20: Uploaded-file restore reports spawn failure without stranding."""
        del backup_policy
        content = postgresql_artifact_file.read_bytes()
        uploaded_file = SimpleUploadedFile(
            postgresql_backup_artifact.filename,
            content,
        )
        original_status = postgresql_backup_artifact.status

        staged = StagedAdminRestoreUpload(
            local_path=postgresql_artifact_file,
            checksum_sha256=postgresql_backup_artifact.checksum_sha256,
            size_bytes=postgresql_backup_artifact.size_bytes,
        )

        with (
            patch(
                ("quickscale_modules_backups.services._stage_admin_restore_upload"),
                return_value=staged,
            ),
            patch(
                (
                    "quickscale_modules_backups.services."
                    "_resolve_admin_uploaded_restore_artifact"
                ),
                return_value=postgresql_backup_artifact,
            ),
            patch(
                "quickscale_modules_backups.services.subprocess.Popen",
                side_effect=OSError("manage.py not found"),
            ) as mocked_popen,
        ):
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "source_mode": BackupPolicyRestoreForm.SOURCE_MODE_UPLOADED_FILE,
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                    "uploaded_file": uploaded_file,
                },
            )

        assert response.status_code == 200
        postgresql_backup_artifact.refresh_from_db()
        # Status must NOT have changed to STATUS_RESTORING
        assert postgresql_backup_artifact.status == original_status
        assert "Failed to initiate background restore" in response.content.decode(
            "utf-8"
        )
        mocked_popen.assert_called_once()

    # ------------------------------------------------------------------
    # CR-SA20-007: regression — parent does not clobber fast child
    # terminal status.  The new design persists STATUS_RESTORING before
    # Popen, so a child that completes during Popen (simulated here by
    # writing a terminal status inside the Popen mock) must not be
    # overwritten back to STATUS_RESTORING by the parent return path.
    # ------------------------------------------------------------------

    def test_restore_async_parent_does_not_clobber_fast_child_terminal_status(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        """CR-SA20-007: Recorded-artifact dispatch preserves fast child terminal status.

        The mock simulates a child that completes immediately inside the
        Popen call, setting STATUS_FAILED before the parent return path
        can run.  The parent must not overwrite this terminal state back
        to STATUS_RESTORING.
        """
        del backup_policy

        def _simulate_fast_child_first(*args: object, **kwargs: object) -> MagicMock:
            """Simulate a child that writes terminal status before parent returns."""
            postgresql_backup_artifact.refresh_from_db()
            # Child sees STATUS_RESTORING (parent set it before Popen)
            # and transitions to STATUS_FAILED.
            postgresql_backup_artifact.status = BackupArtifact.STATUS_FAILED
            postgresql_backup_artifact.restore_error = "simulated fast child failure"
            postgresql_backup_artifact.save(
                update_fields=["status", "restore_error", "updated_at"]
            )
            return MagicMock()

        with patch(
            "quickscale_modules_backups.services.subprocess.Popen",
            side_effect=_simulate_fast_child_first,
        ) as mocked_popen:
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "artifact_id": str(postgresql_backup_artifact.pk),
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                },
                follow=True,
            )

        assert response.status_code == 200
        postgresql_backup_artifact.refresh_from_db()
        # The child's terminal STATUS_FAILED must be preserved.  In the
        # old design (STATUS_RESTORING after Popen) the parent would
        # overwrite this back to STATUS_RESTORING.  In the new design
        # (STATUS_RESTORING before Popen) the parent never writes the
        # status again after Popen returns.
        assert postgresql_backup_artifact.status == BackupArtifact.STATUS_FAILED
        assert (
            "simulated fast child failure" in postgresql_backup_artifact.restore_error
        )
        mocked_popen.assert_called_once()

    def test_restore_async_upload_parent_does_not_clobber_fast_child_terminal_status(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
        postgresql_artifact_file: Path,
    ) -> None:
        """CR-SA20-007: Uploaded-file dispatch preserves fast child terminal status."""
        del backup_policy
        content = postgresql_artifact_file.read_bytes()
        uploaded_file = SimpleUploadedFile(
            postgresql_backup_artifact.filename,
            content,
        )

        staged = StagedAdminRestoreUpload(
            local_path=postgresql_artifact_file,
            checksum_sha256=postgresql_backup_artifact.checksum_sha256,
            size_bytes=postgresql_backup_artifact.size_bytes,
        )

        def _simulate_fast_child_first(*args: object, **kwargs: object) -> MagicMock:
            postgresql_backup_artifact.refresh_from_db()
            postgresql_backup_artifact.status = BackupArtifact.STATUS_FAILED
            postgresql_backup_artifact.restore_error = "simulated fast child failure"
            postgresql_backup_artifact.save(
                update_fields=["status", "restore_error", "updated_at"]
            )
            return MagicMock()

        with (
            patch(
                ("quickscale_modules_backups.services._stage_admin_restore_upload"),
                return_value=staged,
            ),
            patch(
                (
                    "quickscale_modules_backups.services."
                    "_resolve_admin_uploaded_restore_artifact"
                ),
                return_value=postgresql_backup_artifact,
            ),
            patch(
                "quickscale_modules_backups.services.subprocess.Popen",
                side_effect=_simulate_fast_child_first,
            ) as mocked_popen,
        ):
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "source_mode": BackupPolicyRestoreForm.SOURCE_MODE_UPLOADED_FILE,
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                    "uploaded_file": uploaded_file,
                },
                follow=True,
            )

        assert response.status_code == 200
        postgresql_backup_artifact.refresh_from_db()
        assert postgresql_backup_artifact.status == BackupArtifact.STATUS_FAILED
        assert (
            "simulated fast child failure" in postgresql_backup_artifact.restore_error
        )
        mocked_popen.assert_called_once()

    # ------------------------------------------------------------------
    # CR-SA20-007: regression — spawn-failure rollback preserves prior
    # restore_started_at and restore_error on retry from FAILED/RESTORED
    # when Popen raises (branch-parity: recorded-artifact + uploaded)
    # ------------------------------------------------------------------

    def test_restore_spawn_failure_preserves_metadata_on_recorded_retry_from_failed(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        """CR-SA20-007: Recorded-artifact retry from FAILED preserves
        pre-spawn restore_started_at and restore_error when Popen raises."""
        del backup_policy
        prior_started_at = timezone.now() - timedelta(hours=1)
        prior_error = "Previous restore attempt failed."
        postgresql_backup_artifact.status = BackupArtifact.STATUS_FAILED
        postgresql_backup_artifact.restore_started_at = prior_started_at
        postgresql_backup_artifact.restore_error = prior_error
        postgresql_backup_artifact.save(
            update_fields=[
                "status",
                "restore_started_at",
                "restore_error",
                "updated_at",
            ]
        )

        with patch(
            "quickscale_modules_backups.services.subprocess.Popen",
            side_effect=OSError("manage.py not found"),
        ) as mocked_popen:
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "artifact_id": str(postgresql_backup_artifact.pk),
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                },
            )

        assert response.status_code == 200
        postgresql_backup_artifact.refresh_from_db()
        # Status must be restored to FAILED (pre-spawn)
        assert postgresql_backup_artifact.status == BackupArtifact.STATUS_FAILED
        # restore_started_at must be preserved from prior attempt
        assert postgresql_backup_artifact.restore_started_at == prior_started_at
        # restore_error must be preserved from prior attempt
        assert postgresql_backup_artifact.restore_error == prior_error
        assert "Failed to initiate background restore" in response.content.decode(
            "utf-8"
        )
        mocked_popen.assert_called_once()

    def test_restore_spawn_failure_preserves_metadata_on_uploaded_retry_from_failed(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
        postgresql_artifact_file: Path,
    ) -> None:
        """CR-SA20-007: Uploaded-file retry from FAILED preserves
        pre-spawn restore_started_at and restore_error when Popen raises."""
        del backup_policy
        prior_started_at = timezone.now() - timedelta(hours=2)
        prior_error = "Prior uploaded restore attempt failed."
        postgresql_backup_artifact.status = BackupArtifact.STATUS_FAILED
        postgresql_backup_artifact.restore_started_at = prior_started_at
        postgresql_backup_artifact.restore_error = prior_error
        postgresql_backup_artifact.save(
            update_fields=[
                "status",
                "restore_started_at",
                "restore_error",
                "updated_at",
            ]
        )

        content = postgresql_artifact_file.read_bytes()
        uploaded_file = SimpleUploadedFile(
            postgresql_backup_artifact.filename,
            content,
        )

        staged = StagedAdminRestoreUpload(
            local_path=postgresql_artifact_file,
            checksum_sha256=postgresql_backup_artifact.checksum_sha256,
            size_bytes=postgresql_backup_artifact.size_bytes,
        )

        with (
            patch(
                "quickscale_modules_backups.services._stage_admin_restore_upload",
                return_value=staged,
            ),
            patch(
                "quickscale_modules_backups.services._resolve_admin_uploaded_restore_artifact",
                return_value=postgresql_backup_artifact,
            ),
            patch(
                "quickscale_modules_backups.services.subprocess.Popen",
                side_effect=OSError("manage.py not found"),
            ) as mocked_popen,
        ):
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "source_mode": BackupPolicyRestoreForm.SOURCE_MODE_UPLOADED_FILE,
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                    "uploaded_file": uploaded_file,
                },
            )

        assert response.status_code == 200
        postgresql_backup_artifact.refresh_from_db()
        assert postgresql_backup_artifact.status == BackupArtifact.STATUS_FAILED
        assert postgresql_backup_artifact.restore_started_at == prior_started_at
        assert postgresql_backup_artifact.restore_error == prior_error
        assert "Failed to initiate background restore" in response.content.decode(
            "utf-8"
        )
        mocked_popen.assert_called_once()

    def test_restore_spawn_failure_preserves_metadata_on_recorded_retry_from_restored(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        """CR-SA20-007: Recorded-artifact retry from RESTORED preserves
        pre-spawn restore_started_at and restore_error when Popen raises."""
        del backup_policy
        prior_started_at = timezone.now() - timedelta(hours=3)
        # RESTORED artifacts may have an empty restore_error and prior
        # restore_started_at still set.
        prior_error = ""
        postgresql_backup_artifact.status = BackupArtifact.STATUS_RESTORED
        postgresql_backup_artifact.restore_started_at = prior_started_at
        postgresql_backup_artifact.restore_error = prior_error
        postgresql_backup_artifact.save(
            update_fields=[
                "status",
                "restore_started_at",
                "restore_error",
                "updated_at",
            ]
        )

        with patch(
            "quickscale_modules_backups.services.subprocess.Popen",
            side_effect=OSError("manage.py not found"),
        ) as mocked_popen:
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "artifact_id": str(postgresql_backup_artifact.pk),
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                },
            )

        assert response.status_code == 200
        postgresql_backup_artifact.refresh_from_db()
        assert postgresql_backup_artifact.status == BackupArtifact.STATUS_RESTORED
        assert postgresql_backup_artifact.restore_started_at == prior_started_at
        assert postgresql_backup_artifact.restore_error == prior_error
        assert "Failed to initiate background restore" in response.content.decode(
            "utf-8"
        )
        mocked_popen.assert_called_once()

    def test_restore_spawn_failure_preserves_metadata_on_uploaded_retry_from_restored(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
        postgresql_artifact_file: Path,
    ) -> None:
        """CR-SA20-007: Uploaded-file retry from RESTORED preserves
        pre-spawn restore_started_at and restore_error when Popen raises."""
        del backup_policy
        prior_started_at = timezone.now() - timedelta(hours=4)
        prior_error = ""
        postgresql_backup_artifact.status = BackupArtifact.STATUS_RESTORED
        postgresql_backup_artifact.restore_started_at = prior_started_at
        postgresql_backup_artifact.restore_error = prior_error
        postgresql_backup_artifact.save(
            update_fields=[
                "status",
                "restore_started_at",
                "restore_error",
                "updated_at",
            ]
        )

        content = postgresql_artifact_file.read_bytes()
        uploaded_file = SimpleUploadedFile(
            postgresql_backup_artifact.filename,
            content,
        )

        staged = StagedAdminRestoreUpload(
            local_path=postgresql_artifact_file,
            checksum_sha256=postgresql_backup_artifact.checksum_sha256,
            size_bytes=postgresql_backup_artifact.size_bytes,
        )

        with (
            patch(
                "quickscale_modules_backups.services._stage_admin_restore_upload",
                return_value=staged,
            ),
            patch(
                "quickscale_modules_backups.services._resolve_admin_uploaded_restore_artifact",
                return_value=postgresql_backup_artifact,
            ),
            patch(
                "quickscale_modules_backups.services.subprocess.Popen",
                side_effect=OSError("manage.py not found"),
            ) as mocked_popen,
        ):
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "source_mode": BackupPolicyRestoreForm.SOURCE_MODE_UPLOADED_FILE,
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                    "uploaded_file": uploaded_file,
                },
            )

        assert response.status_code == 200
        postgresql_backup_artifact.refresh_from_db()
        assert postgresql_backup_artifact.status == BackupArtifact.STATUS_RESTORED
        assert postgresql_backup_artifact.restore_started_at == prior_started_at
        assert postgresql_backup_artifact.restore_error == prior_error
        assert "Failed to initiate background restore" in response.content.decode(
            "utf-8"
        )
        mocked_popen.assert_called_once()

    # ------------------------------------------------------------------
    # CR-SA20-004: regression — async uploaded-file restore rejects
    # ambiguous / incomplete-snapshot cases through shared resolver
    # ------------------------------------------------------------------

    def test_restore_async_upload_rejects_ambiguous_trusted_match(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
        postgresql_artifact_file: Path,
    ) -> None:
        """Async uploaded-file restore rejects ambiguous trusted matches.

        The shared trusted resolver raises BackupRestoreBlocked when
        multiple trusted authoritative artifacts match, and the async
        branch must surface the same rejection as a user-facing form
        error instead of silently picking ``candidates[0]``.
        """
        del backup_policy
        content = postgresql_artifact_file.read_bytes()
        uploaded_file = SimpleUploadedFile(
            postgresql_backup_artifact.filename,
            content,
        )

        staged = StagedAdminRestoreUpload(
            local_path=postgresql_artifact_file,
            checksum_sha256=postgresql_backup_artifact.checksum_sha256,
            size_bytes=postgresql_backup_artifact.size_bytes,
        )

        with (
            patch(
                ("quickscale_modules_backups.services._stage_admin_restore_upload"),
                return_value=staged,
            ),
            patch(
                (
                    "quickscale_modules_backups.services."
                    "_resolve_admin_uploaded_restore_artifact"
                ),
                side_effect=BackupRestoreBlocked(
                    "Restore blocked because the uploaded backup file "
                    "matches multiple trusted authoritative backup "
                    "artifacts."
                ),
            ),
        ):
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "source_mode": BackupPolicyRestoreForm.SOURCE_MODE_UPLOADED_FILE,
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                    "uploaded_file": uploaded_file,
                },
            )

        assert response.status_code == 200
        assert (
            "matches multiple trusted authoritative backup artifacts"
            in response.content.decode("utf-8")
        )
        postgresql_backup_artifact.refresh_from_db()
        # Status must NOT have changed to STATUS_RESTORING
        assert postgresql_backup_artifact.status != BackupArtifact.STATUS_RESTORING

    def test_restore_async_upload_rejects_incomplete_snapshot_contract(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
        postgresql_artifact_file: Path,
    ) -> None:
        """Async uploaded-file restore rejects incomplete authoritative snapshot
        contracts through the shared trusted resolver, matching dry_run parity."""
        del backup_policy
        content = postgresql_artifact_file.read_bytes()
        uploaded_file = SimpleUploadedFile(
            postgresql_backup_artifact.filename,
            content,
        )

        staged = StagedAdminRestoreUpload(
            local_path=postgresql_artifact_file,
            checksum_sha256=postgresql_backup_artifact.checksum_sha256,
            size_bytes=postgresql_backup_artifact.size_bytes,
        )

        with (
            patch(
                ("quickscale_modules_backups.services._stage_admin_restore_upload"),
                return_value=staged,
            ),
            patch(
                (
                    "quickscale_modules_backups.services."
                    "_resolve_admin_uploaded_restore_artifact"
                ),
                side_effect=BackupRestoreBlocked(
                    "Restore blocked because the uploaded backup file "
                    "could not be resolved to a trusted authoritative "
                    "backup artifact: matching recorded artifact is not "
                    "linked to an authoritative snapshot."
                ),
            ),
        ):
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "source_mode": BackupPolicyRestoreForm.SOURCE_MODE_UPLOADED_FILE,
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                    "uploaded_file": uploaded_file,
                },
            )

        assert response.status_code == 200
        assert "not linked to an authoritative snapshot" in response.content.decode(
            "utf-8"
        )
        postgresql_backup_artifact.refresh_from_db()
        # Status must NOT have changed to STATUS_RESTORING
        assert postgresql_backup_artifact.status != BackupArtifact.STATUS_RESTORING

    # ------------------------------------------------------------------
    # CR-SA20-005: regression — async uploaded-file restore ignores
    # unsafe persisted local_path (out-of-tree and symlinked destinations)
    # ------------------------------------------------------------------

    def test_restore_async_upload_remaps_out_of_tree_local_path(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
        postgresql_artifact_file: Path,
        local_backup_settings: Path,
    ) -> None:
        """CR-SA20-005: Out-of-tree persisted local_path is always
        replaced by a safe path under get_local_backup_directory().

        The async uploaded-file restore branch must NOT copy bytes to
        an attacker-controlled destination when the artifact's persisted
        local_path points outside the authoritative backup root.
        """
        del backup_policy
        content = postgresql_artifact_file.read_bytes()
        uploaded_file = SimpleUploadedFile(
            postgresql_backup_artifact.filename,
            content,
        )

        # Set the artifact's local_path to an out-of-tree path whose
        # parent exists (a classic escape scenario).
        out_of_tree_path = local_backup_settings.parent / "escape.dump"
        postgresql_backup_artifact.local_path = str(out_of_tree_path)
        postgresql_backup_artifact.save(
            update_fields=["local_path", "updated_at"],
        )

        staged = StagedAdminRestoreUpload(
            local_path=postgresql_artifact_file,
            checksum_sha256=postgresql_backup_artifact.checksum_sha256,
            size_bytes=postgresql_backup_artifact.size_bytes,
        )

        with (
            patch(
                "quickscale_modules_backups.services._stage_admin_restore_upload",
                return_value=staged,
            ),
            patch(
                "quickscale_modules_backups.services._resolve_admin_uploaded_restore_artifact",
                return_value=postgresql_backup_artifact,
            ),
            patch(
                "quickscale_modules_backups.services.subprocess.Popen",
                return_value=MagicMock(),
            ),
        ):
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "source_mode": BackupPolicyRestoreForm.SOURCE_MODE_UPLOADED_FILE,
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                    "uploaded_file": uploaded_file,
                },
                follow=True,
            )

        assert response.status_code == 200

        # The out-of-tree path must NOT have been written.
        assert not out_of_tree_path.exists()

        # Artifact local_path was updated to a safe path under the
        # configured authoritative backup root.
        postgresql_backup_artifact.refresh_from_db()
        safe_path = Path(postgresql_backup_artifact.local_path)
        assert safe_path.parent == local_backup_settings
        assert safe_path.name == postgresql_backup_artifact.filename
        assert safe_path.exists()
        assert safe_path.read_bytes() == content

    def test_restore_async_upload_remaps_symlinked_local_path(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
        postgresql_artifact_file: Path,
        local_backup_settings: Path,
    ) -> None:
        """CR-SA20-005: Symlink-based local_path is always replaced by a
        safe direct path under get_local_backup_directory().

        The async uploaded-file restore branch must NOT follow a symlink
        that escapes the authoritative backup root when copying staged
        upload bytes.
        """
        del backup_policy
        content = postgresql_artifact_file.read_bytes()
        uploaded_file = SimpleUploadedFile(
            postgresql_backup_artifact.filename,
            content,
        )

        # Create a symlink inside the backup root that points outside.
        # The backup directory must exist before creating a symlink inside it.
        local_backup_settings.mkdir(parents=True, exist_ok=True)
        escape_target = local_backup_settings.parent / "outside-root.dump"
        # Preload with DIFFERENT content so that if the symlink IS
        # followed, shutil.copy2 overwrites the escape target and the
        # assertion below fails -- proving the vulnerability would be
        # exploitable without the fix.
        escape_original = b"ESCAPE TARGET ORIGINAL CONTENT - MUST NOT CHANGE"
        escape_target.write_bytes(escape_original)
        symlink_path = local_backup_settings / postgresql_backup_artifact.filename
        symlink_path.symlink_to(escape_target)

        postgresql_backup_artifact.local_path = str(symlink_path)
        postgresql_backup_artifact.save(
            update_fields=["local_path", "updated_at"],
        )

        staged = StagedAdminRestoreUpload(
            local_path=postgresql_artifact_file,
            checksum_sha256=postgresql_backup_artifact.checksum_sha256,
            size_bytes=postgresql_backup_artifact.size_bytes,
        )

        with (
            patch(
                "quickscale_modules_backups.services._stage_admin_restore_upload",
                return_value=staged,
            ),
            patch(
                "quickscale_modules_backups.services._resolve_admin_uploaded_restore_artifact",
                return_value=postgresql_backup_artifact,
            ),
            patch(
                "quickscale_modules_backups.services.subprocess.Popen",
                return_value=MagicMock(),
            ),
        ):
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "source_mode": BackupPolicyRestoreForm.SOURCE_MODE_UPLOADED_FILE,
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                    "uploaded_file": uploaded_file,
                },
                follow=True,
            )

        assert response.status_code == 200

        # The symlink escape target must still hold the original
        # different content — if the fix were missing, shutil.copy2
        # would follow the symlink and overwrite it.
        assert escape_target.read_bytes() == escape_original

        # The former symlink path must now be a regular file (the
        # symlink was unlinked by the fix, then the regular file was
        # materialized by copy2).
        assert symlink_path.is_file()
        assert not symlink_path.is_symlink()

        # Artifact local_path was updated to a safe direct path under
        # the backup root, NOT the symlink escape target.
        postgresql_backup_artifact.refresh_from_db()
        safe_path = Path(postgresql_backup_artifact.local_path)
        assert safe_path.parent == local_backup_settings
        assert safe_path.name == postgresql_backup_artifact.filename
        assert safe_path.exists()
        assert safe_path.read_bytes() == content

    # ------------------------------------------------------------------
    # CR-SA20-REV-002: regression — atomic restore claim prevents
    # double-dispatch of concurrent restore submissions for the same
    # artifact (stale-row / double-dispatch)
    # ------------------------------------------------------------------

    def test_restore_recorded_artifact_atomic_claim_prevents_double_dispatch(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        """CR-SA20-REV-002: Two sequential recorded-artifact restore
        submissions for the same artifact — exactly one reaches Popen,
        the second receives a blocked message.

        Before the fix the second submission could also pass the TOCTOU
        eligibility check and dispatch a second Popen.  The atomic
        compare-and-swap ensures that only the first caller that wins the
        race claims STATUS_RESTORING; the second caller's claim updates
        zero rows and the caller surfaces a blocked message.
        """
        del backup_policy

        # First submission — must succeed
        with patch(
            "quickscale_modules_backups.services.subprocess.Popen",
            return_value=MagicMock(),
        ):
            response1 = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "artifact_id": str(postgresql_backup_artifact.pk),
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                },
                follow=True,
            )

        assert response1.status_code == 200
        postgresql_backup_artifact.refresh_from_db()
        assert postgresql_backup_artifact.status == BackupArtifact.STATUS_RESTORING

        # Second submission — must be blocked without reaching Popen
        with patch(
            "quickscale_modules_backups.services.subprocess.Popen",
        ) as mocked_popen2:
            response2 = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "artifact_id": str(postgresql_backup_artifact.pk),
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                },
            )

        assert response2.status_code == 200
        mocked_popen2.assert_not_called()
        assert (
            "This backup artifact is currently being restored."
            in response2.content.decode("utf-8")
        )

    def test_restore_uploaded_file_atomic_claim_prevents_double_dispatch(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
        postgresql_artifact_file: Path,
    ) -> None:
        """CR-SA20-REV-002: Two sequential uploaded-file restore
        submissions for the same artifact — exactly one reaches Popen,
        the second receives a blocked message.

        Covers the uploaded-file branch with the same atomic claim
        gate used by the recorded-artifact branch.  The first
        submission claims STATUS_RESTORING via compare-and-swap; the
        second finds the artifact already claimed and returns a blocked
        message without a second Popen.
        """
        del backup_policy
        content = postgresql_artifact_file.read_bytes()
        uploaded_file = SimpleUploadedFile(
            postgresql_backup_artifact.filename,
            content,
        )

        staged = StagedAdminRestoreUpload(
            local_path=postgresql_artifact_file,
            checksum_sha256=postgresql_backup_artifact.checksum_sha256,
            size_bytes=postgresql_backup_artifact.size_bytes,
        )

        with (
            patch(
                ("quickscale_modules_backups.services._stage_admin_restore_upload"),
                return_value=staged,
            ),
            patch(
                (
                    "quickscale_modules_backups.services."
                    "_resolve_admin_uploaded_restore_artifact"
                ),
                return_value=postgresql_backup_artifact,
            ),
            patch(
                "quickscale_modules_backups.services.subprocess.Popen",
                return_value=MagicMock(),
            ),
        ):
            response1 = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "source_mode": BackupPolicyRestoreForm.SOURCE_MODE_UPLOADED_FILE,
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                    "uploaded_file": uploaded_file,
                },
                follow=True,
            )

        assert response1.status_code == 200
        postgresql_backup_artifact.refresh_from_db()
        assert postgresql_backup_artifact.status == BackupArtifact.STATUS_RESTORING

        # Second submission — blocked without reaching Popen.
        # Must include an uploaded file to pass form validation; the
        # staging/resolving patches will return the same artifact (now
        # STATUS_RESTORING), and the atomic claim will fail.
        uploaded_file2 = SimpleUploadedFile(
            postgresql_backup_artifact.filename,
            content,
        )
        with (
            patch(
                ("quickscale_modules_backups.services._stage_admin_restore_upload"),
                return_value=staged,
            ),
            patch(
                (
                    "quickscale_modules_backups.services."
                    "_resolve_admin_uploaded_restore_artifact"
                ),
                return_value=postgresql_backup_artifact,
            ),
            patch(
                "quickscale_modules_backups.services.subprocess.Popen",
            ) as mocked_popen2,
        ):
            response2 = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "source_mode": BackupPolicyRestoreForm.SOURCE_MODE_UPLOADED_FILE,
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                    "uploaded_file": uploaded_file2,
                },
            )

        assert response2.status_code == 200
        mocked_popen2.assert_not_called()
        assert (
            "This backup artifact is currently being restored."
            in response2.content.decode("utf-8")
        )

    # ------------------------------------------------------------------
    # CR-SA20-REV-002: regression — atomic-claim-failure defensive paths
    # (lines 570-581 recorded-artifact; lines 743-755 uploaded-file).
    # These are unreachable in normal flow because earlier guards catch
    # ineligible statuses before the atomic claim.  Patch the helper to
    # simulate a lost compare-and-swap race with a side_effect that sets
    # the artifact's in-memory status and returns False.
    # ------------------------------------------------------------------

    def test_restore_recorded_artifact_atomic_claim_failure_with_ineligible_reason(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        """CR-SA20-REV-002: Recorded-artifact atomic claim failure with
        ineligible_reason (lines 575-576).

        When _atomic_claim_restore fails and the artifact's post-claim
        status maps to a known blocking reason (STATUS_RESTORING), the
        code raises BackupRestoreBlocked with that reason rather than
        the generic fallback message.
        """
        del backup_policy

        def _fail_claim_set_restoring(
            artifact: BackupArtifact,
        ) -> bool:
            artifact.status = BackupArtifact.STATUS_RESTORING
            return False

        with (
            patch(
                "quickscale_modules_backups.services._atomic_claim_restore",
                side_effect=_fail_claim_set_restoring,
            ),
            patch(
                "quickscale_modules_backups.services.subprocess.Popen",
            ) as mocked_popen,
        ):
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "artifact_id": str(postgresql_backup_artifact.pk),
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                },
            )

        assert response.status_code == 200
        mocked_popen.assert_not_called()
        assert (
            "This backup artifact is currently being restored."
            in response.content.decode("utf-8")
        )

    def test_restore_recorded_artifact_atomic_claim_fallback(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
    ) -> None:
        """CR-SA20-REV-002: Recorded-artifact atomic claim fallback
        (lines 577-581).

        When _atomic_claim_restore fails and the artifact's post-claim
        status does not map to a known blocking reason (STATUS_READY
        passes all _get_admin_restore_ineligible_reason checks, returning
        None), the code falls back to a generic message.
        """
        del backup_policy

        def _fail_claim_set_ready(
            artifact: BackupArtifact,
        ) -> bool:
            artifact.status = BackupArtifact.STATUS_READY
            return False

        with (
            patch(
                "quickscale_modules_backups.services._atomic_claim_restore",
                side_effect=_fail_claim_set_ready,
            ),
            patch(
                "quickscale_modules_backups.services.subprocess.Popen",
            ) as mocked_popen,
        ):
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "artifact_id": str(postgresql_backup_artifact.pk),
                    "confirmation": postgresql_backup_artifact.filename,
                    "operation": "restore",
                },
            )

        assert response.status_code == 200
        mocked_popen.assert_not_called()
        assert (
            "This backup artifact is currently being restored."
            in response.content.decode("utf-8")
        )

    def test_restore_uploaded_file_atomic_claim_failure_with_deleted_status(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
        postgresql_artifact_file: Path,
    ) -> None:
        """CR-SA20-REV-002: Uploaded-file atomic claim failure with
        STATUS_DELETED (lines 743-749).

        When _atomic_claim_restore fails and the artifact's post-claim
        status is STATUS_DELETED, the code surfaces the specific
        deleted-artifact message.
        """
        del backup_policy
        content = postgresql_artifact_file.read_bytes()
        uploaded_file = SimpleUploadedFile(
            postgresql_backup_artifact.filename,
            content,
        )

        staged = StagedAdminRestoreUpload(
            local_path=postgresql_artifact_file,
            checksum_sha256=(postgresql_backup_artifact.checksum_sha256),
            size_bytes=postgresql_backup_artifact.size_bytes,
        )

        def _fail_claim_set_deleted(
            artifact: BackupArtifact,
        ) -> bool:
            artifact.status = BackupArtifact.STATUS_DELETED
            return False

        with (
            patch(
                ("quickscale_modules_backups.services._stage_admin_restore_upload"),
                return_value=staged,
            ),
            patch(
                (
                    "quickscale_modules_backups.services."
                    "_resolve_admin_uploaded_restore_artifact"
                ),
                return_value=postgresql_backup_artifact,
            ),
            patch(
                "quickscale_modules_backups.services._atomic_claim_restore",
                side_effect=_fail_claim_set_deleted,
            ),
            patch(
                "quickscale_modules_backups.services.subprocess.Popen",
            ) as mocked_popen,
        ):
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "source_mode": (BackupPolicyRestoreForm.SOURCE_MODE_UPLOADED_FILE),
                    "confirmation": (postgresql_backup_artifact.filename),
                    "operation": "restore",
                    "uploaded_file": uploaded_file,
                },
            )

        assert response.status_code == 200
        mocked_popen.assert_not_called()
        assert (
            "Deleted backup artifacts cannot be restored from admin."
            in response.content.decode("utf-8")
        )

    def test_restore_uploaded_file_atomic_claim_fallback(
        self,
        admin_client: Client,
        backup_policy: BackupPolicy,
        postgresql_backup_artifact: BackupArtifact,
        postgresql_artifact_file: Path,
    ) -> None:
        """CR-SA20-REV-002: Uploaded-file atomic claim fallback
        (lines 751-755).

        When _atomic_claim_restore fails and the artifact's post-claim
        status is not STATUS_DELETED, the code falls back to a generic
        message.
        """
        del backup_policy
        content = postgresql_artifact_file.read_bytes()
        uploaded_file = SimpleUploadedFile(
            postgresql_backup_artifact.filename,
            content,
        )

        staged = StagedAdminRestoreUpload(
            local_path=postgresql_artifact_file,
            checksum_sha256=(postgresql_backup_artifact.checksum_sha256),
            size_bytes=postgresql_backup_artifact.size_bytes,
        )

        def _fail_claim_set_failed(
            artifact: BackupArtifact,
        ) -> bool:
            artifact.status = BackupArtifact.STATUS_FAILED
            return False

        with (
            patch(
                ("quickscale_modules_backups.services._stage_admin_restore_upload"),
                return_value=staged,
            ),
            patch(
                (
                    "quickscale_modules_backups.services."
                    "_resolve_admin_uploaded_restore_artifact"
                ),
                return_value=postgresql_backup_artifact,
            ),
            patch(
                "quickscale_modules_backups.services._atomic_claim_restore",
                side_effect=_fail_claim_set_failed,
            ),
            patch(
                "quickscale_modules_backups.services.subprocess.Popen",
            ) as mocked_popen,
        ):
            response = admin_client.post(
                reverse("admin:quickscale_modules_backups_backuppolicy_restore"),
                {
                    "source_mode": (BackupPolicyRestoreForm.SOURCE_MODE_UPLOADED_FILE),
                    "confirmation": (postgresql_backup_artifact.filename),
                    "operation": "restore",
                    "uploaded_file": uploaded_file,
                },
            )

        assert response.status_code == 200
        mocked_popen.assert_not_called()
        assert (
            "This backup artifact is currently being restored."
            in response.content.decode("utf-8")
        )


@pytest.mark.django_db
class TestBackupArtifactAdmin:
    """Tests for artifact admin actions and download handling."""

    def test_artifact_changelist_includes_roadmap_provenance_columns(self) -> None:
        artifact_admin = _artifact_admin()

        assert "restore_scope_badge" in artifact_admin.list_display
        assert "storage_location" in artifact_admin.list_display
        assert "checksum_sha256" in artifact_admin.list_display
        assert "validated_at" in artifact_admin.list_display
        assert "size_bytes" in artifact_admin.list_display

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

    def test_artifact_changelist_renders_snapshot_provenance_projection(
        self,
        admin_client: Client,
        backup_artifact: BackupArtifact,
        tmp_path: Path,
    ) -> None:
        validated_at = backup_artifact.created_at.replace(
            year=2037,
            month=6,
            day=7,
            hour=8,
            minute=9,
            second=10,
            microsecond=0,
        )
        backup_artifact.checksum_sha256 = "checksum-admin-projection-123"
        backup_artifact.validated_at = validated_at
        backup_artifact.save(
            update_fields=["checksum_sha256", "validated_at", "updated_at"]
        )
        BackupSnapshot.objects.create(
            snapshot_id="snap-artifact-admin",
            authoritative_dump=backup_artifact,
            status=BackupSnapshot.STATUS_FAILED,
            source_environment="railway-prod",
            local_root_path=str(tmp_path / "snapshot-root"),
        )

        response = admin_client.get(
            reverse("admin:quickscale_modules_backups_backupartifact_changelist")
        )

        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert "Snapshot status" in content
        assert "Provenance" in content
        assert "Storage location" in content
        assert "snap-artifact-admin" in content
        assert "railway-prod (snap-artifact-admin)" in content
        assert backup_artifact.local_path in content
        assert backup_artifact.checksum_sha256 in content
        assert "2037" in content
        assert "Failed" in content

    def test_artifact_changelist_exposes_create_button_for_policy_mutation_operator(
        self,
    ) -> None:
        user = _make_staff_user(
            "backups-staff-artifact-create-visible",
            "view_backupartifact",
            "change_backuppolicy",
        )
        client = Client()
        client.force_login(user)

        response = client.get(
            reverse("admin:quickscale_modules_backups_backupartifact_changelist")
        )

        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert "Create backup now" in content
        assert (
            reverse("admin:quickscale_modules_backups_backupartifact_create") in content
        )

    def test_artifact_changelist_hides_create_button_without_policy_change_permission(
        self,
    ) -> None:
        user = _make_staff_user(
            "backups-staff-artifact-change-only",
            "view_backupartifact",
            "change_backupartifact",
        )
        client = Client()
        client.force_login(user)

        response = client.get(
            reverse("admin:quickscale_modules_backups_backupartifact_changelist")
        )

        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert "Create backup now" not in content
        assert (
            reverse("admin:quickscale_modules_backups_backupartifact_create")
            not in content
        )

    def test_artifact_create_endpoint_runs_with_policy_change_permission(
        self,
    ) -> None:
        user = _make_staff_user(
            "backups-staff-artifact-create-endpoint",
            "view_backupartifact",
            "change_backuppolicy",
        )
        client = Client()
        client.force_login(user)
        fake_artifact = BackupArtifact(
            filename="db-project-local-20260326T120000Z.json",
            checksum_sha256="abc",
            size_bytes=1,
            backup_format="json",
            database_engine="django.db.backends.sqlite3",
            database_name="test.sqlite3",
        )

        with patch(
            "quickscale_modules_backups.admin.create_backup",
            return_value=fake_artifact,
        ) as mocked_create:
            response = client.post(
                reverse("admin:quickscale_modules_backups_backupartifact_create"),
                follow=True,
            )

        assert response.status_code == 200
        mocked_create.assert_called_once_with(initiated_by=user, trigger="admin")
        assert [message.message for message in get_messages(response.wsgi_request)] == [
            "Created backup artifact db-project-local-20260326T120000Z.json"
        ]

    def test_artifact_create_endpoint_denies_staff_user_without_policy_change_permission(
        self,
    ) -> None:
        user = _make_staff_user(
            "backups-staff-artifact-create-denied",
            "view_backupartifact",
            "change_backupartifact",
        )
        client = Client()
        client.force_login(user)

        with patch("quickscale_modules_backups.admin.create_backup") as mocked_create:
            response = client.post(
                reverse("admin:quickscale_modules_backups_backupartifact_create")
            )

        assert response.status_code == 403
        mocked_create.assert_not_called()

    def test_change_view_renders_download_link(
        self,
        admin_client: Client,
        backup_artifact: BackupArtifact,
        local_backup_settings: Path,
    ) -> None:
        del local_backup_settings
        _place_artifact_in_authoritative_root(backup_artifact)
        response = admin_client.get(
            reverse(
                "admin:quickscale_modules_backups_backupartifact_change",
                args=[backup_artifact.pk],
            )
        )

        content = response.content.decode("utf-8")

        assert response.status_code == 200
        assert "Download" in content
        assert "export_only" in content
        assert "not a supported restore input" in content

    @pytest.mark.parametrize(
        ("restore_scope", "expected_fragment"),
        [
            (
                BackupArtifact.RESTORE_SCOPE_LOCAL_ONLY,
                "Classification: local_only.",
            ),
            (
                BackupArtifact.RESTORE_SCOPE_PORTABLE,
                "Classification: portable.",
            ),
        ],
    )
    def test_restore_cli_notice_reports_scope_specific_guidance(
        self,
        artifact_file: Path,
        restore_scope: str,
        expected_fragment: str,
    ) -> None:
        artifact = BackupArtifact.objects.create(
            filename=f"artifact-{restore_scope}.dump",
            local_path=str(artifact_file),
            checksum_sha256=hashlib.sha256(artifact_file.read_bytes()).hexdigest(),
            size_bytes=artifact_file.stat().st_size,
            backup_format="pg_dump_custom",
            restore_scope=restore_scope,
            database_engine="django.db.backends.postgresql",
            database_name="quickscale_test",
        )

        artifact_admin = _artifact_admin()
        notice = artifact_admin.restore_cli_notice(artifact)

        assert expected_fragment in notice
        assert (
            "Admin download and validate only work when the local file is present."
            in notice
        )
        assert "BackupArtifact admin page remains download/validate-focused." in notice
        assert "BackupPolicy admin page" in notice
        assert "--file /path/to/backup.dump" in notice
        assert "Admin intentionally does not execute restores." not in notice

    def test_admin_availability_notice_explains_remote_only_artifacts(self) -> None:
        artifact = BackupArtifact.objects.create(
            filename="artifact-remote.dump",
            storage_target=BackupArtifact.STORAGE_TARGET_PRIVATE_REMOTE,
            local_path="",
            remote_key="private/backups/artifact-remote.dump",
            checksum_sha256="abc123",
            size_bytes=100,
            backup_format="pg_dump_custom",
            restore_scope=BackupArtifact.RESTORE_SCOPE_LOCAL_ONLY,
            database_engine="django.db.backends.postgresql",
            database_name="quickscale_test",
        )

        artifact_admin = _artifact_admin()

        assert artifact_admin.admin_availability_notice(artifact) == (
            "No local file recorded. Admin download and validate remain local-file-"
            "only and do not materialize remote-only artifacts."
        )

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
        local_backup_settings: Path,
    ) -> None:
        del local_backup_settings
        _place_artifact_in_authoritative_root(backup_artifact)
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

    def test_download_view_allows_staff_user_with_view_permission(
        self,
        backup_artifact: BackupArtifact,
        local_backup_settings: Path,
    ) -> None:
        del local_backup_settings
        _place_artifact_in_authoritative_root(backup_artifact)
        user = _make_staff_user(
            "backups-staff-artifact-view-only",
            "view_backupartifact",
        )
        client = Client()
        client.force_login(user)

        response = client.get(
            reverse(
                "admin:quickscale_modules_backups_backupartifact_download",
                args=[backup_artifact.pk],
            )
        )

        assert response.status_code == 200
        assert backup_artifact.filename in response["Content-Disposition"]

    def test_download_view_redirects_out_of_tree_artifact(
        self,
        backup_artifact: BackupArtifact,
        superuser: AbstractBaseUser,
        local_backup_settings: Path,
    ) -> None:
        del local_backup_settings
        artifact_admin = _artifact_admin()
        request = RequestFactory().get("/admin/")
        request.user = superuser
        _attach_messages(request)

        response = artifact_admin.download_view(request, backup_artifact.pk)

        assert response.status_code == 302
        assert response.url == reverse(
            "admin:quickscale_modules_backups_backupartifact_change",
            args=[backup_artifact.pk],
        )
        assert [message.message for message in get_messages(request)] == [
            "Download unavailable: this artifact is no longer available."
        ]

    def test_download_link_is_unavailable_for_symlink_escape(
        self,
        backup_artifact: BackupArtifact,
        local_backup_settings: Path,
        tmp_path: Path,
    ) -> None:
        escape_target = tmp_path / "outside-root.json"
        escape_target.write_text("[]", encoding="utf-8")
        symlink_path = local_backup_settings / "database" / backup_artifact.filename
        symlink_path.parent.mkdir(parents=True, exist_ok=True)
        symlink_path.symlink_to(escape_target)
        backup_artifact.local_path = str(symlink_path)
        backup_artifact.save(update_fields=["local_path", "updated_at"])

        artifact_admin = _artifact_admin()

        assert artifact_admin.download_link(backup_artifact) == "Unavailable"

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

        with patch(
            "quickscale_modules_backups.admin.download_backup_path",
            side_effect=BackupError(
                f"Backup file not found: {Path(backup_artifact.local_path)}"
            ),
        ) as mocked:
            response = artifact_admin.download_view(request, backup_artifact.pk)

        assert response.status_code == 302
        assert response.url == reverse(
            "admin:quickscale_modules_backups_backupartifact_change",
            args=[backup_artifact.pk],
        )
        mocked.assert_called_once()

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
