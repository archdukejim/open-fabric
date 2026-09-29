import os
import stat
import subprocess

from fabriclib.common.console import err, ok
from fabriclib.common.dns_query import dns_query
from fabriclib.common.sudo_owner import sudo_owner
from fabriclib.keycloak.user_has_role import user_has_role
from fabriclib.setup.errors import SetupError
from fabriclib.vault.vault_status import vault_status


def _curl(url, host, ip, port, root_ca, client_cert=False):
    ca = ["--cacert", root_ca] if root_ca else []      # None: the host's own trust store
    res = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "10",
                          *ca, "--resolve", f"{host}:{port}:{ip}", url],
                         capture_output=True, text=True)
    return res.returncode, res.stdout


def _ldap_bind(uri, dn, password):
    env = {**os.environ, "CHECK_URI": uri, "CHECK_DN": dn, "CHECK_PW": password}
    code = ("import ldap, os; c = ldap.initialize(os.environ['CHECK_URI']);\n"
            "try:\n c.simple_bind_s(os.environ['CHECK_DN'], os.environ['CHECK_PW']); print('BOUND')\n"
            "except ldap.LDAPError as e: print(type(e).__name__)")
    res = subprocess.run(["docker", "exec", "-e", "CHECK_URI", "-e", "CHECK_DN", "-e", "CHECK_PW", "dirsrv",
                          "python3", "-c", code], capture_output=True, text=True, env=env)
    return res.stdout.strip()


