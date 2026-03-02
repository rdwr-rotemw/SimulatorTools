import threading
from contextlib import contextmanager
from typing import Dict, List

from fastapi import HTTPException, status

from backend.app.utils.logger import logger

# Default lock acquisition timeout in seconds (10 minutes)
DEFAULT_LOCK_TIMEOUT_SECONDS = 600


class MapLockManager:
    """Per-map exclusive lock manager for Sapro operations.

    Provides map-level mutual exclusion so that concurrent operations
    on the same map are serialised.  All users share the same locks.
    Operations that cannot acquire the lock within the timeout raise
    HTTP 409 Conflict.
    """

    def __init__(self):
        self._locks: Dict[str, threading.Lock] = {}
        self._guard: threading.Lock = threading.Lock()

    def _get_lock(self, map_name: str) -> threading.Lock:
        """Get or lazily create a lock for *map_name*."""
        with self._guard:
            if map_name not in self._locks:
                self._locks[map_name] = threading.Lock()
            return self._locks[map_name]

    # ------------------------------------------------------------------
    # Context-manager API (for sync route handlers)
    # ------------------------------------------------------------------

    @contextmanager
    def lock(self, map_name: str, timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS):
        """Acquire an exclusive lock on a single map (context manager).

        Usage::

            with lock_mgr.lock("my_map"):
                sapro_handler.create_device(...)
        """
        lk = self._get_lock(map_name)
        acquired = lk.acquire(timeout=timeout)
        if not acquired:
            logger.error("Failed to acquire lock for map '%s' within %ss", map_name, timeout)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Map '{map_name}' is currently locked by another operation. Try again later.",
            )
        try:
            logger.debug("Acquired lock for map '%s'", map_name)
            yield
        finally:
            lk.release()
            logger.debug("Released lock for map '%s'", map_name)

    @contextmanager
    def lock_maps(self, map_names: List[str], timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS):
        """Acquire exclusive locks on *multiple* maps (context manager).

        Locks are acquired in sorted order to prevent deadlocks.
        On timeout for any individual map the already-acquired locks
        are released before the exception propagates.

        Usage::

            with lock_mgr.lock_maps(["map_a", "map_b"]):
                ...
        """
        sorted_maps = sorted(set(map_names))
        acquired: List[threading.Lock] = []
        try:
            for name in sorted_maps:
                lk = self._get_lock(name)
                got = lk.acquire(timeout=timeout)
                if not got:
                    logger.error(
                        "Failed to acquire lock for map '%s' within %ss (multi-lock)", name, timeout
                    )
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Map '{name}' is currently locked by another operation. Try again later.",
                    )
                acquired.append(lk)
                logger.debug("Acquired lock for map '%s' (multi-lock)", name)
            yield
        finally:
            for lk in reversed(acquired):
                lk.release()
            if acquired:
                logger.debug("Released locks for maps: %s", sorted_maps)

    # ------------------------------------------------------------------
    # Manual acquire / release API (for async streaming endpoints)
    # ------------------------------------------------------------------

    def acquire(self, map_name: str, timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS) -> None:
        """Manually acquire a single map lock.  Caller **must** call :meth:`release` in a ``finally`` block."""
        lk = self._get_lock(map_name)
        got = lk.acquire(timeout=timeout)
        if not got:
            logger.error("Failed to acquire lock for map '%s' within %ss", map_name, timeout)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Map '{map_name}' is currently locked by another operation. Try again later.",
            )
        logger.debug("Acquired lock for map '%s' (manual)", map_name)

    def release(self, map_name: str) -> None:
        """Release a previously acquired single map lock."""
        self._get_lock(map_name).release()
        logger.debug("Released lock for map '%s' (manual)", map_name)

    def acquire_maps(self, map_names: List[str], timeout: float = DEFAULT_LOCK_TIMEOUT_SECONDS) -> List[str]:
        """Manually acquire locks for multiple maps in sorted order.

        Returns the sorted, deduplicated list of map names that were locked
        (pass this to :meth:`release_maps` in a ``finally`` block).
        On failure, already-acquired locks are rolled back before the
        exception propagates.
        """
        sorted_maps = sorted(set(map_names))
        acquired: List[str] = []
        try:
            for name in sorted_maps:
                lk = self._get_lock(name)
                got = lk.acquire(timeout=timeout)
                if not got:
                    logger.error(
                        "Failed to acquire lock for map '%s' within %ss (multi-lock manual)", name, timeout
                    )
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Map '{name}' is currently locked by another operation. Try again later.",
                    )
                acquired.append(name)
                logger.debug("Acquired lock for map '%s' (multi-lock manual)", name)
            return acquired
        except Exception:
            # Roll back any locks we already acquired
            for acq_name in reversed(acquired):
                self._get_lock(acq_name).release()
            raise

    def release_maps(self, map_names: List[str]) -> None:
        """Release locks previously acquired via :meth:`acquire_maps`."""
        for name in reversed(map_names):
            self._get_lock(name).release()
        if map_names:
            logger.debug("Released locks for maps: %s (manual)", map_names)


# Module-level singleton
_map_lock_manager: MapLockManager = MapLockManager()


def get_map_lock_manager() -> MapLockManager:
    """Return the singleton MapLockManager instance."""
    return _map_lock_manager
