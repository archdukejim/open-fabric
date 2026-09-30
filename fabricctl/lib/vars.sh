#!/bin/bash
# YAML mutation helpers — source this file, do not execute directly.

# -----------------------------------------------------------------------
# Purpose: append one entry to a top-level list in the vars file (e.g. extra_certs).
# Inputs:  $1 — the top-level key; $2 — the entry as a JSON object string.
#          Reads $VARS_FILE (manage.sh sets it to <fabric>/config/vars.yaml, not a custom-vars.yaml).
# Returns: the file rewritten with the entry added (list created if missing); prints "[+] ... (comments preserved)"
#          with ruamel.yaml, or "[!] ... comments may be reformatted" when it falls back to PyYAML; exit status 0.
# Fails:   non-zero exit status with a Python traceback on invalid JSON, an unreadable/unwritable file or a
#          vars file that is not a mapping. Does not lock the file and does not validate the entry.
# Feeds:   do_extra_certs (certs.sh), which then mints the entry.
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
# Purpose: save a timestamped copy of the vars file before it is changed.
# Inputs:  $1 — a label for the file name; reads $VARS_FILE and $ARCHIVE_DIR (manage.sh: <base>/fabric/archive).
# Returns: the copy at $ARCHIVE_DIR/vars/<UTC yyyymmdd-HHMMSS>_<label>.yaml; prints an ok line; exit status 0.
# Fails:   non-zero status of mkdir/cp (e.g. $VARS_FILE missing); under manage.sh's `set -e` that ends the script.
# Feeds:   do_extra_certs (certs.sh), before _vars_list_append.
_vars_archive() {
    local label="$1"
    local timestamp; timestamp="$(date -u '+%Y%m%d-%H%M%S')"
    local vars_archive_dir="$ARCHIVE_DIR/vars"
    mkdir -p "$vars_archive_dir"
    local backup="${vars_archive_dir}/${timestamp}_${label}.yaml"
    cp "$VARS_FILE" "$backup"
    ok "vars.yaml backed up to ${backup}"
}
