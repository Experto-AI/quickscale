"""Unit tests for the log_scanner module."""
import os
import tempfile
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from quickscale.utils.log_scanner import LogScanner, LogPattern, LogIssue


class TestLogPattern:
    """Tests for the LogPattern class."""
    
    def test_pattern_initialization(self):
        """Test that LogPattern initializes correctly."""
        pattern = LogPattern("test pattern", "error", "Test description", 2)
        
        assert pattern.severity == "error"
        assert pattern.description == "Test description"
        assert pattern.context_lines == 2
        assert hasattr(pattern, "pattern")  # Compiled regex
    
    def test_pattern_matching(self):
        """Test that compiled patterns match as expected."""
        # Test case-insensitive matching
        pattern = LogPattern("error")
        text = "This is an ERROR message"
        match = pattern.pattern.search(text)
        assert match is not None
        assert match.group(0).lower() == "error"
        
        # Test multiline matching
        pattern = LogPattern("traceback", "error")
        text = "Line 1\nTraceback (most recent call last):\nLine 3"
        match = pattern.pattern.search(text)
        assert match is not None
        assert match.group(0).lower() == "traceback"


class TestLogIssue:
    """Tests for the LogIssue class."""
    
    def test_issue_initialization(self):
        """Test that LogIssue initializes correctly."""
        issue = LogIssue("Error message", "error", "build", 42, ["context line"])
        
        assert issue.message == "Error message"
        assert issue.severity == "error"
        assert issue.source == "build"
        assert issue.line_number == 42
        assert issue.context == ["context line"]
    
    def test_issue_string_representation(self):
        """Test string representation of LogIssue."""
        issue = LogIssue("Error message", "error", "build")
        str_rep = str(issue)
        
        assert "[ERROR]" in str_rep
        assert "Error message" in str_rep
        assert "build" in str_rep


