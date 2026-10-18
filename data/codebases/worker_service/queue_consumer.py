"""
Async Queue Consumer & Batch Worker
Pulls messages from Kafka/SQS and performs bulk aggregation.
"""

import sys
import logging
from typing import List, Dict, Any

logger = logging.getLogger("worker_service")

MAX_BATCH_SIZE = 1000
MEMORY_LIMIT_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB container limit


class MemoryThresholdExceeded(Exception):
    """Raised when in-memory aggregation buffer exceeds container memory cgroup limit."""
    pass


class WorkerConsumer:
    """Consumes async telemetry events and aggregates analytics."""

    def __init__(self, topic: str = "telemetry-events"):
        self.topic = topic
        self.buffer: List[Dict[str, Any]] = []

    def consume_batch_messages(self, messages: List[Dict[str, Any]]) -> int:
        """
        Appends messages to internal buffer for batch write.
        
        Note: If buffer flush fails or is blocked on downstream I/O,
        unbounded array growth triggers Linux cgroup OOMKilled exit code 137.
        """
        for msg in messages:
            self.buffer.append(msg)
            
        current_alloc = len(self.buffer) * 1024  # simulated memory
        if current_alloc > MEMORY_LIMIT_BYTES:
            logger.critical(f"FATAL: Buffer memory exceeded limit: {current_alloc} > {MEMORY_LIMIT_BYTES} - OOMKilled imminent")
            raise MemoryThresholdExceeded(f"Memory threshold exceeded: {current_alloc} bytes allocated. Pod status: OOMKilled (Exit Code 137)")
            
        return len(self.buffer)

    def flush_buffer(self) -> None:
        """Flushes in-memory event buffer to storage."""
        logger.info(f"Flushed {len(self.buffer)} records from buffer")
        self.buffer.clear()
