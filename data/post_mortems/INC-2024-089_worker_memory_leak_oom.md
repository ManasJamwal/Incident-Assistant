# Incident Post-Mortem: INC-2024-089 - Worker Pod Eviction Storm (OOMKilled Exit Code 137)

**Incident ID**: INC-2024-089  
**Date**: 2024-12-28  
**Duration**: 55 minutes  
**Severity**: P1  
**Impacted Services**: `worker_service.queue_consumer`, `kafka-cluster`  
**Root Cause**: Unbounded memory buffering during downstream data sink degradation.

## Summary
At 03:00 UTC, a batch telemetry ingestion spike caused `WorkerConsumer.consume_batch_messages` to buffer 450,000 JSON events in RAM because the downstream ClickHouse cluster was running table optimizations. Memory grew past the 2 GiB cgroup limit, prompting Linux OOM killer to terminate pods with exit code 137 (`MemoryThresholdExceeded`). Kubernetes entered a CrashLoopBackOff cycle, cascading Kafka partition rebalances.

## Timeline
- 03:12 UTC - Kubernetes emits pod OOMKilled events for 12 worker replicas.
- 03:18 UTC - Kafka consumer group lag jumped to 1.8M messages.
- 03:30 UTC - SRE increased worker pod memory limits from 2Gi to 6Gi.
- 03:45 UTC - Patched worker batch configuration to cap maximum buffer length to 5,000 items.

## Remediation & Preventative Actions
1. Implement bounded memory queue with backpressure instead of raw Python lists.
2. Configure pod memory alerts at 80% utilization before kernel OOM killer triggers.