class TestLogScanner:
    """Tests for the LogScanner class."""
    
    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary directory for the project."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield Path(tmp_dir)
    
    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger."""
        return MagicMock()
    
    @pytest.fixture
    def scanner(self, temp_project_dir, mock_logger):
        """Create a LogScanner instance."""
        return LogScanner(temp_project_dir, mock_logger)
    
    def test_scanner_initialization(self, scanner, temp_project_dir, mock_logger):
        """Test that LogScanner initializes correctly."""
        assert scanner.project_dir == temp_project_dir
        assert scanner.logger == mock_logger
        assert scanner.issues == []
    
    def test_scan_file(self, scanner, temp_project_dir):
        """Test scanning a log file for issues."""
        # Create a test log file
        log_content = """
        [INFO] Build started
        [ERROR] Failed to start services
        [INFO] Retrying
        [WARNING] Container status check timed out
        [ERROR] Database setup failed
        """
        
        log_file = temp_project_dir / "test_log.txt"
        with open(log_file, "w") as f:
            f.write(log_content)
        
        # Scan the file
        issues = scanner._scan_file(log_file, "build")
        
        # Verify the results - our important specific patterns are matched
        assert issues is not None
        assert any(issue.message == "Failed to start services" for issue in issues)
        assert any(issue.message == "Database setup failed" for issue in issues)
        
        # Verify that error severity is correctly assigned
        error_issues = [issue for issue in issues if issue.severity == "error"]
        assert len(error_issues) >= 2
        
        # Verify that the specific errors we care about are marked as errors
        specific_errors = [issue for issue in issues 
                          if issue.message in ["Failed to start services", "Database setup failed"]]
        assert all(issue.severity == "error" for issue in specific_errors)
    
    def test_generate_summary(self, scanner):
        """Test generating a summary of issues."""
        # Add some test issues
        scanner.issues = [
            LogIssue("Error 1", "error", "build"),
            LogIssue("Error 2", "error", "container:web"),
            LogIssue("Warning 1", "warning", "migration")
        ]
        
        # Set logs_accessed to True
        scanner.logs_accessed = True
        
        # Generate summary
        summary = scanner.generate_summary()
        
        # Verify the summary
        assert summary["total_issues"] == 3
        assert summary["error_count"] == 2
        assert summary["warning_count"] == 1
        assert "build" in summary["issues_by_source"]
        assert "container:web" in summary["issues_by_source"]
        assert "migration" in summary["issues_by_source"]
        assert len(summary["issues_by_severity"]["error"]) == 2
        assert len(summary["issues_by_severity"]["warning"]) == 1
        assert summary["has_critical_issues"] is True
    
    def test_empty_summary(self, scanner):
        """Test generating a summary with no issues."""
        # No issues
        scanner.issues = []
        
        # Set logs_accessed to True
        scanner.logs_accessed = True
        
        # Generate summary
        summary = scanner.generate_summary()
        
        # Verify the summary
        assert summary["total_issues"] == 0
        assert summary["error_count"] == 0
        assert summary["warning_count"] == 0
        assert summary["issues_by_source"] == {}
        assert summary["has_critical_issues"] is False
    
    def test_summary_no_logs_accessed(self, scanner):
        """Test generating a summary when no logs were accessed."""
        # No issues
        scanner.issues = []
        
        # Ensure logs_accessed is False
        scanner.logs_accessed = False
        
        # Generate summary
        summary = scanner.generate_summary()
        
        # Verify the summary
        assert summary["total_issues"] == 0
        assert summary["error_count"] == 0
        assert summary["warning_count"] == 0
        assert summary["issues_by_source"] == {}
        assert summary["has_critical_issues"] is False
        assert summary["logs_accessed"] is False
    
    @patch("builtins.print")
    def test_print_summary_no_issues(self, mock_print, scanner):
        """Test printing a summary with no issues."""
        scanner.issues = []
        scanner.logs_accessed = True
        scanner.print_summary()
        mock_print.assert_called_with("\n✅ No issues found in logs")
    
    @patch("builtins.print")
    def test_print_summary_with_issues(self, mock_print, scanner):
        """Test printing a summary with issues."""
        scanner.issues = [
            LogIssue("Error 1", "error", "build"),
            LogIssue("Warning 1", "warning", "migration")
        ]
        scanner.logs_accessed = True
        scanner.print_summary()
        # Verify that print was called multiple times with the expected content
        assert any("🔍 Log Scan Results:" in args[0] for args, _ in mock_print.call_args_list)
        assert any("- 1 errors" in args[0] for args, _ in mock_print.call_args_list)
        assert any("- 1 warnings" in args[0] for args, _ in mock_print.call_args_list)
        assert any("❌ Critical Issues:" in args[0] for args, _ in mock_print.call_args_list)
        assert any("Error 1" in args[0] for args, _ in mock_print.call_args_list)
        assert any("⚠️ Warnings:" in args[0] for args, _ in mock_print.call_args_list)
        assert any("Warning 1" in args[0] for args, _ in mock_print.call_args_list)
    
    @patch("builtins.print")
    def test_print_summary_no_logs_accessed(self, mock_print, scanner):
        """Test printing a summary when no logs were accessed."""
        scanner.issues = []
        scanner.logs_accessed = False
        scanner.print_summary()
        
        # Verify that appropriate message is printed
        assert any("⚠️ Could not access any log files for scanning" in args[0] 
                  for args, _ in mock_print.call_args_list)
        assert any("This may be because:" in args[0] 
                  for args, _ in mock_print.call_args_list)
    
    @patch("subprocess.run")
    def test_scan_container_logs(self, mock_run, scanner):
        """Test scanning container logs."""
        # Mock the subprocess.run call for containers
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "[ERROR] Connection refused"
        mock_run.return_value = mock_process
        
        # Patch the _scan_content method to control its output
        with patch.object(scanner, '_scan_content') as mock_scan_content:
            mock_scan_content.return_value = [LogIssue("Connection refused", "error", "container:web")]
            
            # Call scan_container_logs
            issues = scanner.scan_container_logs()
            
            # Verify that _scan_content was called for each service
            assert mock_scan_content.call_count == 2  # web and db
            
            # Verify that issues were collected
            assert len(issues) == 2  # One issue per service
    
    @patch("subprocess.run")
    def test_scan_migration_logs(self, mock_run, scanner):
        """Test scanning migration logs."""
        # Mock the subprocess.run call for migrations
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "[ ] 0001_initial"  # Unapplied migration
        mock_run.return_value = mock_process
        
        # Patch the _scan_content method to control its output
        with patch.object(scanner, '_scan_content') as mock_scan_content:
            mock_scan_content.return_value = [LogIssue("[ ] 0001_initial", "warning", "migration")]
            
            # Call scan_migration_logs
            issues = scanner.scan_migration_logs()
            
            # Verify that _scan_content was called
            mock_scan_content.assert_called_once_with("[ ] 0001_initial", "migration")
            
            # Verify that issues were collected
            assert len(issues) == 1
    
    def test_scan_all_logs(self, scanner):
        """Test scanning all logs."""
        # Patch the individual scan methods
        with patch.object(scanner, 'scan_build_log') as mock_scan_build, \
             patch.object(scanner, 'scan_container_logs') as mock_scan_container, \
             patch.object(scanner, 'scan_migration_logs') as mock_scan_migration:
            
            # Set up return values
            mock_scan_build.return_value = [LogIssue("Build error", "error", "build")]
            mock_scan_container.return_value = [LogIssue("Container error", "error", "container:web")]
            mock_scan_migration.return_value = [LogIssue("Migration warning", "warning", "migration")]
            
            # Setup side effects to set logs_accessed flag
            def set_logs_accessed_true(*args, **kwargs):
                scanner.logs_accessed = True
                return [LogIssue("Build error", "error", "build")]
            
            mock_scan_build.side_effect = set_logs_accessed_true
            
            # Call scan_all_logs
            issues = scanner.scan_all_logs()
            
            # Verify that all scan methods were called
            mock_scan_build.assert_called_once()
            mock_scan_container.assert_called_once()
            mock_scan_migration.assert_called_once()
            
            # Verify that issues were collected
            assert len(issues) == 3
            assert issues[0].message == "Build error"
            assert issues[1].message == "Container error" 
            assert issues[2].message == "Migration warning"
            
            # Verify logs_accessed was set to True
            assert scanner.logs_accessed is True 