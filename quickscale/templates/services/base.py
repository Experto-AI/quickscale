from abc import ABC, abstractmethod
from decimal import Decimal
from django.contrib.auth import get_user_model
from credits.models import CreditAccount, Service, ServiceUsage, InsufficientCreditsError, CreditTransaction

User = get_user_model()


class BaseService(ABC):
    """Base class for all services that consume credits."""
    
    def __init__(self, service_name: str):
        """Initialize the service with its name."""
        self.service_name = service_name
        self._service_model = None
    
    @property
    def service_model(self) -> Service:
        """Get the Service model instance for this service."""
        if self._service_model is None:
            try:
                self._service_model = Service.objects.get(name=self.service_name, is_active=True)
            except Service.DoesNotExist:
                raise ValueError(f"Service '{self.service_name}' not found or is inactive")
        return self._service_model
    
    def consume_credits(self, user: User) -> ServiceUsage:
        """Consume credits for this service and record usage."""
        if not isinstance(user, User):
            raise ValueError("User must be a valid User instance")
        
        # Get the credit account for the user
        credit_account = CreditAccount.get_or_create_for_user(user)
        
        # Get the service model to check credit cost and availability
        service = self.service_model
        
        try:
            # Handle zero-cost services
            if service.credit_cost == 0:
                # For free services, create a zero-amount transaction
                credit_transaction = CreditTransaction.objects.create(
                    user=user,
                    amount=Decimal('0'),
                    description=f"Service usage: {service.name} (free)",
                    credit_type='CONSUMPTION'
                )
            else:
                # Consume credits using the priority system
                credit_transaction = credit_account.consume_credits_with_priority(
                    amount=service.credit_cost,
                    description=f"Service usage: {service.name}"
                )
            
            # Record service usage
            service_usage = ServiceUsage.objects.create(
                user=user,
                service=service,
                credit_transaction=credit_transaction
            )
            
            return service_usage
            
        except InsufficientCreditsError as e:
            # Re-raise with service-specific context
            raise InsufficientCreditsError(
                f"Insufficient credits to use {service.name}. "
                f"Required: {service.credit_cost} credits. {str(e)}"
            )
    
    def check_user_credits(self, user: User) -> dict:
        """Check if user has sufficient credits for this service."""
        if not isinstance(user, User):
            raise ValueError("User must be a valid User instance")
        
        credit_account = CreditAccount.get_or_create_for_user(user)
        service = self.service_model
        
        available_balance = credit_account.get_available_balance()
        has_sufficient_credits = available_balance >= service.credit_cost
        
        return {
            'has_sufficient_credits': has_sufficient_credits,
            'required_credits': service.credit_cost,
            'available_credits': available_balance,
            'shortfall': max(Decimal('0'), service.credit_cost - available_balance)
        }
    
    @abstractmethod
    def execute_service(self, user: User, **kwargs):
        """Execute the service logic. Must be implemented by subclasses."""
        pass
    
    def run(self, user: User, **kwargs):
        """Run the service: consume credits, execute logic, and return result."""
        # First consume credits and record usage
        service_usage = self.consume_credits(user)
        
        try:
            # Execute the service logic
            result = self.execute_service(user, **kwargs)
            
            return {
                'success': True,
                'result': result,
                'service_usage': service_usage,
                'credits_consumed': service_usage.service.credit_cost
            }
            
        except Exception as e:
            # If service execution fails, we don't refund credits
            # This is by design to prevent abuse
            raise e