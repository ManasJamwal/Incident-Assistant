# Runbook: Cascading Circuit Breaker Trips & System Recovery

**Severity**: P1  
**Affected Components**: Payment Service, Upstream Integration, Resiliency Mesh

## 1. Outage Symptoms
- Log alarms with `CircuitBreakerOpenException: Payment circuit breaker tripped! Failing fast to prevent cascading timeout`.
- Downstream callers immediately receive fast-fail errors without network calls reaching upstream.
- Zero network traffic observed on payment outbound NAT gateway.

## 2. Root Cause Analysis
1. A brief transient outage from third-party vendor pushed error rate over 40% window.
2. Half-open state probe requests timed out, keeping the breaker locked OPEN.

## 3. Immediate Mitigation Steps
1. **Force Circuit Breaker Reset**:
   ```bash
   redis-cli -h redis-cluster.internal DEL circuit_breaker:payment_gateway:state
   ```
2. **Verify Third-Party Gateway Status Page**:
   Check upstream partner API status and ping latency before closing circuit.
