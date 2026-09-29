# Operations

## Live Configuration Changes (`fabricctl`)

Use `fabricctl` (the global wrapper powered by the interactive Python engine) for post-install changes to DNS records, TSIG keys, certificates, and infrastructure variables — no full redeploy needed. Run it **on the target machine** (requires root / sudo). The same DNS and apply operations are also available in the browser through webui — see [webui.md](webui.md).

### Table of Contents
- [Live Configuration Management (`fabricctl`)](#live-configuration-management-fabricctl)
  - [`--interactive`](#--interactive)
  - [`--print`](#--print)
  - [`--apply`](#--apply)
  - [`fabricctl images`](#fabricctl-images) (was `--update-containers`)
  - [`--version`](#--version)
  - [`--client-cert <user>`](#--client-cert-user)
  - [`--keycloak-sync`](#--keycloak-sync)
- [Interactive Menu Categories](#interactive-menu-categories)
  - [DNS Configuration](#dns-configuration)
  - [Mint Certificates](#mint-certificates)
  - [TSIG Keys (RFC2136)](#tsig-keys-rfc2136-dynamic-updates)
  - [ACLs](#acls)
  - [Landing Page Links](#landing-page-links)
- [Lifecycle Commands](#lifecycle-commands)
- [Service Ports](#service-ports)

---

### Live Configuration Management (`fabricctl`)

The infrastructure variables defined in `vars.yaml` can be managed directly via `fabricctl` using the interactive menu system or by editing the YAML manually. 

#### `--interactive`
Launch the interactive configuration menu. This will display categories of variables in `vars.yaml`, allowing you to select and modify them one by one. Immutable variables are protected from modification to prevent breaking the deployment. Changes are audit-logged, and applying changes to network variables will prompt a warning before restarting services.

```bash
sudo fabricctl --interactive
```

#### `--print`
Print the current contents of `vars.yaml` in a colorized, human-readable format.

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

#### `fabricctl images`
Every container image is pinned by digest (amd64 + arm64). The validated
list is `fabric/images.lock.yaml` of the installed fabric. **A fabric
upgrade never changes a running image**: `fabricctl setup` keeps what each
host runs; these commands move it.

| Command | What |
|---|---|
| `sudo fabricctl images status` | Each service: what it runs, the validated image, `current` / `update available` / `held (set by the admin)` |
| `sudo fabricctl images update <service…>` or `--all` | Move to the validated images |
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
Print the version from `fabric/VERSION` plus the build stamp in `fabric/BUILD` (git commit, `-dirty` if the tree had local changes, and UTC build time — written by `setup.sh` on each run).

```bash
sudo fabricctl --version
```

#### `--client-cert <user>`
Mint a webui admin client certificate (same as `fabricctl client-cert <user>`). The CN is `<user>` and **must equal the Keycloak username**. Issued offline by the Step-CA intermediate (RSA 3072, `webui_client_cert_days`, default 365), bundled with the chain into `~/fabric-admin/<user>.p12` (home of the account that ran `sudo`, mode `0600`) with a generated password that is shown once. The private key exists only inside the `.p12`. Setup already does this for the first admin — see [webui.md](webui.md#first-time-setup).

```bash
sudo fabricctl --client-cert jdoe
```

#### `--keycloak-sync`
Re-run `keycloak_bootstrap.py`: realm, LDAP federation to 389-DS, group mapper and sync, `fabric-admin` role → `admins` group, the `fabric-webui` OIDC client and its TOTP flow. Idempotent — use after changing `webui_*` vars or to repair drift made in the admin console.

```bash
sudo fabricctl --keycloak-sync
```

---

### Interactive Menu Categories

All granular modifications are now managed within the unified `--interactive` menu system rather than via individual command-line flags. 

#### DNS Configuration

Add, modify, or remove records in BIND9 zones without a full redeploy via the interactive menu. Supported record types include `A`, `AAAA`, `CNAME`, `MX`, `TXT`, and `SRV`.

**DNS Sync Status & Actions:**
When entering a specific zone, the menu compares the serial BIND9 is serving (`rndc zonestatus`) with the serial in the deployed `db.<zone>` file:
- `IN SYNC (serial N)`: BIND9 serves the deployed file (or newer, e.g. after dynamic updates).
- `OUT OF SYNC (serving serial N, file has M; run 'l')`: the file on disk is newer than what BIND9 serves.
- `NOT LOADED in BIND9` / `? BIND9 not reachable`: the zone failed to load or the container is down.

Records are listed with their full value (`A`/`AAAA` ip, `CNAME` target, `MX` priority + exchange, `TXT` text, `SRV` priority/weight/port/target). Records without a name (or named `None`) are shown as `(missing name)`, rejected on entry, and filtered out at render time.

You have two powerful options to apply your pending `vars.yaml` modifications directly from the menu:
- **`l` (Live update):** Runs the same apply as `fabricctl --apply`: each changed zone is frozen, its file swapped, the `.jnl` removed and the zone thawed. *Non-disruptive to DNS resolution.*
- **`f` (Force update):** Stops BIND9, deletes `db.<zone>` and its `.jnl`, then runs the apply, which rewrites the zone and starts BIND9 again. *Warning: Disruptive — DNS is down while it runs.*

Changes edit `vars.yaml` and re-render forward and reverse zone files natively using Jinja2. Rendered files are written to `/opt/bind9/data/` with bind ownership. **Reverse zones are auto-generated** based on `/24` subnets found in `A` records.

`dns:` zone key uses the actual domain string (the `dynamic_zone_var` placeholder is already resolved to `domain` at install time):

```yaml
dns:
  yourdomain.internal:
    zone_authority: true    # emit NS A record pointing to host_ip
    tsig: acme_dns-01
    A:
    - { name: myserver, ip: 10.0.3.99 }
    CNAME:
    - { name: app, canonical: myserver }
    TXT:
    - { name: myserver, text: "v=spf1 -all" }
```

#### Mint Certificates

Mint offline or ACME-based TLS certificates for services outside this stack (NAS apps, VMs, etc.) via the interactive menu. `vars.yaml` structure for extra certificates:

```yaml
extra_certs:
- cn: nas-apps.internal
  sans: [jellyfin.internal, sonarr.internal]
  days: 365
  kty: RSA           # RSA | EC | OKP  (default: RSA)
  size: 4096         # RSA: 2048/3072/4096  EC: 256/384  (default: 4096)
  out_dir: /srv/certs
```

**Offline mode:** signed directly by Step-CA using the internal `leaf.tpl` x509 template — no ACME required.

**ACME mode:** issued via Step-CA's ACME provisioner with DNS-01 validation against BIND9 using the primary TSIG key. All core service certs (`dns.internal`, `ldap.internal`, `ca.internal`) are offline Step-CA certs issued at install time.

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

Every change updates the vars and secrets and applies at once: BIND reloads its configuration, and apply fails loudly if BIND rejects it. `--no-apply` records a change without applying (batch several, then `fabricctl --apply`). A secret is never taken on the command line: `--secret-file` or `--secret-prompt`.

#### ACLs

`bind_acls` are named BIND address match lists; each may query fabric's zones (`allow-query`). `dns-resolvers` (loopback, the LAN, fabric's Docker subnet) and `acme-updaters` are built in and cannot be removed; `tsig-updaters` always lists every TSIG key.

```bash
sudo fabricctl acl list
sudo fabricctl acl add lab 192.168.50.0/24 10.9.9.9 'key npm' '!192.168.50.7'
sudo fabricctl acl remove lab 10.9.9.9       # one entry
sudo fabricctl acl remove lab                # the whole ACL
```

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

At every start, **fabric-unlock** (the openbao unit's `ExecCondition`) takes
the key from any present method. It checks the key against its check value
and writes it to `/run/fabric/openbao/` (RAM, openbao user, 0400). OpenBao
reads it and unseals, and the unit's `ExecStartPost` wipes it. With no
method present, systemd does not start OpenBao at all, while DNS, LDAP, SSO
and nginx keep running. A power cut needs no human as long as a method is
present. Whoever holds this disk and a method holds the vault.

| Command | What |
|---|---|
| `sudo fabricctl vault slots` | Unlock methods: present?, type, key version, what it was tested against |
| `sudo fabricctl vault test <id>` | Unwrap the key through one method and verify it |
| `sudo fabricctl vault rotate --yes` | New vault key for every present method (the others are dropped); OpenBao restarts twice |
| `sudo fabricctl vault remove <id> --yes` | Remove a method (never the last one) |

| `sudo fabricctl vault add-usb /dev/sdX --label NAME --yes` | **Erase** a USB stick and make it an unlock method |

USB sticks can also be added in the web UI (OpenBao → Unlock methods →
Add USB stick; needs a sign-in within the last 5 minutes and the host name
typed). Only a whole, unmounted USB disk is accepted. fabric formats it
(ext4, label `FABRIC-KEY`, a UUID fabric chooses), writes the key
(root 0400), reads it back and only then saves the method. A plain stick can
be copied by whoever holds it: if one goes missing, `vault rotate`.

**Kill switch.** udev rules (`/etc/udev/rules.d/90-fabric-unlock.rules`)
watch enrolled sticks. Pulling one runs `fabricctl vault device-event`,
which stops OpenBao when no method is left present; plugging it back in
starts it again. *Tested with loop devices and by hand with a real stick on a Pi 5
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
| `sudo fabricctl vault add-key <serial> [--key-id new\|HEX] [--label L] --yes` | Add one; the PIN is asked for (or read from stdin), never an argument |

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
are untested.* HSMs (KMIP) are shown in the web UI but not built yet.

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
(password + TOTP, the same flow as the web UI). Only holders of the web UI
admin role get in; they get the `fabric-admin` policy:

| May | May not |
|---|---|
| everything under `apps/` (read, write, versions) | read or change fabric's own secrets (`fabric/`: listed only) |
| read engines, sign-in methods and policies | change policies, engines or sign-in methods |

fabric itself keeps full access to its secrets and health through its
AppRoles; on the host `sudo fabricctl secrets show` stays the way to read
them (audited). The web UI's OpenBao → Secrets page shows their state and
links to OpenBao's UI.

**Break glass** (Keycloak down, nobody can sign in):

| Command | What |
|---|---|
| `sudo fabricctl vault break-glass` | Enter the recovery key(s) (asked, or on stdin, never as arguments): a root token, shown once, audited |
| `sudo fabricctl vault revoke-token` | Paste it to revoke it when done |

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
- `fabricctl reinstall` exports a root-only copy into its backup, and the
  reinstalled setup re-imports and shreds it.

**What is still in plain files:** the configuration each service needs to
run (rendered LDIF, compose files, `named.conf.keys`, `rfc2136.ini`, the
web UI's OIDC config, Step-CA's password file). The planned protection for
those is disk encryption (design §7d).

**Boot independence.** No core service (DNS, LDAP, SSO, nginx, CA) needs
OpenBao to start. The sandbox test stops OpenBao and restarts BIND9 and
nginx to prove it.

**Commands.**
- `sudo fabricctl vault status`: sealed?, version, seal key state, engines.
  Exits 0 only when unsealed.
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

The following chart outlines the memory footprint and CPU impact of the deployed applications. When `host_ram_capacity` is set to a value between 3 and 4, the infrastructure automatically enforces Docker Compose memory constraints (389-DS: `256M` at 3 GB, `384M` at 4 GB; webui: `96M`) to prevent these services from exceeding the host's physical memory boundaries.

| Service | Startup (Peak RAM) | Idle (RAM) | Typical Usage | CPU Impact |
|---------|--------------------|------------|---------------|------------|
| Keycloak | 800MB – 1.2GB | 500MB – 700MB | 800MB – 1.2GB | High (during auth) |
| Postgres | 150MB | 80MB | 100MB – 200MB | Low |
| 389-DS | 150MB – 250MB | 60MB – 120MB | 100MB – 250MB | Very Low |
| webui (container) + fabric-agent (host) | 30MB + 20MB | 20MB – 30MB each | 20MB – 40MB each | Minimal |
| AdGuardHome | 100MB | 30MB – 50MB | 60MB – 120MB | Low (sustained) |
| BIND9 | 60MB | 30MB – 40MB | 40MB – 80MB | Very Low |
| Nginx | 20MB | 5MB – 10MB | 15MB – 40MB | Very Low |
| Step-ca | 50MB | 15MB – 25MB | 30MB – 50MB | Minimal |

---

## Lifecycle Commands

Install, repair and removal are `fabricctl` subcommands (Python, `fabric/lib/fabriclib/setup/`). All are idempotent. See [install.md](install.md#run-the-installer) for options and the step list.

| Command | What it does |
|---|---|
| `sudo fabricctl setup [--file vars.yaml]` | Install or re-converge. Re-run after changing settings. |
| `sudo fabricctl setup --step <name>` | Run one step, e.g. `--step firewall` after editing `security.firewall_allow` |
| `sudo fabricctl status/start/stop/restart` | The whole stack through systemd `fabric.target` |
| `sudo fabricctl doctor` | End-to-end checks of the running install (the `verify` step) |
| `sudo fabricctl tsig list/add/update/set-secret/rotate/remove` | TSIG keys for RFC2136 clients — see [TSIG Keys](#tsig-keys-rfc2136-dynamic-updates) |
| `sudo fabricctl acl list/add/remove` | BIND ACLs — see [ACLs](#acls) |
| `sudo fabricctl client-cert <user>` | Web UI client certificate for another admin (`~/fabric-admin/<user>.p12`) |
| `sudo fabricctl certs [--force]` | Renew service certificates that are missing, expiring within 30 days or missing a name (`--force`: all of them); restarts only the services whose certificates changed |
| `sudo fabricctl reinstall` | Uninstall + setup, keeping config, secrets, the CA and certificates. Directory users/groups and Keycloak's database are **not** kept; the first admin is re-created with a new login kit |
| `sudo fabricctl uninstall` | Remove fabric (asks: export all data to a folder you choose? purge the package too?); see install.md |

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

> `bind_dns_port` (default `53`) is the Docker host port mapped to BIND9's internal port 53 (`bind_dns_port:53`). BIND9 only listens on port 53 inside the container; Docker forwards host traffic on `bind_dns_port` to it. The default port is 53 natively, allowing BIND9 to answer standard DNS queries directly. If you install the `home-core` add-on, this port is shifted to `5353` automatically to allow AdGuard Home to claim port 53 instead.
