# Fortinet FortiGate

FortiOS CLI for policy and traffic tracing, VPN, HA, firmware, and IPS. Back up the config (`execute backup config ...`) before any change.

## Policy and traffic

1. `get firewall policy` lists all policies. `diagnose firewall iprope lookup <src> <dst> <port>` traces which policy matches.
2. `diagnose sys session list` shows active sessions; narrow first with `diagnose sys session filter ...`.
3. `execute log filter category traffic` then `execute log display` for allowed/denied traffic.
4. Adding or modifying a policy is L2; deleting a policy is L3.

## VPN

1. `diagnose vpn ike gateway list` - IKE SA status (established/connecting/down).
2. `diagnose vpn tunnel list` - IPsec SAs and traffic selectors.
3. `get vpn ssl monitor` - connected SSL VPN users and assigned IPs.

## HA and system

1. `get system ha status` - cluster role, sync status, uptime.
2. `get system status` - firmware version; cross-reference FortiGuard PSIRT advisories (triage per [vulnerability.md](vulnerability.md)).
3. `diagnose ips anomaly list` - IPS detections and blocked signatures.
