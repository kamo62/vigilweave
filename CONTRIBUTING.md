# Contributing to VigilWeave

Thank you for your interest in VigilWeave.

## License

VigilWeave is released under the [MIT License](LICENSE). By submitting a pull
request you agree that your contribution is licensed under the same terms.

## Code of Conduct

This project and everyone participating in it is governed by our commitment to:
- Being respectful and inclusive
- Focusing on constructive feedback
- Welcoming newcomers
- Prioritizing user safety and security

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues to see if the problem has already been reported. When you are creating a bug report, please include as many details as possible:

- **Use a clear and descriptive title**
- **Describe the exact steps to reproduce the problem**
- **Provide specific examples to demonstrate the steps**
- **Describe the behavior you observed and what behavior you expected**
- **Include code samples and screenshots if applicable**

### Suggesting Enhancements

Enhancement suggestions are tracked as issues. When creating an enhancement
suggestion, please include:

- **Use a clear and descriptive title**
- **Provide a step-by-step description of the suggested enhancement**
- **Provide specific examples to demonstrate the enhancement**
- **Explain why this enhancement would be useful**

### Pull Requests

1. Work from an approved branch in the authorized source repository.
2. Create a new branch from `main` (`git checkout -b feat/amazing-feature`)
3. Make your changes.
4. Run the required tests and checks.
5. Open a pull request in the authorized repository.

## Development Setup

### Prerequisites

- Python 3.14+
- Node.js 20+ and Bun
- Docker (optional)
- Redis (for background tasks)

### Backend Setup

```bash
# Obtain access to the authorized source repository, then clone it locally.
cd vigilweave

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Run migrations
alembic upgrade head

# Start the development server
uvicorn app.main:app --reload
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
bun install

# Start development server
bun run dev
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_scans_api.py -v
```

### Code Style

We use the following tools to maintain code quality:

- **Python:** Ruff for linting and formatting
- **TypeScript:** ESLint and Prettier
- **Type checking:** mypy for Python

Please ensure your code passes all required checks before submitting a PR.

```bash
# Python linting
ruff check .
ruff format .

# Type checking
mypy app

# Frontend linting (in frontend/ directory)
cd frontend
bun run lint
bun run typecheck
```

## Project Structure

```
vigilweave/
├── app/                    # Backend (Python/FastAPI)
│   ├── api/               # API endpoints
│   ├── core/              # Core modules (config, security, database)
│   ├── models/            # SQLModel database models
│   ├── services/          # Business logic
│   └── tasks/             # Celery background tasks
├── frontend/              # Frontend (React/TypeScript)
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── pages/         # Page components
│   │   └── lib/           # Utilities and API client
├── tests/                 # Test suite
├── docs/                  # Documentation
└── infrastructure/        # Deployment configurations
```

## Architecture Guidelines

### Backend

- **API Layer:** Use FastAPI dependency injection for shared resources
- **Services:** Keep business logic in services, not endpoints
- **Models:** Use SQLModel for type-safe database operations
- **Error Handling:** Use custom exceptions and consistent error responses

### Frontend

- **Components:** Keep components small and focused
- **State Management:** Use TanStack Query for server state
- **Types:** All TypeScript types should be generated from OpenAPI spec
- **Styling:** Use Tailwind CSS with consistent design tokens

## Testing Guidelines

- **Unit Tests:** Test individual functions and classes
- **Integration Tests:** Test API endpoints with TestClient
- **E2E Tests:** Test complete user workflows
- **Coverage:** Aim for >80% code coverage

## Documentation

- Update the README.md if you change functionality
- Add docstrings to public functions and classes
- Update the OpenAPI spec if you modify API endpoints
- Add examples for new features

## Security

- Never commit secrets or API keys
- Use environment variables for configuration
- Follow security best practices for authentication
- Report security vulnerabilities privately to security@vigilweave.com

## Feature Flags

Some features may be behind feature flags for gradual rollout:

```python
if settings.FEATURE_NEW_AWESOME_FEATURE:
    # New feature code
```

## Commit Message Guidelines

We follow conventional commits:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Adding or updating tests
- `chore:` Build process or auxiliary tool changes

Example: `feat: Add support for custom quality gates`

## Questions?

Open a discussion or issue in the repository, or email contributors@vigilweave.com.

## Recognition

Thank you for contributing to VigilWeave.
