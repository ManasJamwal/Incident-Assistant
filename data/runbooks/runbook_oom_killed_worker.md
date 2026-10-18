# Runbook: Kubernetes OOMKilled Pod Eviction (Exit Code 137)

**Severity**: P1  
**Affected Components**: Worker Service (`worker_service.queue_consumer`), Celery / Kafka Consumer Pods

## 1. Outage Symptoms
- Pods terminating with `Last State: Terminated, Reason: OOMKilled, Exit Code: 137`.
- `MemoryThresholdExceeded: Memory threshold exceeded. Pod status: OOMKilled (Exit Code 137)`.
- Sudden spike in consumer group lag on Kafka topic `telemetry-events`.
- Frequent CrashLoopBackOff on consumer workers.

## 2. Root Cause Analysis
1. Unbounded buffer accumulation in `WorkerConsumer.consume_batch_messages` due to downstream write stalls.
2. Ingestion of unexpectedly large payloads causing JSON serialization memory explosion.
3. Memory leak in Python C-extensions or circular references not freed by garbage collection.

## 3. Immediate Mitigation Steps
1. **Temporarily Bump Container Memory Limits**:
   ```bash
   kubectl set resources deployment worker-service --limits=memory=4Gi --requests=memory=2Gi
   ```
2. **Throttle Batch Ingestion Rate**:
   Update `MAX_BATCH_SIZE` from 1000 to 250 via ConfigMap:
   ```bash
   kubectl patch configmap worker-config --type merge -p '{"data":{"MAX_BATCH_SIZE":"250"}}'
   kubectl rollout restart deployment worker-service
   ```
3. **Inspect Top Memory Consuming Namespaces**:
   ```bash
   kubectl top pods -n production --sort-by=memory
   ```
