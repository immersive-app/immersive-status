import os
import json
import tempfile
import pytest
from unittest.mock import patch, MagicMock, mock_open
import sys
from pathlib import Path

# Add the scripts directory to the path so we can import check_uptime
sys.path.insert(0, str(Path(__file__).parent.parent / "docs" / ".github" / "workflows" / "scripts"))

# Set up environment variables before importing check_uptime
os.environ.update({
    "TARGET_URL": "https://test.example.com/up",
    "TIMEOUT_SECONDS": "5",
    "AWS_REGION": "us-east-1",
    "FROM_EMAIL": "test@example.com",
    "TO_EMAIL": "admin@example.com"
})

import check_uptime


class TestCheckUptime:
    """Test cases for the check_uptime module."""
    
    def setup_method(self):
        """Set up test environment before each test."""
        # Set up environment variables
        os.environ.update({
            "TARGET_URL": "https://test.example.com/up",
            "TIMEOUT_SECONDS": "5",
            "AWS_REGION": "us-east-1",
            "FROM_EMAIL": "test@example.com",
            "TO_EMAIL": "admin@example.com"
        })
        
        # Create a temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Create docs directory
        os.makedirs("docs", exist_ok=True)
        
        # Clear any existing status file
        if os.path.exists("docs/status.json"):
            os.remove("docs/status.json")
        
        # Clear environment variable
        if "SHOULD_COMMIT" in os.environ:
            del os.environ["SHOULD_COMMIT"]
    
    def teardown_method(self):
        """Clean up after each test."""
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_read_previous_status_no_file(self):
        """Test reading previous status when no file exists."""
        result = check_uptime.read_previous_status()
        assert result is None
    
    def test_read_previous_status_invalid_json(self):
        """Test reading previous status when file contains invalid JSON."""
        with open("docs/status.json", "w") as f:
            f.write("invalid json")
        
        result = check_uptime.read_previous_status()
        assert result is None
    
    def test_read_previous_status_valid_json(self):
        """Test reading previous status when file contains valid JSON."""
        expected_status = {
            "ok": True,
            "status": 200,
            "latency_ms": 150,
            "checked_at": "2024-01-01T12:00:00Z",
            "url": "https://test.example.com/up",
            "error": None
        }
        
        with open("docs/status.json", "w") as f:
            json.dump(expected_status, f)
        
        result = check_uptime.read_previous_status()
        assert result == expected_status
    
    
    @patch('check_uptime.boto3.client')
    def test_send_email_success(self, mock_boto3_client):
        """Test successful email sending."""
        mock_ses = MagicMock()
        mock_boto3_client.return_value = mock_ses
        
        check_uptime.send_email("Test Subject", "<h1>Test Body</h1>")
        
        mock_boto3_client.assert_called_once_with("sesv2", region_name="us-east-1")
        mock_ses.send_email.assert_called_once_with(
            FromEmailAddress="test@example.com",
            Destination={"ToAddresses": ["admin@example.com"]},
            Content={"Simple": {"Subject": {"Data": "Test Subject"}, "Body": {"Html": {"Data": "<h1>Test Body</h1>"}}}}
        )
    
    def test_write_status_success(self):
        """Test writing status file with success status."""
        result = check_uptime.write_status(True, 200, 150, None)
        
        # Check that file was written
        assert os.path.exists("docs/status.json")
        
        with open("docs/status.json", "r") as f:
            data = json.load(f)
        
        assert data["ok"] is True
        assert data["status"] == 200
        assert data["latency_ms"] == 150
        assert data["error"] is None
        assert data["url"] == "https://test.example.com/up"
        assert "checked_at" in data
        
        # Should commit on first write (no previous status)
        assert result is True
    
    def test_write_status_failure(self):
        """Test writing status file with failure status."""
        result = check_uptime.write_status(False, 500, 1000, "Connection timeout")
        
        # Check that file was written
        assert os.path.exists("docs/status.json")
        
        with open("docs/status.json", "r") as f:
            data = json.load(f)
        
        assert data["ok"] is False
        assert data["status"] == 500
        assert data["latency_ms"] == 1000
        assert data["error"] == "Connection timeout"
        assert data["url"] == "https://test.example.com/up"
        assert "checked_at" in data
        
        # Should commit on first write (no previous status)
        assert result is True
    
    @patch('check_uptime.requests.get')
    def test_main_success(self, mock_get):
        """Test main function with successful request."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Mock time to control latency
        with patch('check_uptime.time.time') as mock_time:
            mock_time.side_effect = [0, 0.15]  # 150ms latency
            
            check_uptime.main()
        
        # Check that status was written
        assert os.path.exists("docs/status.json")
        
        with open("docs/status.json", "r") as f:
            data = json.load(f)
        
        assert data["ok"] is True
        assert data["status"] == 200
        assert data["latency_ms"] == 150
        
        # Check environment variable
        assert os.environ.get("SHOULD_COMMIT") == "true"
    
    @patch('check_uptime.requests.get')
    def test_main_failure(self, mock_get):
        """Test main function with failed request."""
        # Mock failed response
        mock_get.side_effect = Exception("Connection timeout")
        
        with patch('check_uptime.send_email') as mock_send_email:
            with pytest.raises(SystemExit) as exc_info:
                check_uptime.main()
            
            # Should exit with code 2
            assert exc_info.value.code == 2
        
        # Check that status was written
        assert os.path.exists("docs/status.json")
        
        with open("docs/status.json", "r") as f:
            data = json.load(f)
        
        assert data["ok"] is False
        assert data["status"] is None
        assert data["error"] == "Connection timeout"
        
        # Check environment variable
        assert os.environ.get("SHOULD_COMMIT") == "true"
        
        # Check that email was sent
        mock_send_email.assert_called_once()
    
    @patch('check_uptime.requests.get')
    def test_main_http_error(self, mock_get):
        """Test main function with HTTP error status."""
        # Mock HTTP error response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        with patch('check_uptime.send_email') as mock_send_email:
            with pytest.raises(SystemExit) as exc_info:
                check_uptime.main()
            
            # Should exit with code 2
            assert exc_info.value.code == 2
        
        # Check that status was written
        assert os.path.exists("docs/status.json")
        
        with open("docs/status.json", "r") as f:
            data = json.load(f)
        
        assert data["ok"] is False
        assert data["status"] == 500
        
        # Check that email was sent
        mock_send_email.assert_called_once()
    
    @patch('check_uptime.requests.get')
    def test_main_success_no_commit_when_unchanged(self, mock_get):
        """Test main function doesn't commit when status remains success."""
        # Create previous status with success
        previous_status = {
            "ok": True,
            "status": 200,
            "latency_ms": 150,
            "checked_at": "2024-01-01T12:00:00Z",
            "url": "https://test.example.com/up",
            "error": None
        }
        
        with open("docs/status.json", "w") as f:
            json.dump(previous_status, f)
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Mock time to control latency
        with patch('check_uptime.time.time') as mock_time:
            mock_time.side_effect = [0, 0.15]  # 150ms latency
            
            check_uptime.main()
        
        # Check environment variable - should not commit
        assert os.environ.get("SHOULD_COMMIT") == "false"
    
    @patch('check_uptime.requests.get')
    def test_main_failure_to_success_commits(self, mock_get):
        """Test main function commits when status changes from failure to success."""
        # Create previous status with failure
        previous_status = {
            "ok": False,
            "status": 500,
            "latency_ms": 1000,
            "checked_at": "2024-01-01T12:00:00Z",
            "url": "https://test.example.com/up",
            "error": "Connection timeout"
        }
        
        with open("docs/status.json", "w") as f:
            json.dump(previous_status, f)
        
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Mock time to control latency
        with patch('check_uptime.time.time') as mock_time:
            mock_time.side_effect = [0, 0.15]  # 150ms latency
            
            check_uptime.main()
        
        # Check environment variable - should commit
        assert os.environ.get("SHOULD_COMMIT") == "true"
