"""Command for crawling QuickScale applications with login capabilities."""
import logging
from typing import Any, Dict, List, Optional

from quickscale.utils.error_manager import error_manager
from quickscale.utils.message_manager import MessageManager

from .command_base import Command


class CrawlApplicationCommand(Command):
    """Command to crawl a QuickScale application for validation."""

    def execute(self, args: List[str], **kwargs) -> bool:
        """Execute the crawl command."""
        try:
            # Import crawler components (lazy import to avoid dependency issues)
            from quickscale.crawler.application_crawler import ApplicationCrawler

            # Parse command line arguments
            config = self._parse_arguments(args)
            if not config:
                return False

            base_url = config['base_url']
            crawler_config = config['crawler_config']
            detailed = config['detailed']

            MessageManager.info(f"🕷️  Starting application crawl of: {base_url}")

            # Create and configure crawler
            crawler = ApplicationCrawler(base_url, crawler_config)

            try:
                # Perform the crawl
                report = crawler.crawl_all_pages(authenticate_first=True)

                # Display results
                self._display_crawl_report(report, detailed=detailed)

                # Determine success
                success = (
                    report.authentication_successful and
                    report.success_rate >= 80.0 and  # At least 80% success rate
                    len(report.missing_required_pages) == 0 and
                    len(report.errors) == 0
                )

                if success:
                    MessageManager.success("✅ Application crawl completed successfully!")
                    return True
                else:
                    MessageManager.error("❌ Application crawl found issues")
                    return False

            finally:
                crawler.close()

        except ImportError as e:
            MessageManager.error(f"Required dependencies not available: {str(e)}")
            MessageManager.info("Install with: pip install beautifulsoup4 requests")
            return False
        except Exception as e:
            error_manager.handle_command_error(e, exit_on_error=False)
            return False

    def _parse_arguments(self, args: List[str]) -> Optional[Dict[str, Any]]:
        """Parse command line arguments for the crawl command."""
        from quickscale.crawler.crawler_config import CrawlerConfig

        # Default configuration
        base_url = "http://localhost:8000"
        user_email = None
        user_password = None
        admin_mode = False
        max_pages = 50
        verbose = False
        detailed = False

        # Parse arguments
        i = 0
        while i < len(args):
            arg = args[i]

            if arg in ['-h', '--help']:
                self._show_help()
                return None
            elif arg in ['-u', '--url']:
                if i + 1 >= len(args):
                    MessageManager.error("Missing URL after --url")
                    return None
                base_url = args[i + 1]
                i += 2
            elif arg in ['-e', '--email']:
                if i + 1 >= len(args):
                    MessageManager.error("Missing email after --email")
                    return None
                user_email = args[i + 1]
                i += 2
            elif arg in ['-p', '--password']:
                if i + 1 >= len(args):
                    MessageManager.error("Missing password after --password")
                    return None
                user_password = args[i + 1]
                i += 2
            elif arg in ['-a', '--admin']:
                admin_mode = True
                i += 1
            elif arg in ['-m', '--max-pages']:
                if i + 1 >= len(args):
                    MessageManager.error("Missing number after --max-pages")
                    return None
                try:
                    max_pages = int(args[i + 1])
                except ValueError:
                    MessageManager.error("Invalid number for --max-pages")
                    return None
                i += 2
            elif arg in ['-v', '--verbose']:
                verbose = True
                i += 1
            elif arg in ['-d', '--detailed']:
                detailed = True
                i += 1
            else:
                MessageManager.error(f"Unknown argument: {arg}")
                self._show_help()
                return None

        # Configure logging level
        if verbose:
            logging.getLogger('quickscale.crawler').setLevel(logging.DEBUG)

        # Create crawler configuration
        crawler_config = CrawlerConfig(max_pages=max_pages, admin_mode=admin_mode)

        # Set credentials based on mode
        if admin_mode:
            crawler_config.default_user_email = user_email or crawler_config.default_admin_email
            crawler_config.default_user_password = user_password or crawler_config.default_admin_password
        else:
            crawler_config.default_user_email = user_email or crawler_config.default_user_email
            crawler_config.default_user_password = user_password or crawler_config.default_user_password

        return {
            'base_url': base_url,
            'crawler_config': crawler_config,
            'verbose': verbose,
            'detailed': detailed
        }

    def _show_help(self) -> None:
        """Display help information for the crawl command."""
        help_text = '''
QuickScale Application Crawler

USAGE:
    quickscale crawl [OPTIONS]

DESCRIPTION:
    Crawls a QuickScale application to validate that all pages render correctly.
    Tests authentication, page loading, CSS/JS functionality, and overall health.

OPTIONS:
    -u, --url URL           Base URL of the application (default: http://localhost:8000)
    -e, --email EMAIL       Email for authentication (default: user@test.com)
    -p, --password PASS     Password for authentication (default: userpasswd)
    -a, --admin             Use admin credentials (admin@test.com/adminpasswd)
    -m, --max-pages NUM     Maximum pages to crawl (default: 50)
    -v, --verbose           Enable verbose logging
    -d, --detailed          Show detailed lists of all pages (successful, warnings, failed)
    -h, --help              Show this help message

EXAMPLES:
    # Crawl local QuickScale project
    quickscale crawl
    
    # Crawl with custom URL and credentials
    quickscale crawl --url http://localhost:8080 --email test@example.com --password mypass
    
    # Crawl as admin user with detailed output
    quickscale crawl --admin --detailed
    
    # Crawl with verbose logging and detailed reporting
    quickscale crawl --verbose --detailed --max-pages 20

REQUIREMENTS:
    - QuickScale application must be running at the specified URL
    - Application must have test users configured
    - Required Python packages: beautifulsoup4, requests
'''
        MessageManager.info(help_text.strip())

    def _display_crawl_report(self, report, detailed: bool = False) -> None:
        """Display the crawl report in a user-friendly format."""
        MessageManager.info("\\n" + "="*60)
        MessageManager.info("🕷️  APPLICATION CRAWL REPORT")
        MessageManager.info("="*60)

        # Authentication status
        auth_status = "✅ SUCCESS" if report.authentication_successful else "❌ FAILED"
        MessageManager.info(f"Authentication: {auth_status}")

        # Overall statistics
        MessageManager.info(f"Base URL: {report.base_url}")
        MessageManager.info(f"Pages crawled: {report.total_pages_crawled}")
        MessageManager.info(f"Success rate: {report.success_rate:.1f}%")
        MessageManager.info(f"Crawl time: {report.total_crawl_time:.2f} seconds")

        # Page breakdown
        if report.total_pages_crawled > 0:
            MessageManager.info("\\nPage Results:")
            MessageManager.success(f"  ✅ Successful: {report.successful_pages}")
            if report.failed_pages > 0:
                MessageManager.error(f"  ❌ Failed: {report.failed_pages}")
            if report.pages_with_warnings > 0:
                MessageManager.warning(f"  ⚠️  With warnings: {report.pages_with_warnings}")

        # Missing required pages
        if report.missing_required_pages:
            MessageManager.warning("\\nMissing Required Pages:")
            for page in report.missing_required_pages:
                MessageManager.warning(f"  - {page}")

        # General errors
        if report.errors:
            MessageManager.error("\\nGeneral Errors:")
            for error in report.errors:
                MessageManager.error(f"  - {error}")

        # Successful pages list (only in detailed mode)
        successful_pages = [r for r in report.page_results if r.validation_result.is_valid and not r.validation_result.warnings]
        if detailed and successful_pages:
            MessageManager.success(f"\\n✅ Successful Pages ({len(successful_pages)}):")
            for page_result in successful_pages:
                MessageManager.success(f"  📄 {page_result.url} (HTTP {page_result.status_code})")

        # Pages with warnings (complete list in detailed mode, summary otherwise)
        warning_pages = [r for r in report.page_results if r.validation_result.warnings and r.validation_result.is_valid]
        if warning_pages:
            if detailed:
                MessageManager.warning(f"\\n⚠️  Pages with Warnings ({len(warning_pages)}):")
                for page_result in warning_pages:
                    MessageManager.warning(f"  📄 {page_result.url} (HTTP {page_result.status_code})")
                    for warning in page_result.validation_result.warnings:
                        MessageManager.warning(f"     ⚠️  {warning}")
            else:
                MessageManager.warning(f"\\n⚠️  Pages with Warnings ({len(warning_pages)}):")
                for page_result in warning_pages[:3]:  # Show first 3 in summary mode
                    MessageManager.warning(f"  📄 {page_result.url}")
                    for warning in page_result.validation_result.warnings[:2]:  # Show first 2 warnings
                        MessageManager.warning(f"     ⚠️  {warning}")
                if len(warning_pages) > 3:
                    MessageManager.warning(f"  ... and {len(warning_pages) - 3} more (use --detailed for full list)")

        # Failed pages (complete list in detailed mode, summary otherwise)
        failed_pages = [r for r in report.page_results if not r.validation_result.is_valid]
        if failed_pages:
            if detailed:
                MessageManager.error(f"\\n❌ Failed Pages ({len(failed_pages)}):")
                for page_result in failed_pages:
                    MessageManager.error(f"  📄 {page_result.url} (HTTP {page_result.status_code})")
                    if page_result.validation_result.errors:
                        for error in page_result.validation_result.errors:
                            MessageManager.error(f"     ❌ {error}")
                    if page_result.validation_result.warnings:
                        for warning in page_result.validation_result.warnings:
                            MessageManager.warning(f"     ⚠️  {warning}")
            else:
                MessageManager.error(f"\\n❌ Failed Pages ({len(failed_pages)}):")
                for page_result in failed_pages[:5]:  # Show first 5 in summary mode
                    MessageManager.error(f"  📄 {page_result.url} (HTTP {page_result.status_code})")
                    if page_result.validation_result.errors:
                        for error in page_result.validation_result.errors[:3]:  # Show first 3 errors
                            MessageManager.error(f"     ❌ {error}")
                    if page_result.validation_result.warnings:
                        for warning in page_result.validation_result.warnings[:2]:  # Show first 2 warnings
                            MessageManager.warning(f"     ⚠️  {warning}")
                if len(failed_pages) > 5:
                    MessageManager.error(f"  ... and {len(failed_pages) - 5} more (use --detailed for full list)")

        MessageManager.info("\\n" + "="*60)

        # Summary recommendation
        if report.success_rate >= 95.0 and not report.missing_required_pages and not report.errors:
            MessageManager.success("🎉 Application appears to be working perfectly!")
        elif report.success_rate >= 80.0 and not report.missing_required_pages:
            MessageManager.warning("⚠️  Application is mostly working but has some issues")
        else:
            MessageManager.error("🚨 Application has significant issues that need attention")

    def get_help_text(self) -> str:
        """Return help text for this command."""
        return "Crawl a QuickScale application to validate page rendering and functionality"
