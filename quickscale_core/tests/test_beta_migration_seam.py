"""SA114-REV-001: validateQuickScaleSeam.ts seam ownership in beta migration.

useModules.ts imports from validateQuickScaleSeam.ts at runtime.
When in-place migration delivers useModules.ts to the recipient,
validateQuickScaleSeam.ts must also be delivered — otherwise the
migrated recipient will have a broken import.

The seam is now required during donor preflight in addition to being
in the copy targets, so a missing donor seam fails closed instead of
silently skipping the copy.
"""

from quickscale_devtools.beta_migration import (
    IN_PLACE_INFRASTRUCTURE_TARGETS,
    MODE_REQUIRED_SPECS,
)


class TestBetaMigrationSeamOwnership:
    """Regression: validateQuickScaleSeam.ts must be managed alongside useModules.ts.

    SA114-REV-001 identified that the seam validation file was listed in
    INTENTIONALLY_UNMANAGED, so in-place migration would deliver
    useModules.ts (an infrastructure target) without its required seam
    dependency, leaving the recipient with a broken import chain.
    """

    def test_seam_in_infrastructure_targets(self) -> None:
        """validateQuickScaleSeam.ts is in IN_PLACE_INFRASTRUCTURE_TARGETS."""
        seam_path = "frontend/src/lib/validateQuickScaleSeam.ts"
        assert seam_path in IN_PLACE_INFRASTRUCTURE_TARGETS, (
            f"{seam_path} is imported by useModules.ts but is not included "
            "in IN_PLACE_INFRASTRUCTURE_TARGETS — in-place migration will "
            "deliver useModules.ts without its required seam dependency"
        )

    def test_use_modules_also_in_infrastructure_targets(self) -> None:
        """useModules.ts remains in IN_PLACE_INFRASTRUCTURE_TARGETS."""
        assert "frontend/src/hooks/useModules.ts" in IN_PLACE_INFRASTRUCTURE_TARGETS, (
            "useModules.ts must remain in IN_PLACE_INFRASTRUCTURE_TARGETS"
        )

    def test_seam_in_in_place_donor_preflight(self) -> None:
        """validateQuickScaleSeam.ts is required during in-place donor preflight.

        SA114-REV-001: The seam was a silent-skip copy target without a
        preflight requirement.  If the donor was missing the seam file,
        in-place migration would copy useModules.ts (preflight-checked)
        but silently skip the imported dependency, leaving the recipient
        with a broken import chain.  This test enforces fail-closed donor
        preflight for the seam.
        """
        donor_specs = MODE_REQUIRED_SPECS["in-place"]["donor"]
        seam_spec_path = "frontend/src/lib/validateQuickScaleSeam.ts"
        spec_paths = [spec.relative_path for spec in donor_specs]
        assert seam_spec_path in spec_paths, (
            f"{seam_spec_path} must be in MODE_REQUIRED_SPECS['in-place']['donor'] "
            "so that a missing donor seam fails closed rather than silently skipping "
            "the copy during in-place migration. Found specs: {spec_paths}"
        )

    def test_use_modules_in_in_place_donor_preflight(self) -> None:
        """useModules.ts remains required during in-place donor preflight."""
        donor_specs = MODE_REQUIRED_SPECS["in-place"]["donor"]
        use_modules_path = "frontend/src/hooks/useModules.ts"
        spec_paths = [spec.relative_path for spec in donor_specs]
        assert use_modules_path in spec_paths, (
            f"{use_modules_path} must remain in MODE_REQUIRED_SPECS['in-place']['donor']"
        )
