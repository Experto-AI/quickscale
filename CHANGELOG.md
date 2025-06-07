# Quickscale Changelog

All notable changes to this project will be documented in this file.

## v0.24.0 (2025-06-07)
v0.24.0 feat: Implement Service Management Admin Interface

This PR implements comprehensive service management and analytics capabilities for administrators, enhancing the ability to manage and monitor services effectively within QuickScale's admin interface.

- Backend Implementation:
  - Enhanced Django admin for Service and ServiceUsage models with comprehensive analytics and usage tracking.
  - Added bulk operations for enabling/disabling services with proper audit trail logging.
  - Implemented detailed service usage analytics including total usage, credits consumed, and unique user counts.
  - Created custom admin views for service configuration and performance monitoring.
  - Added service usage analytics with 30-day trends and detailed performance metrics.
- Frontend Implementation:
  - Created admin service management pages with real-time enable/disable functionality via HTMX.
  - Developed service detail views showing usage statistics, credit consumption, and user engagement metrics.
  - Integrated Alpine.js for dynamic UI interactions, notifications, and state management.
  - Added service filtering capabilities and responsive admin dashboard components.
  - Implemented comprehensive service analytics templates with detailed performance insights.
- Testing:
  - Added comprehensive integration tests for end-to-end service management workflows.
  - Implemented unit tests for service admin enhancements, security, and error handling.
  - Created tests for Alpine.js and HTMX functionalities within service management templates.
  - Verified data integrity and consistency across service analytics calculations.

This PR completes the Service Management Admin Interface, providing administrators with powerful tools to manage services, view detailed analytics, and monitor service performance with real-time controls and comprehensive usage insights.

## v0.23.0 (2025-06-05)
v0.23.0 feat: Implement API Authentication & Basic Endpoints for AI Services

This PR introduces a new API application for QuickScale, enabling AI services integration. This implementation lays the groundwork for a robust API framework, enhancing the capabilities of QuickScale's AI services.

- Backend Implementation:
  - Created api Django app with essential configurations and URL routing.
  - Developed utility functions for standardized API responses and validation.
  - Implemented views for text processing operations, including a text analysis service.
  - Added middleware for API key authentication to secure API endpoints.
  - Integrated credit consumption logic for service usage.
- Frontend Implementation:
  - Added base template for API documentation and user interface for API key management.
  - Created templates for displaying API keys and generated keys.
- Testing:
  - Comprehensive test suite for API endpoints, middleware, and key management functionality.

This PR completes the API authentication and basic endpoints for AI services, allowing users to generate API keys and call service endpoints with authentication.

## v0.22.0 (2025-05-31)
v0.22.0 feat: Implement AI Service Framework Foundation

This PR lays the foundation for AI engineers to easily integrate their services into QuickScale, introducing a basic service framework.

- Backend Implementation:
  - Created a `services/` Django app template.
  - Added a basic `Service` model in the credits app with name, description, credit_cost, and is_active fields.
  - Implemented a `BaseService` class with core credit consumption logic.
  - Added a service registration decorator for streamlined service integration.
- Frontend Implementation:
  - Integrated a services section into the user dashboard to display available services.
  - Created a basic service listing page for user access.
  - Developed a service usage form template.
- Testing:
  - Comprehensive tests were added covering the Service model creation and credit cost configuration.
  - Implemented tests for `BaseService` class credit consumption integration.
  - Included tests for service registration and listing functionality.

This PR completes the initial framework for AI services, enabling AI engineers to define services with configurable credit costs, which will be visible in the user dashboard.

## v0.21.0 (2025-05-29)
v0.21.0 feat: Implement Pro Subscription Plan

This PR implements the Pro subscription plan, offering users a higher credit allocation at a better rate compared to the Basic plan, and adds the logic for upgrading and downgrading between plans with prorated billing.

