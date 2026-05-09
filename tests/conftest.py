"""
E2E Integration Test Suite - Configuration and Fixtures

Provides httpx AsyncClient fixtures for end-to-end testing against the running API.
"""

import asyncio
import os
import sys
from collections import namedtuple
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Database URL for tests - use embedded postgres from Paperclip config
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:54329/app_db",
)

# Set environment variable before importing
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# API base URL for testing
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """
    AsyncClient fixture for making HTTP requests to the API.
    Uses ASGITransport to test directly against the FastAPI app.
    """
    from main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url=API_BASE_URL) as ac:
        yield ac


@pytest.fixture
def mock_active_user():
    """Fixture providing a mock active user for auth tests."""
    MockUser = namedtuple("MockUser", ["id", "email", "name", "is_active", "role"])
    return MockUser(
        id="test-user-e2e-id",
        email="e2e@test.com",
        name="E2E Test User",
        is_active=True,
        role="admin",
    )


@pytest.fixture
def mock_inactive_user():
    """Fixture providing a mock inactive user for auth tests."""
    MockUser = namedtuple("MockUser", ["id", "email", "name", "is_active", "role"])
    return MockUser(
        id="test-inactive-user-id",
        email="inactive@test.com",
        name="Inactive User",
        is_active=False,
        role="viewer",
    )


@pytest.fixture
def sample_csv_content() -> bytes:
    """Sample CSV content for testing uploads."""
    return b"""name,age,active,joined,salary
Alice,30,true,2024-01-01,50000
Bob,25,false,2024-02-15,45000
Charlie,35,true,2024-03-20,60000
Diana,28,true,2024-04-10,55000
Eve,32,false,2024-05-05,48000
"""


@pytest.fixture
def time_series_csv_content() -> bytes:
    """Time series CSV for anomaly detection tests."""
    return b"""timestamp,value
2024-01-01 00:00:00,100
2024-01-01 01:00:00,102
2024-01-01 02:00:00,98
2024-01-01 03:00:00,101
2024-01-01 04:00:00,99
2024-01-01 05:00:00,250
2024-01-01 06:00:00,103
2024-01-01 07:00:00,101
2024-01-01 08:00:00,99
2024-01-01 09:00:00,100
"""


@pytest.fixture
def forecast_csv_content() -> bytes:
    """CSV with date and value columns for forecasting."""
    return b"""date,sales
2024-01-01,100
2024-01-02,120
2024-01-03,115
2024-01-04,130
2024-01-05,125
2024-01-06,140
2024-01-07,138
2024-01-08,145
2024-01-09,150
2024-01-10,155
2024-01-11,160
2024-01-12,158
"""


@pytest.fixture
def override_get_current_user(mock_active_user):
    """Override the get_current_user dependency with a mock user."""
    from auth import get_current_user, main

    main.app.dependency_overrides[get_current_user] = lambda: mock_active_user
    yield mock_active_user
    main.app.dependency_overrides.clear()


@pytest.fixture
def override_get_current_user_inactive(mock_inactive_user):
    """Override the get_current_user dependency with an inactive mock user."""
    from auth import get_current_user, main

    main.app.dependency_overrides[get_current_user] = lambda: mock_inactive_user
    yield mock_inactive_user
    main.app.dependency_overrides.clear()