"""Admin configuration for admin dashboard models."""
from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin interface for AuditLog model."""
    
    list_display = ['timestamp', 'user', 'action', 'description', 'ip_address']
    list_filter = ['action', 'timestamp']
    search_fields = ['user__email', 'description', 'ip_address']
    ordering = ['-timestamp']
    readonly_fields = ['timestamp', 'user', 'action', 'description', 'ip_address', 'user_agent']
    
    def has_add_permission(self, request):
        """Prevent manual creation of audit logs."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent editing of audit logs."""
        return False 