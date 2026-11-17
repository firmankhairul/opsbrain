# Kubernetes playbooks

Scope: workload debugging, Helm, ArgoCD/GitOps, Karpenter node autoscaling, and pod security on any K8s cluster (EKS/AKS/GKE/CCE/self-managed).

Before any command: `kubectl config current-context` and pass `-n <ns>` explicitly.

## Pod debugging decision tree

| Symptom | First command | Common causes |
|---|---|---|
| CrashLoopBackOff | `kubectl logs <pod> --previous` | Missing config/secret, DB connection, OOM, bad entrypoint |
| OOMKilled | `kubectl describe pod` → check limits | Memory limit too low, JVM `-Xmx` not set, memory leak |
| ImagePullBackOff | `kubectl describe pod` → events | Wrong image/tag, missing imagePullSecrets, registry auth |
| Pending | `kubectl describe pod` → events | Insufficient resources, nodeSelector mismatch, PVC not bound |
| Evicted | `kubectl describe node` → conditions | Node disk/memory pressure, ephemeral-storage exceeded |

### OOMKilled: runtime-specific fixes

| Runtime | Fix |
|---|---|
| Java/JVM | `-Xmx` = 75% of memory limit. limit=1Gi → `-Xmx768m` |
| Node.js | `--max-old-space-size` = 75% of limit. limit=512Mi → `384` |
| Go | `GOMEMLIMIT` = 90% of limit (Go 1.19+). limit=512Mi → `460MiB` |
| Python | No built-in cap; profile with `tracemalloc`. Watch DataFrames. |
| .NET | `DOTNET_GCHeapHardLimit` = 75% of limit (bytes) |

## Service not reachable
1. `kubectl get svc,ep` — check endpoints exist.
2. Empty endpoints → fix selector labels or readiness probe.
3. Port mismatch → `targetPort` must match the container port.
4. NetworkPolicy blocking → `kubectl get networkpolicy`.

## Ingress / 5xx errors
1. `kubectl describe ingress` — rules, annotations, events.
2. `kubectl logs <ingress-controller-pod>` — look for 502/503/504.
3. 502 = backend unreachable. 503 = no backend. 404 = path mismatch (check `pathType`).

## PVC Pending
1. `kubectl describe pvc` → events.
2. "no persistent volumes" → check StorageClass and that the CSI driver is installed.
3. "waiting for first consumer" → `WaitForFirstConsumer` mode; fix pod scheduling first.
4. Zone mismatch → PV and node are in different zones.

## Node NotReady
1. `kubectl describe node` → Conditions (MemoryPressure, DiskPressure, PIDPressure).
2. On the node: `systemctl status kubelet`, `systemctl status containerd`, `df -h`, `free -h`.
3. Recovery (L2): `systemctl restart kubelet`, `crictl rmi --prune`.

## Karpenter / node autoscaling
1. Pending pods → `kubectl describe pod` events for scheduling/provisioning messages.
2. `kubectl get nodepools,nodeclaims` (older releases: `provisioners,machines`) — NodeClaim status and launch errors.
3. `kubectl logs -n <karpenter-ns> -l app.kubernetes.io/name=karpenter` — instance-type/capacity, subnet/SG discovery, IAM errors.
4. NodePool `limits`, requirements (instance families, zones, capacity type) and taints vs pod tolerations/nodeSelector.
5. Disruption/consolidation churn → NodePool `disruption` policy and PodDisruptionBudgets. Changing a shared NodePool in prod is L3.

## Helm
1. `helm history <release>` — revision status (deployed/failed/superseded).
2. `helm rollback <release> <revision>` (L2).
3. `helm get values <release>` vs intended values — identify drift.
4. Hook failures → `kubectl get jobs` for helm hook pods.

## ArgoCD
1. `argocd app get <app>` — sync status (Synced/OutOfSync), health (Healthy/Degraded).
2. `argocd app diff <app>` — live vs desired state.
3. `argocd app rollback <app> <revision>` (L2).
4. Sync errors → check controller logs, RBAC, resource conflicts.

## Security hardening

Mandatory security context:
```yaml
securityContext:
  runAsNonRoot: true
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop: ["ALL"]
```

Pod Security Admission:
- Production namespaces: `restricted`.
- System namespaces: `privileged`.

Network policies: default deny all, then allow explicitly per application.
