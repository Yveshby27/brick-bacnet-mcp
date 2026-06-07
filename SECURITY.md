# Security policy

## Supported versions

v0.1.x is the only currently supported version line. As an alpha, all v0.1 patch releases receive security fixes.

## Scope

brick-bacnet-mcp is a read-only BACnet/IP gateway intended for trusted local-network deployment. v0.1 has:

- No WriteProperty path. The protocol surface that writes to building controllers is intentionally absent.
- No authentication layer. The MCP server is expected to run on a host the operator already trusts.
- No network egress beyond the configured BACnet broadcast domain.

Threats outside this scope (Internet-exposed deployment, multi-tenant hosting, write-back to controllers, BACnet/SC) are not in v0.1's threat model. v0.2 and later may revisit the threat model as those features land.

## Reporting a vulnerability

If you believe you have found a security issue in brick-bacnet-mcp, please report it privately rather than opening a public issue.

Email: yves.habchy@gmail.com

Include:

- A description of the issue and its potential impact
- Reproduction steps or proof-of-concept
- The version (commit hash) you tested against
- Your contact information for follow-up

Reports are acknowledged within 7 days. Coordinated disclosure timeline is negotiated case-by-case based on severity.

## Out-of-scope reports

The following are documented design decisions for v0.1 and are not vulnerabilities:

- The MCP server has no authentication (run on a trusted host)
- WriteProperty is intentionally absent (read-only by design)
- Rule library matches are heuristic, not authoritative (semantic accuracy is best-effort)
- The BACnet stack runs unprivileged but listens on UDP 47808 by default (standard BACnet/IP port)

If you are uncertain whether something is in scope, email anyway. A clarifying reply is cheaper than a missed real issue.
