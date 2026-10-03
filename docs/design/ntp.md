# Design: time (NTP) for the site and its network

Status: **being built** (owner request 2026-10-01: "NTP is a critical service"). Milestone M9 of
[federation.md](federation.md) §8a, built before M8.

## 1. Why

Every part of fabric depends on the clock: certificate validity (the lan/lab clock skew of M1b
made a site CA "not yet valid"), TOTP sign-in, Keycloak tokens, OIDC cookies, DNS TSIG (a
signature more than 5 minutes off is refused), RADIUS and log correlation across sites. A
Raspberry Pi has no battery-backed clock: it boots with the time it shut down at until it syncs.
Today fabric neither serves nor checks time.

## 2. Shape

- **chrony on the host** (Ubuntu's package, a dependency of fabricctl), replacing
  systemd-timesyncd. Not a container: setting the clock needs `CAP_SYS_TIME`, and every container
  already reads the host's clock. fabric renders `/etc/chrony/chrony.conf` and owns it.
- **Sources** (`ntp_servers`): the internet with **NTS** (authenticated time) by default, e.g.
  `time.cloudflare.com`, `nts.netnod.se` and `ptbtime1.ptb.de`, all with NTS — three independent sources, so
  chrony can outvote one that is wrong; or the owner's own (a GPS clock, a router).
  At a federated site the **upstream site comes first** (the hierarchy follows the federation),
  the internet after, so a site keeps time when its upstream is away.
- **Serving**: the LAN (`lan_cidr`, every DHCP subnet, `security.firewall_allow`) may ask; UDP 123
  opened on the firewall for those networks only (rules for networks no longer allowed are removed).
  chronyc answers on localhost only (`bindcmdaddress`), so nobody can query or control chrony
  remotely; rate limiting on.
- **Offline**: `local stratum 10 orphan`: with no source reachable, the site keeps serving its
  own steady clock so the network stays consistent with itself, and linked sites agree on one of
  them.
- **Boot**: chrony starts with `-s` (no RTC: the clock is first set forward to the drift file's
  time, so it never starts in the past) and `makestep` for the first updates; fabric's units are
  ordered after `time-sync.target`, which `chrony-wait` reaches on a sync or after 90 s (never
  blocks forever: offline installs must start). `nocerttimecheck 1` lets NTS reach its servers
  while the clock is still wrong.
- **Containers sharing a kernel clock** (the test sandbox): `ntp_set_clock: false` runs chrony with
  `-x` — it keeps and serves time but never sets the clock.
- **Name and DHCP**: `ntp.<domain>` points at the host; Kea hands out option 42 (`ntp-servers`)
  on every subnet unless a subnet sets its own (M8).

## 3. Visible

- `fabricctl status`: synced or not, source, offset, stratum.
- `fabricctl doctor` / verify: fails when unsynced or more than 1 s off; at a federated site also
  compares against the upstream site.
- Web UI status page: the same.

## 4. Settings

```yaml
ntp_servers: [ "time.cloudflare.com nts", "nts.netnod.se nts", "ptbtime1.ptb.de nts" ]   # default; [] = upstream site / local only
ntp_serve: true                                                    # answer the LAN
ntp_set_clock: true                                                # false: -x, never set the clock
dhcp:
  ntp: [192.168.4.2]                                               # handed out (default this host; [] none)
```
