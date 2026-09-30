#!/bin/bash
# Certificate management — source this file, do not execute directly.

# -----------------------------------------------------------------------
# Purpose: mint one extra certificate described by a JSON entry (one item of extra_certs) and show it.
# Inputs:  $1 — the entry as a JSON object (cn, sans, days, kty, size, optional is_ca/path_len/out_dir);
#          reads $FABRIC_DIR. Must run as root.
# Returns: prints the minted certificate path, its key path and the certificate's subject, dates, basic constraints
#          and SANs; exit status 0.
# Fails:   exits the whole script with 1: "Must be run as root." when not root, or when
#          `fabriclib/cli.py extra-cert` (fabriclib/pki/mint_extra_cert.py, same code as setup) fails — its own
#          error text is shown.
# Feeds:   do_extra_certs (both --apply and interactive modes).
_mint_extra_cert() {
    [[ "$(id -u)" -eq 0 ]] || { err "Must be run as root."; exit 1; }
    # One implementation for setup and this menu: fabriclib/pki/mint_extra_cert.py
    local crt
    crt=$(python3 "$FABRIC_DIR/lib/fabriclib/cli.py" extra-cert "$1") || exit 1
    ok "Certificate minted: ${crt} (key: ${crt%.crt}.key)"
    openssl x509 -in "$crt" -noout -subject -dates -ext basicConstraints -ext subjectAltName 2>/dev/null || true
}

