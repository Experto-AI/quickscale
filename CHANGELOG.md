# Quickscale Changelog

All notable changes to this project will be documented in this file.

## v0.11.0 (2025-05-20)
v0.11.0 feat: Implement Public Plan Selection Interface

- Implemented the plan selection view (`PublicPlanListView`) to display available plans from the database.
- Created the `plan_comparison.html` template with a 3-column layout to showcase pricing tiers and features.
- Updated navigation to include a link to the new plan selection page.
- Added unit tests (`Test_PlanViews`) for plan listing and views, covering different user scenarios.
- Refactored the plan selection interface to remove the Alpine.js billing toggle component, simplifying the pricing display and user flow for plan selection.
- Updated the roadmap and project version to v0.11.0.

These changes provide users with a clear interface to view and compare subscription plans as the first step in the checkout workflow.

## v0.10.0 (2025-05-19)
v0.10.0 feat: Implement Admin Product Management for Stripe

- Stripe Product Model and Admin:
  - Introduced the `StripeProduct` model to store product details from Stripe.
  - Added a Django admin interface for managing these products, including fields for name, description, price, currency, billing interval, and display order.
- Web Admin Interface for Stripe Products:
  - Created views and templates for listing Stripe products (`product_admin.html`) and viewing/editing product details (`product_detail.html`) within the admin dashboard.
- Stripe Sync Functionality:
  - Implemented functionality to sync products from Stripe to the local database.
  - Added a `product_sync` view for syncing individual products.
  - Introduced a `sync_all_products` view in the admin interface for bulk synchronization.
  - Updated product management views and templates to include sync actions.
- Display Order Management:
  - Implemented functionality for manually setting the `display_order` of products.
- Testing:
  - Added comprehensive tests for the `StripeProduct` model, admin interface, and dashboard templates, covering product listing, detail views, sync functionality, and display order management.
- Other improvements:
  - Updated service commands, reducing retry attempts for starting services and improving logging.
  - Added `iputils-ping` to the Dockerfile for network diagnostics.

These changes provide administrators with the necessary tools to manage Stripe products directly within the application's admin interface, including synchronization with Stripe and control over product display order.

## v0.9.0 (2025-05-17)
-feat: Migrate to official Stripe API and implement plan synchronization
- Completed the migration of the Stripe integration from the dj-stripe library to the official Stripe Python API, fulfilling Session 1 of the Sprint 2 roadmap.
- Key changes include:
- Removed the dj-stripe dependency and updated settings to use the official Stripe API.
- Introduced a new StripeManager class to handle API interactions and configuration.
- Updated views, templates, and tests to align with the new Stripe integration structure.
- Removed the deprecated djstripe directory and related files.
- Added utility functions and template tags for enhanced Stripe data handling.
- Implemented functionality to synchronize Stripe plan and product data with the application's database, completing part of Session 2.
- Enhanced product management views and templates to support the new synchronization and display Stripe data.
- Added comprehensive unit tests for the migrated Stripe functionality and synchronization process.
- Updated documentation, including the .env.example and technical documentation, to reflect the changes.

## v0.8.0 (2025-05-13)
- v0.8.0 feat: Comprehensive CLI improvements and enhanced system reliability
- Implemented MessageManager for consistent CLI output with color and icon support
- Enhanced error handling for unknown commands and execution errors
- Added security settings and validation for environment variables
- Standardized database environment variables and connection handling
- Implemented default user creation command
- Added comprehensive test coverage:
  - Unit tests for settings validation
  - Tests for system commands and Docker checks
  - Environment utility function tests
  - Help manager and message formatting tests
  - Log scanner and logging manager tests
- Refactored codebase to improve maintainability (McCabe < 10)
- Updated roadmap and enhanced code documentation

## v0.7.0 (2025-05-08)
- v0.7.0 feat: Remove the build stage and just use a copy of the templates
- Remove the quickscale build command
- Add a new quickscale init command to create a new project from the templates
- Add unit, integration and E2E tests

## v0.7.0 (2025-05-08)
- v0.7.0 feat: Remove the build stage and just use a copy of the templates
- Remove the quickscale build command
- Add a new quickscale init command to create a new project from the templates
- Add unit, integration and E2E tests

## v0.6.2 (2025-04-19)
- v0.6.2 docs: refactor CONTRIBUTING.md into structured documentation files for AI programming ssistants (#5)
- Improve documentation for AI coding assistants and human contributors by:
- Creating 7 specialized documentation files in docs/contrib/
- Grouping related topics and standardizing section numbering
- Implementing a logical progression from system prompts to task focus
- Ensuring clean, maintainable documentation structure
- Created compile_docs.sh to generate CONTRIBUTING.md as a navigable index and Cursor rules
- Ensuring compatibility with Cursor, Windsurf and Github Copilot.

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