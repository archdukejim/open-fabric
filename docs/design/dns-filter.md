# Design: an optional DNS filter (AdGuard Home) in front of BIND

Status: **being built** (branch `feature/federation`, milestone M7 of
[federation.md](federation.md) §8a). Owner decision 2026-10-01: AdGuard Home
is an optional part of the stack, in the order the owner runs it today —
clients ask AdGuard, AdGuard forwards the fabric domains to BIND and the rest
of the internet over DNS-over-HTTPS/TLS. Every site, the root included, may
run its own. An install can instead use an AdGuard (or Pi-hole) of its own
outside fabric.

## 1. Why this order

DHCP hands out a DNS server's **address**, never a port, so whatever answers
the clients must listen on 53. With AdGuard in front, it sees every device
(per-client logs, statistics and rules); BIND keeps answering the fabric
zones and TSIG/RFC2136 updates on its own port. With BIND in front AdGuard
would only ever see BIND's address. Front is therefore the only position
built; "behind" is not offered.

## 2. Settings

**Out of the box AdGuard points at local DNS only** (owner decision 2026-10-01): everything goes to this
site's BIND. The internet upstreams (the owner uses `https://dns.google/dns-query`,
`https://dns.cloudflare.com/dns-query`, `tls://dns.google`), bootstrap servers and filter lists are set up
in AdGuard's own UI after the OIDC sign-in, and fabric keeps them across deploys.

```yaml
dns_filter: adguard            # none (default) | adguard
adguard_upstreams: []          # prefills a first deploy only (then the UI owns them)
adguard_filter_lists: []       # prefills a first deploy only
adguard_rules: []              # your rules, after the generated ones
```

With `dns_filter: adguard`, `bind_dns_port` defaults to 5053: AdGuard takes
`host_ip:53`, BIND stays reachable for RFC2136 clients and linked sites on
its own port (federation links carry each site's port, M4).

## 3. What fabric generates

| AdGuard setting | From |
|---|---|
| `dns.upstream_dns` | fabric's lines `[/<domain>/]<ip_bind9>` (this site's domain, the organisation's, every linked site's — dns_links — and the reverse zones) kept in step, in front of everything else; on a first deploy the rest is `adguard_upstreams` or `<ip_bind9>` alone (local DNS only), afterwards the UI's |
| `dns.local_ptr_upstreams` | `<ip_bind9>` |
| `dns.allowed_clients` | `lan_cidr`, `fabric_subnet`, `security.firewall_allow` |
| `user_rules` | `@@\|\|<domain>^$important` for each fabric domain and `@@\|\|<host_ip>^$important`, then `adguard_rules` |
| `filters` | `adguard_filter_lists`, only on a first deploy (afterwards the UI's) |
| `users` | one local user, password generated and kept in OpenBao (`adguard_admin_password`) |
| `http.address`, `dns.port` | unprivileged ports inside the container |

**Ownership.** AdGuard rewrites its own YAML (schema migrations, edits in its
UI). fabric owns only the keys above: on every deploy it reads the current
file, replaces those keys and keeps everything else, so upstreams, bootstrap
servers, lists and clients set in AdGuard's UI survive a deploy. The file is
rewritten (and AdGuard restarted) only when the merged content differs. Generated rules are kept
in front of the owner's; rules typed in the UI after them are kept.

## 4. Container

- `fabric/adguard:local`, built FROM `adguard/adguardhome` pinned by digest
  (arm64 + amd64): the upstream binary carries file capabilities, which the
  kernel refuses to exec with every capability dropped, so the build copies
  it without them. On `fabric_net` with a fixed address (`ip_adguard`); a
  service user of its own.
- No capabilities: it listens on unprivileged ports inside the container and
  Docker publishes `host_ip:53` (TCP/UDP) to them. No DHCP (fabric has Kea).
- The admin UI is **never published**: only nginx reaches it.
- Memory limit 256 MB (Pi budget), health check on its HTTP port.

## 5. Signing in (OIDC)

`https://adguard.<domain>` → nginx → **oauth2-proxy** (OIDC against the site's
Keycloak realm, client `fabric-adguard` created by `keycloak_bootstrap`, its
client secret and cookie secret in OpenBao and passed through files, never
argv) → AdGuard. Access needs the fabric permission `dns:filter` (in the admin
bundle and the network-operator bundle). After sign-in nginx adds AdGuard's
own local user (Basic auth) to the request, so AdGuard is never
unauthenticated, even from inside `fabric_net`.

oauth2-proxy is a unit of its own (`adguard-auth`), and it is given Keycloak's endpoints instead of
discovering them at start: it starts while Keycloak is down or still starting. DNS never depends on
the sign-in, on Keycloak or on BIND being restarted (AdGuard's unit requires neither).

## 6. Federation

Each site decides for itself. A site's AdGuard forwards the fabric domains to
its own BIND, which keeps copies of its neighbours' zones (M4), so names of
the root and of the sites next to it resolve locally even when the link is
down. Domains of sites further away resolve only through a neighbour that
holds them (not in this milestone).

## 7. Offline

Nothing is fetched by default (local DNS only, no lists). Lists and upstreams
added in the UI are the owner's choice; offline, AdGuard keeps answering
fabric's zones from BIND and applies the rules it has.

## 8. Later

Backlog, not strictly needed (owner 2026-10-01: everything is filtered anyway): DNS-over-HTTPS for
clients (`https://dns.<domain>/dns-query` through nginx to AdGuard) and DoT on 853 with a
certificate from the site's CA. A Pi-hole alternative is not planned (owner).
