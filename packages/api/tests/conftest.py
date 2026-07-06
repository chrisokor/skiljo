import pytest

from skiljo_api.dependencies import verify_api_key
from skiljo_api.main import app


@pytest.fixture(autouse=True)
def bypass_auth() -> None:
    """Override bearer-auth for all API tests so they don't need a real API_KEY."""
    app.dependency_overrides[verify_api_key] = lambda: None
    yield
    # Remove only the auth override; let individual tests manage their own overrides.
    app.dependency_overrides.pop(verify_api_key, None)
