"""
Enhanced Error Handling Framework for Futures Trading Log
"""
import time
from enum import Enum
import logging

class CircuitBreakerState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    """Circuit breaker to prevent repeated calls to a failing service"""
    
    def __init__(self, failure_threshold: int, recovery_timeout: int):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED
        self.last_failure_time = 0
        self.logger = logging.getLogger(__name__)

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            self.logger.warning("Circuit breaker opened")

    def record_success(self):
        self.failure_count = 0
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.CLOSED
            self.logger.info("Circuit breaker closed")

    def can_execute(self) -> bool:
        if self.state == CircuitBreakerState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                self.logger.info("Circuit breaker half-opened")
                return True
            else:
                return False
        return True

class DataDownloaderError(Exception):
    """Base exception for data download errors"""
    pass

class RateLimitError(DataDownloaderError):
    """Exception for rate limiting errors"""
    pass

class NetworkError(DataDownloaderError):
    """Exception for network errors"""
    pass

class DataQualityError(DataDownloaderError):
    """Exception for data quality errors"""
    pass

class InvalidSymbolError(DataDownloaderError):
    """Exception for invalid symbols"""
    pass
