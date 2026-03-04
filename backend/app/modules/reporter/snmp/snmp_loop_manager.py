"""
SNMP Loop Manager Service - Manages background SNMP loops for all users.

This service handles:
- Starting/stopping loops for users
- Managing asyncio background tasks
- Storing loop state in MongoDB
- Sending SNMP traps at specified intervals
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Dict, Optional, Any
import random

from pymongo.database import Database

from backend.app.models.snmp_loop import SNMPLoopConfig, SNMPLoopStatus
from backend.app.modules.reporter.snmp.attack_traps import send_attack_traps

logger = logging.getLogger("sim-tools.snmp-loop-manager")


class SNMPLoopManager:
    """
    Manages SNMP loops for all users.

    Uses asyncio tasks to run loops in the background, independent of HTTP requests.
    Stores loop state in MongoDB for persistence and status queries.
    """

    def __init__(self, db: Database):
        self.db = db
        self.collection = db["snmp_loops"]
        # Track running tasks: user_id -> asyncio.Task
        self._running_tasks: Dict[str, asyncio.Task] = {}
        # Track stop events: user_id -> asyncio.Event
        self._stop_events: Dict[str, asyncio.Event] = {}
        # Dedicated thread pool for loop sends — keeps main thread pool free for API requests
        self._executor = ThreadPoolExecutor(max_workers=64, thread_name_prefix="snmp-loop")

    async def initialize(self):
        """Initialize the manager - restore active loops from database."""
        try:
            # Find all active loops from database (use asyncio.to_thread for blocking call)
            active_loops = await asyncio.to_thread(
                lambda: list(self.collection.find({"is_active": True}))
            )

            logger.info(f"Found {len(active_loops)} active loops in database")

            for loop_doc in active_loops:
                config = SNMPLoopConfig(**loop_doc)

                # Check if loop has expired
                if config.start_time:
                    elapsed = (datetime.now(timezone.utc) - config.start_time.replace(tzinfo=timezone.utc)).total_seconds()
                    if elapsed >= config.loop_timeout:
                        # Loop expired, mark as inactive
                        logger.info(f"Loop for user {config.user_id} expired, marking as inactive")
                        await asyncio.to_thread(
                            self.collection.update_one,
                            {"user_id": config.user_id},
                            {"$set": {"is_active": False, "updated_at": datetime.now()}}
                        )
                        continue

                # Restore the loop
                logger.info(f"Restoring loop for user {config.user_id}")
                await self._start_loop_task(config)

        except Exception as e:
            logger.error(f"Error initializing SNMP loop manager: {e}", exc_info=True)

    async def shutdown(self):
        """Shutdown the manager - cancel all running tasks (but keep state in DB)."""
        logger.info("Shutting down SNMP loop manager")

        # Cancel all running tasks
        for user_id, task in list(self._running_tasks.items()):
            logger.info(f"Cancelling loop task for user {user_id}")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._running_tasks.clear()
        self._stop_events.clear()
        self._executor.shutdown(wait=False)

    async def start_loop(self, user_id: str, config: SNMPLoopConfig) -> None:
        """
        Start a new SNMP loop for the user.

        Args:
            user_id: User ID (username)
            config: Loop configuration

        Raises:
            ValueError: If loop is already running for this user
        """
        # Check if loop already running
        if user_id in self._running_tasks:
            raise ValueError(f"Loop already running for user {user_id}")

        # Store config in database
        config.is_active = True
        config.start_time = datetime.now(timezone.utc)
        config.batches_sent = 0
        config.failed_batches = 0
        config.traps_sent = 0
        config.failed_traps = 0
        config.last_error = None
        config.created_at = datetime.now()
        config.updated_at = datetime.now()

        await asyncio.to_thread(
            self.collection.replace_one,
            {"user_id": user_id},
            config.dict(),
            upsert=True
        )

        # Start the background task
        await self._start_loop_task(config)

        logger.info(f"Started SNMP loop for user {user_id}")

    async def stop_loop(self, user_id: str) -> None:
        """
        Stop the SNMP loop for the user.

        Args:
            user_id: User ID (username)

        Raises:
            ValueError: If no loop is running for this user
        """
        if user_id not in self._running_tasks:
            raise ValueError(f"No loop running for user {user_id}")

        # Signal the task to stop
        if user_id in self._stop_events:
            self._stop_events[user_id].set()

        # Update database
        await asyncio.to_thread(
            self.collection.update_one,
            {"user_id": user_id},
            {"$set": {"is_active": False, "updated_at": datetime.now()}}
        )

        logger.info(f"Stopped SNMP loop for user {user_id}")

    async def get_status(self, user_id: str) -> SNMPLoopStatus:
        """
        Get the current loop status for the user.

        Args:
            user_id: User ID (username)

        Returns:
            Loop status
        """
        # Fetch from database
        loop_doc = await asyncio.to_thread(
            self.collection.find_one,
            {"user_id": user_id}
        )

        if not loop_doc:
            # No loop config found
            return SNMPLoopStatus(
                is_active=False,
                batches_sent=0,
                elapsed_seconds=0,
                remaining_seconds=0,
                simulators=[]
            )

        config = SNMPLoopConfig(**loop_doc)

        # Calculate elapsed and remaining time
        elapsed_seconds = 0
        remaining_seconds = config.loop_timeout if config.loop_timeout else 0

        if config.start_time:
            elapsed_seconds = int((datetime.now(timezone.utc) - config.start_time.replace(tzinfo=timezone.utc)).total_seconds())
            if config.is_active:
                remaining_seconds = max(0, config.loop_timeout - elapsed_seconds)
            else:
                elapsed_seconds = min(elapsed_seconds, config.loop_timeout)
                remaining_seconds = 0

        return SNMPLoopStatus(
            is_active=config.is_active,
            loop_delay=config.loop_delay,
            loop_timeout=config.loop_timeout,
            start_time=config.start_time,
            batches_sent=config.batches_sent,
            failed_batches=config.failed_batches,
            traps_sent=config.traps_sent,
            failed_traps=config.failed_traps,
            last_error=config.last_error,
            elapsed_seconds=elapsed_seconds,
            remaining_seconds=remaining_seconds,
            simulators=config.simulators,
            destination_port=config.destination_port
        )

    async def _start_loop_task(self, config: SNMPLoopConfig) -> None:
        """Create and start the background task for the loop."""
        user_id = config.user_id

        # Create stop event
        stop_event = asyncio.Event()
        self._stop_events[user_id] = stop_event

        # Create and start task
        task = asyncio.create_task(self._loop_executor(config, stop_event))
        self._running_tasks[user_id] = task

        # Add done callback to cleanup
        task.add_done_callback(lambda t: self._task_done_callback(user_id, t))

    def _task_done_callback(self, user_id: str, task: asyncio.Task):
        """Callback when task completes or is cancelled."""
        # Clean up
        self._running_tasks.pop(user_id, None)
        self._stop_events.pop(user_id, None)

        if task.cancelled():
            logger.info(f"Loop task cancelled for user {user_id}")
        elif task.exception():
            logger.error(f"Loop task failed for user {user_id}: {task.exception()}", exc_info=task.exception())
        else:
            logger.info(f"Loop task completed normally for user {user_id}")

    async def _loop_executor(self, config: SNMPLoopConfig, stop_event: asyncio.Event) -> None:
        """
        Execute the SNMP loop - sends traps at specified intervals until timeout or stop.

        Args:
            config: Loop configuration
            stop_event: Event to signal when to stop the loop
        """
        user_id = config.user_id

        try:
            # Calculate end time
            if not config.start_time:
                config.start_time = datetime.now(timezone.utc)

            end_time = config.start_time.replace(tzinfo=timezone.utc).timestamp() + config.loop_timeout

            logger.info(f"Loop executor started for user {user_id}, will run for {config.loop_timeout}s")

            # Send first batch immediately
            await self._send_batch(config)

            # Loop until timeout or stopped
            while True:
                # Check if we should stop
                if stop_event.is_set():
                    logger.info(f"Loop stopped by user request for {user_id}")
                    break

                # Check if timeout reached
                if datetime.now(timezone.utc).timestamp() >= end_time:
                    logger.info(f"Loop timeout reached for {user_id}")
                    break

                # Wait for loop_delay seconds (or until stopped)
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=config.loop_delay)
                    # If we get here, stop was signaled
                    logger.info(f"Loop stopped during delay for {user_id}")
                    break
                except asyncio.TimeoutError:
                    # Timeout reached, continue with next send
                    pass

                # Send next batch
                await self._send_batch(config)

        except asyncio.CancelledError:
            logger.info(f"Loop task cancelled for {user_id}")
            raise
        except Exception as e:
            logger.error(f"Error in loop executor for {user_id}: {e}", exc_info=True)
        finally:
            # Mark as inactive in database (use dedicated pool)
            await asyncio.get_event_loop().run_in_executor(
                self._executor,
                self.collection.update_one,
                {"user_id": user_id},
                {"$set": {"is_active": False, "updated_at": datetime.now()}}
            )

    async def _send_batch(self, config: SNMPLoopConfig) -> None:
        """
        Send one batch of SNMP traps.

        Args:
            config: Loop configuration
        """
        loop = asyncio.get_event_loop()
        try:
            # Send to all simulators in parallel
            error_messages = []

            async def send_to_simulator(simulator_ip: str):
                map_name = config.simulator_maps.get(simulator_ip)
                if not map_name:
                    error_msg = f"No map found for simulator {simulator_ip}"
                    logger.error(error_msg)
                    return 0, 0, error_msg

                # Prepare traps with attack IDs if needed
                traps_to_send = [dict(t) for t in config.traps]  # Deep copy each trap

                if config.configured_attack_ids and simulator_ip in config.configured_attack_ids:
                    for index, trap in enumerate(traps_to_send):
                        if config.regenerate_attack_id:
                            trap["attackId"] = self._generate_random_attack_id()
                        else:
                            trap["attackId"] = config.configured_attack_ids[simulator_ip][index]
                elif config.regenerate_attack_id:
                    for trap in traps_to_send:
                        trap["attackId"] = self._generate_random_attack_id()

                payload = {
                    "map": map_name,
                    "traps": traps_to_send
                }

                success_count, failed_count, total_count = await loop.run_in_executor(
                    self._executor,
                    send_attack_traps,
                    config.destination_port,
                    simulator_ip,
                    payload
                )

                # Update DB per-simulator for real-time progress
                inc_fields: Dict[str, int] = {}
                if success_count > 0:
                    inc_fields["traps_sent"] = success_count
                    config.traps_sent += success_count
                if failed_count > 0:
                    inc_fields["failed_traps"] = failed_count
                    config.failed_traps += failed_count
                if inc_fields:
                    await loop.run_in_executor(
                        self._executor,
                        self.collection.update_one,
                        {"user_id": config.user_id},
                        {"$inc": inc_fields}
                    )

                error_msg = f"{simulator_ip}: {failed_count}/{total_count} traps failed" if failed_count > 0 else None
                return success_count, failed_count, error_msg

            sim_results = await asyncio.gather(
                *[send_to_simulator(sim_ip) for sim_ip in config.simulators],
                return_exceptions=True,
            )

            total_failed = 0
            for result in sim_results:
                if isinstance(result, Exception):
                    error_messages.append(str(result))
                    total_failed += len(config.traps)
                else:
                    sc, fc, err = result
                    total_failed += fc
                    if err:
                        error_messages.append(err)

            # Batch-end: update batches_sent, failed_batches, last_error
            inc_fields: Dict[str, int] = {"batches_sent": 1}
            if total_failed > 0:
                error_msg = "; ".join(error_messages)
                logger.error(f"SNMP batch had failures for user {config.user_id}: {error_msg}")
                inc_fields["failed_batches"] = 1

                await loop.run_in_executor(
                    self._executor,
                    self.collection.update_one,
                    {"user_id": config.user_id},
                    {
                        "$inc": inc_fields,
                        "$set": {"updated_at": datetime.now(), "last_error": error_msg}
                    }
                )

                config.batches_sent += 1
                config.failed_batches += 1
                config.last_error = error_msg
            else:
                await loop.run_in_executor(
                    self._executor,
                    self.collection.update_one,
                    {"user_id": config.user_id},
                    {
                        "$inc": inc_fields,
                        "$set": {"updated_at": datetime.now(), "last_error": None}
                    }
                )

                config.batches_sent += 1
                config.last_error = None

                logger.debug(f"Sent batch #{config.batches_sent} ({config.traps_sent} total traps) for user {config.user_id}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error sending batch for user {config.user_id}: {e}", exc_info=True)

            await loop.run_in_executor(
                self._executor,
                self.collection.update_one,
                {"user_id": config.user_id},
                {
                    "$inc": {"batches_sent": 1, "failed_batches": 1},
                    "$set": {"updated_at": datetime.now(), "last_error": error_msg}
                }
            )

            config.batches_sent += 1
            config.failed_batches += 1
            config.last_error = error_msg

    @staticmethod
    def _generate_random_attack_id() -> str:
        """Generate a random attack-ID in the format: XXX-XXXXXXXXXX"""
        prefix = random.randint(100, 9999)
        suffix = random.randint(1000000000, 9999999999)
        return f"{prefix}-{suffix}"


# Global instance (will be initialized in main.py)
_loop_manager: Optional[SNMPLoopManager] = None


def get_loop_manager() -> SNMPLoopManager:
    """Get the global loop manager instance."""
    if _loop_manager is None:
        raise RuntimeError("SNMPLoopManager not initialized")
    return _loop_manager


async def initialize_loop_manager(db: Database) -> SNMPLoopManager:
    """Initialize the global loop manager."""
    global _loop_manager
    _loop_manager = SNMPLoopManager(db)
    await _loop_manager.initialize()
    return _loop_manager


async def shutdown_loop_manager() -> None:
    """Shutdown the global loop manager."""
    global _loop_manager
    if _loop_manager:
        await _loop_manager.shutdown()
        _loop_manager = None
