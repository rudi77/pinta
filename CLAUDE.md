# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI-based backend for "Maler Kostenvoranschlag" - an AI-powered quote generation system for painting contractors. The application uses OpenAI GPT-4 for intelligent document analysis, quote generation, and natural language processing, with PostgreSQL/SQLite for data persistence and Redis for caching.

**Note**: The README mentions Flask but the codebase actually uses **FastAPI** - this is the authoritative framework in use.

## Architecture & Key Components

### Core Structure
- **FastAPI Application**: Main app in `src/main.py` with lifespan management for startup/shutdown
- **Database Layer**: SQLAlchemy async with conditional pooling (supports both SQLite and PostgreSQL)
- **Authentication**: JWT-based with token blacklisting and refresh token support
- **AI Integration**: OpenAI GPT-4o integration for document analysis and quote generation
- **Document Processing**: OCR with Tesseract, PDF processing with pdfplumber
- **Caching**: Redis-based caching service
- **Background Tasks**: Async task management system

### Import Path Configuration
The codebase uses `src/` as the Python path root. All imports are relative to `src/`, e.g.:
```python
from core.database import Base
from models.models import User
from routes.auth import router
```

### Database Models Architecture
- **User**: Core user entity with quota tracking, Stripe integration, premium subscriptions
- **Quote**: Quote entities with AI conversation history, status workflow
- **QuoteItem**: Line items within quotes with room/area details
- **Document**: File uploads with OCR results, processing metadata
- **Payment**: Stripe payment integration
- **UsageTracking**: Resource usage monitoring
- **QuotaNotification**: User quota limit notifications

### Circular Import Management
The codebase uses local imports in functions to avoid circular dependencies:
```python
# In security.py
async def get_current_user(...):
    from models.models import User  # Local import to avoid circular dependency
```

## Development Commands

### Environment Setup
```bash
# Backend setup
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt

# Set PYTHONPATH for development
$env:PYTHONPATH = "C:\Users\rudi\source\pinta\backend\src"  # PowerShell
```

### Testing (Integration Test Suite)
```bash
# Run all integration tests
python scripts/run_tests.py all

# Run specific test suites
python scripts/run_tests.py auth     # Authentication tests
python scripts/run_tests.py quotes   # Quote management tests
python scripts/run_tests.py ai       # AI service tests
python scripts/run_tests.py documents # Document processing tests
python scripts/run_tests.py users    # User management tests

# Coverage and parallel execution
python scripts/run_tests.py coverage
python scripts/run_tests.py all --parallel

# Using make commands
make test
make test-cov
make test-auth
```

### Database Management
```bash
# Run Alembic migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "Description"
```

### Docker Development Environment
```bash
# Full stack with PostgreSQL + Redis
docker-compose up --build

# Individual services
docker-compose up db redis  # Just database and cache
```

### Code Quality
```bash
make lint     # Run flake8, black --check, isort --check
make format   # Auto-format with black and isort
make clean    # Clean generated files
```

## Database Configuration Notes

### SQLite vs PostgreSQL Compatibility
The database engine configuration conditionally applies pooling parameters:
```python
# Only PostgreSQL gets connection pooling
if not settings.database_url.startswith("sqlite"):
    engine_kwargs.update({
        "pool_size": settings.database_pool_max_size,
        # ... other pooling params
    })
```

### Settings & Environment Variables
Settings use Pydantic with field validators. Key environment variables:
- `DATABASE_URL`: Database connection string
- `OPENAI_API_KEY`: Required for AI features
- `STRIPE_SECRET_KEY`: For payment processing
- `REDIS_URL`: Cache connection
- `SECRET_KEY`: JWT signing (must be 32+ chars)

## Testing Architecture

### Integration Test Structure
- **Test Database**: In-memory SQLite with fresh schema per test
- **Test Fixtures**: Comprehensive fixtures in `conftest.py` for users, auth, quotes
- **Mocked Services**: AI service calls are mocked for reliability
- **Isolated App**: Tests create separate FastAPI app to avoid main app conflicts

### Key Test Patterns
```python
# Authentication testing
async def test_login(client: AsyncClient, test_user: User):
    response = await client.post("/auth/login", data={"username": "...", "password": "..."})
    
# Authorized requests
async def test_protected_endpoint(client: AsyncClient, auth_headers: dict):
    response = await client.get("/quotes/", headers=auth_headers)
```

## AI Service Integration

### Document Processing Pipeline
1. **Upload**: File validation, hash-based deduplication
2. **OCR**: Tesseract text extraction with confidence scoring
3. **AI Analysis**: GPT-4 document interpretation
4. **Structured Data**: Extract rooms, measurements, work requirements

### Quote Generation Flow
1. **Input Processing**: Natural language or document-based input
2. **AI Enhancement**: GPT-4 generates intelligent follow-up questions
3. **Cost Calculation**: AI-assisted pricing based on extracted requirements
4. **PDF Generation**: Professional quote formatting

## Critical Development Notes

### Model Changes & Migrations
When modifying SQLAlchemy models:
1. Avoid reserved field names like `metadata` (use `action_metadata`)
2. Always run `alembic revision --autogenerate` after model changes
3. Test migrations on both SQLite and PostgreSQL

### Security Considerations
- JWT tokens use blacklisting for logout
- All database queries use SQLAlchemy ORM to prevent SQL injection
- File uploads are validated by type and size
- Sensitive data (API keys) are environment variables only

### Performance Patterns
- Use Redis caching for expensive AI calls
- Background task processing for long-running operations
- Database connection pooling for PostgreSQL deployments
- Async/await throughout for I/O operations

## Service Dependencies

### Required External Services
- **OpenAI API**: Core AI functionality
- **Stripe**: Payment processing
- **Redis**: Caching (optional but recommended)
- **PostgreSQL**: Production database (SQLite for development)

### Optional Integrations
- **SMTP**: Email notifications
- **Tesseract OCR**: Document text extraction
- **pdf2image**: PDF to image conversion