"""Log scanning for critical errors and warnings in build processes and container logs."""
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
        """Initialize a log pattern with regex matching configuration."""
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
        """Initialize a log issue with message details and contextual information."""
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
        """Initialize log scanner with project directory configuration."""
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
    
    def _find_build_log_path(self) -> Optional[Path]:
        """Find the build log file path from possible locations."""
        possible_locations = [
            self.project_dir / "quickscale_build_log.txt",
            self.project_dir.parent / "quickscale_build_log.txt",
            Path(self.project_dir.name) / "quickscale_build_log.txt"
        ]
        
        for build_log_path in possible_locations:
            self.logger.debug(f"Looking for build log at {build_log_path}")
            if build_log_path.exists():
                self.logger.info(f"Found build log at {build_log_path}")
                return build_log_path
        
        # If we couldn't find the build log file, log a warning
        self.logger.warning("Build log not found in any of the expected locations")
        return None

    def _filter_docker_warnings(self, warnings: List[str]) -> List[str]:
        """Filter Docker warnings to exclude known false positives."""
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
        return filtered_warnings

    def _check_for_docker_warnings(self, content: str) -> None:
        """Check if log content contains Docker warnings and log them for debugging."""
        if "WARN[" in content:
            self.logger.debug("Build log contains Docker warnings")
            # Extract the warnings for debugging
            warnings = re.findall(r"WARN\[\d+\].*", content)
            if warnings:
                self.logger.debug(f"Docker warnings found: {len(warnings)}")
                filtered_warnings = self._filter_docker_warnings(warnings)
                for warning in filtered_warnings[:3]:  # Log first few warnings
                    self.logger.debug(f"Warning: {warning.strip()}")

    def scan_build_log(self) -> List[LogIssue]:
        """Scan build log for issues."""
        build_log_path = self._find_build_log_path()
        if not build_log_path:
            return []
        
        try:
            # First check if the log contains Docker warnings
            with open(build_log_path, 'r') as f:
                content = f.read()
                self._check_for_docker_warnings(content)
        except Exception as e:
            self.logger.warning(f"Error checking build log for warnings: {e}")
        
        # Now scan the file for issues
        issues = self._scan_file(build_log_path, "build")
        if issues is not None:
            self.logs_accessed = True
            # Log how many issues were found
            self.logger.debug(f"Found {len(issues)} issues in build log")
            return issues
        
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
        """Scan log content directly for issues using pattern matching."""
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
    
    def _check_static_files_false_positive(self, message: str) -> bool:
        """Check for static files related false positives."""
        return "Static files not accessible yet" in message

    def _check_postgres_auth_false_positive(self, message: str) -> bool:
        """Check for PostgreSQL authentication related false positives."""
        # PostgreSQL trust authentication warning is expected during initialization
        if "trust authentication" in message or "enabling \"trust\" authentication" in message:
            return True
            
        # Specific PostgreSQL initdb trust authentication warning
        if "initdb: warning: enabling" in message and "trust" in message and "authentication for local connections" in message:
            return True
            
        return False

    def _check_postgres_status_false_positive(self, message: str) -> bool:
        """Check for PostgreSQL normal status messages that look like errors."""
        return ("database system was shut down" in message or 
                "database system is ready to accept connections" in message)

    def _check_django_migration_false_positive(self, message: str, lines: List[str], line_number: int) -> bool:
        """Check for Django migration related false positives."""
        # Django auth permission duplication errors are handled gracefully in migrations
        if "duplicate key value violates unique constraint" in message and "auth_permission" in message:
            # Check if we're continuing despite this error by looking at surrounding lines
            for i in range(max(0, line_number), min(len(lines), line_number + 5)):
                if "Continuing despite error with auth migrations" in lines[i]:
                    return True
            
        # Django missing migrations warning during build is handled by auto-generation
        if "have changes that are not yet reflected in a migration" in message:
            return True
            
        return False

    def _check_docker_connection_false_positive(self, message: str, lines: List[str], line_number: int) -> bool:
        """Check for Docker connection issues that eventually succeed."""
        if "Error response from daemon" in message and "container not running" in message:
            # Check if service starts successfully later
            for i in range(min(len(lines), line_number + 20)):
                if "Starting" in lines[i] and "Started" in lines[i]:
                    return True
        return False

    def _check_migration_error_false_positive(self, message: str, source_type: str, lines: List[str], line_number: int) -> bool:
        """Check for false positive errors in migration messages."""
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
        return False

    def _is_false_positive(self, message: str, source_type: str, lines: List[str], line_number: int) -> bool:
        """Check if a log match is a known false positive to avoid reporting normal conditions as errors."""
        # Check different categories of false positives
        checks = [
            self._check_static_files_false_positive(message),
            self._check_postgres_auth_false_positive(message),
            self._check_postgres_status_false_positive(message),
            self._check_django_migration_false_positive(message, lines, line_number),
            self._check_docker_connection_false_positive(message, lines, line_number),
            self._check_migration_error_false_positive(message, source_type, lines, line_number)
        ]
        
        # If any check returns True, this is a false positive
        return any(checks)
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate a summary of issues found during log scanning."""
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
    
    def _print_no_logs_message(self) -> None:
        """Print a message when no logs could be accessed."""
        print("\n⚠️ Could not access any log files for scanning")
        print("   This may be because:")
        print("   - Log files haven't been generated yet")
        print("   - The scanner doesn't have permission to read the logs")
        print("   - Docker logs collection failed")

    def _print_no_issues_message(self) -> None:
        """Print a message when no issues were found."""
        print("\n✅ No issues found in logs")

    def _print_issue_counts(self, total: int, error_count: int, warning_count: int) -> None:
        """Print counts of issues found."""
        print("\n🔍 Log Scan Results:")
        print(f"   Found {total} issues:")
        if error_count > 0:
            print(f"   - {error_count} errors")
        if warning_count > 0:
            print(f"   - {warning_count} warnings")

    def _print_issue_context(self, issue: LogIssue) -> None:
        """Print context lines for an issue."""
        if not issue.context:
            return
        
        for i, line in enumerate(issue.context):
            prefix = ">> " if i == len(issue.context) // 2 else "   "
            print(f"      {prefix}{line}")

    def _print_critical_issues(self, error_issues: List[LogIssue], has_real_errors: bool) -> None:
        """Print critical (error) issues."""
        if not error_issues:
            return
        
        print("\n❌ Critical Issues:")
        
        # Add note about false positives if we have migration errors that are false positives
        has_migration_errors = any("migration" in issue.source or "apply" in issue.message.lower() 
                                   for issue in error_issues)
        
        if has_migration_errors and not has_real_errors:
            print("   Note: The following errors are likely false positives from normal operation")
            print("   Migration names containing 'error' or database shutdown messages are usually normal")
            
        for issue in error_issues:
            source_label = f" ({issue.source})" if issue.source else ""
            print(f"   * {issue.message}{source_label}")
            self._print_issue_context(issue)

    def _print_warning_issues(self, warning_issues: List[LogIssue]) -> None:
        """Print warning issues."""
        if not warning_issues:
            return
        
        print("\n⚠️ Warnings:")
        
        # Add note about expected warnings
        print("   Note: Most warnings below are expected during normal development and startup")
        
        for issue in warning_issues:
            source_label = f" ({issue.source})" if issue.source else ""
            print(f"   * {issue.message}{source_label}")
            self._print_issue_context(issue)

    def print_summary(self) -> None:
        """Print a summary of issues found during scanning."""
        summary = self.generate_summary()  # This already filters out PostgreSQL trust warnings
        
        # Check if any logs were successfully accessed
        if not summary.get("logs_accessed", False):
            self._print_no_logs_message()
            return
        
        # If no issues found after filtering, print a success message
        if summary["total_issues"] == 0:
            self._print_no_issues_message()
            return
        
        # Print issue counts
        self._print_issue_counts(
            summary["total_issues"],
            summary["error_count"],
            summary["warning_count"]
        )
        
        # Print critical issues
        self._print_critical_issues(
            summary["issues_by_severity"].get("error", []),
            summary.get("real_errors", False)
        )
        
        # Print warnings
        self._print_warning_issues(
            summary["issues_by_severity"].get("warning", [])
        )
        
        # Print a separator line
        print("\n" + "-" * 50)
    
    def _analyze_migration_issue(self, issue: LogIssue) -> bool:
        """Analyze a migration issue to determine if it's a real error or false positive."""
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