# -----------------------------------------------------------------------
# Purpose: `fabricctl --mint-certs`: mint offline certificates via Step-CA. With --apply, mint every extra_certs
#          entry in the vars file; otherwise prompt for one (leaf, or subordinate CA with --intermediate-ca),
#          record it in the vars file and mint it.
# Inputs:  none as arguments; reads globals from manage.sh: $VARS_FILE (<fabric>/config/vars.yaml — messages call it
#          custom-vars.yaml), $SUB_MODE, $IS_CA, $PATH_LEN, $CERT_KTY, $CERT_SIZE; prompts on stdin.
# Returns: progress on stdout; the vars file archived (_vars_archive) and the entry appended (_vars_list_append)
#          in interactive mode; exit status 0. With --apply and no entries it warns and returns 0.
# Fails:   exit 1 when the vars file is missing ("fabric not deployed"), when the Common Name is empty, or from
#          _mint_extra_cert. Answering anything but y/Y at the review prompt exits 0 ("Cancelled."). The JSON entry is
#          built by string concatenation, so a quote or backslash in CN, SAN or output directory makes it invalid
#          (_vars_list_append then fails).
# Feeds:   manage.sh (MODE mint-certs).
do_extra_certs() {
    echo -e "${BOLD}fabric mint-certs${NC}"
    echo ""

    local vars_file="$VARS_FILE"
    [ -f "$vars_file" ] || { err "fabric not deployed (${vars_file} not found)."; exit 1; }

    if [ "$SUB_MODE" = "apply" ]; then
        info "Minting certificates from custom-vars.yaml..."
        echo ""

        local entries
        entries=$(python3 -c "
import yaml, json, sys
with open('$VARS_FILE') as f:
    d = yaml.safe_load(f)
certs = d.get('extra_certs') or []
if not certs:
    print('__EMPTY__')
    sys.exit(0)
for c in certs:
    print(json.dumps(c))
")
        if [ "$entries" = "__EMPTY__" ]; then
            warn "No extra_certs entries in custom-vars.yaml — nothing to mint."; return
        fi

        while IFS= read -r entry; do
            _mint_extra_cert "$entry"
            echo ""
        done <<< "$entries"

        ok "Certificate minting complete."
        return
    fi

    # --- Interactive ---
    if $IS_CA; then
        info "Interactive subordinate CA minting (pathLen=${PATH_LEN} — signed by Step-CA)"
    else
        info "Interactive certificate minting (offline — signed by Step-CA)"
    fi
    echo ""

    local cn; read -rp "  Common Name (e.g. myservice.internal): " cn
    [ -n "$cn" ] || { err "Common Name is required."; exit 1; }

    local sans=()
    if ! $IS_CA; then
        echo "  Additional SANs (blank to finish):"
        while true; do
            local san; read -rp "    SAN: " san
            [ -z "$san" ] && break
            sans+=("$san")
        done
    fi

    local days="" out_dir=""
    read -rp "  Validity in days [365]: " days; days="${days:-365}"
    read -rp "  Output directory [caller's home]: " out_dir

    local kty size
    read -rp "  Key type [${CERT_KTY}]: " kty;   kty="${kty:-${CERT_KTY}}"
    read -rp "  Key size [${CERT_SIZE}]: " size;  size="${size:-${CERT_SIZE}}"

    # Build type label for summary
    local type_label
    if $IS_CA; then
        if [ "$PATH_LEN" -eq 0 ]; then
            type_label="Subordinate CA (pathLen=0 — cannot sign further CAs)"
        else
            type_label="Subordinate CA (pathLen=${PATH_LEN} — can sign up to ${PATH_LEN} more CA level(s))"
        fi
    else
        type_label="Leaf"
    fi

    echo ""
    echo -e "  ${BOLD}─── Certificate — Review ───────────────────────────────────────${NC}"
    echo ""
    echo    "    CN:     ${cn}"
    echo    "    Type:   ${type_label}"
    echo    "    Key:    ${kty} ${size}"
    echo    "    Days:   ${days}"
    if ! $IS_CA && [ ${#sans[@]} -gt 0 ]; then
        echo "    SANs:"
        for s in "${sans[@]}"; do echo "      - ${s}"; done
    fi
    echo    "    Output: ${out_dir:-caller home}"
    echo ""
    echo -e "  ${BOLD}────────────────────────────────────────────────────────────────${NC}"
    echo ""
    local confirm; read -rp "  Add to custom-vars.yaml and mint? [y/N] " confirm
    [[ "$confirm" =~ ^[yY] ]] || { info "Cancelled."; exit 0; }

    # Build JSON
    local sans_json
    if [ ${#sans[@]} -gt 0 ]; then
        sans_json=$(printf '"%s",' "${sans[@]}"); sans_json="[${sans_json%,}]"
    else
        sans_json="[]"
    fi
    local json_entry="{\"cn\":\"${cn}\",\"sans\":${sans_json},\"days\":${days}"
    json_entry+=",\"kty\":\"${kty}\",\"size\":${size}"
    $IS_CA && json_entry+=",\"is_ca\":true,\"path_len\":${PATH_LEN}"
    [ -n "$out_dir" ] && json_entry+=",\"out_dir\":\"${out_dir}\""
    json_entry+="}"

    echo ""
    _vars_archive "mint-certs_${cn}"
    _vars_list_append "extra_certs" "$json_entry"
    echo ""

    info "Minting certificate..."
    echo ""
    _mint_extra_cert "$json_entry"
    echo ""
    ok "Certificate for '${cn}' minted."
}

# -----------------------------------------------------------------------
# Purpose: `fabricctl --service-cert`: re-issue every core service certificate (`fabriclib/cli.py certs --force`,
#          fabriclib/setup/mint_service_certs.py), which restarts the affected services. Interactive mode first
#          lists expiry dates and asks for confirmation.
# Inputs:  none as arguments; reads $VARS_FILE, $SUB_MODE and $FABRIC_DIR from manage.sh; deploy_base_dir and domain
#          from the vars file; prompts on stdin.
# Returns: progress and the expiry list on stdout; exit status 0.
# Fails:   exit 1 when the vars file is missing ("fabric not deployed"); answering anything but y/Y exits 0
#          ("Cancelled."); a failing `cli.py certs` ends the script through manage.sh's `set -e`.
# Feeds:   manage.sh (MODE service-cert).
# Notes:   the expiry list only looks at <base>/nginx/certs/{dns,ldap,ca,certificates}.<domain>/fullchain.pem.
#          The issued set follows the hostname_* vars and has more services; by default ldap's certificate is in
#          dirsrv/data/tls and the certs site is certs.<domain>, so those two always show "(not yet issued)".
do_service_cert() {
    echo -e "${BOLD}fabric service-cert${NC}"
    echo ""

    local vars_file="$VARS_FILE"
    [ -f "$vars_file" ] || { err "fabric not deployed (${vars_file} not found)."; exit 1; }

    if [ "$SUB_MODE" = "apply" ]; then
        info "Re-issuing all core service certificates..."
        echo ""
        python3 "$FABRIC_DIR/lib/fabriclib/cli.py" certs --force
        echo ""
        ok "Service certificates re-issued (affected services restarted)."
        return
    fi

    # --- Interactive: show current cert expiry then confirm ---
    local deploy_base domain
    deploy_base=$(python3 -c "import yaml; v=yaml.safe_load(open('${vars_file}')); print(v.get('deploy_base_dir','/opt'))")
    domain=$(python3 -c "import yaml; v=yaml.safe_load(open('${vars_file}')); print(v.get('domain','home'))")

    info "Current core service certificates:"
    echo ""
    for svc_host in "dns.${domain}" "ldap.${domain}" "ca.${domain}" "certificates.${domain}"; do
        local cert_path="${deploy_base}/nginx/certs/${svc_host}/fullchain.pem"
        if [[ -f "$cert_path" ]]; then
            local expiry
            expiry=$(openssl x509 -in "$cert_path" -noout -enddate 2>/dev/null | cut -d= -f2)
            printf "  %-30s expires %s\n" "${svc_host}" "${expiry}"
        else
            printf "  %-30s %b\n" "${svc_host}" "${YELLOW}(not yet issued)${NC}"
        fi
    done

    echo ""
    warn "Re-issuing replaces every service certificate and restarts the affected services."
    local confirm; read -rp "  Re-issue all service certificates? [y/N] " confirm
    [[ "$confirm" =~ ^[yY] ]] || { info "Cancelled."; exit 0; }

    echo ""
    python3 "$FABRIC_DIR/lib/fabriclib/cli.py" certs --force
    echo ""
    ok "Service certificates re-issued (affected services restarted)."
}
