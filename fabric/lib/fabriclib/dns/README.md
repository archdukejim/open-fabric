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
