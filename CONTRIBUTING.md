# Contributing to MVP Launch API

Thank you for your interest in contributing to the MVP Launch API! This document provides guidelines and instructions for contributing.

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
- PostgreSQL 15+
- Redis 7+
- Docker (optional)

### Local Development
1. Clone your fork: `git clone https://github.com/your-username/mvp-launch-api.git`
2. Create virtual environment: `python -m venv venv`
3. Activate: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Set up environment variables (see README.md)
6. Run tests: `pytest tests/ -v`

## Code Style

### Python
- Follow PEP 8 style guidelines
- Use type hints for all function parameters and return values
- Maximum line length: 120 characters
- Use `black` for code formatting
- Use `isort` for import sorting

### Formatting Commands
```bash
# Format code
black .

# Check formatting
black --check .

# Sort imports
isort .

# Check import sorting
isort --check-only .
```

### Linting
```bash
# Run flake8
flake8 . --exclude=.venv,venv,__pycache__,.pytest_cache --max-line-length=120

# Run mypy
mypy . --ignore-missing-imports --exclude='(.venv|venv|__pycache__|\.pytest_cache)'
```

## Testing

### Writing Tests
- Place tests in the `tests/` directory
- Name test files `test_*.py`
- Use descriptive test function names starting with `test_`
- Group related tests in classes
- Use fixtures for common test data

### Running Tests
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=. --cov-report=term

# Run specific test
pytest tests/test_anomaly.py::TestAnomalyDetection::test_detect_anomalies -v
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