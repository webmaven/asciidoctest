import pytest

# Enable pytester fixture for integration tests
pytest_plugins = ["pytester"]


@pytest.fixture(autouse=True)
def _configure_pytester_ini(request: pytest.FixtureRequest) -> None:
    """Ensure pytester sub-runs have asyncio loop scope configured to avoid warnings."""
    if "pytester" in request.fixturenames:
        pytester = request.getfixturevalue("pytester")
        pytester.makeini("""
            [pytest]
            asyncio_default_fixture_loop_scope = function
        """)
