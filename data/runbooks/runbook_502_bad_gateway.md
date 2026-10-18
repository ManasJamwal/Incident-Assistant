# Runbook: Upstream HTTP 502 Bad Gateway Triage & Remediation

**Severity**: P0 / P1  
**Affected Components**: API Gateway, Payment Processor Client (`payment_service.client`), Nginx Ingress

## 1. Outage Symptoms
- Sudden spike in 502 Bad Gateway HTTP status codes returned to clients.
- Error logs displaying `GatewayTimeoutError: HTTP 502 Bad Gateway: Upstream payment processor dropped connection`.
- Upstream latency metrics (p99) exceeding 10,000ms followed by TCP RST packets.

## 2. Root Cause Analysis
1. Upstream payment partner experiencing latency degradation or cold restart.
2. Ingress timeout (`proxy_read_timeout`) shorter than downstream payment processing window.
3. Keep-alive connection pooling holding stale sockets that were terminated on upstream NAT.

## 3. Emergency Mitigation Steps
1. **Enable Circuit Breaker Fallback**:
   ```bash
   curl -X POST https://admin.internal/api/flags/payment_circuit_breaker -d '{"state": "FORCED_OPEN_WITH_DEFERRED_QUEUE"}'
   ```
2. **Failover to Secondary Gateway**:
   Update environment variable `PAYMENT_GATEWAY_UPSTREAM_URL` to point to backup provider endpoint:
   ```bash
   kubectl set env deployment/payment-service UPSTREAM_PROVIDER=ADYEN_FALLBACK
   kubectl rollout status deployment/payment-service
   ```
3. **Verify Upstream Connectivity**:
   ```bash
   kubectl exec -it deploy/payment-service -- curl -I -v https://api.upstream-gateway.com/healthz
   ```
