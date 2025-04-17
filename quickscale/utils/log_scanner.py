"""Log scanning for critical errors and warnings in build process.

This module provides functionality to scan logs from the build process,
container logs, and migration logs to identify critical issues that may
affect project functionality.
"""
import re
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Any
import logging

class LogPattern:
    """Represents a log pattern to search for in logs."""
    
    def __init__(self, 
                 pattern: str, 
                 severity: str = "error", 
                 description: str = "",
                 context_lines: int = 0):
        """Initialize a log pattern.
        
        Args:
            pattern: Regular expression pattern to match
            severity: Severity level ('error', 'warning', 'info')
            description: Human-readable description of the issue
            context_lines: Number of lines of context to include (before and after)
        """
        self.pattern = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
        self.severity = severity
        self.description = description
        self.context_lines = context_lines


class LogIssue:
    """Represents an issue found during log scanning."""
    
    def __init__(self, 
                 message: str, 
                 severity: str, 
                 source: str,
                 line_number: Optional[int] = None,
                 context: Optional[List[str]] = None):
        """Initialize a log issue.
        
        Args:
            message: The actual log message that was matched
            severity: Severity level ('error', 'warning', 'info')
            source: Source of the log (build, container, migration)
            line_number: Line number in the log file where the issue was found
            context: Context lines around the issue
        """
        self.message = message
        self.severity = severity
        self.source = source
        self.line_number = line_number
        self.context = context or []
    
    def __str__(self) -> str:
        """Return a string representation of the issue."""
        return f"[{self.severity.upper()}] {self.message} (Source: {self.source})"


