from typing import Dict, Type, Any, Optional, Protocol
from abc import ABC, abstractmethod
import threading
from functools import wraps

class Container:
    """
    Simple dependency injection container for managing service dependencies.
    Supports singleton and transient lifecycles.
    """
    
    def __init__(self):
        self._services: Dict[Type, Any] = {}
        self._singletons: Dict[Type, Any] = {}
        self._factories: Dict[Type, callable] = {}
        self._lock = threading.Lock()
    
    def register_singleton(self, interface: Type, implementation: Type):
        """Register a service as singleton (one instance per container)"""
        with self._lock:
            self._services[interface] = implementation
            self._factories[interface] = lambda: implementation()
    
    def register_transient(self, interface: Type, implementation: Type):
        """Register a service as transient (new instance each time)"""
        with self._lock:
            self._services[interface] = implementation
            self._factories[interface] = lambda: implementation()
    
    def register_instance(self, interface: Type, instance: Any):
        """Register an existing instance"""
        with self._lock:
            self._services[interface] = type(instance)
            self._singletons[interface] = instance
    
    def register_factory(self, interface: Type, factory: callable):
        """Register a factory function for creating instances"""
        with self._lock:
            self._factories[interface] = factory
    
    def get(self, interface: Type) -> Any:
        """Get an instance of the requested service"""
        with self._lock:
            # Check if already created singleton
            if interface in self._singletons:
                return self._singletons[interface]
            
            # Check if factory exists
            if interface in self._factories:
                factory = self._factories[interface]
                instance = factory()
                
                # Store as singleton if it's registered as one
                if interface in self._services:
                    self._singletons[interface] = instance
                
                return instance
            
            # If no factory, try to create directly
            if interface in self._services:
                implementation = self._services[interface]
                instance = implementation()
                self._singletons[interface] = instance
                return instance
            
            raise ValueError(f"Service {interface} not registered")
    
    def is_registered(self, interface: Type) -> bool:
        """Check if a service is registered"""
        return interface in self._services or interface in self._factories
    
    def clear(self):
        """Clear all registered services (useful for testing)"""
        with self._lock:
            self._services.clear()
            self._singletons.clear()
            self._factories.clear()

# Global container instance
_container = Container()

def get_container() -> Container:
    """Get the global container instance"""
    return _container

def inject(interface: Type):
    """Decorator for automatic dependency injection"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if interface.__name__.lower() not in kwargs:
                kwargs[interface.__name__.lower()] = _container.get(interface)
            return func(*args, **kwargs)
        return wrapper
    return decorator

class Injectable(ABC):
    """Base class for injectable services"""
    pass

# Context manager for scoped services
class ServiceScope:
    """Context manager for creating scoped service instances"""
    
    def __init__(self, container: Container):
        self.container = container
        self.scoped_instances = {}
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Clean up scoped instances
        for instance in self.scoped_instances.values():
            if hasattr(instance, 'dispose'):
                instance.dispose()
        self.scoped_instances.clear()
    
    def get(self, interface: Type) -> Any:
        """Get service instance within this scope"""
        if interface in self.scoped_instances:
            return self.scoped_instances[interface]
        
        instance = self.container.get(interface)
        self.scoped_instances[interface] = instance
        return instance