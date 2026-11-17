# Azure playbooks

Scope: Azure troubleshooting playbooks, risk examples, and golden signals via `az` CLI. Pass `--subscription <id>` and scope to the resource group from customer docs.

## Risk examples

- **L1:** `list`, `show`, `get-instance-view`, `monitor metrics`.
- **L2:** `vm start/stop/restart`, `nsg rule create/update`, VM resize, nodepool scale, App Service plan scale, SQL firewall rule update.
- **L3:** `vm delete`, `sql db delete`, `storage account delete`.

Change Proposal fields: Subscription, Resource Group, Action, Target, Why, Risk, Rollback.

## VM unreachable
1. `az vm get-instance-view` (PowerState, ProvisioningState).
2. `az network nsg rule list` + `az network watcher check-ip-flow`.
3. Deallocated: propose `start` (L2). Failed: check Activity Logs.

## High resource utilization
1. `az monitor metrics list` (`Percentage CPU`, `Available Memory`).
2. Check VM size vs workload. Correlate with the Activity Log.
3. Propose resize (L2).

## Azure SQL connectivity
1. `az sql db show` + `az sql server firewall-rule list`.
2. Verify VNet service endpoints or Private Link.
3. Propose firewall rule update (L2) or scaling (L2).

## AKS cluster issues
1. `az aks show` (ProvisioningState) + `az aks nodepool list`.
2. `kubectl get nodes` for Ready/NotReady.
3. Propose nodepool scale or upgrade (L2).

## App Service / Web Apps
1. `az webapp show`: `state`, `availabilityState`.
2. `az webapp deployment slot list` for blue/green.
3. `az webapp log tail` for live logs.
4. `az appservice plan show`: SKU, worker count. Propose scale (L2).

## Storage account
1. `az storage account show`: `allowBlobPublicAccess`, `networkRuleSet`.
2. Check `sku.name` (LRS/GRS/RA-GRS) for redundancy.
3. Verify SAS token expiry, permissions, IP restrictions.

## VNet peering
1. `az network vnet peering list`: `peeringState` (Connected/Disconnected).
2. Verify no overlapping CIDR ranges.
3. Check `allowGatewayTransit` / `useRemoteGateways` for hub-spoke.

## Azure Monitor and alerts
1. `az monitor metrics alert list`: enabled state, thresholds.
2. `az monitor action-group list`: notification targets.
3. `az monitor diagnostic-settings list`: verify logs/metrics destinations.
4. `az monitor log-analytics query`: KQL for deep investigation.

## Key Vault
1. `az keyvault show`: access policies, RBAC.
2. `az keyvault certificate list`: flag certificates expiring in < 30 days.
3. Check secret versions and expiry. Recommend rotation for secrets older than 90 days.

## Azure Front Door
1. `az afd route list`: routing rules, origin groups.
2. `az afd origin-group list`: health probes, origin status.
3. `az afd waf-policy list`: managed/custom rules.

## Azure Functions
1. `az functionapp show`: runtime status. Check Application Insights for failures.
2. Check Consumption vs Premium plan. Verify scale limits.
3. Verify connection strings for trigger bindings.

## Security posture
1. **Defender for Cloud:** CSPM score, recommendations by severity.
2. **Sentinel:** KQL queries for threat detection. Check analytics rules.
3. **Entra ID:** Conditional Access policies, PIM assignments, risky sign-ins.

## Golden signals

| Signal | Metric / table | Threshold |
|---|---|---|
| Latency | AppRequests P99 | < X ms |
| Errors | AppRequests ResultCode 5xx | < X% |
| Saturation | Perf % CPU | < 85% |
| Heartbeat | Heartbeat | every 1m |

## Session
Expired: stop and return `az login`.
