"""
Payment Gateway Integration Client
Handles upstream credit card and digital wallet transactions with external gateways.
"""

import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("payment_service")

GATEWAY_CONNECT_TIMEOUT_SEC = 5.0
GATEWAY_READ_TIMEOUT_SEC = 10.0
MAX_IDEMPOTENCY_RETRIES = 3


class GatewayTimeoutError(Exception):
    """Raised when upstream gateway fails with HTTP 502 or HTTP 504 gateway timeout."""
    def __init__(self, message: str = "HTTP 502 Bad Gateway: Upstream payment processor dropped connection", status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class CircuitBreakerOpenException(Exception):
    """Raised when payment gateway circuit breaker enters OPEN state due to failure spikes."""
    pass


def send_upstream_transaction(payload: Dict[str, Any], idempotency_key: str) -> Dict[str, Any]:
    """
    Submits raw payment transaction to third-party processor.
    
    Raises:
        GatewayTimeoutError: If processor returns HTTP 502 or HTTP 504.
        CircuitBreakerOpenException: If upstream error rate > 40%.
    """
    logger.info(f"Dispatching charge to upstream with idempotency_key={idempotency_key}")
    
    # Simulate connection logic that can throw during gateway instability
    raise GatewayTimeoutError("HTTP 502 Bad Gateway: Upstream gateway connection dropped during TLS handshake")


def handle_gateway_timeout(transaction_id: str, attempt: int) -> bool:
    """
    Evaluates retry eligibility when encountering HTTP 502 Bad Gateway or 504 Gateway Timeout.
    """
    if attempt >= MAX_IDEMPOTENCY_RETRIES:
        logger.error(f"Transaction {transaction_id} exceeded max retries. Marking transaction as PENDING_MANUAL_REVIEW.")
        return False
    backoff = 2 ** attempt
    logger.warning(f"Backing off for {backoff} seconds before retrying {transaction_id}")
    time.sleep(backoff)
    return True
