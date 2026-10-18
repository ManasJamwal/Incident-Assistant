# Incident Post-Mortem: INC-2025-033 - Redis Session Connection Spike & Connection Refused

**Incident ID**: INC-2025-033  
**Date**: 2025-02-18  
**Duration**: 19 minutes  
**Severity**: P2  
**Impacted Services**: `auth_service.redis_session`, `redis-cluster`  
**Root Cause**: Unpooled Redis client initialization in session validation hot path exhausted max clients.

## Summary
At 19:40 UTC, during an email marketing campaign blast, `refresh_session_cache` created raw TCP connections per incoming HTTP request instead of reusing `REDIS_POOL_MAX_CONNECTIONS`. Redis reached its `maxclients 10000` limit, resulting in `ConnectionRefusedError: [Errno 111] Connection refused` across all auth pods.

## Timeline
- 19:42 UTC - Redis alert `connected_clients > 9800`.
- 19:46 UTC - Clients experiencing connection drops and 500 errors.
- 19:51 UTC - Redis `maxclients` raised to 30000; pooled connection singleton deployed.

## Remediation & Preventative Actions
1. Enforce strict connection pooling in `RedisSessionManager`.
2. Add Redis client count monitoring alarms at 75% capacity.
