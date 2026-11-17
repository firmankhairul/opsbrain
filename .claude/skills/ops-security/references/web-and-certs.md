# WAF and TLS Certificates

WAF rule review and false-positive handling, rate limiting, and SSL/TLS certificate hygiene.

## WAF

1. Review rule sets (OWASP CRS, managed, custom). Check blocked requests for false positives.
2. False positive: identify the rule ID, then propose an exception scoped to the URI/parameter (L2). Never disable a whole rule group.
3. Rate limiting: review thresholds; check whether legitimate traffic was blocked during peaks.

## SSL/TLS

1. **Inventory:** catalog all certificates (load balancers, CDN, web servers, VPN).
2. **Expiry:** flag < 30 days; critical alert < 7 days. Quick check: `echo | openssl s_client -connect <host>:443 -servername <host> 2>/dev/null | openssl x509 -noout -enddate`.
3. **Cipher audit:** flag weak ciphers (RC4, 3DES, SHA1); require TLS 1.2+.
4. **HSTS:** verify a `Strict-Transport-Security` header with an appropriate `max-age` (`curl -sI https://<host>`).
