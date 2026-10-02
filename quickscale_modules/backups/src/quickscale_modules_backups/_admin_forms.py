"""Restore-source form for the backups admin surface.

Re-exported from ``quickscale_modules_backups.admin`` so the admin module
keeps its full import surface after the split.
"""

from __future__ import annotations

from typing import Any

from django import forms


class BackupPolicyRestoreForm(forms.Form):
    """Collect either a local artifact or uploaded file plus exact confirmation."""

    SOURCE_MODE_RECORDED_ARTIFACT = "recorded_artifact"
    SOURCE_MODE_UPLOADED_FILE = "uploaded_file"

    source_mode = forms.ChoiceField(
        label="Restore source",
        required=False,
        choices=[
            (SOURCE_MODE_RECORDED_ARTIFACT, "Recorded local artifact"),
            (SOURCE_MODE_UPLOADED_FILE, "Uploaded backup file"),
        ],
        initial=SOURCE_MODE_RECORDED_ARTIFACT,
        widget=forms.RadioSelect,
        help_text=(
            "Use a recorded local artifact already present on disk, or upload a "
            "backup file that must resolve to one trusted authoritative artifact "
            "recorded on the snapshot seam."
        ),
    )

    artifact_id = forms.IntegerField(
        label="Eligible local artifact",
        min_value=1,
        required=False,
        widget=forms.Select(),
        help_text=(
            "Choose a row-backed PostgreSQL dump artifact whose local file is "
            "already present on disk."
        ),
    )
    uploaded_file = forms.FileField(
        label="Uploaded backup file",
        required=False,
        help_text=(
            "Upload a PostgreSQL custom dump to quarantine staging. The upload is "
            "accepted only when its checksum and size resolve to exactly one "
            "trusted authoritative artifact with a complete snapshot contract."
        ),
    )
    confirmation = forms.CharField(
        label="Exact artifact filename",
        strip=False,
        help_text=(
            "Type the exact authoritative artifact filename before dry-run "
            "validation or restore can continue. Uploaded files must still match "
            "the recorded artifact filename exactly here."
        ),
    )

    def __init__(
        self,
        *args: Any,
        artifact_choices: list[tuple[int, str]],
        allow_recorded_artifact_source: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.allow_recorded_artifact_source = allow_recorded_artifact_source
        if allow_recorded_artifact_source:
            self.fields["source_mode"].choices = [  # type: ignore[attr-defined]
                (
                    self.SOURCE_MODE_RECORDED_ARTIFACT,
                    "Recorded local artifact",
                ),
                (self.SOURCE_MODE_UPLOADED_FILE, "Uploaded backup file"),
            ]
            self.fields["source_mode"].initial = self.SOURCE_MODE_RECORDED_ARTIFACT
        else:
            self.fields["source_mode"].choices = [  # type: ignore[attr-defined]
                (self.SOURCE_MODE_UPLOADED_FILE, "Uploaded backup file")
            ]
            self.fields["source_mode"].initial = self.SOURCE_MODE_UPLOADED_FILE
            self.fields["source_mode"].error_messages["invalid_choice"] = (
                "Recorded local artifacts are unavailable for your current permissions."
            )
            self.fields["source_mode"].help_text = (
                "Uploaded backup file is the only restore source available for "
                "your current permissions."
            )
        self.fields["artifact_id"].widget.choices = [
            ("", "Select an eligible local backup artifact"),
            *artifact_choices,
        ]

    def clean(self) -> dict[str, Any]:
        """Require the source-specific restore input before continuing."""
        cleaned_data: dict[str, Any] = super().clean() or {}
        default_source_mode = (
            self.SOURCE_MODE_RECORDED_ARTIFACT
            if self.allow_recorded_artifact_source
            else self.SOURCE_MODE_UPLOADED_FILE
        )
        source_mode = cleaned_data.get("source_mode") or default_source_mode
        cleaned_data["source_mode"] = source_mode

        if self.has_error("source_mode"):
            return cleaned_data

        if source_mode == self.SOURCE_MODE_RECORDED_ARTIFACT:
            if not self.allow_recorded_artifact_source:
                self.add_error(
                    "source_mode",
                    "Recorded local artifacts are unavailable for your current permissions.",
                )
                return cleaned_data
            if cleaned_data.get("artifact_id") is None:
                self.add_error(
                    "artifact_id",
                    "Choose an eligible local backup artifact before continuing.",
                )
        elif source_mode == self.SOURCE_MODE_UPLOADED_FILE:
            if cleaned_data.get("uploaded_file") is None:
                self.add_error(
                    "uploaded_file",
                    "Upload a backup file before continuing.",
                )
        else:
            self.add_error("source_mode", "Choose a restore source before continuing.")

        return cleaned_data