class LogScanner:
    """Scans logs for critical errors and warnings."""
    
    # Define log patterns to look for in different log sources
    PATTERNS = {
        "build": [
            # Specific patterns first
            LogPattern(
                r"Failed to start services", 
                "error",
                "Docker services failed to start"
            ),
            LogPattern(
                r"Error creating project", 
                "error",
                "Project creation failed"
            ),
            LogPattern(
                r"Database setup failed", 
                "error",
                "Database initialization failed"
            ),
            LogPattern(
                r"Migration.*failed", 
                "error", 
                "Migration failure detected"
            ),
            LogPattern(
                r"Error verifying container status", 
                "warning", 
                "Container verification issue"
            ),
            LogPattern(
                r"WARN\[\d+\].*", 
                "warning",
                "Docker compose warning"
            ),
            LogPattern(
                r"Error: .*", 
                "error",
                "Build process error"
            ),
            LogPattern(
                r"The \"[^\"]+\" variable is not set", 
                "warning",
                "Docker environment variable not set"
            ),
            LogPattern(
                r"FATAL:.*role .* does not exist", 
                "error",
                "PostgreSQL role/user does not exist"
            ),
            # Generic patterns to catch other issues
            LogPattern(
                r"(?i)\b(error|exception|fail|failed|failure)\b(?!.*OK)", 
                "error",
                "Generic error detected",
                context_lines=2
            ),
            LogPattern(
                r"(?i)\b(fatal|killed|crash)\b(?!.*OK)", 
                "error",
                "Fatal error detected",
                context_lines=2
            ),
            LogPattern(
                r"(?i)\babort\b(?!.*normal)", 
                "error",
                "Abort detected",
                context_lines=2
            ),
            LogPattern(
                r"(?i)\b(warn|warning)\b(?!.*404)(?!.*development server)(?!.*trust authentication)", 
                "warning",
                "Generic warning detected",
                context_lines=1
            )
        ],
        "container": [
            # Specific patterns first
            LogPattern(
                r"Traceback \(most recent call last\):", 
                "error", 
                "Python exception in container", 
                context_lines=5
            ),
            LogPattern(
                r"\bERROR\b.*\b(Django|Uvicorn|Gunicorn)\b", 
                "error", 
                "Server error detected", 
                context_lines=2
            ),
            LogPattern(
                r"ConnectionRefused|ConnectionError", 
                "error", 
                "Connection error", 
                context_lines=1
            ),
            LogPattern(
                r"OperationalError", 
                "error", 
                "Database operational error", 
                context_lines=1
            ),
            LogPattern(
                r"Permission denied", 
                "error", 
                "Permission issue detected", 
                context_lines=1
            ),
            LogPattern(
                r"The \S+ variable is not set", 
                "warning",
                "Environment variable not set",
                context_lines=0
            ),
            LogPattern(
                r"WARN\[\d+\].*", 
                "warning",
                "Docker compose warning"
            ),
            LogPattern(
                r"warning: enabling \"trust\" authentication for local connections", 
                "warning",
                "PostgreSQL using trust authentication"
            ),
            LogPattern(
                r"FATAL:.*role .* does not exist", 
                "error",
                "PostgreSQL role/user does not exist"
            ),
            # Generic patterns to catch other issues
            LogPattern(
                r"(?i)\b(error|exception|fail|failed|failure)\b(?!.*OK)", 
                "error",
                "Generic error detected",
                context_lines=2
            ),
            LogPattern(
                r"(?i)\b(fatal|killed|crash)\b(?!.*OK)", 
                "error",
                "Fatal error detected",
                context_lines=2
            ),
            LogPattern(
                r"(?i)\babort\b(?!.*normal)", 
                "error",
                "Abort detected",
                context_lines=2
            ),
            LogPattern(
                r"(?i)\b(warn|warning)\b(?!.*404)(?!.*development server)(?!.*trust authentication)", 
                "warning",
                "Generic warning detected",
                context_lines=1
            )
        ],
        "migration": [
            # Specific patterns first
            LogPattern(
                r"Traceback \(most recent call last\):", 
                "error", 
                "Exception during migration", 
                context_lines=5
            ),
            LogPattern(
                r"Migration.*failed", 
                "error", 
                "Migration failure", 
                context_lines=2
            ),
            LogPattern(
                r"RuntimeWarning", 
                "warning", 
                "Runtime warning during migration", 
                context_lines=1
            ),
            LogPattern(
                r"OperationalError", 
                "error", 
                "Database operational error", 
                context_lines=1
            ),
            LogPattern(
                r"\[ \] [0-9]{4}_.*", 
                "warning", 
                "Unapplied migration detected", 
                context_lines=0
            ),
            LogPattern(
                r"No migrations to apply", 
                "info",
                "No pending migrations",
                context_lines=0
            ),
            # Generic patterns to catch other issues
            LogPattern(
                r"(?i)\b(error|exception|fail|failed|failure)\b(?!.*OK)", 
                "error",
                "Generic error detected",
                context_lines=2
            ),
            LogPattern(
                r"(?i)\b(fatal|killed|crash)\b(?!.*OK)", 
                "error",
                "Fatal error detected",
                context_lines=2
            ),
            LogPattern(
                r"(?i)\babort\b(?!.*normal)", 
                "error",
                "Abort detected",
                context_lines=2
            ),
            LogPattern(
                r"(?i)\b(warn|warning)\b(?!.*404)(?!.*development server)(?!.*trust authentication)", 
                "warning",
                "Generic warning detected",
                context_lines=1
            )
        ]
    }
    
    def __init__(self, project_dir: Path, logger: Optional[logging.Logger] = None):
        """Initialize log scanner.
        
        Args:
            project_dir: Project directory containing logs
            logger: Logger to use (or create a new one if None)
        """
        # Ensure project_dir is an absolute path and exists
        self.project_dir = project_dir.resolve() if project_dir else Path.cwd().resolve()
        # Ensure we're using the correct directory
        if self.project_dir.name == self.project_dir.parent.name:
            # Avoid duplicate paths like /path/to/project/project
            self.project_dir = self.project_dir.parent
        self.logger = logger or logging.getLogger(__name__)
        self.issues: List[LogIssue] = []
        self.logs_accessed = False  # Track if any logs were successfully accessed
        self.logger.debug(f"Log scanner initialized with project directory: {self.project_dir}")
    
    def scan_build_log(self) -> List[LogIssue]:
        """Scan build log for issues."""
        # Try multiple possible locations for the build log
        possible_locations = [
            self.project_dir / "quickscale_build_log.txt",
            self.project_dir.parent / "quickscale_build_log.txt",
            Path(self.project_dir.name) / "quickscale_build_log.txt"
        ]
        
        for build_log_path in possible_locations:
            self.logger.debug(f"Looking for build log at {build_log_path}")
            if build_log_path.exists():
                self.logger.info(f"Found build log at {build_log_path}")
                try:
                    # First check if the log contains Docker warnings
                    with open(build_log_path, 'r') as f:
                        content = f.read()
                        if "WARN[" in content:
                            self.logger.debug(f"Build log contains Docker warnings")
                            # Extract the warnings for debugging
                            warnings = re.findall(r"WARN\[\d+\].*", content)
                            if warnings:
                                self.logger.debug(f"Docker warnings found: {len(warnings)}")
                                filtered_warnings = []
                                for warning in warnings:
                                    # Check for static files warning false positive
                                    if "Static files not accessible yet" in warning:
                                        static_css_path = os.path.join(self.project_dir, "static", "css")
                                        static_js_path = os.path.join(self.project_dir, "static", "js")
                                        if os.path.isdir(static_css_path) and os.path.isdir(static_js_path):
                                            # This warning is a known false positive as static assets (css and js) are present
                                            continue  # Skip adding this warning
                                    # Add warning if it doesn't match known benign patterns
                                    filtered_warnings.append(warning)
                                for warning in filtered_warnings[:3]:  # Log first few warnings
                                    self.logger.debug(f"Warning: {warning.strip()}")
                except Exception as e:
                    self.logger.warning(f"Error checking build log for warnings: {e}")
                
                # Now scan the file for issues
                issues = self._scan_file(build_log_path, "build")
                if issues is not None:
                    self.logs_accessed = True
                    # Log how many issues were found
                    self.logger.debug(f"Found {len(issues)} issues in build log")
                    return issues
        
        # If we couldn't find the build log file, log a warning
        self.logger.warning("Build log not found in any of the expected locations")
        return []
    
    def scan_container_logs(self) -> List[LogIssue]:
        """Scan container logs for issues."""
        issues = []
        
        # Use docker-compose logs to get container logs without temporary files
        try:
            import subprocess
            from ..commands.command_utils import DOCKER_COMPOSE_COMMAND
            
            # Get logs for both services
            for service in ["web", "db"]:
                try:
                    self.logger.debug(f"Running {DOCKER_COMPOSE_COMMAND} logs {service} in {self.project_dir}")
                    result = subprocess.run(
                        [DOCKER_COMPOSE_COMMAND, "logs", service],
                        capture_output=True,
                        text=True,
                        check=False,  # Don't raise an exception on non-zero exit
                        cwd=str(self.project_dir)  # Run in the project directory
                    )
                    
                    if result.returncode != 0:
                        self.logger.warning(f"Failed to get logs for {service} service: {result.stderr}")
                        continue
                    
                    # Process the logs directly from the command output
                    if result.stdout:
                        self.logger.debug(f"Obtained {len(result.stdout.splitlines())} log lines for {service} service")
                        service_issues = self._scan_content(result.stdout, f"container:{service}")
                        issues.extend(service_issues)
                        self.logs_accessed = True  # Mark that we successfully accessed logs
                    else:
                        self.logger.warning(f"No logs found for {service} service")
                    
                except Exception as e:
                    self.logger.warning(f"Error processing logs for {service} service: {e}")
        
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            self.logger.warning(f"Failed to scan container logs: {e}")
        
        return issues
    
    def scan_migration_logs(self) -> List[LogIssue]:
        """Scan migration logs for issues."""
        issues = []
        
        # Get migration information directly
        try:
            import subprocess
            from ..commands.command_utils import DOCKER_COMPOSE_COMMAND
            
            # Run showmigrations to check for any unapplied migrations
            try:
                self.logger.debug(f"Running {DOCKER_COMPOSE_COMMAND} exec -T web python manage.py showmigrations in {self.project_dir}")
                result = subprocess.run(
                    [DOCKER_COMPOSE_COMMAND, "exec", "-T", "web", 
                     "python", "manage.py", "showmigrations"],
                    capture_output=True,
                    text=True,
                    check=False,  # Don't raise an exception on non-zero exit
                    cwd=str(self.project_dir)  # Run in the project directory
                )
                
                if result.returncode != 0:
                    self.logger.warning(f"Failed to check migrations: {result.stderr}")
                else:
                    # Process the migration status directly
                    if result.stdout:
                        self.logger.debug(f"Obtained {len(result.stdout.splitlines())} migration status lines")
                        migration_issues = self._scan_content(result.stdout, "migration")
                        issues.extend(migration_issues)
                        self.logs_accessed = True  # Mark that we successfully accessed migration logs
                    else:
                        self.logger.warning("No migration status output found")
            except Exception as e:
                self.logger.warning(f"Error processing migration logs: {e}")
        
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            self.logger.warning(f"Failed to scan migration logs: {e}")
        
        return issues
    
    def scan_all_logs(self) -> List[LogIssue]:
        """Scan all logs for issues."""
        # Reset issues list and logs_accessed flag
        self.issues = []
        self.logs_accessed = False
        
        # Scan all log sources
        self.issues.extend(self.scan_build_log())
        self.issues.extend(self.scan_container_logs())
        self.issues.extend(self.scan_migration_logs())
        
        return self.issues
    
    def _scan_file(self, file_path: Path, source_type: str) -> Optional[List[LogIssue]]:
        """Scan a log file for issues.
        
        Args:
            file_path: Path to the log file
            source_type: Type of log source (build, container, migration)
            
        Returns:
            List of LogIssue objects or None if file couldn't be accessed
        """
        issues = []
        
        try:
            with open(file_path, "r") as f:
                content = f.read()
                lines = content.splitlines()
                
                # Check if content contains Docker warnings (for debugging)
                if "WARN[" in content:
                    self.logger.debug(f"Content of {file_path} contains Docker warnings")
                
                patterns = self.PATTERNS.get(source_type.split(":")[0], [])
                self.logger.debug(f"Using {len(patterns)} patterns for source type {source_type}")
                
                for pattern in patterns:
                    # Log the pattern we're using (for debugging)
                    self.logger.debug(f"Scanning with pattern: {pattern.pattern.pattern}")
                    matches = list(pattern.pattern.finditer(content))
                    self.logger.debug(f"Pattern matched {len(matches)} times")
                    
                    for match in matches:
                        line_number = content[:match.start()].count('\n') + 1
                        message = match.group(0).strip()
                        self.logger.debug(f"Match found at line {line_number}: {message}")
                        
                        # Get context lines if needed
                        context = []
                        if pattern.context_lines > 0:
                            start_line = max(0, line_number - pattern.context_lines - 1)
                            end_line = min(len(lines), line_number + pattern.context_lines)
                            context = lines[start_line:end_line]
                        
                        # Create issue
                        issue = LogIssue(
                            message=message,
                            severity=pattern.severity,
                            source=source_type,
                            line_number=line_number,
                            context=context
                        )
                        issues.append(issue)
            
            return issues
        
        except (FileNotFoundError, PermissionError) as e:
            self.logger.warning(f"Failed to scan log file {file_path}: {e}")
            return None
    
    def _scan_content(self, content: str, source_type: str) -> List[LogIssue]:
        """Scan log content directly for issues.
        
        Args:
            content: String content to scan
            source_type: Type of log source (build, container, migration)
            
        Returns:
            List of LogIssue objects
        """
        issues = []
        lines = content.splitlines()
        
        patterns = self.PATTERNS.get(source_type.split(":")[0], [])
        for pattern in patterns:
            for match in pattern.pattern.finditer(content):
                line_number = content[:match.start()].count('\n') + 1
                message = match.group(0).strip()
                
                # Skip known false positives
                if self._is_false_positive(message, source_type, lines, line_number):
                    self.logger.debug(f"Skipping false positive: {message}")
                    continue
                
                # Get context lines if needed
                context = []
                if pattern.context_lines > 0:
                    start_line = max(0, line_number - pattern.context_lines - 1)
                    end_line = min(len(lines), line_number + pattern.context_lines)
                    context = lines[start_line:end_line]
                
                # Create issue
                issue = LogIssue(
                    message=message,
                    severity=pattern.severity,
                    source=source_type,
                    line_number=line_number,
                    context=context
                )
                issues.append(issue)
        
        return issues
    
    def _is_false_positive(self, message: str, source_type: str, lines: List[str], line_number: int) -> bool:
        """Check if a match is a known false positive.
        
        Args:
            message: The matched message
            source_type: Type of log source
            lines: All lines in the log file
            line_number: Line number of the match

        Returns:
            True if the match is a false positive, False otherwise
        """
        # Static files warning during initial build is expected
        if "Static files not accessible yet" in message:
            return True
            
        # PostgreSQL trust authentication warning is expected during initialization
        if "trust authentication" in message or "enabling \"trust\" authentication" in message:
            return True
            
        # Specific PostgreSQL initdb trust authentication warning
        if "initdb: warning: enabling" in message and "trust" in message and "authentication for local connections" in message:
            return True
            
        # Django auth permission duplication errors are handled gracefully in migrations
        if "duplicate key value violates unique constraint" in message and "auth_permission" in message:
            # Check if we're continuing despite this error by looking at surrounding lines
            for i in range(max(0, line_number), min(len(lines), line_number + 5)):
                if "Continuing despite error with auth migrations" in lines[i]:
                    return True
            
        # Django missing migrations warning during build is handled by auto-generation
        if "have changes that are not yet reflected in a migration" in message:
            return True
            
        # Postgres normal shutdown messages should not be treated as errors
        if "database system was shut down" in message or "database system is ready to accept connections" in message:
            return True
            
        # Docker temporary connection issues that eventually succeed
        if "Error response from daemon" in message and "container not running" in message:
            # Check if service starts successfully later
            for i in range(min(len(lines), line_number + 20)):
                if "Starting" in lines[i] and "Started" in lines[i]:
                    return True
        
        # False positive errors in migration messages
        if source_type == "build" and ("ERROR" in message or "Error" in message):
            # Check context to see if this is part of a migration that actually succeeded
            context_start = max(0, line_number - 5)
            context_end = min(len(lines), line_number + 5)
            context = lines[context_start:context_end]
            
            # If the error is followed by "Migrations applied successfully", it's a false positive
            for line in context:
                if "Migrations for" in line and "applied successfully" in line:
                    return True
                    
            # Skip errors about continuing after auth migrations which are handled
            if "Continuing despite error with auth migrations" in message:
                return True
        
        # Default: not a false positive
        return False
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate a summary of issues found during scanning.
        
        Returns:
            Dictionary with summary information
        """
        # Check if any logs were successfully accessed
        if not self.logs_accessed:
            return {
                "total_issues": 0,
                "error_count": 0,
                "warning_count": 0,
                "issues_by_source": {},
                "issues_by_severity": {},
                "has_critical_issues": False,
                "logs_accessed": False,  # Important flag to indicate no logs were accessed
                "real_errors": False
            }
            
        if not self.issues:
            return {
                "total_issues": 0,
                "error_count": 0,
                "warning_count": 0,
                "issues_by_source": {},
                "issues_by_severity": {},
                "has_critical_issues": False,
                "logs_accessed": True,  # Logs were accessed but no issues found
                "real_errors": False
            }
        
        # Filter out PostgreSQL trust authentication warnings
        filtered_issues = []
        for issue in self.issues:
            if (issue.severity == "warning" and 
                ("trust authentication" in issue.message or "enabling \"trust\" authentication" in issue.message)):
                # Skip this warning
                continue
            filtered_issues.append(issue)
        
        # Count issues by severity and source
        error_count = sum(1 for issue in filtered_issues if issue.severity == "error")
        warning_count = sum(1 for issue in filtered_issues if issue.severity == "warning")
        
        # Analyze error issues to check if they're real errors
        error_issues = [issue for issue in filtered_issues if issue.severity == "error"]
        real_errors = any(self._analyze_migration_issue(issue) for issue in error_issues 
                          if "migration" in issue.source or "apply" in issue.message.lower())
        
        issues_by_source = {}
        for issue in filtered_issues:
            if issue.source not in issues_by_source:
                issues_by_source[issue.source] = []
            issues_by_source[issue.source].append(issue)
        
        issues_by_severity = {
            "error": [issue for issue in filtered_issues if issue.severity == "error"],
            "warning": [issue for issue in filtered_issues if issue.severity == "warning"],
            "info": [issue for issue in filtered_issues if issue.severity == "info"]
        }
        
        return {
            "total_issues": len(filtered_issues),
            "error_count": error_count,
            "warning_count": warning_count,
            "issues_by_source": issues_by_source,
            "issues_by_severity": issues_by_severity,
            "has_critical_issues": error_count > 0,
            "logs_accessed": True,
            "real_errors": real_errors
        }
    
    def print_summary(self) -> None:
        """Print a summary of issues found during scanning."""
        summary = self.generate_summary()  # This already filters out PostgreSQL trust warnings
        
        # Check if any logs were successfully accessed
        if not summary.get("logs_accessed", False):
            print("\n⚠️ Could not access any log files for scanning")
            print("   This may be because:")
            print("   - Log files haven't been generated yet")
            print("   - The scanner doesn't have permission to read the logs")
            print("   - Docker logs collection failed")
            return
        
        # If no issues found after filtering, print a success message
        if summary["total_issues"] == 0:
            print("\n✅ No issues found in logs")
            return
        
        print("\n🔍 Log Scan Results:")
        print(f"   Found {summary['total_issues']} issues:")
        if summary['error_count'] > 0:
            print(f"   - {summary['error_count']} errors")
        if summary['warning_count'] > 0:
            print(f"   - {summary['warning_count']} warnings")
            
        # Print critical issues first
        if summary['error_count'] > 0:
            print("\n❌ Critical Issues:")
            
            # Add note about false positives if we have migration errors that are false positives
            has_migration_errors = any("migration" in issue.source or "apply" in issue.message.lower() 
                                      for issue in summary["issues_by_severity"]["error"])
            
            if has_migration_errors and not summary.get('real_errors', False):
                print("   Note: The following errors are likely false positives from normal operation")
                print("   Migration names containing 'error' or database shutdown messages are usually normal")
                
            for issue in summary["issues_by_severity"]["error"]:
                source_label = f" ({issue.source})" if issue.source else ""
                print(f"   * {issue.message}{source_label}")
                # Print context if available
                if issue.context:
                    for i, line in enumerate(issue.context):
                        prefix = ">> " if i == len(issue.context) // 2 else "   "
                        print(f"      {prefix}{line}")
        
        # Print warnings
        if summary['warning_count'] > 0:
            print("\n⚠️ Warnings:")
            
            # Add note about expected warnings
            print("   Note: Most warnings below are expected during normal development and startup")
            
            for issue in summary["issues_by_severity"]["warning"]:
                source_label = f" ({issue.source})" if issue.source else ""
                print(f"   * {issue.message}{source_label}")
                # Print context for warnings too
                if issue.context:
                    for i, line in enumerate(issue.context):
                        prefix = ">> " if i == len(issue.context) // 2 else "   "
                        print(f"      {prefix}{line}")
                
        # Print a separator line
        print("\n" + "-" * 50)
    
    def _analyze_migration_issue(self, issue: LogIssue) -> bool:
        """Analyze a migration issue to determine if it's a real error.
        
        Args:
            issue: The migration issue to analyze
            
        Returns:
            True if it's a real error, False if it's a false positive
        """
        # If the issue is related to migrations and contains "OK" or "[X]", it's a false positive
        message = issue.message.lower()
        
        # If it has indication of successful completion, it's not a real error
        if "... ok" in message or "[x]" in message:
            return False
            
        # If it contains error-like words but is actually a migration name, it's a false positive
        if ("error" in message or "validator" in message) and (
            "apply" in message or "migration" in message):
            return False
            
        return True 