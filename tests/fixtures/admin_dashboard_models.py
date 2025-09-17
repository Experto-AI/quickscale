"""Mock AuditLog model for testing."""
from django.contrib.auth import get_user_model

User = get_user_model()

class AuditLog:
    """Mock AuditLog for testing purposes."""
    def __init__(self, user=None, action=None, description=None, **kwargs):
        self.user = user
        self.action = action
        self.description = description
        
    @classmethod
    def objects(cls):
        return MockManager()

class MockManager:
    def create(self, **kwargs):
        return AuditLog(**kwargs)
