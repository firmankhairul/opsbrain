# CrowdStrike Falcon

Falcon API for host inventory, detections, live response, containment, and custom IOCs.

## Host management

1. `GET /devices/queries/devices/v1` - filter by hostname, IP, OS.
2. Check `agent_version`, `last_seen`, `status` (`normal` / `reduced_functionality` / `containment`).
3. `GET /detects/queries/detects/v1` - filter by severity (Critical/High/Medium/Low).

## Response

1. **RTR (Real Time Response):** live investigation with `runscript`, `get`, `put`.
2. **Containment (L3, double confirmation):** `POST /devices/entities/devices-actions/v2` with `action_name=contain`. Network-isolates the host.
3. **Custom IOCs:** `POST /indicators/entities/iocs/v1` for hash, domain, or IP indicators.
4. **Lift containment (L2):** `action_name=lift_containment`, only after investigation confirms the host is safe.
