# Design: joining Linux machines to the domain

Status: **planned** (owner request 2026-10-02). Milestone M10 of [federation.md](federation.md) §8a.

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

## 2. Plan

**Step 1 — the basics (one milestone):**

- **POSIX identity for people.** Every person gets `posixAccount` + a private group: `uidNumber` from the
  range of their OU (`ldap_organizational_units[].uid_range`, already a setting, unused), never reused;
  `homeDirectory /home/<uid>`, `loginShell /bin/bash`. Added when Keycloak or `fabricctl` creates a person,
  and once for existing people on upgrade. Directory groups that should exist on machines get
  `posixGroup` + `gidNumber` from a group range. Federation: the organisation's ranges are the root site's
  (people come from it, M5).
- **Who may log in where.** Login is allowed to members of named directory groups per host or host group
  (`ldap_access_filter` / SSSD `simple` access), default: `fabric-admins` only. Kept in the directory so
  the web UI can manage it later.
- **sudo from the directory.** The `sudoRole` schema in 389-DS and SSSD's sudo provider; default rule:
  `fabric-admins` on all joined hosts.
- **A trusted installer.** `curl https://…` with the CA pinned by fingerprint shown on `certs.<domain>`
  (the federation join already works this way); the script checks the fingerprint before trusting
  anything. No plain-HTTP trust anchor.
- **Client basics.** `enumerate = false`, a cache that survives the server being down, the client's
  chrony pointed at `ntp.<domain>`, `resolved` pointed at the site's DNS, `passwd` through LDAP's password
  modify operation.
- **Tests.** A real Ubuntu container joins a running sandbox install: `id`, an SSH login, sudo allowed for
  an admin and refused for others, a login refused for someone outside the allowed groups, and the
  installer refusing a wrong CA fingerprint.

**Step 2 — machine enrolment:** `fabricctl hosts enroll` (and the web UI) gives a machine a one-time token;
the installer exchanges it for a host entry in the site's part of the directory, a host certificate from
Step-CA (also usable for SSH host keys) and its own bind account. Machines are then listed, put into host
groups (login and sudo rules) and removed centrally; removal unlinks the certificate.

**Step 3 — Kerberos / single sign-on (decision for the owner):** a KDC backed by 389-DS (FreeIPA-style),
`realm join`, tickets for SSH and web. Large; worth it only if SSO between Linux machines is wanted.

**Later:** TOTP for SSH/console (PAM with the person's existing TOTP, or SSH certificates issued after a
web sign-in with TOTP); Windows and macOS clients.

## 3. Decisions for the owner

| # | Question | Proposal |
|---|---|---|
| J1 | Default login policy on a joined machine | `fabric-admins` only; other groups added per host group |
| J2 | Kerberos (Step 3) | Decide after Step 2; SSH certificates may cover most of the SSO need |
| J3 | UID/GID ranges | Per OU as configured; organisation-wide when federated |
