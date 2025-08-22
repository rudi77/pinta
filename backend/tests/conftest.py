import pytest
import asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Import models and database separately to avoid main app initialization
from src.core.database import Base, get_db
from src.core.settings import Settings
from src.models.models import User, Quote, Document
from src.core.security import get_password_hash

# Test database configuration
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

class TestSettings(Settings):
    """Test-specific settings"""
    database_url: str = TEST_DATABASE_URL
    secret_key: str = "test-secret-key-for-jwt-tokens-must-be-32-chars-long"
    debug: bool = True
    openai_api_key: str = "test-key"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def test_engine():
    """Create test database engine for each test"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    
    # Create tables for each test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Clean up
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session with proper isolation using savepoints"""
    connection = await test_engine.connect()
    transaction = await connection.begin()
    
    TestSessionLocal = async_sessionmaker(
        bind=connection, class_=AsyncSession, expire_on_commit=False
    )
    
    async with TestSessionLocal() as session:
        # Create a savepoint for this test
        savepoint = await connection.begin_nested()
        
        try:
            yield session
        finally:
            # Rollback to savepoint to clean state
            await savepoint.rollback()
            await session.close()
    
    await transaction.rollback()
    await connection.close()

def create_test_app():
    """Create FastAPI app for testing without initializing main database"""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    
    app = FastAPI(title="Test API")
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Import and include routers
    from src.routes import auth, users, quotes, ai, payments, chat, documents, quota
    
    app.include_router(auth.router, tags=["authentication"])
    app.include_router(users.router, tags=["users"])
    app.include_router(quotes.router)
    app.include_router(ai.router, tags=["ai"])
    app.include_router(payments.router, tags=["payments"])
    app.include_router(chat.router, tags=["chat"])
    app.include_router(documents.router, tags=["documents"])
    app.include_router(quota.router, tags=["quota"])
    
    return app

@pytest.fixture
async def client(test_session) -> AsyncGenerator[AsyncClient, None]:
    """Create test client with test database"""
    
    app = create_test_app()
    
    async def get_test_db():
        yield test_session
    
    app.dependency_overrides[get_db] = get_test_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

@pytest.fixture
async def test_user(test_session) -> User:
    """Create a test user"""
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    user = User(
        email=f"test-{unique_id}@example.com",
        username=f"testuser-{unique_id}",
        hashed_password=get_password_hash("testpassword123"),
        is_active=True,
        is_verified=True,
        phone_number="+1234567890",
        company_name="Test Company"
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user

@pytest.fixture
async def admin_user(test_session) -> User:
    """Create a test admin user"""
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    user = User(
        email=f"admin-{unique_id}@example.com",
        username=f"admin-{unique_id}",
        hashed_password=get_password_hash("adminpassword123"),
        is_active=True,
        is_verified=True,
        is_superuser=True,
        phone_number="+1234567891",
        company_name="Admin Company"
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user

@pytest.fixture
async def auth_headers(client: AsyncClient, test_user: User) -> dict:
    """Get authentication headers for test user"""
    login_data = {
        "username": test_user.email,
        "password": "testpassword123"
    }
    
    response = await client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200
    
    token_data = response.json()
    return {"Authorization": f"Bearer {token_data['access_token']}"}

@pytest.fixture
async def admin_auth_headers(client: AsyncClient, admin_user: User) -> dict:
    """Get authentication headers for admin user"""
    login_data = {
        "username": admin_user.email,
        "password": "adminpassword123"
    }
    
    response = await client.post("/api/v1/auth/login", data=login_data)
    assert response.status_code == 200
    
    token_data = response.json()
    return {"Authorization": f"Bearer {token_data['access_token']}"}

@pytest.fixture
async def test_quote(test_session, test_user) -> Quote:
    """Create a test quote"""
    quote = Quote(
        quote_number="TEST-001",
        customer_name="Test Customer",
        customer_email="customer@example.com",
        customer_phone="+1234567890",
        customer_address="123 Test St",
        user_id=test_user.id,
        rooms=[
            {
                "name": "Living Room",
                "area": 25.5,
                "wall_area": 45.0,
                "ceiling_area": 25.5,
                "floor_area": 25.5,
                "paint_type": "Premium",
                "coating_type": "Latex",
                "labor_hours": 8
            }
        ],
        total_amount=1250.00,
        labor_cost=400.00,
        material_cost=850.00,
        status="draft"
    )
    test_session.add(quote)
    await test_session.commit()
    await test_session.refresh(quote)
    return quote