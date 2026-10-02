# Design: joining Linux machines to the domain

Status: **being built** — step 1 (POSIX identities) and step 2 (M5 directory replication) done (owner request 2026-10-02). Milestone M10 of [federation.md](federation.md) §8a, built together with M5.

## 1. Where it stands

fabric publishes an Ubuntu client installer, `https://ldap.<domain>/install-ldap.sh`
(`jinja/nginx/www/ldap/install-ldap.sh.j2`): it installs the root CA, configures SSSD against 389-DS over
LDAPS and enables home-directory creation. The directory lets SSSD read the POSIX name-service attributes
anonymously over TLS (never passwords; `30-aci.ldif`). DNS, the CA and time (M9, handed out by DHCP) are
the other basics a client needs.

It does **not** make a working join today:

| # | Gap | Effect |
|---|---|---|
| G1 | No user has a POSIX identity: nothing sets `posixAccount` (`uidNumber`, `gidNumber`, `homeDirectory`, `loginShell`); Keycloak creates plain `inetOrgPerson` entries | `id alice` on a client finds nobody — **blocker** |
| G2 | No access control: every directory person may log in to every joined machine | Too broad for any real use |
| G3 | No sudo rules in the directory (no `sudoRole` schema) | Admin rights cannot be managed centrally |
| G4 | The installer fetches the root CA over plain HTTP and trusts it without a fingerprint check | Someone on the LAN can substitute their own CA — **security** |
| G5 | No machine identity: no enrolment, no machine account, no central list or removal of joined machines | Cannot see or revoke what joined |
| G6 | No Kerberos: no `realm join`, no single sign-on ticket; logins send the password to LDAP | No SSO; passwords cross the network (inside TLS) on every login |
| G7 | No second factor for console or SSH logins (TOTP protects the web sign-ins only) | Weaker than the web UI |
| G8 | `enumerate = true`; the client's time and DNS are left to DHCP; password changes from the client not set up | Scale and convenience |
| G9 | No test exercises the installer | How G1 went unnoticed |

## 2. Plan (built together with federation M5, owner decision 2026-10-02)

Domain join is mostly directory features, and M5 is what spreads the directory across sites: IDs must be
unique across the federation (assigned where people are created, the root site, and replicated down); a
joined machine asks its own site's copy (logins keep working while the root is away); login and sudo rules
are directory entries (organisation-wide or site-scoped groups); enrolled machines live in their site's
part (replicated up). So one milestone, in this order:

**Step 1 — POSIX identities.** Every person gets `posixAccount` + a private group: `uidNumber` from the
range of their OU (`ldap_organizational_units[].uid_range`, already a setting, unused), never reused
(a high-water mark in the directory, so a deleted person's number is not handed out again);
`homeDirectory /home/<uid>`, `loginShell /bin/bash`. Added when Keycloak or `fabricctl` creates a person,
and once for existing people on upgrade. Directory groups that should exist on machines get `posixGroup`
+ `gidNumber` from a group range. Assigned only where people are created (the root site's organisation
part); works on a standalone install.

**Step 2 — M5 replication** (federation.md §3.2): the organisation part to every site read-only; each
site's part up to its parent; each site's Keycloak read-only for people; sharing between sites by consent
(F3, below). *Done* except the consent sharing, which follows step 5: how it is built is in
federation.md §3.2a.

**Step 3 — join basics:**

- **Host groups carry the policy** (owner decision J1, 2026-10-02): a machine's entry lives in its site's
  part (`ou=machines,ou=<site>,<base>`: which site owns it, who administers it, replicated up), and it is a
  member of one or more **host groups** (`web-servers`, `lab-machines`, site-scoped ones such as
  `lab-web-servers`). **Rules** name which groups or people may log in to which host groups, and which may
  use sudo there; a machine's rights are the sum of its host groups'. A new machine lands in a default
  host group that allows `fabric-admins` only. fabric writes the rules into what SSSD already reads — each
  person's allowed hosts (`host`, SSSD `ldap_access_order = host`) and `sudoRole` entries — so a change takes
  effect at the next login without touching the machines.
- **sudo from the directory:** the `sudoRole` schema in 389-DS and SSSD's sudo provider.
- **A trusted installer:** `curl https://…` with the CA pinned by the fingerprint shown on `certs.<domain>`
  (the federation join already works this way); no plain-HTTP trust anchor.
- **Client basics:** `enumerate = false`, a cache that survives the server being down, chrony pointed at
  `ntp.<domain>`, `resolved` at the site's DNS, `passwd` through LDAP's password modify operation (sent to
  the root site: people are written only there).
- **Tests:** a real Ubuntu container joins a sandbox site: `id`, an SSH login, sudo allowed for an admin and
  refused for others, a login refused outside the OU's groups, the installer refusing a wrong CA
  fingerprint, and logins still working with the root site unreachable.

**Step 4 — machine enrolment:** `fabricctl hosts enroll [--group <host-group>…]` (and the web UI) gives a machine a
one-time token; the installer exchanges it for a host entry in the site's part, a host certificate from the
site's Step-CA (also for SSH host keys) and its own bind account. Machines are then listed, put into and taken out of
host groups and removed centrally; removal unlinks the certificate. Visible upstream through M5.

**Step 5 — Kerberos single sign-on** (owner decision J2: planned): an MIT KDC with its principals in 389-DS
(the kldap backend, FreeIPA-style), so they replicate with M5 and **every site runs its own KDC** reading
its local copy (tickets keep working while the root is away). One realm for the organisation
(`<ORG_DOMAIN>` upper-cased); enrolment (step 4) creates the host principal and keytab; `realm join`-style
client setup through SSSD's krb5 provider; SSH with GSSAPI; later Keycloak's Kerberos bridge for web SSO.
Password changes (kpasswd) go to the root site, where people are written. Design to be detailed before
building: key storage (master key per KDC, from OpenBao), clock skew (M9 keeps it under Kerberos' 5
minutes), DNS SRV records for the KDCs.

**Later:** TOTP for SSH/console (PAM with the person's existing TOTP, or SSH certificates issued after a
web sign-in with TOTP); Windows and macOS clients.

## 3. Decisions

| # | Question | Decision |
|---|---|---|
| J1 | Default login policy on a joined machine | **Decided 2026-10-02**: by host groups and rules (a machine may be in several; its OU is only where it lives); a new machine allows `fabric-admins` only |
| J2 | Kerberos | **Decided 2026-10-02**: planned (step 5), a KDC per site on the replicated directory |
| J3 | UID/GID ranges | Per OU as configured; assigned at the root site only (unique organisation-wide) |
