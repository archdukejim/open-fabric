#!/bin/bash
set -euo pipefail

# -----------------------------------------------------------------------
# manage.sh — Live configuration management for a running fabric
#
# Run this script ON the target machine (must be root / sudo).
#
# Modes:
#   tsig list|add|update|set-secret|rotate|remove  TSIG keys for RFC2136 updates.
#   acl list|add|remove   BIND ACLs (who may query the zones).
#   vault status          OpenBao: sealed?, version, seal key, secret engines.
#   secrets list|show <n> fabric's own secrets (in OpenBao); show is audited.
#   --mint-certs    Mint an offline certificate and save to vars.yaml.
#                   --intermediate-ca [N]  Issue as a subordinate CA cert (pathLen=N, default 0).
#                                          pathLen=0: can sign leaf certs, cannot issue further CAs.
#   --service-cert  Re-issue core service TLS certs (dns, ldap, ca, certificates) via Step-CA.
#   --render-jinja <j2>  Render a Jinja2 template using fabric vars.
#   --client-cert <user> Mint a webui client certificate (.p12) for a Keycloak user
#                        (same as: fabricctl client-cert <user>).
#   --keycloak-sync      Re-run the idempotent Keycloak configuration (federation, webui client, MFA).
#
# Common flags:
#   --apply            Apply without interactive prompting (uses existing vars.yaml)
#   --vars <file>      Vars file to use for --render-jinja (default: /opt/fabric/vars.yaml)
#   --output <file>    Output destination for --render-jinja (default: non-root user's home directory)
#   --kty <type>       Key type for minted certs: RSA | EC | OKP  (default: RSA)
#   --size <bits>      Key size (RSA: 2048/3072/4096, EC: 256/384) (default: 4096)
#
# Examples:
#   sudo fabricctl tsig add npm --record npm      # DNS-01 key for one host
#   sudo fabricctl tsig list
#   sudo ./manage.sh --mint-certs                              # Interactive: mint a leaf cert
#   sudo ./manage.sh --mint-certs --intermediate-ca            # Interactive: mint a subordinate CA (pathLen=0)
#   sudo ./manage.sh --mint-certs --intermediate-ca 1          # Subordinate CA that can sign one more CA level
#   sudo ./manage.sh --mint-certs --apply                      # Non-interactive: mint all extra_certs from vars.yaml
#   sudo ./manage.sh --service-cert               # Interactive: re-issue core service certs
#   sudo ./manage.sh --service-cert --apply       # Non-interactive: re-issue all core service certs
# -----------------------------------------------------------------------

# Resolve the actual script path even if invoked via a symlink
actual_script=$(readlink -f "${BASH_SOURCE[0]}" 2>/dev/null || realpath "${BASH_SOURCE[0]}")
SCRIPT_DIR="$(cd "$(dirname "$actual_script")" && pwd)"
FABRIC_DIR="$(dirname "$SCRIPT_DIR")"

# Lifecycle commands are Python (fabric/lib/fabriclib/cli.py).
case "${1:-}" in
    setup|doctor|certs|client-cert|tsig|acl|images|vault|secrets|status|start|stop|restart|uninstall|reinstall) exec python3 "$FABRIC_DIR/lib/fabriclib/cli.py" "$@" ;;
esac
VARS_FILE="$FABRIC_DIR/config/vars.yaml"

# Source shared library modules
source "$FABRIC_DIR/lib/output.sh"
source "$FABRIC_DIR/lib/vars.sh"
source "$FABRIC_DIR/lib/certs.sh"

# --- Globals ---
TARGET_BASE="$(dirname "$FABRIC_DIR")"
MODE=""
SUB_MODE="interactive"
IS_CA=false
PATH_LEN=0
CERT_KTY="RSA"
CERT_SIZE="4096"
RENDER_TEMPLATE=""
RENDER_VARS=""
RENDER_OUTPUT=""
CLIENT_CERT_USER=""

ARCHIVE_DIR="$TARGET_BASE/fabric/archive"

# --- Parse arguments ---
ARGS=("$@")

# Pass 1: extract mode
for arg in "${ARGS[@]}"; do
    case "$arg" in
        --mint-certs)   MODE="mint-certs" ;;
        --service-cert) MODE="service-cert" ;;
        --render-jinja) MODE="render-jinja" ;;
        --print)        MODE="print" ;;
        --interactive)  MODE="interactive" ;;
        --version)      MODE="version" ;;
        --update-containers) MODE="update-containers" ;;
        --client-cert)  MODE="client-cert" ;;
        --keycloak-sync) MODE="keycloak-sync" ;;
        --apply)        [ -z "$MODE" ] && MODE="apply" ;;
    esac
done

if [ -z "$MODE" ]; then
    MODE="interactive"
fi

