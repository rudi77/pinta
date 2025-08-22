# Backend Integration Testing Guide

This document describes the comprehensive integration test suite for the Maler Kostenvoranschlag backend API.

## Test Structure

The test suite includes integration tests for all major backend endpoints:

- **Authentication** (`test_auth_integration.py`) - Login, registration, token management
- **Quotes** (`test_quotes_integration.py`) - Quote CRUD operations, PDF generation, exports
- **AI Services** (`test_ai_integration.py`) - Project analysis, recommendations, optimizations
- **Documents** (`test_documents_integration.py`) - File upload, processing, text extraction
- **User Management** (`test_users_integration.py`) - Profile management, settings, admin functions

## Prerequisites

1. Install test dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure the application is properly configured with test settings.

## Running Tests

### Using Python Script (Recommended)
```bash
# Run all tests
python scripts/run_tests.py all

# Run specific test suites
python scripts/run_tests.py auth
python scripts/run_tests.py quotes
python scripts/run_tests.py ai
python scripts/run_tests.py documents
python scripts/run_tests.py users

# Run with coverage report
python scripts/run_tests.py coverage

# Run tests in parallel (faster)
python scripts/run_tests.py all --parallel
```

### Using Makefile
```bash
# Run all tests
make test

# Run specific test suites
make test-auth
make test-quotes
make test-ai
make test-docs
make test-users

# Run with coverage
make test-cov

# Run in parallel
make test-parallel
```

### Using pytest directly
```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_auth_integration.py

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run with markers
pytest -m "auth" tests/
pytest -m "not slow" tests/
```

## Test Configuration

### Test Database
Tests use an in-memory SQLite database that is created fresh for each test session:
- Database URL: `sqlite+aiosqlite:///:memory:`
- Tables are created automatically using SQLAlchemy metadata
- Each test gets a fresh database session with automatic rollback

### Test Fixtures
The test suite includes comprehensive fixtures in `conftest.py`:

- `test_engine` - Test database engine
- `test_session` - Database session with rollback
- `client` - Async HTTP client for API testing
- `test_user` - Regular test user account
- `admin_user` - Admin test user account
- `auth_headers` - Authentication headers for requests
- `test_quote` - Sample quote for testing

### Mocking
AI and external service calls are mocked to ensure:
- Tests run fast and reliably
- No external API calls during testing
- Predictable test outcomes
- No costs for external services

## Test Coverage

The test suite covers:

### Authentication Tests
- ✅ User registration (success/duplicate email)
- ✅ User login (success/invalid credentials)
- ✅ Token refresh and validation
- ✅ Password change functionality
- ✅ Logout and token blacklisting
- ✅ Protected endpoint access control

### Quotes Tests
- ✅ Quote creation and validation
- ✅ Quote retrieval (by ID, user filtering)
- ✅ Quote updates and status changes
- ✅ Quote deletion
- ✅ PDF generation
- ✅ Export functionality (JSON, CSV)
- ✅ Search and filtering
- ✅ Access control (users see only their quotes)

### AI Services Tests
- ✅ Project analysis from descriptions
- ✅ Quote optimization suggestions
- ✅ AI recommendations generation
- ✅ Quote accuracy validation
- ✅ Document content analysis
- ✅ Market insights retrieval
- ✅ Rate limiting protection

### Documents Tests
- ✅ File upload (various formats)
- ✅ File validation (type, size limits)
- ✅ Document metadata management
- ✅ File download functionality
- ✅ Text extraction from documents
- ✅ Floor plan analysis
- ✅ Search and filtering
- ✅ Access control and security
- ✅ Bulk operations

### User Management Tests
- ✅ Profile viewing and updates
- ✅ User settings management
- ✅ Activity tracking and statistics
- ✅ Account deactivation
- ✅ Data export (GDPR compliance)
- ✅ Admin user management
- ✅ Quota and subscription tracking
- ✅ Notifications system

## Test Data Management

### Test User Accounts
- Regular user: `test@example.com` / `testpassword123`
- Admin user: `admin@example.com` / `adminpassword123`

### Sample Data
- Test quotes with realistic room and pricing data
- Sample documents for upload testing
- Mock AI responses for consistent testing

## Performance and Best Practices

### Fast Test Execution
- In-memory database for speed
- Parallel test execution support
- Efficient fixture management
- Mocked external dependencies

### Test Isolation
- Each test gets fresh database session
- No shared state between tests
- Automatic cleanup after tests
- Independent test data

### Realistic Testing
- Uses actual HTTP requests through FastAPI TestClient
- Tests full request/response cycle
- Validates JSON responses and status codes
- Tests authentication flow end-to-end

## Continuous Integration

The test suite is designed for CI/CD pipelines:

```bash
# CI command
make ci-test
```

This generates:
- JUnit XML test results (`test-results.xml`)
- Coverage report in XML format
- Terminal coverage summary

## Troubleshooting

### Common Issues

1. **Import Errors**
   ```bash
   # Ensure PYTHONPATH includes src directory
   export PYTHONPATH=src:$PYTHONPATH
   ```

2. **Database Errors**
   - Tests use in-memory database, so no persistent storage issues
   - If SQLAlchemy errors occur, check model definitions

3. **Authentication Errors**
   - Ensure test JWT secret key is at least 32 characters
   - Check that fixtures are properly creating test users

4. **Mock Errors**
   - Verify mock patches match actual service method names
   - Check that mock return values match expected schemas

### Debug Mode
Run tests with verbose output and disable warnings:
```bash
pytest tests/ -v -s --disable-warnings
```

## Adding New Tests

When adding new endpoints or features:

1. Add integration tests to appropriate test file
2. Create necessary fixtures in `conftest.py`
3. Mock external service calls
4. Test both success and error cases
5. Verify access control and authorization
6. Update this documentation

## Coverage Goals

- Target: 80%+ test coverage
- Focus on critical business logic
- Test error handling paths
- Verify security controls
- Cover edge cases and validation