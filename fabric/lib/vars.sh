#!/bin/bash
# YAML mutation helpers — source this file, do not execute directly.

# -----------------------------------------------------------------------
# _vars_list_append <key> <json_entry>
# Append an entry to a top-level YAML list in custom-vars.yaml.
# Tries ruamel.yaml first (preserves comments), falls back to PyYAML.
# -----------------------------------------------------------------------
_vars_list_append() {
    local key="$1" json_entry="$2"
    VARS_KEY="$key" VARS_ENTRY="$json_entry" VARS_FILE="$VARS_FILE" \
    python3 - <<'PYEOF'
import json, os
key = os.environ['VARS_KEY']
entry = json.loads(os.environ['VARS_ENTRY'])
vars_file = os.environ['VARS_FILE']
try:
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedSeq
    ry = YAML(); ry.preserve_quotes = True; ry.width = 4096
    with open(vars_file) as f: data = ry.load(f)
    lst = data.get(key)
    if not lst:
        data[key] = CommentedSeq([entry])
    else:
        lst.append(entry)
    with open(vars_file, 'w') as f: ry.dump(data, f)
    print("[+] vars.yaml updated (comments preserved)")
except ImportError:
    import yaml
    with open(vars_file) as f: data = yaml.safe_load(f)
    if not data.get(key): data[key] = []
    data[key].append(entry)
    with open(vars_file, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print("[!] vars.yaml updated (ruamel.yaml unavailable — comments may be reformatted)")
PYEOF
}

# -----------------------------------------------------------------------
# _vars_archive <label>
# Save a timestamped backup of custom-vars.yaml before modifying it.
# Backups stored in $ARCHIVE_DIR/vars/<timestamp>_<label>.yaml
# -----------------------------------------------------------------------
_vars_archive() {
    local label="$1"
    local timestamp; timestamp="$(date -u '+%Y%m%d-%H%M%S')"
    local vars_archive_dir="$ARCHIVE_DIR/vars"
    mkdir -p "$vars_archive_dir"
    local backup="${vars_archive_dir}/${timestamp}_${label}.yaml"
    cp "$VARS_FILE" "$backup"
    ok "vars.yaml backed up to ${backup}"
}
