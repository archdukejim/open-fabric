#!/bin/bash
# Spike helper: print sample rules convert.py skipped from the given lists, by reason (manual 2.3.12.1).
#     bash spikes/dns-filter/samples.sh 1 56 59 71
HERE=$(cd "$(dirname "$0")" && pwd)
W=${SPIKE_DIR:-$HOME/fabric-spike-dns}
for id in "$@"; do
    echo "== list $id"
    python3 - "$HERE" "$W/lists/$id.txt" <<'EOF'
import sys, collections
sys.path.insert(0, sys.argv[1])
import convert
seen = collections.defaultdict(list)
for line in open(sys.argv[2], encoding="utf-8", errors="replace").read().splitlines():
    _, skipped = convert.parse([line])
    for reason in skipped:
        if len(seen[reason]) < 6:
            seen[reason].append(line.strip())
for reason, lines in seen.items():
    print(f"  {reason}:")
    for l in lines:
        print(f"    {l[:110]}")
EOF
done
