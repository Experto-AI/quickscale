"""Admin dashboard models."""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class AuditLog(models.Model):
    """Model to track admin actions for audit purposes."""
    
    ACTION_CHOICES = [
        ('USER_SEARCH', 'User Search'),
        ('USER_VIEW', 'User View'),
        ('USER_EDIT', 'User Edit'),
        ('CREDIT_ADJUSTMENT', 'Credit Adjustment'),
        ('SERVICE_TOGGLE', 'Service Toggle'),
        ('PRODUCT_SYNC', 'Product Sync'),
        ('ADMIN_LOGIN', 'Admin Login'),
        ('ADMIN_LOGOUT', 'Admin Logout'),
        ('PAYMENT_INVESTIGATION', 'Payment Investigation'),
        ('PAYMENT_REFUND', 'Payment Refund'),
        ('OTHER', 'Other Action'),
    ]
    
    # Admin user who performed the action
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='audit_logs'
    )
    
    # Action performed
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    
    # Descriptive text of what was done
    description = models.TextField()
    
    # Timestamp when action was performed
    timestamp = models.DateTimeField(default=timezone.now)
    
    # Optional: IP address for security tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Optional: User agent for additional context
    user_agent = models.TextField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Log Entry'
        verbose_name_plural = 'Audit Log Entries'
    
    def __str__(self):
        user_email = self.user.email if self.user else 'Unknown User'
        return f"{user_email} - {self.get_action_display()} - {self.timestamp}" 