- Backend Implementation:
  - Added Pro plan as a Stripe subscription product.
  - Added plan upgrade/downgrade logic.
  - Handled prorated billing for plan changes.
  - Implemented logic to transfer remaining credits to pay-as-you-go and charge immediately upon upgrade/downgrade.
- Frontend Implementation:
  - Added Pro plan option to the subscription page.
  - Created plan comparison table (Basic vs Pro).
  - Added upgrade/downgrade buttons for existing subscribers.
  - Added message to the user about credit transfer and immediate charge on upgrade/downgrade.
- Testing:
  - Tests for Pro plan subscription.
  - Tests for plan upgrades/downgrades, including scenarios with no credits left and immediate changes.
  - Integration tests for multiple plan types.

This PR completes the implementation of the Pro Subscription Plan, allowing users to choose between Basic and Pro plans and manage their subscriptions through upgrades and downgrades, enhancing the flexibility of the credit system.

## v0.20.0 (2025-05-28)
v0.20.0 feat: Implement Payment History and Receipts System

This PR implements a comprehensive payment history and receipt management system, allowing users to view their payment history, download receipts, and manage payment records effectively.

- Backend Implementation:
  - Created `Payment` model for all payment tracking.
  - Linked payments to credit transactions and subscriptions.
  - Generated receipt data for all payment types.
  - Added payment status tracking (success, failed, refunded).
- Frontend Implementation:
  - Created `/admin_dashboard/payments/` page with payment history.
  - Show detailed payment information (amount, date, type, status).
  - Added downloadable receipts for each payment.
  - Separated views for subscription payments vs credit purchases.
- Testing:
  - Tests for payment tracking.
  - Tests for receipt generation.
  - Integration tests for payment history display.

This PR completes the implementation of the Payment History and Receipts system, providing users with better visibility and control over their transactions.

## v0.19.0 (2025-05-27)
v0.19.0 feat: Implement Credit Type Priority System

This PR implements subscription credits consumed first, then pay-as-you-go credits, enhancing the credit system with intelligent consumption priority logic.

- Backend Implementation:
  - Introduced new credit consumption method that prioritizes subscription credits over pay-as-you-go credits.
  - Updated `CreditAccount` model with methods for calculating available balance and balance breakdown by credit type.
  - Enhanced service usage functionality to reflect the new priority consumption logic.
  - Implemented credit expiration logic for subscription credits with proper billing cycle handling.
  - Updated `consume_credits()` method with priority logic ensuring subscription credits are consumed first.
- Frontend Implementation:
  - Updated credit balance display to show breakdown by credit type (subscription vs pay-as-you-go).
  - Enhanced templates to display credit breakdown and consumption details clearly.
  - Added visual indicators showing which credit type is being consumed during service usage.
  - Implemented expiration date display for subscription credits.
- Testing:
  - Added comprehensive tests for credit priority consumption logic.
  - Created tests for credit expiration logic and billing cycle handling.
  - Implemented integration tests for mixed credit scenarios to ensure proper priority handling.
  - Added tests to ensure correct implementation of balance calculations by credit type.

This PRenhances the credit system by implementing a priority consumption model where subscription credits are consumed before pay-as-you-go credits, improving user experience and providing clear visibility into credit usage patterns. The implementation ensures users maximize value from their subscription credits while preserving their never-expiring pay-as-you-go credits as backup.

## v0.18.0 (2025-05-27)
v0.18.0 feat: Implement Basic Monthly Subscription System

- Added `UserSubscription` model to manage user subscriptions and billing information.
- Integrated Stripe for subscription management, including product creation and webhook handling.
- Updated user dashboard to display subscription status and balance breakdown.
- Created subscription management page with options to subscribe and view plans.
- Implemented success and cancellation pages for subscription checkout.
- Added tests for subscription functionality and credit allocation.
  
This commit completes the implementation of the Basic Monthly Subscription feature, allowing sers to subscribe and receive monthly credits automatically.

