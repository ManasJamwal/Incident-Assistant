# Runbook: Authentication Token Rejection & NTP Clock Skew

**Severity**: P0  
**Affected Components**: Auth Service (`auth_service.token_validator`), Edge API Gateway, Identity Provider

## 1. Outage Symptoms
- Clients receiving mass HTTP 401 Unauthorized errors across all protected API routes.
- Error logs displaying `TokenExpiredError: Token signature expired or NTP time skew exceeded threshold`.
- Valid user sessions suddenly kicked out to login page.

## 2. Root Cause Analysis
1. NTP daemon (`chrony` or `systemd-timesyncd`) drifted by > 15 seconds across Kubernetes worker nodes.
2. Token issued by gateway has `nbf` (not before) or `iat` (issued at) in the future relative to auth service node clock.
3. Strict `ALLOWED_CLOCK_SKEW_SECONDS` threshold in `validate_jwt_token`.

## 3. Immediate Mitigation Steps
1. **Force NTP Sync on Worker Nodes**:
   ```bash
   sudo chronyc makestep
   sudo systemctl restart chronyd
   ```
2. **Increase Allowed Clock Skew Tolerance**:
   Temporarily override `ALLOWED_CLOCK_SKEW_SECONDS=120` in auth service deployment:
   ```bash
   kubectl set env deployment/auth-service ALLOWED_CLOCK_SKEW_SECONDS=120
   kubectl rollout status deployment/auth-service
   ```
