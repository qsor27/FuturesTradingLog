"""
Dependency Injection Configuration
Sets up the DI container with all required services and repositories
"""

import os
from typing import Dict, Any
from pathlib import Path

from .container import Container, get_container
from .config import config

# Repository interfaces
from repositories.interfaces import (
    ITradeRepository, IPositionRepository, IOHLCRepository,
    ISettingsRepository, IProfileRepository, IStatisticsRepository
)

# Repository implementations
from repositories.sqlite_repository import (
    SQLiteTradeRepository, SQLitePositionRepository, SQLiteOHLCRepository,
    SQLiteSettingsRepository, SQLiteProfileRepository, SQLiteStatisticsRepository
)

# Service interfaces
from services.interfaces import (
    IPositionService, ITradeService, IChartService, IValidationService,
    IAnalyticsService, IUserService, IDataService, INotificationService
)

# Service implementations
from services.position_service import PositionService

def configure_container() -> Container:
    """
    Configure the dependency injection container with all required services
    
    This function sets up the entire application dependency graph:
    - Repositories for data access
    - Services for business logic
    - Configuration for application settings
    """
    container = get_container()
    
    # Clear any existing registrations (useful for testing)
    container.clear()
    
    # Register configuration
    container.register_instance(type(config), config)
    
    # Register repositories as singletons
    container.register_factory(
        ITradeRepository,
        lambda: SQLiteTradeRepository(str(config.db_path))
    )
    
    container.register_factory(
        IPositionRepository,
        lambda: SQLitePositionRepository(str(config.db_path))
    )
    
    container.register_factory(
        IOHLCRepository,
        lambda: SQLiteOHLCRepository(str(config.db_path))
    )
    
    container.register_factory(
        ISettingsRepository,
        lambda: SQLiteSettingsRepository(str(config.db_path))
    )
    
    container.register_factory(
        IProfileRepository,
        lambda: SQLiteProfileRepository(str(config.db_path))
    )
    
    container.register_factory(
        IStatisticsRepository,
        lambda: SQLiteStatisticsRepository(str(config.db_path))
    )
    
    # Register services
    container.register_factory(
        IPositionService,
        lambda: PositionService(
            container.get(IPositionRepository),
            container.get(ITradeRepository)
        )
    )
    
    # TODO: Register other services as they are implemented
    # container.register_factory(
    #     ITradeService,
    #     lambda: TradeService(
    #         container.get(ITradeRepository),
    #         container.get(IPositionRepository)
    #     )
    # )
    
    # container.register_factory(
    #     IChartService,
    #     lambda: ChartService(
    #         container.get(IOHLCRepository),
    #         container.get(ISettingsRepository)
    #     )
    # )
    
    # container.register_factory(
    #     IValidationService,
    #     lambda: ValidationService(
    #         container.get(ITradeRepository),
    #         container.get(IPositionRepository)
    #     )
    # )
    
    # container.register_factory(
    #     IAnalyticsService,
    #     lambda: AnalyticsService(
    #         container.get(IStatisticsRepository),
    #         container.get(ITradeRepository),
    #         container.get(IPositionRepository)
    #     )
    # )
    
    # container.register_factory(
    #     IUserService,
    #     lambda: UserService(
    #         container.get(IProfileRepository),
    #         container.get(ISettingsRepository)
    #     )
    # )
    
    # container.register_factory(
    #     IDataService,
    #     lambda: DataService(
    #         container.get(IOHLCRepository),
    #         config.redis_url if config.cache_enabled else None
    #     )
    # )
    
    # container.register_factory(
    #     INotificationService,
    #     lambda: NotificationService()
    # )
    
    return container

def get_service(service_type: type) -> Any:
    """
    Get a service instance from the configured container
    
    Args:
        service_type: The service interface type to retrieve
        
    Returns:
        Instance of the requested service
    """
    container = get_container()
    return container.get(service_type)

def configure_for_testing(test_db_path: str = None) -> Container:
    """
    Configure container for testing with optional test database
    
    Args:
        test_db_path: Path to test database, if None uses in-memory database
        
    Returns:
        Configured container for testing
    """
    container = get_container()
    container.clear()
    
    # Use test database path or in-memory database
    db_path = test_db_path or ':memory:'
    
    # Register test repositories
    container.register_factory(
        ITradeRepository,
        lambda: SQLiteTradeRepository(db_path)
    )
    
    container.register_factory(
        IPositionRepository,
        lambda: SQLitePositionRepository(db_path)
    )
    
    container.register_factory(
        IOHLCRepository,
        lambda: SQLiteOHLCRepository(db_path)
    )
    
    container.register_factory(
        ISettingsRepository,
        lambda: SQLiteSettingsRepository(db_path)
    )
    
    container.register_factory(
        IProfileRepository,
        lambda: SQLiteProfileRepository(db_path)
    )
    
    container.register_factory(
        IStatisticsRepository,
        lambda: SQLiteStatisticsRepository(db_path)
    )
    
    # Register test services
    container.register_factory(
        IPositionService,
        lambda: PositionService(
            container.get(IPositionRepository),
            container.get(ITradeRepository)
        )
    )
    
    return container

class DIConfig:
    """
    Dependency injection configuration class
    Provides centralized configuration for the DI container
    """
    
    def __init__(self):
        self._container = None
        self._configured = False
    
    @property
    def container(self) -> Container:
        """Get the configured container"""
        if not self._configured:
            self.configure()
        return self._container
    
    def configure(self, force_reconfigure: bool = False):
        """Configure the container"""
        if self._configured and not force_reconfigure:
            return
        
        self._container = configure_container()
        self._configured = True
    
    def get_service(self, service_type: type) -> Any:
        """Get a service from the container"""
        return self.container.get(service_type)
    
    def is_configured(self) -> bool:
        """Check if container is configured"""
        return self._configured
    
    def reset(self):
        """Reset configuration (useful for testing)"""
        if self._container:
            self._container.clear()
        self._configured = False

# Global DI configuration instance
di_config = DIConfig()

# Helper functions for easy access
def get_position_service() -> IPositionService:
    """Get position service instance"""
    return di_config.get_service(IPositionService)

def get_trade_repository() -> ITradeRepository:
    """Get trade repository instance"""
    return di_config.get_service(ITradeRepository)

def get_position_repository() -> IPositionRepository:
    """Get position repository instance"""
    return di_config.get_service(IPositionRepository)

def get_ohlc_repository() -> IOHLCRepository:
    """Get OHLC repository instance"""
    return di_config.get_service(IOHLCRepository)

def get_settings_repository() -> ISettingsRepository:
    """Get settings repository instance"""
    return di_config.get_service(ISettingsRepository)

def get_profile_repository() -> IProfileRepository:
    """Get profile repository instance"""
    return di_config.get_service(IProfileRepository)

def get_statistics_repository() -> IStatisticsRepository:
    """Get statistics repository instance"""
    return di_config.get_service(IStatisticsRepository)