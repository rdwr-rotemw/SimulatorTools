import threading
from contextlib import contextmanager

from fastapi import HTTPException, status

from backend.app.utils.logger import logger

# Lock acquisition timeout in seconds (10 minutes)
DEFAULT_LOCK_TIMEOUT_SECONDS = 600


class SimulatorLockManager:
    """Global exclusive lock manager for simulator database synchronization.

    Prevents concurrent upsert/cleanup operations on the simulators table
    to avoid PostgreSQL deadlocks when multiple requests try to sync simulators
    from Sapro simultaneously.
    """

    def __init__(self):
        self._lock = threading.Lock()

    @contextmanager
    def lock(self, timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS):
        """Acquire an exclusive lock on the simulator sync operation (context manager).

        Usage::

            with simulator_lock_mgr.lock():
                # Upsert simulators to DB
                db.execute(stmt)
                db.commit()
        """
        acquired = self._lock.acquire(timeout=timeout)
        if not acquired:
            logger.error("Failed to acquire simulator lock within %ss", timeout)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Simulator sync is currently in progress. Try again later.",
            )
        try:
            logger.debug("Acquired simulator sync lock")
            yield
        finally:
            self._lock.release()
            logger.debug("Released simulator sync lock")


# Module-level singleton
_simulator_lock_manager: SimulatorLockManager = SimulatorLockManager()


def get_simulator_lock_manager() -> SimulatorLockManager:
    """Return the singleton SimulatorLockManager instance."""
    return _simulator_lock_manager
