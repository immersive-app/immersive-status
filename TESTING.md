# Testing

This project includes comprehensive tests for the uptime checker functionality.

## Running Tests

### Using the test runner script (recommended)
```bash
python run_tests.py
```
The test runner automatically:
- Creates a virtual environment if it doesn't exist
- Installs all required dependencies
- Runs the tests in isolation

### Using pytest directly with virtual environment
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-test.txt
pip install requests boto3

# Run tests
pytest tests/ -v
```

### Using pytest directly (not recommended)
```bash
# Install test dependencies globally
pip install -r requirements-test.txt

# Run tests
pytest tests/ -v
```
**Note**: This is not recommended as it may conflict with system packages.

## Test Coverage

The tests cover:

- **Status file operations**: Reading and writing status.json
- **Commit logic**: Only committing when status changes from failure to success
- **HTTP requests**: Mocked external API calls
- **Email sending**: Mocked AWS SES operations
- **Error handling**: Various failure scenarios
- **Environment variables**: Proper configuration handling

## Test Structure

- `tests/test_check_uptime.py`: Main test file with comprehensive test cases
- `pytest.ini`: Pytest configuration
- `requirements-test.txt`: Test dependencies
- `.github/workflows/test.yml`: CI/CD test workflow

## Mocking

All external dependencies are properly mocked:
- HTTP requests to the target URL
- AWS SES email sending
- File system operations
- Time functions for consistent latency testing

This ensures tests run quickly and don't require actual external services.