## v0.17.0 (2025-05-26)
v0.17.0 refactor: Refactor and Maintenance 

This PR implements the tasks focusing on improving code quality, user flow, and maintainability.

- Django Admin:
  - Updated technical documentation diagrams to reflect the new structure.
  - Fixed synchronization of credit amounts and display order from Stripe product metadata.
  - Ensured graceful failure when Stripe metadata is missing, avoiding default creation.
  - Removed the manual "ADD STRIPE PRODUCT" button from the Stripe Products admin section.
  - Analyzed the grouping of Email Address and Custom Users in Django Admin.
- Backend and Frontend Implementation:
  - Renamed the 'dashboard' app and related components to 'admin_dashboard' for clarity and to distinguish from the user dashboard ("My Dashboard").
  - Consolidated credit system and stripe manager initial migrations into one file.
- Testing:
  - Updated unit and integration tests to reflect the changes in app names, migration structure, and Stripe integration.

This sprint focused on refining existing features and the codebase structure, ensuring accurate data synchronization from Stripe, clarifying naming conventions, and streamlining initial project migrations for improved maintainability and a better user experience.

## v0.16.0 (2025-05-24)
v0.16.0 feat: Implement Pay-as-You-Go Credit Purchase System

- Backend:
    - Added `credit_type` field to `CreditTransaction` (PURCHASE, CONSUMPTION, ADMIN).
    - Created credit purchase packages (100, 500, 1000 credits) and integrated Stripe Checkout for one-time payments.
    - Implemented webhook handling for successful payments and automatic credit allocation.
    - Refactored credit purchase system to use Stripe products instead of `CreditPurchasePackage`.
    - Introduced `StripeCustomer` model to link Django users with Stripe customers.
- Frontend:
    - Created `/dashboard/buy-credits/` page with package options.
    - Added Stripe Checkout integration with package selection.
    - Created payment success/failure pages.
    - Updated dashboard template to display recent purchase details.
    - Enhanced credit transaction history to show purchase records.
- Testing:
    - Tests for credit purchase flow.
    - Tests for Stripe webhook processing.
    - Integration tests for complete purchase process.
- Documentation:
    - Updated ROADMAP.md to mark sprint as completed.
    - Clarified `CREDIT_SYSTEM.md` documentation regarding the use of Stripe Products for credit purchases.

This PR implements the pay-as-you-go credit purchase functionality. Users can now buy credits that never expire using Stripe Checkout. Successful payments trigger automatic credit allocation, and the system maintains a comprehensive transaction history. The implementation uses Stripe Products for managing credit packages, ensuring a streamlined and robust credit purchasing experience.

## v0.15.0 (2025-05-24)
v0.15.0 feat: Implement Basic Service Credit Consumption

- Backend:
  - Created `Service` model with name, description, and credit_cost fields.
  - Implemented `consume_credits()` method with validation and insufficient credits error handling.
  - Enhanced `CreditAccount` with service usage tracking functionality.
  - Added service admin interface for managing available services.
- Frontend:
  - Created `/services/` page listing available services with credit costs and descriptions.
  - Added "Use Service" buttons that consume credits with real-time feedback.
  - Implemented success/error message display for service usage attempts.
  - Enhanced credit dashboard to display updated balance after service usage.
- Testing:
  - Created comprehensive test suite covering credit consumption logic and insufficient credits scenarios.
  - Added integration tests for complete service usage flow and user experience.
  - Ensured no regression with existing credit and dashboard functionality.
- Documentation:
  - Updated version to v0.15.0 and marked sprint as completed in ROADMAP.md.

This PR implements comprehensive service credit consumption functionality. Users can now view available services, use services that consume credits with validation, see updated balances in real-time, and receive clear feedback when insufficient credits are available. The implementation includes proper error handling, transaction tracking, and maintains complete audit trail integrity for compliance and testing purposes.

