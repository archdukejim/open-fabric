import os
import subprocess

from fabriclib.common.console import ok
from fabriclib.pki.install_cert import install_cert
from fabriclib.pki.mint_cert import mint_cert
from fabriclib.pki.needs_renewal import needs_renewal
from fabriclib.setup.mint_extra_certs import mint_extra_certs


def _targets(ctx):
    """(cn, extra sans, [(dest dir, service user)], services to restart on change)"""
    v, p = ctx.vars, ctx.path
    nginx = lambda host: (p("nginx", "certs", host), "nginx")   # noqa: E731
    t = [
        (v["hostname_bind9"], [f"ns.{v['domain']}", "127.0.0.1"],
         [nginx(v["hostname_bind9"]), (p("bind9", "ssl"), "bind")], ["nginx", "bind9"]),
        (v["hostname_stepca"], [], [nginx(v["hostname_stepca"])], ["nginx"]),
        (v["hostname_landing"], [], [nginx(v["hostname_landing"])], ["nginx"]),
        (v["hostname_certs"], [], [nginx(v["hostname_certs"])], ["nginx"]),
    ]
    if v.get("install_ldap", True):
        t.append((v["hostname_ldap"], [], [("dirsrv-tls", "ldap")], ["ldap"]))
    if v.get("install_keycloak"):
        t.append((v["hostname_keycloak"], [], [nginx(v["hostname_keycloak"]), (p("keycloak", "certs"), "keycloak")],
                  ["nginx", "keycloak"]))
        t.append(("postgres", [f"postgres.{v['domain']}"], [(p("postgres", "certs"), "postgres")], ["postgres"]))
    if v.get("install_webui"):
        t.append((v["hostname_mgr"], [], [nginx(v["hostname_mgr"])], ["nginx"]))
    return t


def _install_dirsrv_tls(ctx, crt, key, root_ca, intermediate):
    """389-DS imports /data/tls/server.{crt,key} and ca/*.crt on start."""
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
    """Issue (or renew) every service certificate from Step-CA. Certs that
    exist, cover their names and are valid for 30+ days are left alone
    unless ctx.force_certs is set.
    Adds the services that need a restart to ctx.restart_services."""
    certs_dir = ctx.path("stepca", "data", "certs")
    root_ca = os.path.join(certs_dir, "root_ca.crt")
    intermediate = os.path.join(certs_dir, "intermediate_ca.crt")
    restart = set()

    for cn, sans, dests, services in _targets(ctx):
        first = dests[0][0]
        check = ctx.path("dirsrv", "data", "tls", "server.crt") if first == "dirsrv-tls" \
            else os.path.join(first, "fullchain.pem")
        if not ctx.force_certs and not needs_renewal(check, [cn, *sans], (root_ca, intermediate)):
            ok(f"{cn}: current")
            continue
        crt, key = mint_cert(ctx, cn, sans, cn.replace(".", "-"))
        for dest, user in dests:
            if dest == "dirsrv-tls":
                _install_dirsrv_tls(ctx, crt, key, root_ca, intermediate)
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
            for src in (intermediate, root_ca):
                out.write(open(src).read())
        os.chown(bundle, uid, gid)
        os.chmod(bundle, 0o644)
        ok("web UI client-certificate CA bundle")
    ctx.restart_services.update(restart)
    mint_extra_certs(ctx)
