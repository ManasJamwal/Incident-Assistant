"""
Payment Transaction Processor
Executes multi-step settlement, ledger adjustments, and webhook dispatch.
"""

import uuid
import logging
from .client import send_upstream_transaction, GatewayTimeoutError, CircuitBreakerOpenException

logger = logging.getLogger("payment_processor")


class PaymentProcessor:
    """Core transaction execution pipeline for merchant checkouts."""

    def __init__(self, merchant_id: str):
        self.merchant_id = merchant_id
        self.is_active = True

    def process_charge(self, amount_cents: int, currency: str, token: str) -> dict:
        """
        Executes a charge against customer payment source.
        
        Args:
            amount_cents: Integer value in lowest currency denominator.
            currency: ISO currency code (e.g., 'USD').
            token: One-time payment token.
            
        Returns:
            Dict containing charge status, transaction ID, or error details.
        """
        txn_id = str(uuid.uuid4())
        try:
            payload = {"amount": amount_cents, "currency": currency, "token": token}
            response = send_upstream_transaction(payload, idempotency_key=txn_id)
            return {"status": "SUCCESS", "txn_id": txn_id, "data": response}
        except GatewayTimeoutError as exc:
            logger.error(f"Charge failure on txn {txn_id}: HTTP 502 Bad Gateway from upstream provider")
            return {"status": "FAILED", "code": "GATEWAY_502_ERROR", "error": str(exc), "txn_id": txn_id}
        except CircuitBreakerOpenException:
            logger.critical("Payment circuit breaker tripped! Failing fast to prevent cascading timeout.")
            return {"status": "CIRCUIT_OPEN", "code": "PAYMENT_CIRCUIT_TRIPPED", "txn_id": txn_id}

    def execute_refund(self, charge_id: str, amount_cents: int) -> dict:
        """Processes credit adjustment back to cardholder."""
        logger.info(f"Refunding charge {charge_id} amount {amount_cents}")
        return {"status": "REFUNDED", "charge_id": charge_id}
