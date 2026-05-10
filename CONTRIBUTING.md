# Contributing to Forge Intelligence — MVP Launch

Thank you for your interest in contributing! This project has both a **Python FastAPI backend** and a **React + TypeScript frontend**. Please follow the guidelines below for the area you're working on.

## Getting Started

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes
4. Run tests to ensure nothing is broken
5. Commit your changes with a clear message
6. Push to your fork and submit a pull request

## Development Setup

### Prerequisites
- Python 3.11+
- PostgreSQL 15+ (with pgvector)
- Redis 7+
- Node.js 20+ (for frontend)
- Docker (optional, for containerized deployment)

### Local Development (Backend)
1. Clone your fork: `git clone https://github.com/unn-Known1/mvp-launch-api.git`
2. Create virtual environment: `python -m venv venv`
3. Activate: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Set up environment variables (see README.md)
6. Run tests: `pytest tests/ -v`

### Local Development (Frontend)
1. Navigate to the frontend directory: `cd frontend`
2. Install dependencies: `npm install`
3. Start dev server: `npm run dev`
4. The app runs at `http://localhost:5173`

## Code Style

### Python (Backend)
- Follow PEP 8 style guidelines
- Use type hints for all function parameters and return values
- Maximum line length: 120 characters
- Use `black` for code formatting
- Use `isort` for import sorting

### TypeScript / React (Frontend)
- Use functional components with hooks
- Follow project ESLint config (`eslint.config.js`)
- Use TypeScript strict mode
- Use the shared design system components (see `src/components/ui/`)
- Prefer CSS modules or Tailwind utility classes over inline styles

### Formatting Commands

**Backend:**
```bash
black .
black --check .
isort .
isort --check-only .
```

**Frontend:**
```bash
cd frontend
npm run lint
npm run format
```

### Linting

**Backend:**
```bash
flake8 . --exclude=.venv,venv,__pycache__,.pytest_cache --max-line-length=120
mypy . --ignore-missing-imports --exclude='(.venv|venv|__pycache__|\.pytest_cache)'
```

**Frontend:**
```bash
cd frontend
npx tsc --noEmit
npm run lint
```

## Testing

### Backend Tests (Python)
- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Use descriptive test function names starting with `test_`
- Group related tests in classes
- Use fixtures for common test data

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=. --cov-report=term

# Run specific test
pytest tests/test_anomaly.py::TestAnomalyDetection::test_detect_anomalies -v
```

### Frontend Tests (TypeScript)
- Place tests next to source files as `*.test.tsx`
- Use Vitest and React Testing Library

```bash
cd frontend
npm test
npm test -- --coverage
```

## Commit Messages

Use clear, descriptive commit messages following conventional commits:

- `feat: Add new endpoint for user authentication`
- `fix: Resolve database connection timeout issue`
- `docs: Update API documentation for new endpoints`
- `style: Format code with black`
- `refactor: Restructure anomaly detection module`
- `test: Add unit tests for CSV upload functionality`
- `chore: Update dependencies to latest versions`

## Pull Request Process

1. **Update documentation** if you're adding features or changing behavior
2. **Add tests** for new functionality
3. **Ensure all tests pass** before submitting
4. **Update the README** if needed
5. **Keep pull requests focused** - one feature or fix per PR

### PR Template
```markdown
## Description
[Describe your changes]

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests pass locally
- [ ] New tests added (if applicable)
- [ ] Manual testing performed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings generated
```

## Reporting Issues

### Bug Reports
- Use the GitHub issue tracker
- Include reproduction steps
- Include expected vs actual behavior
- Include environment details (OS, Python version, etc.)

### Feature Requests
- Describe the feature clearly
- Explain the use case
- Consider implementation approach

## Code Review

All submissions require review before merging. We use GitHub pull requests for this purpose. Please respond to review feedback promptly and make requested changes.

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (proprietary and confidential).