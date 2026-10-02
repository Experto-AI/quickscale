"""Unified :class:`ProjectStateManager` for state and config.

Owns the additive single entry point over ``.quickscale/state.yml`` and
``.quickscale/config.yml``. The lower-level ``StateManager`` and
``quickscale_core.config`` helpers remain in their original modules and keep
working unchanged; this module only orchestrates them. The unified owner
stays importable from ``quickscale_core.project_state``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from quickscale_core.config.module_config import (
    ConfigError,
    ModuleConfig,
    load_config,
    save_config,
)
from quickscale_core.project_state_drift import check_version_drift
from quickscale_core.project_state_hashes import (
    FILE_HASHES_FILENAME,
    _read_managed_file_hashes,
    _write_managed_file_hashes,
    compute_file_hashes,
    hash_managed_file,
)
from quickscale_core.project_state_legacy import (
    load_raw_state_data,
    merge_legacy_file_hashes,
    merge_legacy_module_tracking,
    read_project_timestamps,
    state_data_has_consolidated_sections,
)
from quickscale_core.project_state_records import (
    ManagedFileHash,
    VersionDriftWarning,
)
from quickscale_core.schema.state_schema import (
    ManagedFileRecord,
    ModuleState,
    ProjectState,
    QuickScaleState,
    StateError,
    StateManager,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = logging.getLogger(__name__)


class ProjectStateManager:
    """Unified owner of the two QuickScale-managed YAML files.

    The two files keep their on-disk format and location:

    * ``.quickscale/state.yml`` — authoritative applied state
      (delegated to :class:`StateManager`).
    * ``.quickscale/config.yml`` — legacy module tracking
      (delegated to ``quickscale_core.config`` helpers).

    The class is additive: it does not replace the existing per-file
    loaders/savers, it just exposes a single entry point that can act on
    both. The single-file helpers continue to work without modification.
    """

    def __init__(self, project_path: Path):
        """Initialize the unified manager.

        Args:
            project_path: Root of the generated project.

        """
        self.project_path = Path(project_path)
        self.state_dir = self.project_path / ".quickscale"
        self.state_file = self.state_dir / "state.yml"
        self.config_file = self.state_dir / "config.yml"
        self.file_hashes_file = self.state_dir / FILE_HASHES_FILENAME

        # Reuse existing managers so behavior stays identical.
        self._state_manager = StateManager(self.project_path)

    # ------------------------------------------------------------------
    # State (.quickscale/state.yml)
    # ------------------------------------------------------------------

    def _state_file_has_consolidated_sections(self) -> bool:
        """Check whether ``state.yml`` has consolidated sections on disk.

        Returns True when the state file exists and contains either the
        ``managed_files`` section, an explicit ``modules`` key (even when
        empty — signalling that M2 has authoritatively recorded "no
        modules"), or modules with consolidated tracking fields
        (``prefix``/``branch``).  This determines whether legacy
        ``config.yml`` and ``file_hashes.yml`` should be read-through
        imported or ignored.
        """
        data = load_raw_state_data(self.state_file)
        if data is None:
            return False
        return state_data_has_consolidated_sections(data)

    def load_state(self) -> QuickScaleState | None:
        """Load ``.quickscale/state.yml`` with read-through import.

        Phase 2 (M2) makes ``state.yml`` the sole authority.  When the
        consolidated sections (``managed_files`` or module tracking
        fields) are absent from ``state.yml``, this method read-through
        imports from legacy ``config.yml`` and ``file_hashes.yml``.

        When consolidated sections are present, legacy files are ignored
        even if they still exist on disk.

        Returns:
            :class:`QuickScaleState` if state can be loaded, ``None`` if
            no state file exists.

        Raises:
            StateError: If the state file is malformed.
        """
        state = self._state_manager.load()
        if state is None:
            return None

        # If consolidated sections are present, return as-is.
        if self._state_file_has_consolidated_sections():
            return state

        # Read-through import from legacy files.
        return self._read_through_import_legacy(state)

    def _read_through_import_legacy(self, state: QuickScaleState) -> QuickScaleState:
        """Import legacy ``config.yml`` and ``file_hashes.yml`` into state.

        This is called only when ``state.yml`` lacks consolidated sections.
        Legacy module-tracking metadata from ``config.yml`` is merged into
        the module states, and legacy file hashes from ``file_hashes.yml``
        are merged into ``managed_files``.

        The returned state is not persisted; callers should save it if they
        want to materialize the consolidation.

        """
        # F-EXCEPTION: F12.2
        # Pre-M2 projects may still need legacy config.yml/file_hashes.yml
        # read-through import until consolidated state is materialized. Log
        # and skip stale legacy data so the one-time M2 migration is not blocked.
        legacy_config = self._load_legacy_config(context="for read-through import")
        merge_legacy_module_tracking(state.modules, legacy_config)

        legacy_hashes = self._load_legacy_hashes(context="for read-through import")
        merge_legacy_file_hashes(state.managed_files, legacy_hashes)

        return state

    def _load_legacy_config(self, *, context: str) -> ModuleConfig | None:
        """Load legacy ``config.yml``, logging and skipping a stale file."""
        # Import legacy module tracking from config.yml.
        try:
            return self.load_config()
        except (ConfigError, OSError, yaml.YAMLError) as error:
            logger.warning(
                "Failed to load legacy config.yml %s: %s",
                context,
                error,
            )
            return None

    def _load_legacy_hashes(self, *, context: str) -> dict[str, ManagedFileHash]:
        """Load legacy ``file_hashes.yml``, logging and skipping a stale file."""
        try:
            return self.load_managed_file_hashes()
        except StateError as error:
            logger.warning(
                "Failed to load legacy file_hashes.yml %s: %s",
                context,
                error,
            )
            return {}

    def save_state(self, state: QuickScaleState) -> None:
        """Persist ``.quickscale/state.yml`` via the existing ``StateManager``."""
        self._state_manager.save(state)

    # ------------------------------------------------------------------
    # Config (.quickscale/config.yml)
    # ------------------------------------------------------------------

    def load_config(self) -> ModuleConfig:
        """Load ``.quickscale/config.yml`` via the existing helpers.

        Returns the default empty config when the file is missing.
        """
        return load_config(self.project_path)

    def save_config(self, config: ModuleConfig) -> None:
        """Persist ``.quickscale/config.yml`` via the existing helpers."""
        save_config(config, self.project_path)

    # ------------------------------------------------------------------
    # Managed file hashes (.quickscale/file_hashes.yml)
    # ------------------------------------------------------------------

    def load_managed_file_hashes(self) -> dict[str, ManagedFileHash]:
        """Load the managed-file hash ledger, returning empty on absence."""
        return _read_managed_file_hashes(self.project_path)

    def save_managed_file_hashes(
        self,
        hashes: dict[str, ManagedFileHash] | dict[str, str],
    ) -> None:
        """Persist a managed-file hash ledger.

        Accepts either :class:`ManagedFileHash` records or plain hex
        digest strings; when strings are given the current timestamp is
        recorded for each path.
        """
        if not hashes:
            return

        normalized: dict[str, ManagedFileHash] = {}
        for path, value in hashes.items():
            normalized_path = str(path).replace("\\", "/").lstrip("/")
            if isinstance(value, ManagedFileHash):
                normalized[normalized_path] = value
            else:
                normalized[normalized_path] = ManagedFileHash(
                    path=normalized_path,
                    hash=str(value),
                )
        _write_managed_file_hashes(self.project_path, normalized)

    def capture_managed_file_hashes(
        self,
        file_paths: Iterable[str],
    ) -> dict[str, ManagedFileHash]:
        """Compute hashes for the given managed files and persist them.

        Returns the full set of persisted hash records. Paths whose files
        do not exist at capture time are omitted (callers should treat
        missing files as drift and surface a separate warning).
        """
        computed = compute_file_hashes(self.project_path, file_paths)
        records = {
            path: ManagedFileHash(path=path, hash=digest)
            for path, digest in computed.items()
        }
        if records:
            self.save_managed_file_hashes(records)
        return records

    def detect_managed_file_drift(
        self,
        file_paths: Iterable[str] | None = None,
    ) -> list[ManagedFileHash]:
        """Return a list of managed files that have drifted since last apply.

        A file is considered drifted if:

        * it was hashed at last apply but no longer exists, or
        * it was hashed at last apply and its current content hash differs
          from the recorded hash.

        The list contains the *recorded* :class:`ManagedFileHash` so the
        caller can report both the path and the expected hash. The current
        hash, if any, is recomputed here and not stored on the record.

        Phase 2 (M2): reads authoritative ``state.yml.managed_files`` first.
        Falls back to the legacy ``file_hashes.yml`` ledger only when the
        consolidated section is absent from state.
        """
        stored = self._load_managed_file_records_for_drift()
        if not stored:
            return []

        candidates = list(file_paths) if file_paths is not None else list(stored)
        normalized_targets = {str(p).replace("\\", "/").lstrip("/") for p in candidates}

        drifted: list[ManagedFileHash] = []
        for path, record in stored.items():
            if normalized_targets and path not in normalized_targets:
                continue
            current = self.project_path / path
            if not current.is_file():
                drifted.append(record)
                continue
            try:
                current_hash = hash_managed_file(current)
            except OSError:
                drifted.append(record)
                continue
            if current_hash != record.hash:
                drifted.append(record)
        return drifted

    def _load_managed_file_records_for_drift(self) -> dict[str, ManagedFileHash]:
        """Load managed-file hash records from the authoritative source.

        Phase 2 (M2) priority:

        1. ``state.yml.managed_files`` — consolidated authoritative records.
        2. ``file_hashes.yml`` — legacy fallback, only when the consolidated
           section is absent from state.

        Note:
            This method is explicitly OUTSIDE F12.2 scope. Its legacy
            fallback to ``file_hashes.yml`` is a drift-detection design
            choice, not an M2 migration compatibility path.  F12.2 covers
            only the read-through import in ``_read_through_import_legacy``
            and ``materialize_authoritative_state``.
        """
        # Try consolidated state.yml first.
        if self._state_file_has_consolidated_sections():
            state = self._state_manager.load()
            if state is not None and state.managed_files:
                return {
                    path: ManagedFileHash(
                        path=record.path,
                        hash=record.hash,
                        applied_at=record.applied_at,
                    )
                    for path, record in state.managed_files.items()
                }
            # Consolidated sections present but managed_files empty — no
            # records to check.  Do not fall back to legacy.
            if state is not None:
                return {}

        # Legacy fallback: read file_hashes.yml when consolidated data
        # is absent from state.yml.
        return self.load_managed_file_hashes()

    # ------------------------------------------------------------------
    # Authoritative project metadata resolution
    # ------------------------------------------------------------------

    def resolve_authoritative_project_metadata(
        self,
    ) -> tuple[str, str, str] | None:
        """Resolve real project slug, package, and theme from authoritative sources.

        Resolution order:

        1. ``state.yml`` — when it has consolidated sections (or a valid
           ``project`` block), its slug/package/theme are authoritative.
        2. ``quickscale.yml`` — validated desired-state file as fallback.

        Returns:
            ``(slug, package, theme)`` if derivable, ``None`` if neither
            source provides valid project metadata.  Callers that need to
            abort rather than synthesize should check for ``None``.
        """
        # 1. Try authoritative state.yml.
        if self.state_file.exists():
            try:
                state = self._state_manager.load()
            except StateError:
                state = None

            if state is not None:
                return (
                    state.project.slug,
                    state.project.package,
                    state.project.theme,
                )

        # 2. Fall back to validated quickscale.yml.
        # SA18.6: validation errors propagate — a malformed or invalid
        # quickscale.yml must fail loudly, not be indistinguishable from
        # "no project here."
        quickscale_yml = self.project_path / "quickscale.yml"
        if quickscale_yml.exists():
            from quickscale_core.schema.config_schema import validate_config

            desired = validate_config(quickscale_yml.read_text())
            return (
                desired.project.slug,
                desired.project.package,
                desired.project.theme,
            )

        return None

    def _read_raw_project_timestamps(self) -> tuple[str, str] | None:
        """Read project timestamps from raw ``state.yml`` without fabrication.

        CR-M5-P3-006: ``StateManager.load()`` fills in ``datetime.now()``
        when ``created_at`` or ``last_applied`` are absent from the YAML.
        This helper bypasses that default and returns the raw values only
        when both are explicitly present in the on-disk file.

        Returns:
            ``(created_at, last_applied)`` when both fields are present as
            strings in the raw YAML, or ``None`` when ``state.yml`` does
            not exist, is unparseable, or lacks either timestamp field.
        """
        data = load_raw_state_data(self.state_file)
        if data is None:
            return None
        return read_project_timestamps(data)

    def materialize_authoritative_state(
        self,
    ) -> QuickScaleState | None:
        """Materialize ``state.yml`` for config-only / non-consolidated projects.

        When ``state.yml`` already has consolidated sections this is a no-op
        that returns the loaded state.  When consolidated sections are absent
        (config-only project), this method:

        1. Resolves real project metadata from ``quickscale.yml`` (or from
           the existing ``state.yml`` project block when parseable).
        2. Imports legacy module tracking from ``config.yml``.
        3. Preserves any existing module entries in ``state.yml`` that lack
           consolidated tracking fields (merges rather than replaces).
        4. Writes a fully consolidated ``state.yml``.

        Returns:
            The materialized :class:`QuickScaleState`, or ``None`` when
            materialization is impossible (e.g. no ``quickscale.yml`` and
            no valid ``state.yml``).

        Raises:
            StateError: When ``state.yml`` exists but is malformed.

        """
        # F-EXCEPTION: F12.2
        # Materialization still consumes legacy config.yml/file_hashes.yml
        # during the bounded M2 compatibility window; log-and-skip behavior
        # keeps stale legacy inputs from blocking consolidation.
        # Already consolidated — nothing to materialize.
        if self._state_file_has_consolidated_sections():
            return self._state_manager.load()

        # Load existing state if parseable (may have modules without
        # consolidated tracking fields).
        existing_state = (
            self._state_manager.load() if self.state_file.exists() else None
        )

        # Resolve project metadata: prefer existing state, fall back to
        # quickscale.yml.
        metadata = self.resolve_authoritative_project_metadata()
        if metadata is None:
            return None

        # Merge legacy module tracking and file hashes from the legacy files.
        legacy_config = self._load_legacy_config(context="during materialization")
        legacy_hashes = self._load_legacy_hashes(context="during materialization")

        # CR-M5-P3-006: preserve authoritative project timestamps from
        # raw state.yml when available.  When no authoritative timestamp
        # source exists, abort rather than fabricate timestamps.
        timestamps = self._read_raw_project_timestamps()
        if timestamps is None:
            return None

        state = _build_materialized_state(
            existing_state=existing_state,
            metadata=metadata,
            legacy_config=legacy_config,
            legacy_hashes=legacy_hashes,
            timestamps=timestamps,
        )

        # Only persist when new data was added from legacy sources or
        # when creating a brand-new state from scratch.  Skipping the
        # save for unchanged states avoids unnecessary YAML
        # re-serialization that could alter quoting (F12.2).
        if _should_persist_materialized_state(
            existing_state, legacy_config, legacy_hashes
        ):
            self.save_state(state)
        return state

    # ------------------------------------------------------------------
    # Cross-file consistency
    # ------------------------------------------------------------------

    def verify_consistency(self) -> dict[str, list[VersionDriftWarning]]:
        """Cross-check state and config and report version disagreements.

        Returns:
            A mapping with a single key ``"version_drift"`` whose value is
            a list of :class:`VersionDriftWarning` entries. The wrapper
            dict leaves room for additional consistency categories without
            changing the call sites.

        Raises:
            StateError: If ``.quickscale/config.yml`` cannot be loaded
                because the file is malformed. The boundary normalizes
                :class:`quickscale_core.config.ConfigError` (and the
                underlying :class:`yaml.YAMLError`) into :class:`StateError`
                so that downstream CLI surfaces only need to handle one
                error type for both ``state.yml`` and ``config.yml``.
        """
        state = self.load_state()
        try:
            config = self.load_config()
        except (ConfigError, OSError, yaml.YAMLError) as error:
            raise StateError(
                f"Failed to load .quickscale/config.yml: {error}"
            ) from error
        return {
            "version_drift": check_version_drift(state, config),
        }


def _should_persist_materialized_state(
    existing_state: QuickScaleState | None,
    legacy_config: ModuleConfig | None,
    legacy_hashes: dict[str, ManagedFileHash],
) -> bool:
    """Return whether materialization produced new data worth persisting."""
    return existing_state is None or legacy_config is not None or bool(legacy_hashes)


def _build_materialized_state(
    *,
    existing_state: QuickScaleState | None,
    metadata: tuple[str, str, str],
    legacy_config: ModuleConfig | None,
    legacy_hashes: dict[str, ManagedFileHash],
    timestamps: tuple[str, str],
) -> QuickScaleState:
    """Build the consolidated state written by materialization."""
    slug, package, theme = metadata

    # Start from existing modules (if any) to preserve entries that
    # lack consolidated tracking fields.
    modules: dict[str, ModuleState] = (
        dict(existing_state.modules) if existing_state is not None else {}
    )
    merge_legacy_module_tracking(modules, legacy_config)

    # Import legacy file hashes, keeping consolidated records authoritative.
    managed_files: dict[str, ManagedFileRecord] = (
        dict(existing_state.managed_files) if existing_state is not None else {}
    )
    merge_legacy_file_hashes(managed_files, legacy_hashes)

    created_at, last_applied = timestamps

    # The project contract and its adopted step ids are authoritative
    # project state; materialization must carry them forward rather than
    # erase them (SA207).
    project_contract = (
        existing_state.project.project_contract if existing_state is not None else None
    )
    adopted_contract_steps = (
        list(existing_state.project.adopted_contract_steps)
        if existing_state is not None
        and existing_state.project.adopted_contract_steps is not None
        else None
    )

    return QuickScaleState(
        version="1",
        project=ProjectState(
            slug=slug,
            package=package,
            theme=theme,
            project_contract=project_contract,
            adopted_contract_steps=adopted_contract_steps,
            created_at=created_at,
            last_applied=last_applied,
        ),
        modules=modules,
        managed_files=managed_files,
    )
