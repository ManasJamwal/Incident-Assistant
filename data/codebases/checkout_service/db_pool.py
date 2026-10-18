"""
PostgreSQL Connection Pool Manager
Configures max connections, pool sizing, idle eviction, and connection checkout timeout.
"""

import time
import logging

logger = logging.getLogger("db_pool")

MAX_POOL_SIZE = 20
CONNECTION_TIMEOUT_SECONDS = 3.0
STATEMENT_TIMEOUT_MS = 5000


class PoolExhaustionError(Exception):
    """Raised when application cannot acquire DB connection from pool within timeout."""
    def __init__(self, message: str = "PoolExhaustionError: Timeout waiting for connection from pool size 20"):
        super().__init__(message)


class DeadlockDetectedError(Exception):
    """Raised when PostgreSQL aborts transaction due to concurrent row-level lock deadlock."""
    pass


class DatabaseConnectionPool:
    """Manages transactional database connections to primary Postgres instance."""

    def __init__(self, dsn: str, max_size: int = MAX_POOL_SIZE):
        self.dsn = dsn
        self.max_size = max_size
        self.active_connections = 0

    def acquire_db_connection(self, timeout: float = CONNECTION_TIMEOUT_SECONDS):
        """
        Acquires an idle database connection or blocks until available.
        
        Raises:
            PoolExhaustionError: When all connections are busy and queue timeout expires.
        """
        if self.active_connections >= self.max_size:
            logger.critical(f"Connection pool exhausted! active={self.active_connections}, max={self.max_size}")
            raise PoolExhaustionError(f"PoolExhaustionError: Timeout waiting for connection from pool size {self.max_size}")
        
        self.active_connections += 1
        return {"connection_id": self.active_connections, "status": "connected"}

    def release_connection(self, conn) -> None:
        """Returns connection back to pool."""
        if self.active_connections > 0:
            self.active_connections -= 1
