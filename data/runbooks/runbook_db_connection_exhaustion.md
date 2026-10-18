# Runbook: Database Connection Pool Exhaustion (PoolExhaustionError)

**Severity**: P0  
**Affected Components**: Checkout Service (`checkout_service.db_pool`), PostgreSQL, PgBouncer

## 1. Outage Symptoms
- Application logs flooded with `PoolExhaustionError: Timeout waiting for connection from pool size 20`.
- API endpoints hanging until gateway timeout (HTTP 504 / HTTP 500).
- Latency surge on cart checkout and inventory decrement operations.
- Postgres `pg_stat_activity` reveals maximum client connections reached.

## 2. Root Cause Analysis
1. Unindexed slow query holding connections open for > 5000ms.
2. Connection leak in `checkout_flow.py` where exception bypasses `release_connection()`.
3. Application replica scaling exceeded PostgreSQL `max_connections = 200`.

## 3. Immediate Mitigation Steps
1. **Kill Blocking / Idle In Transaction Queries**:
   ```sql
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE state = 'idle in transaction' 
     AND state_change < current_timestamp - INTERVAL '2 minutes';
   ```
2. **Dynamically Bump Pool Size in PgBouncer**:
   ```bash
   kubectl exec -it deploy/pgbouncer -- psql -p 6432 -U pgbouncer -c "SET default_pool_size = 50; RELOAD;"
   ```
3. **Restart Checkout Service Replicas to Clear Leaked Sockets**:
   ```bash
   kubectl rollout restart deployment/checkout-service
   ```
