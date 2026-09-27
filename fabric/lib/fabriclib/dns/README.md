# fabriclib/dns

DNS zones and records as stored in `vars.yaml` (`dns:`), used by fabricd
(web UI) and the `fabricctl --interactive` editor alike. Publishing happens
through apply (`deploy.py`), which reloads only changed zones.

| File | What |
|---|---|
| `constants.py` | Supported record types |
| `zone_name.py` | Zone key → zone name (`dynamic_zone_var` is the main domain) |
| `validate_record.py` | Build a record dict from user input, rejecting anything unsafe for a zone file |
| `format_value.py` | Human-readable right-hand side of a record (as rendered in the zone file) |
| `sync_status.py` | Serial BIND is serving vs. the deployed zone file |
| `list_zones.py` | Zones with record counts |
| `zone_detail.py` | One zone's records and sync status |
| `add_record.py` | Validate and add a record (locked, audited) |
| `remove_record.py` | Remove a record, refusing if it changed since it was shown (locked, audited) |
| `normalize_tsig_keys.py` | Validate `tsig_keys`, fill defaults, take embedded secrets out (they belong in `fabric-secrets.yml`) |
| `add_tsig_key.py` | Add a TSIG key (new or existing secret) to vars + secrets (locked, audited) |
| `remove_tsig_key.py` | Remove a TSIG key and its secret (locked, audited) |
| `list_tsig_keys.py` | TSIG keys and what each may update |
| `run_tsig_command.py` | `fabricctl tsig list/add/remove` (applies after a change) |
