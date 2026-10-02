# Operations

## Live Configuration Changes (`fabricctl`)

Use `fabricctl` for post-install changes to DNS records, TSIG keys, certificates, and infrastructure variables — no full redeploy needed. Run it **on the target machine**; every command needs root (`sudo`). The command is `/usr/bin/fabricctl` from the package (or `/usr/local/bin/fabricctl` when setup was run straight from a git checkout). It has two kinds of commands:

- **subcommands** (`fabricctl setup`, `fabricctl tsig …`, `fabricctl vault …`): Python, in `fabricctl/lib/fabriclib/`. `setup`, `reinstall`, `uninstall`, `restore` and `--help` run the packaged code; the others run the deployed install in `/opt/fabric`.
- **flags** (`fabricctl --interactive`, `--apply`, `--mint-certs`, …): the older interface (`fabricctl/lib/manage.sh`); still supported. With no argument at all, `fabricctl` opens the interactive menu.

The same DNS and apply operations are also available in the browser through webui — see [webui.md](webui.md).

### Table of Contents
- [Live Configuration Management (`fabricctl`)](#live-configuration-management-fabricctl)
  - [`--interactive`](#--interactive)
  - [`--print`](#--print)
  - [`--apply`](#--apply)
  - [Log forwarding (optional: Fluent Bit)](#log-forwarding-optional-fluent-bit)
  - [DHCP (optional: Kea)](#dhcp-optional-kea)
  - [802.1X (optional: FreeRADIUS)](#8021x-optional-freeradius)
  - [`fabricctl images`](#fabricctl-images) (was `--update-containers`)
  - [`--version`](#--version)
  - [`--client-cert <user>`](#--client-cert-user)
  - [`--keycloak-sync`](#--keycloak-sync)
  - [`--mint-certs`](#--mint-certs)
  - [`--service-cert`](#--service-cert)
  - [`--render-jinja <file.j2>`](#--render-jinja-filej2)
- [Interactive Menu Categories](#interactive-menu-categories)
  - [DNS Configuration](#dns-configuration)
  - [Mint Certificates](#mint-certificates)
  - [TSIG Keys (RFC2136)](#tsig-keys-rfc2136-dynamic-updates)
  - [ACLs](#acls)
  - [Landing Page Links](#landing-page-links)
- [DNS filter (optional: AdGuard Home)](#dns-filter-optional-adguard-home)
- [Federation (sites)](#federation-sites)
- [OpenBao (secrets)](#openbao-secrets)
- [Lifecycle Commands](#lifecycle-commands)
- [Service Ports](#service-ports)

---

### Live Configuration Management (`fabricctl`)

The infrastructure variables in `/opt/fabric/config/vars.yaml` can be managed with the `fabricctl` subcommands below, the interactive menu, or by editing the YAML by hand and running `--apply`. Setup keeps these edits: a re-run starts from this file.

#### `--interactive`
Launch the interactive configuration menu (also what `fabricctl` with no arguments does). Its categories are DNS Configuration, Mint Certificates, Docker & Services, TSIG Keys, Landing Page Links and Advanced Configuration (every other key); `a` adds a variable, `d` deletes one, `apply` saves and applies, `q` quits without applying. Each change is saved to `vars.yaml` at once and audit-logged. Immutable variables (the CA settings, `byoc` and its paths, `extra_certs`, `stepca_port`, `deploy_base_dir`, `domain`, `org_domain`, `site_name`) cannot be edited or deleted here. Changes to `hostname`, `host_ip`, `lan_cidr`, `lan_gateway` or `fabric_subnet` are marked with a warning.

```bash
sudo fabricctl --interactive
```

#### `--print`
List the top-level variables of `vars.yaml`, one numbered line each, in colour. Lists and dictionaries are shown as `(complex structure)`.

```bash
sudo fabricctl --print
```

#### `--apply`
Apply any manual changes made directly to `vars.yaml`. `fabricctl` leverages the native Python `deploy.py` engine to compare the file against the running configuration, directly render Jinja2 templates, and selectively reload or restart only the affected systemd-managed services. 

**Intelligent Restarts:** `deploy.py` tracks exact file modifications.
- If only `nginx/www/...` templates change, Nginx natively live-reads the files. No restart or reload is performed.
- If `bind9` configuration changes, BIND9 gets `rndc reconfig`; if `nginx` configuration changes, `nginx -s reload`.
- **DNS zones** are compared ignoring the SOA serial, so only zones whose records actually changed are touched. Forward zones are dynamic (they carry an `update-policy`), so each changed zone is updated with `rndc freeze` → swap the zone file → delete the stale `.jnl` → `rndc thaw` (static zones get `rndc reload <zone>`). Non-disruptive; dynamic updates made since the last apply (e.g. ACME TXT records) are discarded for that zone.
- If a **389-DS seed file** (`/opt/dirsrv/seed/*.ldif`) changes, it is applied live with `dirsrv.sh seed`; the `ldap` service is restarted only if `cn=config` changed.
- If the **webui** config, app code or Dockerfile changes, the `webui` image is rebuilt (if needed) and the container restarted last (queued with `--no-block`, so an apply started from webui completes). If the `fabric-agent` unit changes, `fabric-agent` is restarted (also queued).
- A full container restart (`docker compose down/up` via systemctl) is ONLY triggered if immutable service definitions (like `docker-compose.yml` or the systemd `.service` wrapper) or service-specific config files (like StepCA templates) actually change their rendered contents.

```bash
sudo fabricctl --apply
```

#### Log forwarding (optional: Fluent Bit)
Off unless chosen in setup's Advanced plan or `install_fluentbit: true`.
Fluent Bit (its own hardened container, pinned image) sends:

- the **host journal** — every fabric container logs there (Docker's
  journald driver, tagged with the container name; `docker logs` still
  works) and so does fabric's own audit log (identifier `fabric-audit`);
- **OpenBao's audit log** (secrets HMAC'd): a second audit device writes
  the same trail to `audit-forward.log`, group-readable for the collector
  only (a declared audit device is never changed: OpenBao would refuse to
  become active).

Destinations, in `vars.yaml` (re-run setup to apply):

```yaml
install_fluentbit: true
log_forwarding:
  syslog:  {host: siem.lan, port: 6514}                          # RFC 5424 over TLS
  elastic: {url: "https://es.lan:9200", user: fabric, index: fabric}
  # ca_file: per destination, if its certificate is not from the fabric CA
  # hosts: {siem.lan: 192.168.4.20}                              # names not in DNS
```

Every destination's certificate is verified (the fabric CA unless a
`ca_file` is given). The Elasticsearch password lives in OpenBao:
`sudo fabricctl logs set-password elastic` (asked, or on stdin). A disk
buffer (`/opt/fluentbit/buffer`, 256 MB per destination) keeps records while a
destination is down; they are delivered when it is back.
`sudo fabricctl logs status` shows each destination's records sent,
retries, errors and dropped. Local logs stay; forwarding is a copy.

#### DHCP (optional: Kea)
Off unless chosen in setup's Advanced plan (it suggests the interface,
subnet and router of the default route) or `install_kea: true`.
**Kea 3.0 LTS**, from ISC's signed apt repository (key pinned by
fingerprint, exact package version in `images.lock.yaml`), built locally on
fabric's pinned Debian image. One DHCP server per LAN: switch off your
router's DHCP first.

```yaml
install_kea: true
dhcp:
  interfaces: [eth0]
  lease_time: 86400                       # seconds, 300 to 2592000
  # ddns: false                           # don't register hostnames in DNS
  # ddns_subdomain: dhcp                  # -> <name>.dhcp.<domain>
  # dns: [192.168.4.2]                    # DNS servers handed out (default: this host)
  subnets:
    - subnet: 192.168.4.0/22
      pools: ["192.168.5.100 - 192.168.5.200"]
      routers: 192.168.4.1
      reservations:
        - { mac: "aa:bb:cc:dd:ee:ff", ip: 192.168.4.20, hostname: printer }
```

Setup refuses (before changing anything) a pool outside its subnet, a
reservation inside a pool or outside every subnet, duplicate MACs or
addresses, and a static A record inside a pool (Kea would hand it out).

**Hostnames in DNS.** Clients that send a hostname are registered as
`<name>.dhcp.<domain>`: a zone of its own, delegated from `<domain>`, that
fabric creates once and never re-renders (apply would wipe the dynamic
names otherwise). Kea's DDNS key (`kea-ddns`, in OpenBao) may change only
A, AAAA and DHCID records in that zone — nothing in `<domain>` itself — and
a client cannot take over another client's name (`check-with-dhcid`).
Reverse (PTR) records for DHCP clients are not registered yet.

Day to day (the Kea tab of the web UI does the same):

```bash
sudo fabricctl dhcp status                              # subnets, pools, reservations
sudo fabricctl dhcp leases                              # active leases, from Kea
sudo fabricctl dhcp reserve aa:bb:cc:dd:ee:ff 192.168.4.20 printer
sudo fabricctl dhcp unreserve aa:bb:cc:dd:ee:ff
```

A reservation is saved to `vars.yaml` and applied at once (`--no-apply` to
batch); the client gets the address at its next renewal. Leases live in
`/opt/kea/leases` (memfile) and survive restarts and upgrades. The firewall
opens UDP 67 on the DHCP interfaces only.

#### 802.1X (optional: FreeRADIUS)
Off unless chosen in setup's Advanced plan or `install_freeradius: true`
(needs the directory, `install_ldap`). FreeRADIUS 3.2 answers your
switches and access points on UDP 1812 (accounting 1813, acknowledged and
not stored) at the host IP.

**Who may join** is decided per device in the directory (389-DS tab →
Devices and Roles), on every request:

- **EAP-TLS** — the device presents a certificate from the fabric CA that is
  *linked* to it (issued or signed for the device on the Step-CA tab, or
  linked on its page), and one of its roles grants `network:eap-tls`.
  Supplicants should check the server certificate `radius.<domain>`
  against the fabric root CA.
- **MAB** (printers, cameras, IoT without a supplicant) — the switch sends
  the device's MAC; one of its roles grants `network:mab`. A MAC can be
  copied, so give MAB roles a restricted VLAN.
- **People by password (EAP-TTLS)** — a person's user name and password,
  inside a TLS tunnel to `radius.<domain>`, checked against the directory.
  Only members of the groups you map may join, each group with an optional
  VLAN. Mapped at first: the directory groups `network-staff` and
  `network-guests`, both empty and without a VLAN — nobody can join by
  password until someone is added to one (in Keycloak). Give
  `network-guests` its guest VLAN before using it:
  `fabricctl radius map-group network-guests --vlan 50 --priority 100`.
- **Default device roles** — a new install starts with `workstations`,
  `phones-tablets`, `servers` (EAP-TLS), `printers`, `iot` (MAB) and
  `network-gear` (SCEP), without VLANs and without devices. They are created
  once: edit or delete them like any role; setup never brings one back.
- **VLAN** — from the device's role (or the person's mapped group) with the
  lowest priority number that sets one (none: the switch port's default).
- **Refused**: a disabled device, an unlinked certificate, a certificate
  from another CA, a role without the permission, a wrong password or a
  locked account, a person in no mapped group, a password sent outside the
  tunnel, and everything while the directory cannot be asked (fail closed). Disabling a device or unlinking a
  certificate takes effect at its next authentication.

RADIUS clients (the switches and access points that ask):

```bash
sudo fabricctl radius add-client switch1 192.168.4.2        # prints its shared secret once
sudo fabricctl radius add-client aps 192.168.10.0/24 --secret-prompt   # keep a secret they already have
sudo fabricctl radius rotate-secret switch1                  # new secret, shown once (--secret-prompt: give one)
sudo fabricctl radius remove-client switch1
sudo fabricctl radius map-group staff --vlan 20              # staff may join by password, on VLAN 20
sudo fabricctl radius map-group guests --vlan 50 --priority 60   # priority default 100
sudo fabricctl radius unmap-group guests
sudo fabricctl radius status                                 # server name, clients, groups that may join by password
sudo fabricctl radius log -n 100                             # recent decisions (default 50): accepted / refused and why
```

Every change is saved and applied at once (FreeRADIUS restarts); `--no-apply`
records it only (apply later with `sudo fabricctl --apply`). A secret is
never taken on the command line: `--secret-prompt` asks for it, hidden.
`add-client … --no-message-authenticator` is the command-line form of
`message_authenticator: false` (below).

Or in `vars.yaml` (re-run setup): `radius_clients: [{name: switch1, address:
192.168.4.2}]`. Secrets live in OpenBao (`radius_secrets`); a `secret:`
written in the vars file is moved there. Every client must send a
Message-Authenticator (BlastRADIUS, CVE-2024-3596); set
`message_authenticator: false` only for a device that cannot, and it shows
on the FreeRADIUS tab. Clients outside the LAN are let through the
firewall to the RADIUS ports only.

Step-by-step setup for switches (UniFi included) and Windows PCs, with
this install's values filled in and a generated Windows setup script per
method, is on the FreeRADIUS tab: **Connect a switch** and **Connect
Windows**.

Password logins, things to know: the directory's lockout counts them (5
wrong passwords lock the account for 15 minutes — someone at any port can
lock a person out by guessing), and there is no second factor. Map only
the groups that need it; devices are better served by certificates.
Supplicants must be set to check the server certificate (`radius.<domain>`,
fabric root CA) — otherwise a rogue access point could collect passwords.
Windows needs a profile for EAP-TTLS (it offers PEAP by default, which
fabric does not use: MSCHAPv2 needs NT hashes the directory does not keep).

#### `fabricctl images`
Every container image is pinned by digest (amd64 + arm64). The validated
list is `fabricctl/images.lock.yaml` of the installed fabric. **A fabric
upgrade never changes a running image**: `fabricctl setup` keeps what each
host runs; these commands move it.

| Command | What |
|---|---|
| `sudo fabricctl images status` | Each service: what it runs, the validated image, `current` / `update available` / `held (set by the admin)` |
| `sudo fabricctl images update <service…>` or `--all` `[--force]` | Move to the validated images (`--force`: also images you pinned in `vars.yaml`) |
| `sudo fabricctl images rollback <service>` | Back to the image before the last update |
| `sudo fabricctl images prune` | Remove old images of fabric's repositories now |

`update`, per service in dependency order: download by digest (nothing is
touched if that fails), re-render, rebuild local layers on the new base,
**compose down/up through the service's systemd unit**, wait until it is
healthy. A service that does not come back healthy is put back on its
previous image the same way, and the run stops. bind9, dirsrv and webui share the
Debian base and move together. Images you set yourself in `vars.yaml`
(`image_pins`) are skipped unless `--force`. After an update, old images
are pruned (`image_prune: false` turns that off): only images of fabric's
repositories that no container uses, keeping each service's previous image
for `rollback`. `sudo fabricctl --update-containers` is the old name of
`images update --all`.

Automatic fetching of newly validated lists (and optional automatic
applying) follow in the next step (design `image-updates.md`).

```bash
sudo fabricctl images status
sudo fabricctl images update --all
```

#### `--version`
Print `fabricctl version <version>` (`/opt/fabric/VERSION`, from the repository's `fabricctl/VERSION`) plus the build stamp in `/opt/fabric/BUILD` (git commit, `-dirty` if the tree had local changes, UTC build time and package version — written by `installers/deb/build-deb.sh`). Before setup has run it prints the package's version and `(package; not set up yet)`. The only command that works without root.

```bash
fabricctl --version
```

#### `--client-cert <user>`
Mint a webui admin client certificate (same as `fabricctl client-cert <user> [--days N]`). The CN is `<user>` and **must equal the Keycloak username**. Issued offline by the Step-CA intermediate (RSA 3072, valid `--days` days, default 365; the flag form always uses 365), bundled with the chain into `~/fabric-admin/<user>.p12` (home of the account that ran `sudo`; the folder is `0700`) with a generated password that is shown once. The private key exists only inside the `.p12`. The certificate alone grants nothing: the user must also pass the Keycloak login. Setup already does this for the first admin (with `webui_client_cert_days`) — see [webui.md](webui.md#first-time-setup).

```bash
sudo fabricctl client-cert jdoe --days 90
sudo fabricctl --client-cert jdoe
```

#### `--keycloak-sync`
Re-run `keycloak_bootstrap.py`: realm, LDAP federation to 389-DS, group mapper and sync, `fabric-admin` role → `admins` group, the `fabric-webui` OIDC client and its TOTP flow. Idempotent — use after changing `webui_*` vars or to repair drift made in the admin console. It reads fabric's secrets, so OpenBao must be unlocked.

```bash
sudo fabricctl --keycloak-sync
```

#### `--mint-certs`
Mint a certificate for something outside the stack with the Step-CA intermediate (offline, no ACME). Interactive: asks for the Common Name, extra SANs (not for a CA), validity in days (365), an output folder (default: the home of the account that ran `sudo`; it must exist), key type and size; shows a review, then adds the entry to `extra_certs` in `vars.yaml` and mints it. With `--apply` it mints every `extra_certs` entry without asking.

| Option | Meaning |
|---|---|
| `--intermediate-ca [N]` | Mint a subordinate CA with `pathLen=N` (default 0: it may sign leaf certificates only) — see [subordinate.md](subordinate.md) |
| `--kty RSA\|EC\|OKP` | Key type offered as the default (RSA) |
| `--size <bits>` | Key size offered as the default (4096; RSA only — EC gets step's default curve) |
| `--apply` | Mint every `extra_certs` entry from `vars.yaml` |

The certificate (with the chain) and its key (`0600`, unencrypted) are written as `<cn>.crt` / `<cn>.key`, with `.`, `/` and spaces in the name turned into `-`, owned by the `sudo` user. Setup's `certs` step and `fabricctl certs` keep every `extra_certs` entry issued: an entry whose file is missing, expires within 30 days or lacks a name is minted again — **with a new key** — so keep the output folder, or remove the entry from `vars.yaml` once you have moved the files.

```bash
sudo fabricctl --mint-certs                        # a leaf certificate
sudo fabricctl --mint-certs --intermediate-ca 1    # a subordinate CA that may sign one more CA level
sudo fabricctl --mint-certs --apply                # every extra_certs entry
```

#### `--service-cert`
Re-issue every core service certificate (`fabricctl certs --force`), restarting the services whose certificates changed. Interactive mode lists the current expiry dates first and asks to confirm; `--apply` skips the question.

```bash
sudo fabricctl --service-cert
```

#### `--render-jinja <file.j2>`
Render one Jinja2 template with fabric's variables and filters, for checking a template or making a config file from them. `--vars <file>` picks another vars file (default `/opt/fabric/config/vars.yaml`); `--output <file or folder>` the destination (default: the `sudo` user's home, named after the template without `.j2`). The result is `0644` and owned by that user.

```bash
sudo fabricctl --render-jinja ./myapp.conf.j2 --output /tmp     # -> /tmp/myapp.conf
```

---

### Interactive Menu Categories

What the `--interactive` menu edits, and the subcommands for the same things (TSIG keys and ACLs are best changed with `fabricctl tsig` and `fabricctl acl`: the menu's TSIG Keys page edits only the fields of `tsig_keys`, and ACLs are not in the menu).

#### DNS Configuration

Add or remove records in BIND9 zones without a full redeploy via the interactive menu (DNS Configuration → a zone; `a` adds a zone). Supported record types include `A`, `AAAA`, `CNAME`, `MX`, `TXT`, and `SRV`.

**DNS Sync Status & Actions:**
When entering a specific zone, the menu compares the serial BIND9 is serving (`rndc zonestatus`) with the serial in the deployed `db.<zone>` file:
- `IN SYNC (serial N)`: BIND9 serves the deployed file (or newer, e.g. after dynamic updates).
- `OUT OF SYNC (serving serial N, file has M; run 'l')`: the file on disk is newer than what BIND9 serves.
- `NOT LOADED in BIND9` / `? BIND9 not reachable`: the zone failed to load or the container is down.

Records are listed with their full value (`A`/`AAAA` ip, `CNAME` target, `MX` priority + exchange, `TXT` text, `SRV` priority/weight/port/target). Records without a name (or named `None`) are shown as `(missing name)`, rejected on entry, and filtered out at render time.

You have two powerful options to apply your pending `vars.yaml` modifications directly from the menu:
- **`l` (Live update):** Runs the same apply as `fabricctl --apply`: each changed zone is frozen, its file swapped, the `.jnl` removed and the zone thawed. *Non-disruptive to DNS resolution.*
- **`f` (Force update):** Stops BIND9, deletes `db.<zone>` and its `.jnl`, then runs the apply, which rewrites the zone and starts BIND9 again. *Warning: Disruptive — DNS is down while it runs.*

Changes edit `vars.yaml` and re-render forward and reverse zone files natively using Jinja2. Rendered files are written to `/opt/bind9/data/` with bind ownership. **Reverse zones are generated** from the A and AAAA records with private addresses — see [Reverse DNS](#reverse-dns).

Under `dns:`, the key `dynamic_zone_var` is the main zone (`domain`); it stays that way in `vars.yaml` and is resolved when the zone is rendered. Any other key is a zone name of its own:

```yaml
dns:
  dynamic_zone_var:         # = domain
    zone_authority: true    # emit the "ns" A record pointing to host_ip
    A:
    - { name: myserver, ip: 10.0.3.99 }
    CNAME:
    - { name: app, canonical: myserver }
    TXT:
    - { name: myserver, text: "v=spf1 -all" }
```

#### Mint Certificates

Mint TLS certificates for services outside this stack (NAS apps, VMs, etc.) via the interactive menu (Mint Certificates: set the fields, `m` mints) or [`--mint-certs`](#--mint-certs). Each is saved as an `extra_certs` entry in `vars.yaml`:

```yaml
extra_certs:
- cn: nas-apps.internal
  sans: [jellyfin.internal, sonarr.internal]
  days: 365
  kty: RSA           # RSA | EC | OKP  (default: RSA)
  size: 4096         # RSA: 2048/3072/4096 (default: 4096); ignored for EC/OKP (step's default curve)
  out_dir: /srv/certs   # must exist; default: the home of the account that ran sudo
  # is_ca: true, path_len: 0   -> a subordinate CA (see subordinate.md)
```

Certificates are signed offline, directly with the Step-CA intermediate key, using the `leaf.tpl` x509 template (`subca.tpl` for a CA) — no ACME. The menu's CA option always uses `path_len: 0`; use `--mint-certs --intermediate-ca N` for more. Setup and `fabricctl certs` re-issue an entry whose file is missing or expiring (see [`--mint-certs`](#--mint-certs)). For ACME, clients use Step-CA's ACME directory (`https://ca.<domain>/acme/acme/directory`) themselves. All core service certificates are offline Step-CA certificates issued by setup.

#### TSIG Keys (RFC2136 dynamic updates)

TSIG keys let other systems update DNS over RFC2136 — typically a reverse proxy obtaining Let's Encrypt certificates with DNS-01, like nginx-proxy-manager's certbot `rfc2136` plugin. A key is a `tsig_keys` entry in the vars; its secret lives only with fabric's secrets (in OpenBao; `fabricctl secrets show tsig/<name>`). From them fabric renders the BIND key, its `update-policy` grants and an `rfc2136.ini` for the client; nothing edits the rendered BIND files by hand, so keys survive every apply and setup re-run.

```yaml
tsig_keys:
- name: npm                   # nginx-proxy-manager
  records: [npm, shelfmark]   # may only set _acme-challenge.npm.<domain> and _acme-challenge.shelfmark.<domain>
  secret: "base64..."         # OPTIONAL: keep an existing key (its clients keep working unchanged)
  acls: [npm-updaters]        # OPTIONAL: BIND ACLs the key belongs to (created if missing)
- name: acme_nas-proxy
  any_name: true              # may update any name in the zone (zonesub) — must be explicit
  record_types: [TXT, A]
```

**Update rights are deny-by-default.** A key may change only what is granted: its own `records`, `primary`, an explicit `any_name`, or the policy of an ACL it is in (below). A key with none of these can authenticate but change nothing.

| Field | Default | Meaning |
|---|---|---|
| `name` | — | Key name the client uses (`dns_rfc2136_name`) |
| `secret` | generated once | Base64 secret. Given in the vars, it is moved into fabric's secrets (OpenBao) and removed from the vars files; it always wins over a stored one |
| `algorithm` | `hmac-sha256` | `hmac-sha256/384/512/224`, `hmac-sha1`, `hmac-md5` |
| `domain` | the fabric domain | Zone the key may update |
| `records` | — | Hosts allowed a DNS-01 challenge: `grant <key> name _acme-challenge.<record>.<zone>. <types>` |
| `any_name` | — | `grant <key> zonesub <types>`: any name in the zone (never implied) |
| `record_types` | `[TXT]` | Record types it may change |
| `primary` | — | The zone's own ACME key: `grant <key> subdomain _acme-challenge <types>` |
| `out` | `/opt/<name>/rfc2136.ini` | Credentials file for the client (`0600`): server = `host_ip`, port = `bind_dns_port`, key, secret, algorithm |
| `acls` | — | BIND ACLs holding `key "<name>"` (see [ACLs](#acls)) |

`tsig list` shows each key's effective rights, including those inherited from ACL policies, or `no update rights`.

```bash
sudo fabricctl tsig list                                     # keys, what each may update, ACLs, credentials file
# add: a new secret, or keep an existing one (pasted, hidden), optionally into ACLs
sudo fabricctl tsig add npm --record npm --acl npm-updaters --secret-prompt
sudo fabricctl tsig add nas --record nas                     # new secret -> /opt/nas/rfc2136.ini
sudo fabricctl tsig set-secret npm --secret-prompt           # replace the secret with one you give
sudo fabricctl tsig rotate npm                               # generate a new secret (update its clients)
sudo fabricctl tsig update npm --record npm --record web     # change what it may update (secret untouched)
sudo fabricctl tsig update npm --any-name --types TXT,A      # any name in the zone, TXT and A (explicit)
sudo fabricctl tsig update npm --acl lab --drop-acl npm-updaters
sudo fabricctl tsig remove npm                               # also leaves every ACL; its rfc2136.ini is deleted
```

`add` and `update` take the fields of the table above as options: `--domain`, `--record` (repeatable), `--any-name` (not together with `--record`), `--types TXT,A`, `--algorithm`, `--out`, `--acl` (repeatable); `update` also `--drop-acl` and refuses when given nothing to change. `set-secret` needs `--secret-file` or `--secret-prompt`.

Every change updates the vars and secrets and applies at once: BIND reloads its configuration, and apply fails loudly if BIND rejects it. `--no-apply` records a change without applying (batch several, then `fabricctl --apply`). A secret is never taken on the command line: `--secret-file` or `--secret-prompt`.

#### ACLs

`bind_acls` are named BIND address match lists; each may query fabric's zones (`allow-query`). `dns-resolvers` (loopback, the LAN, fabric's Docker subnet) and `acme-updaters` are built in and cannot be removed; `tsig-updaters` always lists every TSIG key.

```bash
sudo fabricctl acl list
sudo fabricctl acl add lab 192.168.50.0/24 10.9.9.9 'key npm' '!192.168.50.7'
sudo fabricctl acl remove lab 10.9.9.9       # one entry
sudo fabricctl acl remove lab                # the whole ACL (and its policy)
```

Each change is applied at once; `--no-apply` records it only.

Entries: an IP or CIDR, `key <tsig-key>` (must exist), another ACL, `any`/`none`/`localhost`/`localnets`; a leading `!` excludes. Assigning keys to ACLs is also `tsig add/update --acl`.

##### ACL update policies (who may mint certificates)

An ACL can carry an **update policy**; every TSIG key in the ACL inherits it as BIND `update-policy` grants. Together with deny-by-default keys this limits certificate issuance to authorized certbot devices: only a device holding a key in the ACL can set the DNS-01 challenge for the listed hosts.

```bash
sudo fabricctl acl policy certbot-devices --record web --record git     # TXT at _acme-challenge.web/git.<domain>
sudo fabricctl tsig add laptop --acl certbot-devices --secret-prompt     # this device may now prove web and git
sudo fabricctl tsig update laptop --drop-acl certbot-devices             # ...and no longer
sudo fabricctl acl policy certbot-devices --any-name --types TXT         # or: any name in the zone
sudo fabricctl acl policy certbot-devices --clear                        # members lose these rights
```

`acl policy` needs `--record` (repeatable) or `--any-name`, or `--clear`; `--types` defaults to `TXT` and `--domain` to the fabric domain. The ACL is created if it does not exist.

In the vars:

```yaml
bind_acl_policies:
  certbot-devices: { records: [web, git], record_types: [TXT] }
tsig_keys:
- { name: laptop, acls: [certbot-devices], secret: "<existing>" }
```

BIND grants update rights per key, never per address: address entries in a policy ACL still control queries, but only its `key` members receive the policy. Removing an ACL removes its policy.

**Keeping an existing key (rebuilding a host):** put its `name`, `records` and `secret` in the vars file you give `fabricctl setup --file`, with the same `domain`. BIND on the new host then accepts the same client configuration unchanged (server = `host_ip`, port 53).

#### Landing Page Links

The landing page provides a grid of quick links for the infrastructure. You can add, modify, or delete these links dynamically using the interactive menu. 

All custom links are saved in `link-vars.yaml` and are deployed alongside the normal variables. They natively evaluate Jinja variables such as `{{ domain }}` to ensure links stay accurate even if the base domain changes.

```yaml
links:
  - name: Adguard Home
    link: "adguard.{{ domain }}"
  - name: Keycloak (Admin)
    link: "sso.{{ domain }}/admin"
```

---

## Reverse DNS

PTR records are not edited by hand. Every forward-zone A and AAAA record
gets its reverse record at apply, in a zone fabric creates:

| Address | Reverse zone | PTR name |
|---|---|---|
| `192.168.1.40` | `1.168.192.in-addr.arpa` (/24) | `40` |
| `fd00:1:2:3::10` | `3.0.0.0.2.0.0.0.1.0.0.0.0.0.d.f.ip6.arpa` (/64) | `0.1.0.0.0.0.0.0.0.0.0.0.0.0.0.0` |

- **One PTR per address.** If several names share an address, the first
  named record wins, then the zone apex (`@` → the zone itself), then the
  zone's `ns` host.
- **Private addresses only**: RFC 1918, 100.64.0.0/10, IPv6 ULA (`fc00::/7`).
  A public address gets no PTR. Serving its reverse zone here would
  answer for someone else's network. The web UI lists these under
  *Reverse zones → No reverse record*.
- A reverse zone you define yourself under `dns:` (a key ending in
  `.in-addr.arpa` / `.ip6.arpa`) replaces the generated one for that range.
- Change or delete the forward record and apply: the PTR follows.

## DNS filter (optional: AdGuard Home)

With `dns_filter: adguard` (design [dns-filter.md](design/dns-filter.md)) AdGuard Home answers the
network's DNS on `host_ip:53` and BIND moves to port 5053 (`bind_dns_port`), where RFC2136 clients and
linked federation sites find it. DHCP hands out the host's address as before.

Out of the box AdGuard points at **local DNS only**: every query goes to this site's BIND, so fabric's
names resolve and the internet does not, until you set AdGuard up:

1. Open `https://adguard.<domain>` and sign in (Keycloak, TOTP). You need the `dns:filter` permission
   (admins and network operators have it).
2. In AdGuard: **Settings → DNS settings** — add your upstreams (e.g. `https://dns.google/dns-query`,
   `https://dns.cloudflare.com/dns-query`, `tls://dns.google`) and bootstrap servers; **Filters** — add the
   block lists you want; **Custom filtering rules** — your own rules go below fabric's marked section.

fabric keeps everything you set there across deploys. It manages only its own part: the
`[/<zone>/]10.255.0.30` lines that send fabric's zones (this site's, the organisation's, linked sites',
reverse zones) to BIND, the allow rules that keep those names from ever being blocked, the LAN-only
client list, AdGuard's ports, its local login (sent by nginx after your sign-in) and DHCP off. Your own
AdGuard elsewhere instead: keep `dns_filter: none` and point it at the site's BIND on `bind_dns_port`.

Two units: `adguard` (the DNS filter) and `adguard-auth` (the sign-in in front of its UI). They start and
stop apart: with Keycloak or the sign-in down only `https://adguard.<domain>` is unreachable, DNS keeps
answering, and a BIND restart (every DNS apply) does not touch AdGuard.

## Federation (sites)

Several fabrics can form one: an **upstream** owns identity and the root CA, **sites** join it and run
their own network (design [federation.md](design/federation.md)). On the upstream:

```bash
sudo fabricctl federation status            # standalone, upstream or site; joined sites; open invitations
sudo fabricctl federation enable            # the endpoint sites join through: https://federation.<domain>
sudo fabricctl federation invite lab        # one-time invitation (one hour); lab attaches flat
sudo fabricctl federation invite lab --nest 1   # lab may hold one level of sites of its own
sudo fabricctl federation invite lab3 --via edge1  # lab3 joins (and talks) through the site edge1, which only relays
sudo fabricctl federation invitations       # open invitations
sudo fabricctl federation revoke branch1    # withdraw one (by id or site)
sudo fabricctl federation remove lab        # forget a site that joined here (a lab torn down)
sudo fabricctl federation disable           # no new joins; sites that joined stay
```

**Nesting.** An invitation made on the root site attaches the new site flat (its CA signed by the root).
Made on a site that was invited with `--nest 1` or more (and has its endpoint enabled), it nests the new
site under that site: the site signs its CA, and every chain the nested site hands out carries its
parent's CA. How deep sites may nest is capped by the root's path length (`ca_nest_depth`, default 1,
chosen when the root site is installed). A nested site whose parent is gone for good moves under another
parent with that parent's invitation — on the site itself:

```bash
sudo fabricctl federation reparent         # paste the new parent's invitation at the prompt
```

It keeps its name, directory part and data; it gets a new CA, Step-CA switches to it and every service
certificate is re-issued. People's web UI certificates must then be re-issued (`fabricctl client-cert`).

**DNS between sites.** Each join creates a TSIG key for that link (kept in both sites' secrets). The
parent delegates the site's domain when it lies below its own (`lab.<domain>`: NS + glue), and each side
keeps a read-only secondary copy of the other's zone: transfers are signed with the link's key, changes
are pushed with NOTIFY. The parent applies this right after the join; `remove` takes it away again. The
two sites must reach each other on their DNS ports: each site reports its `bind_dns_port` when it joins,
so a BIND published on 5053 behind another resolver on 53 (e.g. AdGuard Home) works. Resolvers follow a
delegation only on port 53, so with BIND on another port the resolver in front of it forwards the
site domains instead. Sites that joined before this existed have no key: they
get one when they join again (or are re-parented).

**Relay nodes.** `--via edge1` names a site that joined this install (with its endpoint enabled) as the
new site's way in: the invitation points at edge1, edge1 forwards the join to the root, and the root
signs. edge1 signs nothing and keeps nothing of the new site, but it terminates TLS, so it sees the join
request — including the invitation's single-use secret — on the way through. If the relay goes away, the
site talks to its upstream directly:

```bash
sudo fabricctl federation relay direct     # on the site
```

The new site runs `sudo fabricctl setup --join` and pastes it at the prompt (or `--join @FILE`; see
[install.md](install.md#joining-an-existing-fabric-a-new-site)). The invitation carries the endpoint's
name and address, the root CA's fingerprint and a single-use secret — send it over a channel you trust;
only a hash of the secret is kept. The joining node fetches the root over plain HTTP, accepts it only if
it matches the fingerprint, then joins over TLS verified against that root. The upstream signs the
site's intermediate CA (path length 0, never outliving the root) with its root key; the site's key never
leaves the site. Joins, refusals and invitations are audited (`FED_*`).

An upstream whose CA was brought in (`byoc`) has no root key on the host and cannot sign a site's CA
online yet.

## OpenBao (secrets)

OpenBao is a core service: installed by `fabricctl setup` (step `vault`),
at `https://vault.<domain>` (API and OpenBao's own UI), container `openbao`
on fabric_net (`ip_openbao`, default `10.255.0.90`), Raft storage in
`/opt/openbao/data`, TLS from Step-CA, every request in
`/opt/openbao/logs/audit.log` (secrets HMAC'd).

**Unlocking.** OpenBao uses the *static* seal with one **vault key**. The
key lives in one or more **unlock methods** (key slots, design §7c), listed
in `/etc/fabric/openbao/slots.json` (root, 0600, signed with the key).
A fresh install has one: a key file on this host (`local-<key id>.key`,
root 0400).

At every start, **fabric-unlock** (`fabricctl vault unlock`, the openbao
unit's `ExecCondition`) takes the key from any present method. It checks the
key against its check value and writes it to `/run/fabric/openbao/` (RAM,
openbao user, 0400). OpenBao reads it and unseals; once the container is
healthy the unit's `ExecStartPost` runs `fabricctl vault wipe-key`, which
overwrites and deletes that copy. With no method present, `vault unlock`
exits 1 and systemd does not start OpenBao at all, while DNS, LDAP, SSO and
nginx keep running. A power cut needs no human as long as a method is
present. Whoever holds this disk and a method holds the vault.

`vault unlock`, `vault wipe-key` and `vault device-event` are internal: the
openbao unit and the udev rules run them (as
`python3 /opt/fabric/lib/fabriclib/cli.py vault …`). Run by hand,
`sudo fabricctl vault unlock` says which method gave the key (with a warning
if the list of methods was changed while locked), or that none is present;
it does not start OpenBao.

| Command | What |
|---|---|
| `sudo fabricctl vault slots` | Unlock methods: present (●/○), id, type, key version, label, device, when last tested |
| `sudo fabricctl vault test <id>` | Unwrap the key through one method and verify it |
| `sudo fabricctl vault rotate --yes` | New vault key for every present method (the others are dropped); OpenBao restarts twice |
| `sudo fabricctl vault remove <id> --yes` | Remove a method (never the last one) |
| `sudo fabricctl vault add-usb /dev/sdX [--label NAME] --yes` | **Erase** a USB stick and make it an unlock method |

USB sticks can also be added in the web UI (OpenBao → Unlock methods →
Add a USB stick; needs a sign-in within the last 5 minutes and the host name
typed). Only a whole, unmounted USB disk is accepted. fabric formats it
(ext4, label `FABRIC-KEY`, a UUID fabric chooses), writes the key
(root 0400), reads it back and only then saves the method. A plain stick can
be copied by whoever holds it: if one goes missing, `vault rotate`.

**Kill switch.** udev rules (`/etc/udev/rules.d/90-fabric-unlock.rules`)
watch enrolled sticks. Pulling one runs `fabricctl vault device-event`,
which stops OpenBao when no method is left present; plugging it back in
starts it again. The key file on this host always counts as present, so the
kill switch only acts once that method is removed (`vault remove local --yes`,
after a stick or security key holds the current key).
*Tested with loop devices and by hand with a real stick on a Pi 5
(stopped about a second after the pull; unsealed about 10 s after re-plugging).*

**Security keys (PKCS#11).** YubiKey 5 (PIV), Nitrokey, SmartCard-HSM or
any token with a PKCS#11 library. An RSA-2048 key on the token that can
never be read out wraps the vault key (RSA-OAEP); only the ciphertext is in
`slots.json`. The token's PIN is kept root-only on the host
(`/etc/fabric/openbao/pin-<id>`, 0400), so the token is the factor: it
cannot be copied, unlike a stick.

| Command | What |
|---|---|
| `sudo fabricctl vault tokens` | Tokens the allowed libraries see, with PIN state (no login) |
| `sudo fabricctl vault add-key <serial> [--module LIB] [--key-id new\|HEX] [--label L] --yes` | Add one; the PIN is asked for (or read from stdin), never an argument. `--module` picks the library when two see the same serial |

- Needs `python3-pykcs11` (recommended by the package) and the token's
  library: `ykcs11` for YubiKey, `opensc-pkcs11` for most others, both with
  `pcscd`. Only libraries on `openbao_pkcs11_modules` are ever loaded.
- `new` makes a key pair on the token. Tokens that cannot make keys through
  PKCS#11 (YubiKey PIV) take an existing one: `ykman piv keys generate 9d …`
  (optionally `--touch-policy always`: a touch at every unlock, so after a
  power cut someone must touch it), then `--key-id 03`. A key that can be
  exported is refused.
- **PIN retries are protected.** fabric never uses a token's last PIN try,
  and after one wrong PIN an unattended start does not try the token again
  (a stale stored PIN costs one try, not the three a YubiKey allows).
  `sudo fabricctl vault test <id>` logs in once and clears it.
- The kill switch covers a token only when its USB serial matched at
  enrolment (the method's detail says so).

*Tested with SoftHSM2 (a software token). YubiKey, Nitrokey and smart cards
are untested.*

**Disk encryption** is yours to set up (fabric does not): the web UI's
OpenBao → Disk encryption page and [disk-encryption.md](disk-encryption.md)
show how to encrypt fabric's data volume with LUKS, unlocked by the same
YubiKey or USB stick.

**HSMs and key managers (KMIP).** Any KMIP server (CipherTrust, Fortanix,
Entrust KeyControl, IBM GKLM, Cosmian, …) with an active AES-256 key that
fabric's client may use for Encrypt/Decrypt. The device encrypts the vault
key (AES-256-CBC, a random IV per wrap; the result is checked against the
key's check value); the key never leaves it. fabric connects with mutual
TLS, the device's certificate verified against the CA you give.

| Command | What |
|---|---|
| `sudo fabricctl vault add-kmip <host:port> --key-id ID --ca ca.pem --cert client.pem --key client.key --yes` | Add one (`--server-name` if the certificate names another host, `--label`) |

- The client certificate: make one under Step-CA → New key + certificate,
  register it on the device, give it here. The files are kept root-only in
  `/etc/fabric/openbao/kmip-<id>/`.
- **Kill switch:** revoke fabric's client, or disable the key, on the
  device: the method stops unwrapping and fabric-unlock refuses.
- Needs `python3-pykmip` (recommended by the package). fabric makes the TLS
  connection itself: PyKMIP's own TLS code does not verify the server.

*Tested with the PyKMIP server. Vendor HSMs are untested.*

**First install.**
- `init` produces the **recovery key(s)**. They are written once to
  `~/fabric-admin/openbao-recovery-keys.txt` (0600) of the account that ran
  `sudo`. Store them offline and delete the file. They are needed for a new
  root token (`bao operator generate-root`) and for moving the seal, never
  to start OpenBao.
- The initial root token configures OpenBao once and is then **revoked**.
  From then on fabric uses two AppRoles. Their credentials are in
  `/etc/fabric/openbao/*-approle.json` (root, 0400), and their tokens and
  secret IDs work only from fabric_net, i.e. this host:

| AppRole | Used by | May |
|---|---|---|
| `fabric-setup` | `fabricctl setup` | engines, auth methods, policies, AppRoles; `fabric/*` |
| `fabric-agent` | fabric-agent (web UI) | list engines and auth methods; list `apps/` keys — no secret values |

| Mount | What |
|---|---|
| `fabric/` (KV v2) | fabric's own secrets: the entry `fabric/secrets` (see below) |
| `apps/` (KV v2) | secrets for your applications |

**People sign in to OpenBao's own UI with Keycloak** (when Keycloak is
installed): `https://vault.<domain>/ui` → method **OIDC** → Keycloak
(password + TOTP, the same flow as the web UI). The admin bundle gets the
`fabric-admin` policy below; the auditor bundle gets `fabric-auditor`
(application secrets listed with their history, never a value); other
bundles are refused:

| May | May not |
|---|---|
| everything under `apps/` (read, write, versions) | read or change fabric's own secrets (`fabric/`: listed only) |
| read engines, sign-in methods and policies | change policies, engines or sign-in methods |

fabric itself keeps full access to its secrets and health through its
AppRoles; on the host `sudo fabricctl secrets list` names them (TSIG secrets
as `tsig/<key>`) and `sudo fabricctl secrets show <name>` prints one — every
`show` is audited (the name, never the value). The web UI's OpenBao → Secrets page shows their state and
links to OpenBao's UI.

**Break glass** (Keycloak down, nobody can sign in):

| Command | What |
|---|---|
| `sudo fabricctl vault break-glass [--restart]` | Enter the recovery key(s) (asked, or on stdin, never as arguments): a root token, shown once, audited. `--restart` cancels an attempt already in progress |
| `sudo fabricctl vault revoke-token` | Paste it (or give it on stdin) to revoke it when done; fails if the token still works afterwards |

OpenBao 2.5.3+ disables the unauthenticated generate-root endpoints; fabric
keeps them off on the network and enables them only on a unix socket in
`/run/fabric/openbao-admin/` that only root on the host (and OpenBao) can
reach.

**fabric's own secrets live in OpenBao.** The generated passwords (CA,
rndc, LDAP role accounts, Keycloak, web UI OIDC) and every TSIG secret are
written to the plaintext `/opt/fabric/config/fabric-secrets.yml` only
during a fresh install. The `vault` step moves them into OpenBao (KV v2
`fabric/secrets`): it writes them, reads them back, compares, and only then
shreds the file and writes the marker `/opt/fabric/config/secrets.openbao`.

- **From then on** setup, `fabricctl tsig` and the web UI read and change
  them in OpenBao. Every change is a new KV version, so there is history,
  and concurrent changes are refused (check-and-set).
- **If OpenBao is locked,** anything that needs a secret stops with an
  error. It never treats "no file" as "no secrets", which would generate
  new passwords the running services don't know. Running services are not
  affected.
- **Do not create `fabric-secrets.yml` by hand:** while it exists it wins,
  and the next setup imports it.
- `fabricctl reinstall` exports a root-only copy into its backup
  (`/root/fabric-reinstall-<time>/`), and the reinstalled setup re-imports
  and shreds the copy it restored. The backup folder itself is left in
  place, plaintext secrets included: delete it once the reinstall works.

**What is still in plain files:** the configuration each service needs to
run (rendered LDIF, compose files, `named.conf.keys`, `rfc2136.ini`, the
web UI's OIDC config, Step-CA's password file). The planned protection for
those is disk encryption (design §7d).

**Boot independence.** No core service (DNS, LDAP, SSO, nginx, CA) needs
OpenBao to start. The sandbox test stops OpenBao and restarts BIND9 and
nginx to prove it.

**Commands.**
- `sudo fabricctl vault status` (also plain `fabricctl vault`): sealed?,
  version, unlock methods, secret engines, sign-in methods and the version
  of fabric's secrets. Exits 0 only when initialised and unsealed.
- `fabricctl doctor` checks that OpenBao is unsealed, the seal key's
  permissions, both KV mounts, and `vault.<domain>` through nginx.

**Backups.** Data without the key is unreadable; the key without the data
is useless. `fabricctl reinstall` keeps both. For your own backups, copy
`/opt/openbao/data` together with `/etc/fabric/openbao/` (the unlock methods), and keep them
apart from the recovery keys. `fabricctl uninstall` deletes both.

**If it stays locked.** No unlock method is present (`sudo fabricctl vault
unlock` says so): plug one in, or restore `/etc/fabric/openbao/` from your
backup, then `sudo systemctl start openbao`. Setup never generates a new key
next to existing data, because a new key cannot open the old vault.

## Resource Utilization

The following chart outlines the memory footprint and CPU impact of the deployed applications. When `host_ram_capacity` is 3 or 4 (GB), the compose files set memory limits: 389-DS `256M` at 3 GB / `384M` at 4 GB, BIND9 `40M` / `80M`, nginx `128M` / `256M`, webui `96M`. Keycloak gets `800M` at 3 GB and `1200M` × (GB ÷ 4) from 4 GB up. Without `host_ram_capacity` these limits are not set.

| Service | Startup (Peak RAM) | Idle (RAM) | Typical Usage | CPU Impact |
|---------|--------------------|------------|---------------|------------|
| Keycloak | 800MB – 1.2GB | 500MB – 700MB | 800MB – 1.2GB | High (during auth) |
| Postgres | 150MB | 80MB | 100MB – 200MB | Low |
| 389-DS | 150MB – 250MB | 60MB – 120MB | 100MB – 250MB | Very Low |
| webui (container) + fabric-agent (host) | 30MB + 20MB | 20MB – 30MB each | 20MB – 40MB each | Minimal |
| BIND9 | 60MB | 30MB – 40MB | 40MB – 80MB | Very Low |
| Nginx | 20MB | 5MB – 10MB | 15MB – 40MB | Very Low |
| Step-ca | 50MB | 15MB – 25MB | 30MB – 50MB | Minimal |

---

## Lifecycle Commands

Every `fabricctl` subcommand (Python, `fabricctl/lib/fabriclib/`; `sudo fabricctl --help` lists them). Setup and its steps are idempotent. See [install.md](install.md#run-the-installer) for setup's options and the step list.

| Command | What it does |
|---|---|
| `sudo fabricctl setup [--file vars.yaml]` | Install or re-converge. Re-run after changing settings. |
| `sudo fabricctl setup --step <name>` | Run one step, e.g. `--step firewall` after editing `security.firewall_allow` (`--list` shows the steps) |
| `sudo fabricctl status` | `fabric.target` and every unit: state and container health (changes nothing) |
| `sudo fabricctl start/stop/restart` | The whole stack through systemd `fabric.target`; prints the same table, then `fabric: <verb> done` |
| `sudo fabricctl doctor` | End-to-end checks of the running install (the `verify` step); exits 1 if any check fails |
| `sudo fabricctl tsig list/add/update/set-secret/rotate/remove` | TSIG keys for RFC2136 clients — see [TSIG Keys](#tsig-keys-rfc2136-dynamic-updates) |
| `sudo fabricctl acl list/add/remove/policy` | BIND ACLs and their update policies — see [ACLs](#acls) |
| `sudo fabricctl dhcp status/leases/reserve/unreserve` | DHCP (Kea) — see [DHCP](#dhcp-optional-kea) |
| `sudo fabricctl radius status/log/add-client/rotate-secret/remove-client/map-group/unmap-group` | 802.1X (FreeRADIUS) — see [802.1X](#8021x-optional-freeradius) |
| `sudo fabricctl logs status` / `logs set-password elastic` | Log forwarding (Fluent Bit) — see [Log forwarding](#log-forwarding-optional-fluent-bit) |
| `sudo fabricctl images status/update/rollback/prune` | Container images — see [`fabricctl images`](#fabricctl-images) |
| `sudo fabricctl federation status/enable/disable/invite/invitations/revoke/remove/reparent/relay` | Sites joining this install — see [Federation](#federation-sites) |
| `sudo fabricctl vault …` | OpenBao and its unlock methods — see [OpenBao](#openbao-secrets) |
| `sudo fabricctl secrets list` / `secrets show <name>` | fabric's own secrets (in OpenBao); `show` is audited |
| `sudo fabricctl client-cert <user> [--days N]` | Web UI client certificate for another admin (`~/fabric-admin/<user>.p12`, default 365 days) |
| `sudo fabricctl certs [--force]` | Renew service certificates (and `extra_certs`) that are missing, expiring within 30 days, missing a name or not from this CA (`--force`: all service certificates); restarts only the running services whose certificates changed |
| `sudo fabricctl reinstall [--yes]` | Uninstall + setup, keeping config, secrets, the CA, certificates and OpenBao (data and vault key). Directory users/groups and Keycloak's database are **not** kept; the first admin is re-created with a new login kit. Asks first unless `--yes` |
| `sudo fabricctl uninstall` | Remove fabric (asks: export all data to a folder you choose? purge the package too?); see [install.md](install.md#reinstall--uninstall) |
| `sudo fabricctl restore <folder> [--yes]` | Bring back a fabric exported by `uninstall --export` (or `apt purge`); see [install.md](install.md#reinstall--uninstall) |

`setup`, `reinstall`, `uninstall` and `restore` take `--deploy-base DIR` (as two words) for an install outside `/opt`; the package's `/usr/bin/fabricctl` runs every other command from `/opt/fabric`. An unknown command prints the list and exits 2.

---

## Service Ports

| Port | Proto | Handler | Backend |
|------|-------|---------|---------|
| 80 | TCP | nginx | health check · ACME passthrough · HTTPS redirect |
| 389 | TCP | nginx | `dirsrv:3389` (TCP passthrough; 389-DS requires StartTLS before bind) |
| 443 | TCP | nginx | `step-ca:9000` (`ca.<domain>`) · CA certificate page (`certs.<domain>`) · `bind9:8053` (`/dns-query`) · Keycloak · webui (`fabric.<domain>`, mTLS → `/opt/webui/run/web.sock`; the webui container publishes no ports, fabric-agent has no network listener) |
| 636 | TCP | nginx | `dirsrv:3636` (TCP passthrough; LDAPS terminated by 389-DS) |
| `bind_dns_port` | TCP + UDP | bind9 | DNS for the LAN (`host_ip:bind_dns_port` → container 53); default `53` |
| `bind9_doh_port` | TCP | bind9 | plain-HTTP DoH; default `8053` |
| `stepca_port` | TCP | step-ca | internal HTTPS; default `9000` |
| 67 | UDP | kea-dhcp4 (host network) | DHCP; only with `install_kea`, only on the DHCP interfaces |
| 1812, 1813 | UDP | freeradius | RADIUS authentication and accounting; only with `install_freeradius` |

`bind9_doh_port` and `stepca_port` are reached through nginx on fabric_net; they are not published on the host. OpenBao (`vault.<domain>`) is also behind nginx on 443.

> `bind_dns_port` (default `53`) is the Docker host port mapped to BIND9's internal port 53 (`host_ip:bind_dns_port:53`). BIND9 only listens on port 53 inside the container; Docker forwards host traffic on `bind_dns_port` to it. Change it only if another DNS server must keep port 53 on `host_ip`.
