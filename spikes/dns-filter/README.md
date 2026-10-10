# spikes/dns-filter

The spike for 2.1.12.3 (manual 2.3.12.1, Q8): BIND 9.20 as fabric's filtering resolver, before 0.7 is built.
Throwaway (global Rule 4); its findings are recorded in the manual, 2.3.12.1.16.

| File | What |
|---|---|
| `fetch.sh` | Fetch AdGuard's list catalogue (HostlistsRegistry `filters.json`) and every list in it, convert each, summarise |
| `convert.py` | Convert a published list (hosts, domains, AdGuard DNS syntax) into a response policy zone; counts what it skips |
| `samples.sh` | Print sample rules the converter skipped, by reason |
| `run.sh` | Authoritative BIND, the filtering resolver and three clients in Docker; 22 checks. `MODE=copy` (each group view loads the lists) or `MODE=chain` (group views forward to the main view) |
| `measure.sh` | The resolver's memory and load time by number of views and lists |

```bash
bash spikes/dns-filter/fetch.sh
```

```bash
MODE=chain bash spikes/dns-filter/run.sh 1
```

```bash
bash spikes/dns-filter/measure.sh 1: 1:1 2:1 4:1 1:5 1:48
```

Work folder: `~/fabric-spike-dns` (lists, zones, configs; nothing secret). Needs Docker and internet access
(Cloudflare, the lists).