## v0.14.0 (2025-05-24)
v0.14.0 feat: Implement Manual Credit Management System

- Backend:
  - Enhanced `CreditAccountAdmin` with custom actions and individual credit adjustment views.
  - Created `AdminCreditAdjustmentForm` with comprehensive validation and input sanitization.
  - Implemented bulk credit addition action for multiple users simultaneously.
  - Added transaction attribution to track admin operations with user attribution.
  - Made credit transactions read-only to preserve audit trail integrity.
- Frontend:
  - Created credit adjustment templates with responsive form layouts and current balance display.
  - Added bulk credit adjustment interface with confirmation workflows.
  - Enhanced admin interface with credit action buttons and validation warnings.
  - Implemented comprehensive error message handling and form validation feedback.
- Testing:
  - Created comprehensive test suite with 16 tests covering all Sprint 2 functionality.
  - Added template structure validation and admin configuration tests.
  - Implemented form validation and integration tests.
  - Ensured no regression with existing credit and dashboard functionality (44 total tests passed).
- Documentation:
  - Created MANUAL_CREDIT_MANAGEMENT.md with complete implementation documentation.
  - Updated ROADMAP.md marking completed work.
  - Documented admin credit management workflows and validation procedures.

This PR implements comprehensive manual credit management functionality for administrators. Admins can now add/remove credits to any user account with complete audit trails, validation, and bulk operations support. The implementation includes security validation, transaction attribution, and maintains complete data integrity for compliance and testing purposes.

## v0.13.0 (2025-05-23)
v0.13.0 feat: Implement Basic Credit Account Foundation

- Backend:
  - Created `CreditAccount` model linked to users with a single balance field.
  - Created `CreditTransaction` model with basic fields (amount, description, user, timestamp).
  - Added simple credit balance calculation method.
  - Created basic credit operations: `add_credits()` and `get_balance()`.
  - Included admin interfaces for managing credit accounts and transactions.
- Frontend:
  - Created `/dashboard/credits/` page showing current credit balance and recent 5 credit transactions.
  - Added credits section to main dashboard with balance display.
  - Updated dashboard templates with new links and settings adjustments.
- Testing:
  - Unit tests for credit models and basic operations.
  - Integration test for credit dashboard page.
  - Test credit balance calculation.
- Documentation:
  - Updated `README.md` and `USER_GUIDE.md` with new Credit System documentation.
  - Introduced `CREDIT_SYSTEM.md` for detailed information on the credit system.

This PR implements the Basic Credit Account Foundation, introducing a credit system to the application. Users can now view their credit balance and recent transaction history on a dedicated page and the main dashboard. This set of changes provides a foundational credit management system, enhancing user experience and preparing for future credit-related features.

## v0.12.0 (2025-05-22)
v0.12.0 feat: Implement Basic Stripe Checkout Flow 

- Integrated Stripe Checkout session creation with the create_checkout_session method in StripeManager
- Implemented user authentication verification before allowing checkout initiation:
- Redirects unauthenticated users to login/signup with clear messaging
- Seamlessly proceeds to checkout for authenticated users
- Created CheckoutView for handling checkout requests with proper HTMX support
- Added success and error templates for post-checkout user feedback:
- checkout_success.html for successful payments
- checkout_error.html for handling declined/failed payments
- Updated plan_comparison.html to include checkout initiation buttons
- Enhanced the StripeProduct model with stripe_price_id for better product management
- Implemented webhook handler for processing checkout completion events
- Refactored the project roadmap to separate completed work from future sprints:
- Completed core checkout functionality
- Moved subscription model and advanced features to next sprint

This PR completes all core checkout functionality, providing users with a secure and straightforward way to purchase subscriptions. The implementation uses Stripe's hosted checkout page for maximum security and simplicity, with full integration into our authentication system.
The remaining subscription management functionality (subscription model, lifecycle hooks, and comprehensive testing) has been moved to next sprint in the roadmap.

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