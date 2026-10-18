# Incident Post-Mortem: INC-2024-001 - Black Friday Checkout DB Connection Exhaustion

**Incident ID**: INC-2024-001  
**Date**: 2024-11-29  
**Duration**: 42 minutes  
**Severity**: P0  
**Impacted Services**: `checkout_service`, `order_api`, `postgresql-primary`  
**Root Cause**: Unbounded checkout concurrency saturated PostgreSQL connection pool in `db_pool.py`.

## Summary
During the Black Friday peak flash sale, checkout throughput increased from 400 RPS to 3,800 RPS. The connection pool in `DatabaseConnectionPool` was capped at `MAX_POOL_SIZE = 20`, while thread concurrency spiked. Applications began raising `PoolExhaustionError: Timeout waiting for connection from pool size 20`. Incoming HTTP checkout requests blocked until timing out at the edge proxy (504 Gateway Timeout).

## Timeline
- 10:02 UTC - Traffic ramp begins.
- 10:06 UTC - Error rate on checkout endpoint increases to 18%.
- 10:09 UTC - On-call paged on `CheckoutServiceHighErrorRate`.
- 10:14 UTC - Diagnosed `PoolExhaustionError` via log query in Datadog.
- 10:22 UTC - PgBouncer connection pool limit increased from 20 to 100 connections.
- 10:28 UTC - Pods restarted; pool contention subsided; error rate dropped to 0%.

## Remediation & Preventative Actions
1. Deploy PgBouncer in transaction pooling mode.
2. Add connection acquisition latency metric `db_pool_acquire_duration_seconds`.
3. Set aggressive `statement_timeout` to prevent slow queries holding connections.
