"""
Management command to test and validate feature flag system.

This command helps validate that the feature flag system is working correctly
and can be used to test different configurations.
"""

from core.configuration import config
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Test feature flag system."""

    help = 'Test and validate feature flag system'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--mode',
            type=str,
            choices=['list', 'beta', 'production', 'summary'],
            default='summary',
            help='Testing mode: list all flags, test beta mode, test production mode, or show summary'
        )
        parser.add_argument(
            '--flag',
            type=str,
            help='Test specific flag (use with --mode=test)'
        )

    def handle(self, *args, **options):
        """Execute the command."""
        # Create simple adapter for the new configuration system
        feature_flags = config.feature_flags

        mode = options['mode']

        if mode == 'list':
            self._list_all_flags(feature_flags)
        elif mode == 'beta':
            self._test_beta_mode(feature_flags)
        elif mode == 'production':
            self._test_production_mode(feature_flags)
        elif mode == 'summary':
            self._show_summary(feature_flags)

    def _list_all_flags(self, feature_flags):
        """List all feature flags and their status."""
        self.stdout.write(self.style.SUCCESS('All Feature Flags:'))
        self.stdout.write('-' * 50)

        # Get all feature flags from the dataclass
        import dataclasses
        all_flags = {f.name: getattr(feature_flags, f.name) for f in dataclasses.fields(feature_flags)}

        for flag_name, status in sorted(all_flags.items()):
            status_color = self.style.SUCCESS if status else self.style.ERROR
            status_text = 'ENABLED ' if status else 'DISABLED'
            self.stdout.write(f'{flag_name:<30} {status_color(status_text)}')

    def _test_beta_mode(self, feature_flags):
        """Test beta mode configuration."""
        self.stdout.write(self.style.SUCCESS('Beta Mode Configuration Test:'))
        self.stdout.write('-' * 50)

        # Core features that should be enabled in beta
        core_features = [
            'enable_basic_auth',
            'enable_basic_credits',
            'enable_demo_service',
            'enable_basic_admin',
        ]

        # Complex features that should be disabled in beta
        complex_features = [
            'enable_stripe',
            'enable_subscriptions',
            'enable_service_marketplace',
            'enable_advanced_admin',
            'enable_api_endpoints',
            'enable_webhooks',
        ]

        all_passed = True

        self.stdout.write('Core Features (should be ENABLED):')
        for feature in core_features:
            status = getattr(feature_flags, feature, False)
            if status:
                self.stdout.write(f'  ✓ {feature}')
            else:
                self.stdout.write(self.style.ERROR(f'  ✗ {feature} (should be enabled)'))
                all_passed = False

        self.stdout.write('\nComplex Features (should be DISABLED):')
        for feature in complex_features:
            status = getattr(feature_flags, feature, False)
            if not status:
                self.stdout.write(f'  ✓ {feature}')
            else:
                self.stdout.write(self.style.ERROR(f'  ✗ {feature} (should be disabled)'))
                all_passed = False

        if all_passed:
            self.stdout.write(self.style.SUCCESS('\n✓ Beta mode configuration is correct!'))
        else:
            self.stdout.write(self.style.ERROR('\n✗ Beta mode configuration has issues!'))

    def _test_production_mode(self, feature_flags):
        """Test production mode capabilities."""
        self.stdout.write(self.style.SUCCESS('Production Mode Capabilities:'))
        self.stdout.write('-' * 50)

        if feature_flags.enable_stripe:
            self.stdout.write('Current mode: PRODUCTION (Stripe enabled)')
        else:
            self.stdout.write('Current mode: BETA (Stripe disabled)')

    def _show_summary(self, feature_flags):
        """Show feature flag summary."""
        self.stdout.write(self.style.SUCCESS('Feature Flag System Summary:'))
        self.stdout.write('=' * 50)

        # Basic info
        mode = 'BETA' if not feature_flags.enable_stripe else 'PRODUCTION'
        mode_color = self.style.WARNING if not feature_flags.enable_stripe else self.style.SUCCESS
        self.stdout.write(f'Current Mode: {mode_color(mode)}')

        # Show key configuration states
        self.stdout.write(f'Stripe Enabled: {feature_flags.enable_stripe}')
        self.stdout.write(f'Configuration Summary: {config.get_configuration_summary()}')
