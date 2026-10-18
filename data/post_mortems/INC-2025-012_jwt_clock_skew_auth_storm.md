# Incident Post-Mortem: INC-2025-012 - Edge NTP Clock Drift Causing Global 401 Auth Storm

**Incident ID**: INC-2025-012  
**Date**: 2025-01-12  
**Duration**: 34 minutes  
**Severity**: P0  
**Impacted Services**: `auth_service.token_validator`, `edge_gateway`  
**Root Cause**: Virtual machine hypervisor clock drift caused NTP offset of +32 seconds, violating `ALLOWED_CLOCK_SKEW_SECONDS`.

## Summary
At 08:20 UTC, AWS cloud hypervisor time sync stalled on the ingress cluster, leaving edge gateways 32 seconds ahead of the auth verification cluster. When clients presented tokens with issued-at (`iat`) and expiration timestamps, `validate_jwt_token` threw `TokenExpiredError: Token signature expired or NTP time skew exceeded threshold`. Over 85,000 active sessions were rejected with HTTP 401.

## Timeline
- 08:21 UTC - Alert fired: `AuthServiceTokenValidationFailureRate > 15%`.
- 08:29 UTC - Confirmed NTP drift discrepancy between edge proxy nodes and auth pods.
- 08:35 UTC - Hot-patched `ALLOWED_CLOCK_SKEW_SECONDS` from 10 to 120 seconds.
- 08:50 UTC - Ran `chronyd` step sync on all VM instances.

## Remediation & Preventative Actions
1. Implement PTP / AWS Time Sync Service daemon monitoring.
2. Alert when node NTP drift exceeds 500 milliseconds.
