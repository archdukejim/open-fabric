# jinja/dirsrv/seed

LDIF templates rendered by `deploy.py` to `/opt/dirsrv/seed/<name>.ldif`
(root:ldap 0640, mounted read-only at `/seed`) and applied in name order by
`seed.py` (`lib/dirsrv.sh seed`) on every deploy: missing entries are added,
changed attributes replaced, nothing else touched.

| File | What |
|---|---|
| `00-config.ldif.j2` | Server hardening under cn=config: secure binds and SSF 56 (TLS/LDAPI), password policy (PBKDF2-SHA512, length, lockout), TLS 1.2 minimum, the memberOf and entryUUID plugins (a change here restarts `ldap`) |
| `05-schema.ldif.j2` | fabric's schema: device classes (fabricDevice, MAC, certificate fingerprints) and fabricRole (permissions, VLAN, priority); added by OID, once |
| `10-tree.ldif.j2` | The suffix, the organizational units from `ldap_organizational_units` and the groups from `ldap_groups`; only added when missing |
| `20-accounts.ldif.j2` | Role and service accounts under ou=admins of the local suffix; passwords from fabric's secrets, re-applied every deploy |
| `30-aci.ldif.j2` | Every ACI on the suffix (`replace`: hand-added ACIs on the base entry are removed); default deny |
