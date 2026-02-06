"""
Pytest Configuration and Fixtures
"""

import asyncio
import pytest
from typing import AsyncGenerator, Generator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from fastapi.testclient import TestClient
from httpx import AsyncClient

from backend.main import app
from backend.database import Base, get_db
from backend.config import get_settings


# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Get database session for tests."""
    async_session = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create test client for synchronous tests."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_session_data() -> dict:
    """Sample session creation data."""
    return {
        "project_name": "Test SAP App",
        "project_namespace": "com.test.app",
        "project_description": "A test SAP CAP application",
    }


@pytest.fixture
def sample_builder_state() -> dict:
    """Sample builder state for testing agents."""
    return {
        "session_id": "test-session-123",
        "project_name": "TestApp",
        "project_namespace": "com.test",
        "domain_template": "sales",
        "entities": [
            {
                "name": "Customer",
                "description": "Customer entity",
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True},
                    {"name": "name", "type": "String(100)", "nullable": False},
                    {"name": "email", "type": "String(255)"},
                ]
            },
            {
                "name": "Order",
                "description": "Sales order entity", 
                "fields": [
                    {"name": "ID", "type": "UUID", "key": True},
                    {"name": "orderNumber", "type": "String(20)", "nullable": False},
                    {"name": "totalAmount", "type": "Decimal(15,2)"},
                ]
            }
        ],
        "fiori_theme": "sap_horizon",
        "fiori_main_entity": "Customer",
        "auth_type": "mock",
        "roles": ["Viewer", "Editor", "Admin"],
        "agent_history": [],
        "validation_errors": [],
        "artifacts": [],
    }
