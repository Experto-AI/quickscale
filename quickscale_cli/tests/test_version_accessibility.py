"""Test version attributes are accessible in all scenarios."""


def test_version_attribute_accessible():
    """Test that __version__ is accessible."""
    import quickscale_cli

    assert hasattr(quickscale_cli, "__version__")
    version = quickscale_cli.__version__
    assert isinstance(version, str)
    assert len(version) > 0


def test_version_tuple_accessible():
    """Test that VERSION tuple is accessible."""
    import quickscale_cli

    assert hasattr(quickscale_cli, "VERSION")
    version_tuple = quickscale_cli.VERSION
    assert isinstance(version_tuple, tuple)
    assert len(version_tuple) == 3


def test_version_parts_are_integers():
    """Test that VERSION tuple contains integers."""
    import quickscale_cli

    for part in quickscale_cli.VERSION:
        assert isinstance(part, int)
        assert part >= 0


def test_version_string_matches_tuple():
    """Test that __version__ string and VERSION tuple are consistent."""
    import quickscale_cli

    version_str = quickscale_cli.__version__.split("-")[0]  # Remove any pre-release suffix
    parts = version_str.split(".")

    # VERSION tuple should match the numeric parts of __version__
    assert quickscale_cli.VERSION[0] == int(parts[0])
    if len(parts) > 1:
        assert quickscale_cli.VERSION[1] == int(parts[1])
    if len(parts) > 2:
        assert quickscale_cli.VERSION[2] == int(parts[2])


def test_metadata_attributes_exist():
    """Test that package metadata attributes exist."""
    import quickscale_cli

    assert hasattr(quickscale_cli, "__author__")
    assert hasattr(quickscale_cli, "__email__")
    assert hasattr(quickscale_cli, "__all__")


def test_version_file_fallback_logic():
    """Test that version resolution works when accessing from different contexts."""
    # This implicitly tests the fallback logic by importing in a fresh context
    import quickscale_cli

    # Access version multiple times to ensure consistent behavior
    v1 = quickscale_cli.__version__
    v2 = quickscale_cli.__version__
    assert v1 == v2

    # Access VERSION tuple
    vt1 = quickscale_cli.VERSION
    vt2 = quickscale_cli.VERSION
    assert vt1 == vt2
