#!/bin/bash
# Spike (manual 2.3.12.1): fetch AdGuard's list catalogue (HostlistsRegistry) and every list in it, then convert each
# to a response policy zone with convert.py and summarise what was converted and skipped.
#     bash spikes/dns-filter/fetch.sh            work folder: ~/fabric-spike-dns (kept between runs; nothing secret)
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=${SPIKE_DIR:-$HOME/fabric-spike-dns}
mkdir -p "$W/lists" "$W/zones"
cd "$W" || exit 1

curl -fsS --max-time 60 -o filters.json https://adguardteam.github.io/HostlistsRegistry/assets/filters.json || exit 1
python3 - <<'EOF' > urls.tsv
import json
for f in json.load(open("filters.json"))["filters"]:
    print(f"{f['filterId']}\t{f['downloadUrl']}\t{f['name']}")
EOF

while IFS=$'\t' read -r id url name; do
    [ -s "lists/$id.txt" ] && [ -z "${REFETCH:-}" ] && continue
    curl -fsS --max-time 120 -o "lists/$id.txt" "$url" || echo "fetch failed: $id $name"
done < urls.tsv

: > summary.jsonl
while IFS=$'\t' read -r id url name; do
    [ -s "lists/$id.txt" ] || continue
    python3 "$HERE/convert.py" "lists/$id.txt" "list$id.rpz" "zones/list$id.rpz" >> summary.jsonl
done < urls.tsv

python3 - <<'EOF'
import json, collections
names = {l.split("\t")[0]: l.split("\t")[2].strip() for l in open("urls.tsv")}
total = collections.Counter()
print(f"{'list':<52}{'lines':>9}{'blocks':>9}{'allows':>8}{'records':>9}{'skipped':>9}  top skip reasons")
for line in open("summary.jsonl"):
    s = json.loads(line)
    i = s["zone"][4:-4]
    total.update(s["skipped_by_reason"])
    top = ", ".join(f"{k} {v}" for k, v in sorted(s["skipped_by_reason"].items(), key=lambda kv: -kv[1])[:2])
    print(f"{i+' '+names[i][:46]:<52}{s['lines']:>9}{s['blocks']:>9}{s['allows']:>8}{s['rpz_records']:>9}"
          f"{s['skipped']:>9}  {top}")
print("skipped, all lists:", dict(total.most_common()))
EOF
