#!/bin/bash
# Direct execution runner — source this file, do not execute directly.
#
# Replaces the former ansible-based run_playbook() with direct shell/docker
# functions.  manage.sh must run ON the target machine (no remote support).

# -----------------------------------------------------------------------
# run_service_certs
# Re-mint TLS certificates for the four core nginx-proxied services:
#   dns.<domain>, ldap.<domain>, ca.<domain>, certificates.<domain>
# Also installs the dns cert to bind9/ssl/ for DoT.
#
# Replaces: ansible-playbook --tags service-certs  (sections 8b–8f of
#           08-mint-service-certs.yml)
#
# Requires: step-ca image available locally; intermediate CA key present
#           at $deploy_base_dir/stepca/data/secrets/intermediate_ca_key
# -----------------------------------------------------------------------
run_service_certs() {
    local vars_file="$VARS_FILE"
    [ -f "$vars_file" ] || { err "Live vars not found: ${vars_file}. Is fabric deployed?"; exit 1; }

    # Read runtime config from live vars.yaml (all values already resolved)
    local deploy_base image_stepca step_uid step_gid nginx_uid nginx_gid bind_uid bind_gid ldap_uid ldap_gid install_ldap
    local domain hostname_bind9 hostname_ldap hostname_stepca hostname_landing cert_service_days
    IFS=' ' read -r deploy_base image_stepca \
                    step_uid  step_gid \
                    nginx_uid nginx_gid \
                    bind_uid  bind_gid \
                    ldap_uid  ldap_gid install_ldap \
                    domain \
                    hostname_bind9 hostname_ldap hostname_stepca hostname_landing \
                    cert_service_days \
        < <(python3 - <<PYEOF
import yaml
with open('${vars_file}') as f:
    v = yaml.safe_load(f)
su = v['service_users']
print(
    v['deploy_base_dir'],
    v['image_stepca'],
    su['step']['uid'],  su['step']['gid'],
    su['nginx']['uid'], su['nginx']['gid'],
    su['bind']['uid'],  su['bind']['gid'],
    su['ldap']['uid'],  su['ldap']['gid'], str(bool(v.get('install_ldap', True))).lower(),
    v['domain'],
    v['hostname_bind9'],
    v['hostname_ldap'],
    v['hostname_stepca'],
    v['hostname_landing'],
    v.get('cert_service_days', 5475),
)
PYEOF
)

    local stepca_data="${deploy_base}/stepca/data"
    local artifacts="${stepca_data}/artifacts"
    local int_crt="${stepca_data}/certs/intermediate_ca.crt"
    local int_key="${stepca_data}/secrets/intermediate_ca_key"
    local not_after=$(( cert_service_days * 24 ))h

    [ -f "$int_crt" ] || { err "Intermediate CA cert not found: ${int_crt}"; exit 1; }
    [ -f "$int_key" ] || { err "Intermediate CA key not found: ${int_key}"; exit 1; }

    # Ensure artifacts dir exists with step ownership
    mkdir -p "$artifacts"
    chown "${step_uid}:${step_gid}" "$artifacts"

    # ---- helper: mint one cert into artifacts/ ----
    _mint_svc() {
        local cn="$1"; shift
        local sans=("$@")
        local safe; safe=$(echo "$cn" | tr './ ' '---')

        local san_args=("--san" "$cn")
        for s in "${sans[@]}"; do san_args+=("--san" "$s"); done

        info "  Minting ${cn}..."
        docker run --rm \
            -v "${stepca_data}:/home/step" \
            --user "${step_uid}:${step_gid}" \
            --entrypoint /usr/local/bin/step \
            "$image_stepca" \
            certificate create "$cn" \
            "/home/step/artifacts/${safe}.crt" \
            "/home/step/artifacts/${safe}.key" \
            --ca  "/home/step/certs/intermediate_ca.crt" \
            --ca-key "/home/step/secrets/intermediate_ca_key" \
            --no-password --insecure --force \
            --kty RSA --size 4096 \
            --not-after "$not_after" \
            --template "/home/step/templates/certs/leaf.tpl" \
            "${san_args[@]}"
    }

    # ---- helper: install cert + key to nginx certs dir ----
    _install_nginx_cert() {
        local cn="$1"
        local safe; safe=$(echo "$cn" | tr './ ' '---')
        local cert_dir="${deploy_base}/nginx/certs/${cn}"

        mkdir -p "$cert_dir"
        chown "${nginx_uid}:${nginx_gid}" "$cert_dir"
        chmod 750 "$cert_dir"

        local cert_count; cert_count=$(grep -c 'BEGIN CERTIFICATE' "${artifacts}/${safe}.crt" || true)
        if [ "$cert_count" -lt 2 ]; then
            cat "${stepca_data}/certs/intermediate_ca.crt" >> "${artifacts}/${safe}.crt"
        fi
        mv "${artifacts}/${safe}.crt" "${cert_dir}/fullchain.pem"
        mv "${artifacts}/${safe}.key" "${cert_dir}/privkey.pem"

        chown "${nginx_uid}:${nginx_gid}" \
            "${cert_dir}/fullchain.pem" \
            "${cert_dir}/privkey.pem"
        chmod 644 "${cert_dir}/fullchain.pem"
        chmod 640 "${cert_dir}/privkey.pem"
        ok "  Installed ${cn} → ${cert_dir}"
    }

    # ---- Mint + install each service cert ----
    if [ "$install_ldap" = "true" ]; then
        # 389-DS imports /data/tls on start; restart it to pick up the new cert.
        local ldap_safe; ldap_safe=$(echo "$hostname_ldap" | tr './ ' '---')
        local ldap_tls="${deploy_base}/dirsrv/data/tls"
        _mint_svc "$hostname_ldap"
        install -d -m 0750 -o "$ldap_uid" -g "$ldap_gid" "$ldap_tls" "$ldap_tls/ca"
        install -m 0644 -o "$ldap_uid" -g "$ldap_gid" "${artifacts}/${ldap_safe}.crt" "${ldap_tls}/server.crt"
        install -m 0600 -o "$ldap_uid" -g "$ldap_gid" "${artifacts}/${ldap_safe}.key" "${ldap_tls}/server.key"
        install -m 0644 -o "$ldap_uid" -g "$ldap_gid" "${stepca_data}/certs/root_ca.crt" "${ldap_tls}/ca/root_ca.crt"
        install -m 0644 -o "$ldap_uid" -g "$ldap_gid" "${stepca_data}/certs/intermediate_ca.crt" "${ldap_tls}/ca/intermediate_ca.crt"
        rm -f "${artifacts}/${ldap_safe}.crt" "${artifacts}/${ldap_safe}.key"
        ok "  Installed ${hostname_ldap} → ${ldap_tls}"
        if systemctl is-active --quiet ldap; then systemctl restart ldap; fi
    fi
    _mint_svc "$hostname_stepca"; _install_nginx_cert "$hostname_stepca"
    _mint_svc "$hostname_landing";  _install_nginx_cert "$hostname_landing"

    # bind9 hostname gets nginx cert AND a dedicated bind9/ssl/ cert
    _mint_svc "$hostname_bind9" "ns.${domain}" "127.0.0.1"
    _install_nginx_cert "$hostname_bind9"

    # ---- Install dedicated BIND9 TLS cert to bind9/ssl/ ----
    local bind9_ssl="${deploy_base}/bind9/ssl"
    mkdir -p "$bind9_ssl"

    # Re-mint so the nginx copy and the bind9/ssl copy are independent files
    local bind_safe; bind_safe=$(echo "$hostname_bind9" | tr './ ' '---')
    _mint_svc "$hostname_bind9" "ns.${domain}" "127.0.0.1"

    mv  "${artifacts}/${bind_safe}.key" "${bind9_ssl}/privkey.pem"
    cat "${artifacts}/${bind_safe}.crt" \
        "${stepca_data}/certs/intermediate_ca.crt" \
        > "${bind9_ssl}/fullchain.pem"
    cp  "${stepca_data}/certs/root_ca.crt" "${bind9_ssl}/root_ca.crt"
    rm -f "${artifacts}/${bind_safe}.crt"

    chown "${bind_uid}:${bind_gid}" \
        "${bind9_ssl}/privkey.pem" \
        "${bind9_ssl}/fullchain.pem" \
        "${bind9_ssl}/root_ca.crt"
    chmod 600 "${bind9_ssl}/privkey.pem"
    chmod 644 "${bind9_ssl}/fullchain.pem" "${bind9_ssl}/root_ca.crt"
    ok "  Installed BIND9 TLS cert → ${bind9_ssl}"
}
