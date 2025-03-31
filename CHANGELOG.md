# Changelog
All notable changes to this project will be documented in this file.

## v0.4.0 (2025-03-31)
### Added
- Core CLI Improvements:
- Comprehensive error handling system for CLI commands
- User-friendly error messages with recovery suggestions
- Centralized error management module with specialized exception types
- Context-aware error reporting throughout the codebase
- Improved logging with proper log levels
- Error categorization for better diagnostics and debugging
- Unit and integration tests for error handling system with 85% code coverage
- Implemented post-build verification checks for `quickscale build`
- Implemented unit and integration testing for previous task
- Improved test stability and robustness
- Enhanced `quickscale docker logs` functionality
- Enhanced quickscale_build_log.txt logging

## v0.3.0 (2025-03-29)
### Added
- Comprehensive test coverage and documentation
- Complete test suite with pytest integration
- Detailed test coverage reporting
- Unit tests for CLI commands
- Integration tests for Docker operations
- End-to-end workflow tests
- Test fixtures for CLI commands

## v0.2.1 (2025-03-29)
### Fixed
- Improved database connection handling
- Entrypoint script copying during project creation
- Added automatic PostgreSQL port detection and conflict resolution
- Improved database connection retries and error handling
- Added healthchecks for proper container orchestration
- Enhanced environment variable passing between services

## v0.2.0 (2025-03-28)
### Added
- CLI enhancements and AI assistant guidelines
- Shell and django-shell commands for interactive development
- Refactored CLI from functional to object-oriented programming
- Improved help messages for better user experience
- Added guidelines for AI coding assistants (Cursor/WindSurf/GitHub Copilot)

## v0.1.0 (2025-03-19)
### Added
- Initial release of QuickScale
- Basic documentation for setup and usage
- Basic project structure
- Core Django setup
- Basic user authentication features
- Basic Docker and Docker Compose configuration
- Basic PostgreSQL setup
- Basic HTMX and Alpine.js integration
- Basic Bulma CSS integration
- Basic templates and components
- Basic environment variables
- Basic Deploy to local