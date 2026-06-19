# Contributing to Agentic Loop Platform

Thank you for your interest in contributing! This guide will help you get started.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help maintain a welcoming environment

## Getting Started

1. Fork the repository
2. Clone your fork
3. Create a feature branch: `git checkout -b feature/your-feature`
4. Make your changes
5. Run tests: `pytest`
6. Commit your changes
7. Push to your fork
8. Create a Pull Request

## Development Setup

```bash
# Install dependencies
pip install -e ".[dev]"

# Start infrastructure
docker compose up -d

# Run migrations
alembic upgrade head

# Start development server
uvicorn apps.api.main:app --reload
```

## Code Standards

### Python
- Follow PEP 8
- Use type hints
- Write docstrings for public functions
- Keep functions under 50 lines
- Use async/await for I/O operations

### Testing
- Write tests for all new features
- Maintain >80% coverage
- Use pytest fixtures
- Mock external dependencies

### Git
- Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`
- Keep commits atomic
- Write clear commit messages

## Pull Request Process

1. Update documentation if needed
2. Add tests for new features
3. Ensure all tests pass
4. Request review from maintainers
5. Address review feedback
6. Merge after approval

## Architecture

- **packages/** — Core business logic
- **apps/api/** — FastAPI application
- **apps/web/** — Next.js frontend
- **docs/** — Documentation and ADRs
- **tests/** — Test suite

## Adding Features

1. Create an ADR in `docs/adr/`
2. Implement in appropriate package
3. Add API routes if needed
4. Write tests
5. Update documentation
6. Add to feature_list.json

## Reporting Issues

- Use GitHub Issues
- Include reproduction steps
- Include environment details
- Be specific about expected vs actual behavior

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
