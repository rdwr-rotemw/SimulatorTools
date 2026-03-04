"""
IRP Loop Manager Service - Manages background IRP loops for all users.

This service handles:
- Starting/stopping loops for users
- Managing asyncio background tasks
- Storing loop state in MongoDB
- Sending IRP messages at specified intervals
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Dict, Optional, Any

from pymongo.database import Database

from backend.app.models.irp_loop import IRPLoopConfig, IRPLoopStatus
from backend.app.modules.reporter.irp.irp_module import load_schema_from_mongo, send_irp_message

logger = logging.getLogger("sim-tools.irp-loop-manager")


class IRPLoopManager:
    """
    Manages IRP loops for all users.

    Uses asyncio tasks to run loops in the background, independent of HTTP requests.
    Stores loop state in MongoDB for persistence and status queries.
    """

    def __init__(self, db: Database):
        self.db = db
        self.collection = db["irp_loops"]
        # Track running tasks: user_id -> asyncio.Task
        self._running_tasks: Dict[str, asyncio.Task] = {}
        # Track stop events: user_id -> asyncio.Event
        self._stop_events: Dict[str, asyncio.Event] = {}
        # Dedicated thread pool for loop sends — keeps main thread pool free for API requests
        self._executor = ThreadPoolExecutor(max_workers=64, thread_name_prefix="irp-loop")

    async def initialize(self):
        """Initialize the manager - restore active loops from database."""
        try:
            # Find all active loops from database (use asyncio.to_thread for blocking call)
            active_loops = await asyncio.to_thread(
                lambda: list(self.collection.find({"is_active": True}))
            )

            logger.info(f"Found {len(active_loops)} active IRP loops in database")

            for loop_doc in active_loops:
                config = IRPLoopConfig(**loop_doc)

                # Check if loop has expired
                if config.start_time:
                    elapsed = (datetime.now(timezone.utc) - config.start_time.replace(tzinfo=timezone.utc)).total_seconds()
                    if elapsed >= config.loop_timeout:
                        # Loop expired, mark as inactive
                        logger.info(f"IRP loop for user {config.user_id} expired, marking as inactive")
                        await asyncio.to_thread(
                            self.collection.update_one,
                            {"user_id": config.user_id},
                            {"$set": {"is_active": False, "updated_at": datetime.now()}}
                        )
                        continue

                # Restore the loop
                logger.info(f"Restoring IRP loop for user {config.user_id}")
                await self._start_loop_task(config)

        except Exception as e:
            logger.error(f"Error initializing IRP loop manager: {e}", exc_info=True)

    async def shutdown(self):
        """Shutdown the manager - cancel all running tasks (but keep state in DB)."""
        logger.info("Shutting down IRP loop manager")

        # Cancel all running tasks
        for user_id, task in list(self._running_tasks.items()):
            logger.info(f"Cancelling IRP loop task for user {user_id}")
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._running_tasks.clear()
        self._stop_events.clear()
        self._executor.shutdown(wait=False)

    async def start_loop(self, user_id: str, config: IRPLoopConfig) -> None:
        """
        Start a new IRP loop for the user.

        Args:
            user_id: User ID (username)
            config: Loop configuration

        Raises:
            ValueError: If loop is already running for this user
        """
        # Check if loop already running
        if user_id in self._running_tasks:
            raise ValueError(f"IRP loop already running for user {user_id}")

        # Store config in database
        config.is_active = True
        config.start_time = datetime.now(timezone.utc)
        config.batches_sent = 0
        config.failed_batches = 0
        config.messages_sent = 0
        config.failed_messages = 0
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

        logger.info(f"Started IRP loop for user {user_id}")

    async def stop_loop(self, user_id: str) -> None:
        """
        Stop the IRP loop for the user.

        Args:
            user_id: User ID (username)

        Raises:
            ValueError: If no loop is running for this user
        """
        if user_id not in self._running_tasks:
            raise ValueError(f"No IRP loop running for user {user_id}")

        # Signal the task to stop
        if user_id in self._stop_events:
            self._stop_events[user_id].set()

        # Update database
        await asyncio.to_thread(
            self.collection.update_one,
            {"user_id": user_id},
            {"$set": {"is_active": False, "updated_at": datetime.now()}}
        )

        logger.info(f"Stopped IRP loop for user {user_id}")

    async def get_status(self, user_id: str) -> IRPLoopStatus:
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
            return IRPLoopStatus(
                is_active=False,
                batches_sent=0,
                elapsed_seconds=0,
                remaining_seconds=0
            )

        config = IRPLoopConfig(**loop_doc)

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

        return IRPLoopStatus(
            is_active=config.is_active,
            loop_delay=config.loop_delay,
            loop_timeout=config.loop_timeout,
            start_time=config.start_time,
            batches_sent=config.batches_sent,
            failed_batches=config.failed_batches,
            messages_sent=config.messages_sent,
            failed_messages=config.failed_messages,
            last_error=config.last_error,
            elapsed_seconds=elapsed_seconds,
            remaining_seconds=remaining_seconds,
            simulator=config.simulator,
            simulators=config.simulators,
            destination_port=config.destination_port
        )

    async def _start_loop_task(self, config: IRPLoopConfig) -> None:
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
            logger.info(f"IRP loop task cancelled for user {user_id}")
        elif task.exception():
            logger.error(f"IRP loop task failed for user {user_id}: {task.exception()}", exc_info=task.exception())
        else:
            logger.info(f"IRP loop task completed normally for user {user_id}")

    async def _loop_executor(self, config: IRPLoopConfig, stop_event: asyncio.Event) -> None:
        """
        Execute the IRP loop - sends messages at specified intervals until timeout or stop.

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

            logger.info(f"IRP loop executor started for user {user_id}, will run for {config.loop_timeout}s")

            # Send first batch immediately
            await self._send_batch(config, stop_event)

            # Loop until timeout or stopped
            while True:
                # Check if we should stop
                if stop_event.is_set():
                    logger.info(f"IRP loop stopped by user request for {user_id}")
                    break

                # Check if timeout reached
                if datetime.now(timezone.utc).timestamp() >= end_time:
                    logger.info(f"IRP loop timeout reached for {user_id}")
                    break

                # Wait for loop_delay seconds (or until stopped)
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=config.loop_delay)
                    # If we get here, stop was signaled
                    logger.info(f"IRP loop stopped during delay for {user_id}")
                    break
                except asyncio.TimeoutError:
                    # Timeout reached, continue with next send
                    pass

                # Send next batch
                await self._send_batch(config, stop_event)

        except asyncio.CancelledError:
            logger.info(f"IRP loop task cancelled for {user_id}")
            raise
        except Exception as e:
            logger.error(f"Error in IRP loop executor for {user_id}: {e}", exc_info=True)
        finally:
            # Mark as inactive in database (use dedicated pool)
            await asyncio.get_event_loop().run_in_executor(
                self._executor,
                self.collection.update_one,
                {"user_id": user_id},
                {"$set": {"is_active": False, "updated_at": datetime.now()}}
            )

    async def _send_batch(self, config: IRPLoopConfig, stop_event: asyncio.Event) -> None:
        """
        Send one batch of IRP messages to all simulators.
        Sends messages one at a time so the stop event can interrupt mid-batch.

        Args:
            config: Loop configuration
            stop_event: Event to check between messages for early abort
        """
        loop = asyncio.get_event_loop()
        try:
            # Load schema from MongoDB (on dedicated pool)
            schema_obj = await loop.run_in_executor(
                self._executor,
                load_schema_from_mongo,
                self.db,
                config.schema_id
            )

            error_messages = []

            # Send to all simulators in parallel, but within each simulator
            # send messages one at a time so stop_event can interrupt
            async def send_to_simulator(simulator_ip: str):
                sim_messages = config.messages
                if config.per_simulator_messages and simulator_ip in config.per_simulator_messages:
                    sim_messages = config.per_simulator_messages[simulator_ip]

                results: Dict[str, Any] = {}
                for message in sim_messages:
                    if stop_event.is_set():
                        break
                    name = message['message']
                    cleaned = {k: v for k, v in message.items() if k not in ('message', 'pause')}
                    ok, msg = await loop.run_in_executor(
                        self._executor,
                        send_irp_message, schema_obj, name, cleaned,
                        simulator_ip, config.destination_port
                    )
                    results[name] = (ok, msg)
                    # Update DB immediately per message so status reflects real-time progress
                    if ok:
                        await loop.run_in_executor(
                            self._executor,
                            self.collection.update_one,
                            {"user_id": config.user_id},
                            {"$inc": {"messages_sent": 1}}
                        )
                        config.messages_sent += 1
                    else:
                        await loop.run_in_executor(
                            self._executor,
                            self.collection.update_one,
                            {"user_id": config.user_id},
                            {"$inc": {"failed_messages": 1}}
                        )
                        config.failed_messages += 1
                    if not stop_event.is_set():
                        await asyncio.sleep(0.1)

                return simulator_ip, results

            sim_results = await asyncio.gather(
                *[send_to_simulator(sim_ip) for sim_ip in config.simulators],
                return_exceptions=True,
            )

            # If stopped mid-batch, don't count it
            if stop_event.is_set():
                return

            # Check for errors (message counts already updated per-message above)
            has_failures = False
            for result in sim_results:
                if isinstance(result, Exception):
                    has_failures = True
                    error_messages.append(str(result))
                else:
                    simulator_ip, results = result
                    if isinstance(results, dict):
                        for message_name, (success, msg) in results.items():
                            if not success:
                                has_failures = True
                                error_messages.append(f"{simulator_ip}/{message_name}: {msg}")

            if has_failures:
                error_msg = "; ".join(error_messages)
                logger.error(f"IRP batch failed for user {config.user_id}: {error_msg}")

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
            else:
                await loop.run_in_executor(
                    self._executor,
                    self.collection.update_one,
                    {"user_id": config.user_id},
                    {
                        "$inc": {"batches_sent": 1},
                        "$set": {"updated_at": datetime.now(), "last_error": None}
                    }
                )

                config.batches_sent += 1
                config.last_error = None
                logger.debug(f"Sent IRP batch #{config.batches_sent} ({config.messages_sent} total msgs) for user {config.user_id}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error sending IRP batch for user {config.user_id}: {e}", exc_info=True)

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


# Global instance (will be initialized in main.py)
_irp_loop_manager: Optional[IRPLoopManager] = None


def get_irp_loop_manager() -> IRPLoopManager:
    """Get the global IRP loop manager instance."""
    if _irp_loop_manager is None:
        raise RuntimeError("IRPLoopManager not initialized")
    return _irp_loop_manager


async def initialize_irp_loop_manager(db: Database) -> IRPLoopManager:
    """Initialize the global IRP loop manager."""
    global _irp_loop_manager
    _irp_loop_manager = IRPLoopManager(db)
    await _irp_loop_manager.initialize()
    return _irp_loop_manager


async def shutdown_irp_loop_manager() -> None:
    """Shutdown the global IRP loop manager."""
    global _irp_loop_manager
    if _irp_loop_manager:
        await _irp_loop_manager.shutdown()
        _irp_loop_manager = None
