import os
import subprocess

from fabriclib.common.console import ok
from fabriclib.common.write_file_if_changed import write_file_if_changed
from fabriclib.pki.install_cert import install_cert
from fabriclib.pki.mint_cert import mint_cert
from fabriclib.pki.needs_renewal import needs_renewal
from fabriclib.setup.mint_extra_certs import mint_extra_certs


def _targets(ctx):
    """Purpose: the service certificates this install needs and where each one goes.
    Inputs:  ctx — SetupContext: vars hostname_* (bind9, stepca, landing, certs, openbao, ldap, keycloak, mgr,
             radius, federation, adguard, dc), domain, install_ldap (default True), install_keycloak, install_webui,
             install_freeradius, federation_endpoint, install_adguard, install_samba + ad_domain.
    Returns: list of (cn, extra SANs, [(destination dir or "dirsrv-tls", service user or "freeradius:eap")],
             services to restart when it changes). bind9, stepca, landing, certs and openbao always; LDAP,
             Keycloak + Postgres, web UI, FreeRADIUS (EAP-TLS server cert), the federation endpoint, the DNS
             filter's UI and the domain controller when on.
    Fails:   KeyError for a missing hostname_* var.
    Feeds:   run."""
    v, p = ctx.vars, ctx.path
    nginx = lambda host: (p("nginx", "certs", host), "nginx")   # noqa: E731
    t = [
        (v["hostname_bind9"], [f"ns.{v['domain']}", "127.0.0.1"],
         [nginx(v["hostname_bind9"]), (p("bind9", "ssl"), "bind")], ["nginx", "bind9"]),
        (v["hostname_stepca"], [], [nginx(v["hostname_stepca"])], ["nginx"]),
        (v["hostname_landing"], [], [nginx(v["hostname_landing"])], ["nginx"]),
        (v["hostname_certs"], [], [nginx(v["hostname_certs"])], ["nginx"]),
        (v["hostname_openbao"], ["openbao"], [nginx(v["hostname_openbao"]), (p("openbao", "certs"), "openbao")],
         ["nginx", "openbao"]),
    ]
    if v.get("install_ldap", True):
        t.append((v["hostname_ldap"], [], [("dirsrv-tls", "ldap")], ["ldap"]))
    if v.get("install_keycloak"):
        t.append((v["hostname_keycloak"], [], [nginx(v["hostname_keycloak"]), (p("keycloak", "certs"), "keycloak")],
                  ["nginx", "keycloak"]))
        t.append(("postgres", [f"postgres.{v['domain']}"], [(p("postgres", "certs"), "postgres")], ["postgres"]))
    if v.get("install_webui"):
        t.append((v["hostname_mgr"], [], [nginx(v["hostname_mgr"])], ["nginx"]))
    if v.get("federation_endpoint"):
        t.append((v["hostname_federation"], [], [nginx(v["hostname_federation"])], ["nginx"]))
    if v.get("install_adguard"):
        t.append((v["hostname_adguard"], [], [nginx(v["hostname_adguard"])], ["nginx"]))
    if v.get("install_samba"):
        # the DC's LDAPS/TLS certificate (manual 2.11.2.7): Keycloak, FreeRADIUS and members verify it
        t.append((v["hostname_dc"], [v["ad_domain"]], [(p("samba", "tls"), "root")], ["samba"]))
    if v.get("install_freeradius"):
        # the EAP-TLS server certificate supplicants check (server.pem, server.key)
        t.append((v["hostname_radius"], [], [(p("freeradius", "certs"), "freeradius:eap")], ["freeradius"]))
    return t


def _install_dirsrv_tls(ctx, crt, key, root_ca, intermediate):
    """Purpose: install a certificate the way 389-DS imports it on start: /data/tls/server.{crt,key} and the
             CA certificates in ca/.
    Inputs:  ctx — SetupContext (service user ldap, install root); crt, key — minted files; root_ca,
             intermediate — Step-CA certificate paths.
    Returns: None; <deploy_base>/dirsrv/data/tls/server.key, server.crt (the leaf only) and ca/*.crt, owned by
             the ldap user.
    Fails:   CalledProcessError from `openssl x509`; OSError from install_cert/chown.
    Feeds:   run."""
    uid, gid = ctx.uid("ldap")
    tls = ctx.path("dirsrv", "data", "tls")
    install_cert(crt, key, root_ca, tls, uid, gid, names=(None, "server.key", None))
    leaf = subprocess.run(["openssl", "x509", "-in", crt], capture_output=True, text=True, check=True).stdout
    with open(os.path.join(tls, "server.crt"), "w") as f:
        f.write(leaf)
    os.chown(os.path.join(tls, "server.crt"), uid, gid)
    for src in (root_ca, intermediate):
        install_cert(src, key, root_ca, os.path.join(tls, "ca"), uid, gid,
                     names=(os.path.basename(src), None, None))


