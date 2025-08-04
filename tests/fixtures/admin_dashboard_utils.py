"""Mock log_admin_action utility for testing."""

def log_admin_action(user, action, description, request=None):
    """Mock log_admin_action for testing purposes."""
    from .admin_dashboard_models import AuditLog
    return AuditLog(user=user, action=action, description=description)
