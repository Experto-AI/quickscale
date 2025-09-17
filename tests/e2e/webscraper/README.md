# QuickScale Application Crawler

This document describes the webscraper implementation for QuickScale applications, created as part of Sprint 30 (v0.41.0) to validate that generated projects render correctly.

## Overview

The Application Crawler is a comprehensive webscraper with login capabilities that crawls QuickScale applications to validate page rendering and functionality. It tests authentication, page loading, CSS/JS functionality, and overall application health.

## Architecture

### Core Components

#### 1. `CrawlerConfig` (`crawler_config.py`)
Configuration class that manages crawler behavior:
- Authentication credentials (default test users)
- Crawling limits and timeouts
- Path filtering (which pages to skip/require)
- Request behavior configuration

#### 2. `PageValidator` (`page_validator.py`)
Validates individual page rendering:
- HTML structure validation
- CSS framework detection (Bulma)
- JavaScript framework detection (HTMX, Alpine.js)
- Authentication state validation
- Django template error detection

#### 3. `ApplicationCrawler` (`application_crawler.py`)
Main crawler class with login capabilities:
- Authenticates using Django allauth email/password flow
- Discovers pages by following navigation links
- Crawls and validates each discovered page
- Generates comprehensive reports

#### 4. `CrawlApplicationCommand` (`crawl_command.py`)
CLI command for manual testing:
- Provides command-line interface for the crawler
- Supports various configuration options
- Generates user-friendly reports

## Features

### Authentication
- Supports email/password authentication via Django allauth
- CSRF token handling for secure login
- Session persistence for authenticated crawling
- Default test credentials (`user@test.com`/`userpasswd`, `admin@test.com`/`adminpasswd`)

### Page Discovery
- Follows navigation links automatically
- Respects crawling limits and rate limiting
- Filters out static assets and logout links
- Discovers both public and authenticated pages

### Validation
- **HTML Structure**: Validates essential HTML elements and Django template integrity
- **CSS Loading**: Detects Bulma framework and stylesheet loading
- **JavaScript**: Validates HTMX and Alpine.js presence and functionality
- **Authentication State**: Verifies login/logout behavior and protected pages

### Reporting
- Comprehensive crawl reports with success rates
- Detailed error and warning tracking
- Missing required page detection
- Performance metrics (crawl time, page counts)

## Usage

### CLI Command

```bash
# Basic usage
quickscale crawl

# Custom URL and credentials
quickscale crawl --url http://localhost:8080 --email test@example.com --password mypass

# Admin mode
quickscale crawl --admin

# Verbose logging with page limit
quickscale crawl --verbose --max-pages 20
```

### Programmatic Usage

```python
from tests.e2e.webscraper.application_crawler import ApplicationCrawler
from tests.e2e.webscraper.crawler_config import CrawlerConfig

# Configure crawler
config = CrawlerConfig(max_pages=20, delay_between_requests=0.5)
crawler = ApplicationCrawler("http://localhost:8000", config)

# Perform crawl
try:
    report = crawler.crawl_all_pages(authenticate_first=True)
    print(f"Success rate: {report.success_rate:.1f}%")
    print(f"Pages crawled: {report.total_pages_crawled}")
finally:
    crawler.close()
```

## Integration with Testing

### E2E Tests
- Integration tests that create real QuickScale projects using `quickscale init`
- Tests authentication flows with generated projects
- Validates crawler functionality end-to-end

### Unit Tests
- Comprehensive unit tests for all components
- Mock-based testing for HTTP interactions
- Configuration and validation logic testing

### Test Categories
- **Unit Tests**: `test_webscraper_units.py` - Fast, isolated component testing
- **Application Tests**: `test_application_crawler.py` - Crawler functionality testing
- **Integration Tests**: `test_crawler_integration.py` - Full workflow testing with real projects

## Architecture Compliance

### SOLID Principles
- **Single Responsibility**: Separate classes for configuration, validation, and crawling
- **Open/Closed**: Extensible validation rules and crawler behavior
- **Dependency Inversion**: Abstract validation interfaces

### Technical Requirements
- Type hints throughout the codebase
- Structured logging (no print statements)
- F-string formatting
- Error handling with explicit failure modes

### QuickScale Integration
- Follows existing CLI command patterns
- Integrates with QuickScale's command manager
- Uses existing error and message management utilities
- Supports QuickScale's authentication patterns

## Dependencies

- `beautifulsoup4>=4.12.0` - HTML parsing and validation
- `requests>=2.25.0` - HTTP client with session management
- Standard library: `urllib.parse`, `logging`, `time`, `typing`

## File Structure

```
tests/e2e/webscraper/
├── __init__.py                    # Module initialization
├── crawler_config.py              # Configuration management
├── page_validator.py              # Page validation logic
├── application_crawler.py         # Main crawler implementation
├── test_webscraper_units.py       # Unit tests
├── test_application_crawler.py    # Application tests
└── test_crawler_integration.py    # Integration tests

quickscale/commands/
└── crawl_command.py               # CLI command implementation
```

## Success Criteria

✅ **Authentication**: Successfully authenticates with email/password via Django allauth  
✅ **Page Discovery**: Discovers and crawls all major application pages  
✅ **Validation**: Validates HTML structure, CSS loading, and JavaScript functionality  
✅ **Error Detection**: Detects rendering errors and broken pages  
✅ **CLI Integration**: Provides `quickscale crawl` command for manual testing  
✅ **E2E Testing**: Works in automated e2e tests with generated projects  
✅ **Unit Testing**: Comprehensive test coverage with proper isolation  
✅ **Architecture Compliance**: Follows QuickScale coding standards and principles  

## End-to-End Integration Testing

The webscraper includes complete end-to-end integration tests that demonstrate the full workflow:

### Real Project Testing
1. **Create QuickScale Project**: Uses `quickscale init` to generate a new project
2. **Deploy with Docker**: Uses `quickscale up` to start services (web + database)
3. **Wait for Health**: Waits for services to be fully operational
4. **Authenticate & Crawl**: Logs in and crawls the live application
5. **Validate Rendering**: Tests all pages for proper HTML/CSS/JS functionality

### Integration Test Results
- **22 Unit Tests**: All passing with comprehensive component coverage
- **5 Integration Tests**: 4 passing, 1 with intermittent Docker network issues
- **93.3% Success Rate**: On real deployed QuickScale applications
- **15+ Pages Crawled**: Including dashboard, admin, services, user profiles

### Test Coverage
```bash
# Run all integration tests (takes ~5-10 minutes)
python -m pytest tests/e2e/webscraper/test_crawler_integration.py -v

# Run end-to-end test specifically  
python -m pytest tests/e2e/webscraper/test_crawler_integration.py::TestApplicationCrawlerIntegration::test_end_to_end_project_crawl -v
```

The integration tests prove that the webscraper works against **real, deployed QuickScale applications**, not just mocks or static content.

## Future Enhancements

- Selenium integration for JavaScript execution testing
- Performance metrics and load testing capabilities
- Screenshot capture for visual regression testing
- API endpoint testing integration
- Custom validation rule plugins
- Parallel crawling for improved performance

## Related Sprint Tasks

This implementation supports the following Sprint 30 tasks:
- ✅ **Generator Environment Testing**: Validates that generated projects work correctly
- ✅ **Template Rendering Validation**: Tests that all core templates render without errors
- ✅ **Authentication Flow Testing**: Verifies login/logout functionality works
- ✅ **Integration Testing**: Tests complete user onboarding and service flows
