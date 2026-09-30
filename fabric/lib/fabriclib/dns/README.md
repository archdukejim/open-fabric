# fabriclib/dns

DNS zones and records as stored in `vars.yaml` (`dns:`), used by fabric-agent
(web UI) and the `fabricctl --interactive` editor alike. Publishing happens
through apply (`deploy.py`), which reloads only changed zones.

| File | What |
|---|---|
| `constants.py` | Supported record types |
| `zone_name.py` | Zone key → zone name (`dynamic_zone_var` is the main domain) |
| `validate_record.py` | Build a record dict from user input, rejecting anything unsafe for a zone file |
| `format_value.py` | Human-readable right-hand side of a record (as rendered in the zone file) |
| `sync_status.py` | Serial BIND is serving vs. the deployed zone file |
| `list_zones.py` | Zones with record counts (flagging hand-written reverse zones) |
| `ptr_for_ip.py` | Reverse zone and PTR label for an address — or why it gets none (public, loopback, link-local) |
| `reverse_zones.py` | Reverse zones + PTRs generated from all forward A/AAAA records (one per address); used by apply and the web UI |
| `zone_detail.py` | One zone's records (A/AAAA with their automatic PTR) and sync status |
| `add_record.py` | Validate and add a record (locked, audited) |
| `remove_record.py` | Remove a record, refusing if it changed since it was shown (locked, audited) |
| `normalize_tsig_keys.py` | Validate `tsig_keys`, fill defaults, take embedded secrets out (they belong in `fabric-secrets.yml`) |
| `add_tsig_key.py` | Add a TSIG key (new or existing secret) to vars + secrets (locked, audited) |
| `remove_tsig_key.py` | Remove a TSIG key and its secret (locked, audited) |
| `list_tsig_keys.py` | TSIG keys with their effective update rights (own + ACL policies) and ACLs |
| `replace_tsig_secret.py` | Give a key a secret you supply, or a newly generated one (locked, audited) |
| `update_tsig_key.py` | Change what a key may update: records, types, zone, algorithm (locked, audited) |
| `rfc2136_settings.py` | The `rfc2136.ini` text a certbot-style client needs for one key (used by apply and the web UI) |
| `create_zone_tsig_key.py` | Web UI: a new key limited to one forward zone and one scope (listed hosts' ACME, zone ACME, any name + types) |
| `rotate_tsig_key.py` | New generated secret for a key, returned with its `rfc2136.ini` |
| `run_tsig_command.py` | `fabricctl tsig list/add/update/set-secret/rotate/remove` (applies after a change) |
| `set_key_acls.py` | Put a TSIG key in ACLs or take it out (of all, when the key is removed) |
| `builtin_acls.py` | The ACLs fabric always renders (protected from removal) |
| `add_acl_entries.py` | Create a BIND ACL or add validated entries (IP, CIDR, `key <tsig>`, ACL, built-ins, `!`) |
| `remove_acl_entries.py` | Remove ACL entries or a whole ACL (built-ins protected) |
| `normalize_acl_policies.py` | Validate ACL update policies (hosts or any name, record types, zone) |
| `set_acl_policy.py` | Set or clear the update policy every TSIG key in an ACL inherits (locked, audited) |
| `run_acl_command.py` | `fabricctl acl list/add/remove/policy` (applies after a change) |