# Pass 2: parse flags
set -- "${ARGS[@]}"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)    usage ;;
        --version)    shift ;;
        --mint-certs|--service-cert|--print|--interactive|--update-containers)  shift ;;
        --client-cert)  CLIENT_CERT_USER="${2:-}"; shift; [ -n "$CLIENT_CERT_USER" ] && shift || true ;;
        --keycloak-sync) shift ;;
        --render-jinja) RENDER_TEMPLATE="${2:-}"; shift; [ -n "$RENDER_TEMPLATE" ] && shift || true ;;
        --vars)         RENDER_VARS="${2:-}"; shift; [ -n "$RENDER_VARS" ] && shift || true ;;
        --output)       RENDER_OUTPUT="${2:-}"; shift; [ -n "$RENDER_OUTPUT" ] && shift || true ;;
        --apply)      SUB_MODE="apply"; shift ;;
        --kty)        CERT_KTY="$2";  shift 2 ;;
        --size)       CERT_SIZE="$2"; shift 2 ;;
        --intermediate-ca)
            IS_CA=true
            if [[ "${2:-}" =~ ^[0-9]+$ ]]; then PATH_LEN="$2"; shift; fi
            shift ;;
        *)  err "Unknown flag: $1"; exit 1 ;;
    esac
done

# --- Dispatch ---
do_render_jinja() {
    echo -e "${BOLD}fabric render-jinja${NC}"
    if [ -z "$RENDER_TEMPLATE" ]; then
        err "Missing template file. Usage: --render-jinja <file.j2>"
        exit 1
    fi
    if [ ! -f "$RENDER_TEMPLATE" ]; then
        err "Template file not found: $RENDER_TEMPLATE"
        exit 1
    fi

    local vars="${RENDER_VARS:-$VARS_FILE}"
    if [ ! -f "$vars" ]; then
        err "Vars file not found: $vars"
        exit 1
    fi

    local exec_user="${SUDO_USER:-$USER}"
    local exec_home
    exec_home=$(getent passwd "$exec_user" | cut -d: -f6)

    local default_filename="$(basename "${RENDER_TEMPLATE%.j2}")"
    if [[ "$default_filename" == "$(basename "$RENDER_TEMPLATE")" ]]; then
        default_filename="${default_filename}.rendered"
    fi

    local dest
    if [ -n "$RENDER_OUTPUT" ]; then
        if [ -d "$RENDER_OUTPUT" ]; then
            dest="${RENDER_OUTPUT}/${default_filename}"
        else
            dest="$RENDER_OUTPUT"
        fi
    else
        dest="${exec_home}/${default_filename}"
    fi

    echo "Rendering $RENDER_TEMPLATE -> $dest"
    echo "Using vars: $vars"
    
    python3 -c "
import sys, yaml, jinja2, os
vars_path = '$vars'
template_path = '$RENDER_TEMPLATE'
dest_path = '$dest'

try:
    with open(vars_path, 'r') as f:
        vars_dict = yaml.safe_load(f) or {}
except Exception as e:
    print(f'Error reading vars: {e}')
    sys.exit(1)

# Set up jinja environment with the same custom filters as fabricctl
sys.path.insert(0, '$FABRIC_DIR/lib')
from fabriclib.common.jinja_env import jinja_env
env = jinja_env(os.path.dirname(template_path) or '.')

try:
    template = env.get_template(os.path.basename(template_path))
    result = template.render(**vars_dict)
    with open(dest_path, 'w') as f:
        f.write(result)
    os.chmod(dest_path, 0o644)
    if '$exec_user' != 'root':
        import pwd
        try:
            uid = pwd.getpwnam('$exec_user').pw_uid
            gid = pwd.getpwnam('$exec_user').pw_gid
            os.chown(dest_path, uid, gid)
        except Exception as e:
            pass
except Exception as e:
    print(f'Template error: {e}')
    sys.exit(1)
" >/dev/null

    echo -e "${GREEN}Render complete: $dest${NC}"
}

case "$MODE" in
    mint-certs)   do_extra_certs ;;
    service-cert) do_service_cert ;;
    render-jinja) do_render_jinja ;;
    print)        python3 "${FABRIC_DIR}/lib/interactive.py" --print ;;
    interactive)  python3 "${FABRIC_DIR}/lib/interactive.py" --interactive ;;
    apply)        python3 "${FABRIC_DIR}/lib/interactive.py" --apply ;;
    update-containers) exec python3 "${FABRIC_DIR}/lib/fabriclib/cli.py" images update --all ;;   # old name
    client-cert)  exec python3 "$FABRIC_DIR/lib/fabriclib/cli.py" client-cert "$CLIENT_CERT_USER" ;;
    keycloak-sync) python3 "${FABRIC_DIR}/lib/keycloak_bootstrap.py" --vars "$VARS_FILE" --secrets "${FABRIC_DIR}/config/fabric-secrets.yml" ;;
    version)      echo "fabricctl version $(cat "$FABRIC_DIR/VERSION" 2>/dev/null || echo unknown)"
                  cat "$FABRIC_DIR/BUILD" 2>/dev/null || true ;;
esac
