#!/bin/bash
# Certificate management — source this file, do not execute directly.

# -----------------------------------------------------------------------
# _mint_extra_cert <json_entry>
# Mint a single certificate described by a JSON entry (from extra_certs[]).
# Reads runtime config (stepca image, step uid/gid, deploy_base_dir) from
# the live vars.yaml deployed by fabric.
# -----------------------------------------------------------------------
_mint_extra_cert() {
    [[ "$(id -u)" -eq 0 ]] || { err "Must be run as root."; exit 1; }
    # One implementation for setup and this menu: fabriclib/pki/mint_extra_cert.py
    local crt
    crt=$(python3 "$FABRIC_DIR/lib/fabriclib/cli.py" extra-cert "$1") || exit 1
    ok "Certificate minted: ${crt} (key: ${crt%.crt}.key)"
    openssl x509 -in "$crt" -noout -subject -dates -ext basicConstraints -ext subjectAltName 2>/dev/null || true
}

# -----------------------------------------------------------------------
# do_extra_certs
# Interactive or --apply mode: mint an offline certificate via Step-CA
# and record it in custom-vars.yaml.
# -----------------------------------------------------------------------
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
# do_service_cert
# Interactive or --apply mode: re-issue TLS certificates for the four
# core nginx-proxied services (dns, ldap, ca, certificates).
# -----------------------------------------------------------------------
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
