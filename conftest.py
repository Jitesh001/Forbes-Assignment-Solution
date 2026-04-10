import pytest


@pytest.fixture(autouse=True)
def _enable_db(db):
    """Enable database access for all tests by default."""
    pass
