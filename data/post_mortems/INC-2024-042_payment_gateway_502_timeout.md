# Incident Post-Mortem: INC-2024-042 - Payment Gateway Upstream 502 Bad Gateway Outage

**Incident ID**: INC-2024-042  
**Date**: 2024-12-14  
**Duration**: 28 minutes  
**Severity**: P1  
**Impacted Services**: `payment_service.client`, `checkout_service`, `payment_gateway`  
**Root Cause**: Upstream payment partner edge CDN suffered DNS routing failures resulting in HTTP 502 Bad Gateway.

## Summary
At 14:15 UTC, payments processing in Europe began failing with `GatewayTimeoutError: HTTP 502 Bad Gateway: Upstream payment processor dropped connection`. `send_upstream_transaction()` received incomplete TLS handshakes from the vendor gateway. Because retry logic in `handle_gateway_timeout` had exponential backoff without jitter, all worker threads blocked waiting on downstream replies.

## Timeline
- 14:15 UTC - Spike in 502 responses from upstream payment processor.
- 14:19 UTC - Automated circuit breaker did not engage due to high error threshold (50%).
- 14:24 UTC - SRE manually flipped feature flag `UPSTREAM_PROVIDER=ADYEN_FALLBACK`.
- 14:31 UTC - Secondary provider traffic reached 100%; payments resumed.

## Remediation & Preventative Actions
1. Lower circuit breaker threshold from 50% to 25% failure rate over 30-second window.
2. Implement automated secondary gateway failover on sustained HTTP 502/504 errors.