def checks(ctx):
    """[(name, passed, detail)] for a running install."""
    v, s = ctx.vars, ctx.secrets
    root_ca = ctx.path("stepca", "data", "certs", "root_ca.crt")
    port = int(v.get("bind_dns_port", 53))
    results = []

    def add(name, passed, detail=""):
        results.append((name, bool(passed), detail))

    for name in (v["hostname_landing"], f"ns.{v['domain']}", v["hostname_stepca"]):
        try:
            got = dns_query(name, v["host_ip"], port)
            add(f"DNS {name}", v["host_ip"] in got, ", ".join(got) or "no answer")
        except OSError as e:
            add(f"DNS {name}", False, str(e))

    rc, code = _curl(f"http://{v['host_ip']}/", v["host_ip"], v["host_ip"], 80, root_ca)
    add("nginx HTTP", code in ("200", "301", "302"), f"HTTP {code}")
    for host in (v["hostname_landing"], v["hostname_stepca"], v["hostname_bind9"]):
        rc, code = _curl(f"https://{host}/", host, v["ip_nginx"], 443, root_ca)
        add(f"HTTPS {host} (cert verified)", rc == 0, f"HTTP {code}" if rc == 0 else f"curl exit {rc}")
    # certs.<domain>: the CA certificates; ca.<domain>: Step-CA's API, browsers redirected.
    certs_host = v.get("hostname_certs")
    if certs_host:
        res = subprocess.run(["curl", "-s", "--max-time", "10", "--cacert", root_ca, "--resolve",
                              f"{certs_host}:443:{v['ip_nginx']}", f"https://{certs_host}/root-ca.pem"],
                             capture_output=True, text=True)
        with open(root_ca) as f:
            served_ok = res.returncode == 0 and res.stdout.strip() and res.stdout.strip() in f.read()
        add(f"https://{certs_host}/ serves this CA's root certificate", served_ok, f"curl exit {res.returncode}")
        res = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code} %{redirect_url}", "--max-time", "10",
                              "--cacert", root_ca, "--resolve", f"{v['hostname_stepca']}:443:{v['ip_nginx']}",
                              f"https://{v['hostname_stepca']}/"], capture_output=True, text=True)
        add(f"https://{v['hostname_stepca']}/ sends browsers to {certs_host}",
            res.stdout.startswith("302 ") and certs_host in res.stdout, res.stdout)
    rc, code = _curl(f"https://{v['hostname_stepca']}/acme/acme/directory", v["hostname_stepca"], v["ip_nginx"], 443,
                     root_ca)
    add("Step-CA ACME directory reachable (API unaffected)", rc == 0 and code == "200", f"HTTP {code}")
    rc, code = _curl(f"https://{v['hostname_landing']}/", v["hostname_landing"], v["ip_nginx"], 443, None)
    add("this host trusts the fabric CA (system store)", rc == 0, f"HTTP {code}" if rc == 0 else f"curl exit {rc}")

    if v.get("install_ldap", True):
        res = subprocess.run(["openssl", "s_client", "-connect", f"{v['ip_ldap']}:3636",
                              "-servername", v["hostname_ldap"], "-verify_hostname", v["hostname_ldap"],
                              "-CAfile", root_ca], input="", capture_output=True, text=True, timeout=15)
        add("LDAPS certificate", "Verify return code: 0 (ok)" in res.stdout)
        base = v["ldap_base_dn"]
        for role, secret in (("super_admin", "ldap_super_admin_password"), ("keycloak_admin", "ldap_keycloak_password")):
            add(f"LDAP {role} binds", _ldap_bind("ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket",
                                                 f"cn={role},ou=admins,ou=accounts,{base}", s.get(secret, "")) == "BOUND")
        add("LDAP refuses plaintext binds",
            _ldap_bind("ldap://127.0.0.1:3389", f"cn=super_admin,ou=admins,ou=accounts,{base}",
                       s.get("ldap_super_admin_password", "")) == "CONFIDENTIALITY_REQUIRED")

    if v.get("install_webui"):
        rc, code = _curl(f"https://{v['hostname_mgr']}/", v["hostname_mgr"], v["ip_nginx"], 443, root_ca)
        add("web UI refuses requests without a client certificate", code == "400", f"HTTP {code}")
        sock = ctx.path("webui", "agent", "agent.sock")
        st = os.stat(sock) if os.path.exists(sock) else None
        add("fabric-agent socket 0660, webui group only",
            st and stat.S_IMODE(st.st_mode) == 0o660 and st.st_gid == ctx.uid("webui")[1])

        # The first admin, end to end: LDAP user -> admin group -> Keycloak role,
        # and a client certificate from this CA whose CN is that user.
        admin, role = v.get("webui_admin_user"), v.get("webui_admin_role", "fabric-admin")
        if admin and v.get("install_keycloak"):
            try:
                add(f"Keycloak grants {admin} {role}", user_has_role(v, s, admin, role))
            except (SystemExit, OSError) as e:
                add(f"Keycloak grants {admin} {role}", False, str(e))
            crt = os.path.join(sudo_owner()[1], "fabric-admin", f"{admin}.crt")
            if os.path.exists(crt):
                certs = ctx.path("stepca", "data", "certs")
                res = subprocess.run(["openssl", "verify", "-CAfile", os.path.join(certs, "root_ca.crt"),
                                      "-untrusted", os.path.join(certs, "intermediate_ca.crt"), crt],
                                     capture_output=True, text=True)
                subj = subprocess.run(["openssl", "x509", "-in", crt, "-noout", "-subject", "-nameopt", "RFC2253"],
                                      capture_output=True, text=True).stdout
                add(f"client certificate for {admin} (CN, chain)", res.returncode == 0 and f"CN={admin}" in subj,
                    (res.stdout + res.stderr).strip()[-200:])

    bao = vault_status(v)
    add("OpenBao unsealed (static seal, raft)", bao.get("initialized") and bao.get("sealed") is False
        and bao.get("seal_type") == "static", bao.get("error", ""))
    add("OpenBao unlock methods: store root-only, no vault key left in RAM", bao["key"]["ok"], bao["key"]["detail"])
    add("OpenBao KV v2 fabric/ and apps/ (read as fabric-agent)",
        {"fabric/", "apps/"} <= {m["path"] for m in bao.get("mounts", [])}, bao.get("error", ""))
    code = _curl(f"https://{v['hostname_openbao']}/v1/sys/health", v["hostname_openbao"], v["ip_nginx"], 443, root_ca)
    add(f"https://{v['hostname_openbao']} (OpenBao via nginx, TLS verified)", code == (0, "200"), code)

    for unit in ("bind9", "stepca", "nginx", "ldap", "postgres", "keycloak", "openbao", "fabric-agent", "webui",
                 "fabric-firewall"):
        if os.path.exists(f"/etc/systemd/system/{unit}.service"):
            active = subprocess.run(["systemctl", "is-active", unit], capture_output=True, text=True).stdout.strip()
            add(f"service {unit}", active == "active", active)
    return results


def run(ctx):
    """Check the running install end to end; fail setup if anything is wrong.
    Same checks as `fabricctl doctor`."""
    failed = 0
    for name, passed, detail in checks(ctx):
        (ok if passed else err)(f"{name}" + (f" — {detail}" if detail else ""))
        failed += not passed
    if failed:
        raise SetupError(f"{failed} check(s) failed")
