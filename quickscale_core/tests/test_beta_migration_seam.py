"""SA114-REV-001: validateQuickScaleSeam.ts seam ownership in beta migration.

useModules.ts imports from validateQuickScaleSeam.ts at runtime.
When in-place migration delivers useModules.ts to the recipient,
validateQuickScaleSeam.ts must also be delivered — otherwise the
migrated recipient will have a broken import.
"""

from quickscale_devtools.beta_migration import IN_PLACE_INFRASTRUCTURE_TARGETS


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
