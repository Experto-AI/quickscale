from typing import Dict, Type, Optional
from .base import BaseService


class ServiceRegistry:
    """Registry for managing registered services."""
    
    def __init__(self):
        self._services: Dict[str, Type[BaseService]] = {}
    
    def register(self, service_name: str, service_class: Type[BaseService]) -> None:
        """Register a service class with a given name."""
        if not issubclass(service_class, BaseService):
            raise ValueError(f"Service class must inherit from BaseService")
        
        if service_name in self._services:
            raise ValueError(f"Service '{service_name}' is already registered")
        
        self._services[service_name] = service_class
    
    def get_service(self, service_name: str) -> Optional[Type[BaseService]]:
        """Get a registered service class by name."""
        return self._services.get(service_name)
    
    def get_all_services(self) -> Dict[str, Type[BaseService]]:
        """Get all registered services."""
        return self._services.copy()
    
    def is_registered(self, service_name: str) -> bool:
        """Check if a service is registered."""
        return service_name in self._services
    
    def unregister(self, service_name: str) -> bool:
        """Unregister a service. Returns True if service was found and removed."""
        if service_name in self._services:
            del self._services[service_name]
            return True
        return False


# Global service registry instance
service_registry = ServiceRegistry()


def register_service(service_name: str):
    """Decorator to register a service class in the service registry."""
    
    def decorator(service_class: Type[BaseService]):
        # Validate that the class inherits from BaseService
        if not issubclass(service_class, BaseService):
            raise ValueError(f"Service class {service_class.__name__} must inherit from BaseService")
        
        # Register the service
        service_registry.register(service_name, service_class)
        
        # Return the class unchanged
        return service_class
    
    return decorator


def get_registered_service(service_name: str) -> Optional[Type[BaseService]]:
    """Utility function to get a registered service class."""
    return service_registry.get_service(service_name)


def get_all_registered_services() -> Dict[str, Type[BaseService]]:
    """Utility function to get all registered services."""
    return service_registry.get_all_services()


def create_service_instance(service_name: str) -> Optional[BaseService]:
    """Create an instance of a registered service."""
    service_class = get_registered_service(service_name)
    if service_class:
        return service_class(service_name)
    return None