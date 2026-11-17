# Network troubleshooting

Scope: host-side connectivity — DNS, routing, ports, host firewalls, latency/loss, MTU, TLS — walked up the layers, same method for AWS SG, Azure NSG, or on-host firewall.

## Risk levels for network actions

- **L1:** `dig`, `ping`, `mtr`, `ss`, `ip a/r`, `curl -v`, `openssl s_client`, `traceroute`, read-only `tcpdump`. Captures may hold secrets — encrypt or delete after.
- **L2:** add/remove a firewall rule (`ufw`/`firewalld`/SG/NSG), flush DNS cache, runtime `ip route add`, toggle an interface, runtime MTU change.
- **L3:** persisted firewall/routing changes, persisted `/etc/hosts` / `resolv.conf` edits, default-route change, VPN/tunnel reconfig, a rule on a shared prod SG. Warn about SSH self-lockout.

## Protocol

1. Observe: reproduce with the layer ladder. Test with a raw IP to rule DNS in or out.
2. Analyze: name the failing layer. Do not fix at the wrong one — a "DNS bug" is often a firewall drop.
3. Propose: Change Proposal with Scope, Rule change, Lockout risk, Rollback (+ auto-revert timer for remote firewall edits).
4. Act: before a remote firewall/SG edit, stage a revert (`at now + 10 minutes` / cron) in case of self-lockout; cancel it after verifying.
5. Verify: path restored end-to-end, no collateral (other services still reachable).

## Layer ladder (walk top-down)

| Layer | Question | Tool |
|---|---|---|
| L1/2 link | Interface up? errors/drops? | `ip -s link`, `ethtool eth0` |
| L3 IP | Address + route correct? | `ip a`, `ip route get <dst>` |
| Reachability | Host alive / path healthy? | `ping -c5`, `mtr -rwzbc100 <host>` |
| DNS | Name resolves right? | `dig`, `dig @8.8.8.8`, `dig +trace` |
| L4 port | Port open, who listens? | `ss -tlnp`, `nc -vz host port` |
| Firewall | Something dropping it? | `iptables -L -n`, `ufw status`, SG/NSG |
| L7 / TLS | App + cert OK? | `curl -v`, `openssl s_client` |
| Wire | Nothing else explains it | `tcpdump` |

## DNS resolution fails / wrong answer

```bash
cat /etc/resolv.conf              # which resolver is configured?
dig app.example.com               # via configured resolver
dig @8.8.8.8 app.example.com      # via public resolver — bypasses local
dig +trace app.example.com        # follow delegation from root
sudo resolvectl flush-caches      # systemd-resolved: clear stale cache (L2)
```

- Resolves on `@8.8.8.8` but not locally → local resolver / `resolv.conf` / split-horizon issue.
- Right IP but app still fails → not DNS; go to port/firewall.
- `NXDOMAIN` on `+trace` → record genuinely missing or wrong zone.
- Containers: check the container's own `/etc/resolv.conf` and Docker embedded DNS `127.0.0.11` → `ops-platform`.

## Connection refused / timeout

1. Refused = something answered "no" → service down or wrong port. On target: `ss -tlnp | grep :<port>`.
2. Timeout = silent drop → firewall/SG/NSG or routing black hole, not the app.
3. On the box: `curl -v localhost:<port>`. Works locally, fails remotely → firewall/SG.
4. Walk firewalls in order: host (`iptables`/`ufw`/`firewalld`) → cloud SG/NSG → NACL → LB / target-group health.
5. Asymmetric routing / return path: from the server, `ip route get <client-ip>`.

## High latency / packet loss / MTU

1. `mtr -rwzbc 100 <host>` → find the hop where `Loss%` first appears and persists to the final hop. Loss on one mid-path hop only is usually ICMP deprioritisation — ignore it.
2. Loss at final hop only → destination overloaded.
3. Consistent loss from one hop onward → that link / provider segment.
4. Local retransmits/drops: `ss -ti` (retrans), `netstat -s | grep -i retrans`, `ip -s link` (RX/TX errors, overruns).
5. MTU / PMTUD black hole (small requests work, large ones hang; common over VPN/tunnels): `ip link show <if>` for MTU, then `ping -M do -s 1472 <host>` (1500 − 28) and step down until it passes. Fix with runtime MTU change or MSS clamping (L2), persist as L3.

## TLS / certificate problems

```bash
curl -v https://app.example.com                         # handshake + chain + HTTP
openssl s_client -connect app.example.com:443 -servername app.example.com </dev/null 2>/dev/null \
  | openssl x509 -noout -dates -subject -issuer
```

- Expiry → `-dates`. SNI mismatch → pass `-servername`. Incomplete chain → server missing intermediate.
- `curl` verify fails but browser OK → missing intermediate on the server (browser fills it from cache).
- Handshake resets → protocol/cipher mismatch, or a firewall doing TLS inspection.

## Port open but no data (last resort)

```bash
sudo tcpdump -i any -n host <peer> and port <port> -c 50   # SYN? SYN-ACK? RST? retransmits?
```

- SYN out, no SYN-ACK → dropped inbound (firewall/SG) or server not listening.
- SYN-ACK then RST → app rejecting after accept (auth, proxy, backend down).

## Tooling

```bash
for t in dig nslookup ss nc curl openssl tcpdump mtr traceroute ip; do
  command -v $t >/dev/null && echo "ok $t" || echo "MISSING $t"; done
```

Modern swaps: `ss` > `netstat`, `ip` > `ifconfig`/`route`, `dig` > `nslookup`, `mtr` > plain `traceroute`.

## Upstream references

- Basic network troubleshooting in Linux (layered method): https://azureossd.github.io/2026/03/12/Basic-Network-Troubleshooting-in-Linux/index.html
- Essential Linux networking tools for DevOps: https://oneuptime.com/blog/post/2026-02-20-linux-networking-tools/view
- Linux networking troubleshooting command guide: https://networks.tools/learn/article/linux-networking-troubleshooting-tools