def run(ctx):
    """Purpose: issue (or renew) every service certificate from Step-CA and the CA bundles that verify client
             certificates, then the extra_certs.
    Inputs:  ctx — SetupContext: vars (see _targets; install_webui, install_freeradius for the bundles),
             force_certs (re-issue even when current), Step-CA certs under <deploy_base>/stepca/data/certs.
    Returns: None. Certificates that exist, cover their names, chain to this CA and are valid for 30+ days
             are left alone unless force_certs. The web UI client-CA bundle is rewritten on every run; the
             FreeRADIUS ca.pem and the DNS filter's oauth2-proxy root_ca.crt only when changed. Services whose
             certificates changed are added to
             ctx.restart_services.
    Fails:   SetupError from mint_cert (step-ca refused); OSError/CalledProcessError installing files;
             ValidationError from mint_extra_certs; KeyError for missing hostname vars.
    Feeds:   setup step `certs`, run by run_setup via STEPS; renew_service_certs (`fabricctl certs`)."""
    certs_dir = ctx.path("stepca", "data", "certs")
    root_ca = os.path.join(certs_dir, "root_ca.crt")
    intermediate = os.path.join(certs_dir, "intermediate_ca.crt")
    parents = os.path.join(certs_dir, "ca_parents.crt")           # a nested site's parent CAs (else empty/absent)
    chain_cas = [intermediate] + ([parents] if os.path.exists(parents) else [])
    restart = set()

    for cn, sans, dests, services in _targets(ctx):
        first = dests[0][0]
        check = ctx.path("dirsrv", "data", "tls", "server.crt") if first == "dirsrv-tls" \
            else os.path.join(first, "server.pem" if dests[0][1] == "freeradius:eap" else "fullchain.pem")
        if not ctx.force_certs and not needs_renewal(check, [cn, *sans], (root_ca, intermediate)):
            ok(f"{cn}: current")
            continue
        crt, key = mint_cert(ctx, cn, sans, cn.replace(".", "-"))
        for dest, user in dests:
            if dest == "dirsrv-tls":
                _install_dirsrv_tls(ctx, crt, key, root_ca, intermediate)
            elif user == "freeradius:eap":
                install_cert(crt, key, root_ca, dest, *ctx.uid("freeradius"), names=("server.pem", "server.key", None))
            else:
                install_cert(crt, key, root_ca, dest, *ctx.uid(user))
        os.remove(key)
        os.remove(crt)
        restart.update(services)
        ok(f"{cn}: issued")

    if ctx.vars.get("install_webui"):
        uid, gid = ctx.uid("nginx")
        bundle = ctx.path("nginx", "certs", "client-ca", "ca-bundle.pem")
        os.makedirs(os.path.dirname(bundle), mode=0o750, exist_ok=True)
        os.chown(os.path.dirname(bundle), uid, gid)
        with open(bundle, "w") as out:
            for src in (*chain_cas, root_ca):
                out.write(open(src).read())
        os.chown(bundle, uid, gid)
        os.chmod(bundle, 0o644)
        ok("web UI client-certificate CA bundle")
    if ctx.vars.get("install_freeradius"):
        # EAP-TLS accepts client certificates from the fabric CA only; the same
        # bundle verifies 389-DS for the policy's directory lookups
        uid, gid = ctx.uid("freeradius")
        bundle = "".join(open(src).read() for src in (root_ca, *chain_cas))
        os.makedirs(ctx.path("freeradius", "certs"), mode=0o750, exist_ok=True)
        if write_file_if_changed(ctx.path("freeradius", "certs", "ca.pem"), bundle, 0o644, uid, gid):
            restart.add("freeradius")
            ok("FreeRADIUS CA bundle")
    if ctx.vars.get("install_adguard"):
        # oauth2-proxy verifies Keycloak against this CA; on a first install the deploy ran before the CA existed
        if write_file_if_changed(ctx.path("adguard", "oauth2-proxy", "root_ca.crt"), open(root_ca).read(),
                                 0o644, 0, 0):
            restart.add("adguard-auth")
            ok("DNS filter sign-in (oauth2-proxy) trusts the fabric CA")
    ctx.restart_services.update(restart)
    mint_extra_certs(ctx)
