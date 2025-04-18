# Quickscale Changelog

All notable changes to this project will be documented in this file.

## v0.6.1 (2025-04-18)
- v0.6.1 fix: improve log scanning and build process with better error detection
- Add log scanning integration into quickscale build command
- Fix PostgreSQL \"role 'root' does not exist\" error detection
- Fix quickscale manage test functionality after build
- Fix environment variable warnings for DOCKER_UID and DOCKER_GID
- Enhance _is_false_positive method to detect more expected messages
- Add migration-specific analysis to identify real errors vs. false positives
- Improve regular expressions for pattern matching to reduce false matches
- Add better context in CLI output to explain normal messages
- Add more detailed logging about false positive filtering
- Added test to verify codebase directory structure
- Added test to verify Dockerfile and docker-compose.yml file existence

## v0.6.0 (2025-04-15)
- v0.6.0 feat: Add payment integration with django-stripe
- Integrated dj-stripe package with proper configuration and feature flags
- Added CustomUser-StripeCustomer model linking with synchronization
- Implemented Stripe API client configuration and customer creation
- Created basic webhook endpoints with signature verification
- Added product model with price configuration options
- Implemented Stripe product synchronization and webhook handlers
- Created product management dashboard with Stripe integration
- Added comprehensive test suite with mock responses for CI environments
- Ensured compatibility with feature flag for environments without Stripe
- Updated documentation with package requirements and setup instructions


## v0.5.1 (2025-04-13)
- v0.5.1 fix: enhance Docker service reliability and system robustness
- Enhances Docker service handling with better error handling and verification
- Adds quiet mode for test runners to improve CI environment compatibility
- Prevents security issues by blocking root user for PostgreSQL
- Improves port detection with more robust available port discovery
- Replaces silent fallbacks with explicit validation throughout the system
- Updates documentation for technical stack adherence

## v0.5.0 (2025-04-05)
- v0.5.0 feat: Implement django-allauth with comprehensive authentication & testing  
- Migrated from built-in django auth to django-allauth with email-based authentication
- Added CustomUser model, custom user manager, and email verification
- Implemented user profile management with additional profile fields
- Created comprehensive test suite (unit, integration, E2E) for authentication flows
- Enhanced signup form with validation and password strength indicators
- Updated documentation (CONTRIBUTING.md, TECHNICAL_DOCS.md, README.md, ROADMAP.md)
- Added debugging guidelines and updated version to 0.5.0

## v0.4.0 (2025-03-31)
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
- Comprehensive test coverage and documentation
- Complete test suite with pytest integration
- Detailed test coverage reporting
- Unit tests for CLI commands
- Integration tests for Docker operations
- End-to-end workflow tests
- Test fixtures for CLI commands

## v0.2.1 (2025-03-29)
- Improved database connection handling
- Entrypoint script copying during project creation
- Added automatic PostgreSQL port detection and conflict resolution
- Improved database connection retries and error handling
- Added healthchecks for proper container orchestration
- Enhanced environment variable passing between services

## v0.2.0 (2025-03-28)
- CLI enhancements and AI assistant guidelines
- Shell and django-shell commands for interactive development
- Refactored CLI from functional to object-oriented programming
- Improved help messages for better user experience
- Added guidelines for AI coding assistants (Cursor/WindSurf/GitHub Copilot)

## v0.1.0 (2025-03-19)
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