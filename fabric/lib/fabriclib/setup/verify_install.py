import os
import stat
import subprocess

from fabriclib.common.console import err, ok
from fabriclib.common.dns_query import dns_query
from fabriclib.setup.errors import SetupError


def _curl(url, host, ip, port, root_ca, client_cert=False):
    res = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "10",
                          "--cacert", root_ca, "--resolve", f"{host}:{port}:{ip}", url],
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

    for unit in ("bind9", "stepca", "nginx", "ldap", "postgres", "keycloak", "fabric-agent", "webui", "fabric-firewall"):
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
