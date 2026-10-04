"""The `samba` suite (manual 2.11.2.13, 4.8.2): the Windows domain controller.

S1.2: the settings check (D87, D89), the Administrator's password, the rendered container (host network, exactly the
five capabilities, read-only, its limit), nginx giving up 389/636, the unit and the certificate target.
Real containers (provisioning, DLZ, refusals) are added with S1.3-S1.5.
    python3 tests/samba/run.py
"""
import copy
import os
import string
import sys

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "src"))
from fabriclib.common.errors import ValidationError  # noqa: E402
from fabriclib.common.jinja_env import jinja_env  # noqa: E402
from fabriclib.deploy.check_samba_settings import check_samba_settings  # noqa: E402
from fabriclib.deploy.service_units import service_units  # noqa: E402
from fabriclib.secrets.random_password import random_password  # noqa: E402

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        print(f"FAIL {name} {detail}")


def refused(v, words):
    try:
        check_samba_settings(v)
    except ValidationError as e:
        return words in str(e)
    return False


POLICY = {"minimum_length": 14, "complexity": True, "history": 24, "minimum_age_days": 1, "maximum_age_days": 365,
          "lockout_threshold": 5, "lockout_minutes": 15, "lockout_window_minutes": 15}
GOOD = {"install_samba": True, "ad_domain": "ad.lan.test", "domain": "lan.test", "hostname": "pi-core",
        "ad_netbios": "AD", "ad_password_policy": POLICY, "ad_old_password_minutes": 0, "ad_rpc_ports": "49152-49251"}

print("--- settings (D87, D89)")
check_samba_settings({"install_samba": False})
check("nothing is checked while the Windows domain is off", True)
try:
    check_samba_settings(copy.deepcopy(GOOD))
    check("a complete configuration passes", True)
except ValidationError as e:
    check("a complete configuration passes", False, e)
check("refused: no AD domain (it has no default)", refused({**GOOD, "ad_domain": ""}, "needs ad_domain"))
check("refused: an AD domain of one label", refused({**GOOD, "ad_domain": "ad"}, "not a valid DNS domain"))
check("refused: fabric's own domain (same-domain mode dropped, D87)",
      refused({**GOOD, "ad_domain": "lan.test"}, "cannot be fabric's own domain"))
check("accepted: any other domain, not only the suggested ad.<domain>",
      not refused({**GOOD, "ad_domain": "corp.example.net"}, ""))
check("refused: a parent of fabric's domain", refused({**GOOD, "ad_domain": "test.x", "domain": "lan.test.x"},
                                                       "parent of fabric's domain"))
check("refused: a NetBIOS domain name over 15 characters",
      refused({**GOOD, "ad_netbios": "A" * 16}, "at most 15"))
check("refused: a host name Windows cannot use as the DC's NetBIOS name",
      refused({**GOOD, "hostname": "a-very-long-host-name"}, "NetBIOS name"))
check("refused: no password policy (no defaults, D89)",
      refused({**GOOD, "ad_password_policy": {}}, "no defaults"))
check("refused: one policy key missing, named",
      refused({**GOOD, "ad_password_policy": {k: x for k, x in POLICY.items() if k != "history"}}, "history"))
check("refused: an unknown policy key", refused({**GOOD, "ad_password_policy": {**POLICY, "colour": 1}}, "unknown"))
check("refused: complexity that is not true or false",
      refused({**GOOD, "ad_password_policy": {**POLICY, "complexity": "yes"}}, "true or false"))
check("refused: a minimum length over 64 (the Administrator's generated password must fit)",
      refused({**GOOD, "ad_password_policy": {**POLICY, "minimum_length": 65}}, "minimum_length"))
check("refused: a minimum age not below the maximum",
      refused({**GOOD, "ad_password_policy": {**POLICY, "minimum_age_days": 365}}, "below maximum_age_days"))
check("refused: a lockout shorter than its reset window (AD refuses it)",
      refused({**GOOD, "ad_password_policy": {**POLICY, "lockout_minutes": 5}}, "lockout_window_minutes"))
check("accepted: locked until an admin unlocks (lockout 0) with any window",
      not refused({**GOOD, "ad_password_policy": {**POLICY, "lockout_minutes": 0}}, ""))
check("accepted: passwords that never expire (maximum 0) with any minimum age",
      not refused({**GOOD, "ad_password_policy": {**POLICY, "maximum_age_days": 0}}, ""))
check("refused: an RPC range at or below 1024", refused({**GOOD, "ad_rpc_ports": "100-200"}, "ad_rpc_ports"))

print("--- the Administrator's password")
pw = [random_password() for _ in range(200)]
check("64 characters, letters of both cases and digits in every one (any allowed policy accepts it)",
      all(len(p) == 64 and any(c in string.ascii_uppercase for c in p) and any(c in string.ascii_lowercase for c in p)
          and any(c in string.digits for c in p) and p.isalnum() for p in pw))
check("never the same twice", len(set(pw)) == len(pw))

print("--- the rendered container (manual 2.11.2.3, 1.3.9)")
env = jinja_env(os.path.join(REPO, "templates"))
base = {"domain": "lan.test", "hostname": "pi-core", "host_ip": "192.168.7.53", "lan_cidr": "192.168.7.0/24",
        "lan_gateway": "192.168.7.1", "install_samba": True, "ad_domain": "AD.lan.test",
        "ad_password_policy": POLICY}
v = yaml.safe_load(env.get_template("vars.yaml.j2").render(**base))
check("the domain's names follow from ad_domain (lower-cased; realm, base DN, NetBIOS, the DC's name)",
      (v["ad_domain"], v["ad_realm"], v["ad_base_dn"], v["ad_netbios"], v["hostname_dc"])
      == ("ad.lan.test", "AD.LAN.TEST", "DC=ad,DC=lan,DC=test", "AD", "pi-core.ad.lan.test"),
      (v["ad_domain"], v["ad_realm"], v["ad_base_dn"], v["ad_netbios"], v["hostname_dc"]))
check("the limit is 512m by default and 384m at 3 GB",
      v["samba_mem_limit"] == "512m" and yaml.safe_load(env.get_template("vars.yaml.j2").render(
          **base, host_ram_capacity=3))["samba_mem_limit"] == "384m")
dc = yaml.safe_load(env.get_template("samba/docker-compose.yml.j2").render(**v))["services"]["samba"]
check("host network (D98), read-only, no-new-privileges, every capability dropped",
      dc["network_mode"] == "host" and dc["read_only"] is True and dc["cap_drop"] == ["ALL"]
      and "no-new-privileges:true" in dc["security_opt"])
check("exactly the five capabilities of the inventory (1.3.9)",
      sorted(dc["cap_add"]) == ["CHOWN", "DAC_OVERRIDE", "FOWNER", "SETGID", "SETUID"], dc["cap_add"])
check("bound to loopback and the host's address only", dc["environment"]["INTERFACES"] == "127.0.0.1 192.168.7.53")
check("no secret in its environment (the Administrator's password comes as a file)",
      not any(k.endswith(("PASSWORD", "SECRET", "PASS")) for k in dc["environment"]), sorted(dc["environment"]))
check("its secrets, certificate and converge code are mounted read-only",
      all(any(m.endswith(f":{target}:ro") for m in dc["volumes"]) for target in ("/run/secrets", "/tls", "/fabric")))
check("a memory limit", dc["mem_limit"] == "512m")
check("builds locally with BIND's and FreeRADIUS's gids while it is pending",
      dc["build"]["args"]["BIND_GID"] == "600" and dc["build"]["args"]["RADIUS_GID"] == "610")

print("--- what changes around it")
ngx_on = env.get_template("nginx/nginx.conf.j2").render(**v)
ngx_off = env.get_template("nginx/nginx.conf.j2").render(**{**v, "install_samba": False})
ports_on = yaml.safe_load(env.get_template("nginx/docker-compose.yml.j2").render(**v))["services"]["nginx"]["ports"]
check("nginx no longer passes 389/636 to 389-DS (the DC owns them)",
      "listen 389" not in ngx_on and "listen 389" in ngx_off and not any(":389:" in p or ":636:" in p for p in ports_on),
      ports_on)
off = {**v, "install_samba": False}
named_on, named_off = (env.get_template("bind9/config/named.conf.j2").render(**x) for x in (v, off))
opts_on, opts_off = (env.get_template("bind9/config/named.conf.options.j2").render(**x) for x in (v, off))
check("BIND includes the AD zone (DLZ) and the keytab option only with the Windows domain (manual 2.11.2.6)",
      'include "/etc/bind-samba/dlz.conf";' in named_on and "bind-samba" not in named_off
      and 'include "/etc/bind-samba/options.conf";' in opts_on and "bind-samba" not in opts_off)
bind_on = yaml.safe_load(env.get_template("bind9/docker-compose.yml.j2").render(**{**v, "host_ram_capacity": 4}))
bind_off = yaml.safe_load(env.get_template("bind9/docker-compose.yml.j2").render(**{**off, "host_ram_capacity": 4}))
b_on, b_off = bind_on["services"]["bind9"], bind_off["services"]["bind9"]
check("BIND mounts fabric's DLZ files and the DC's smb.conf read-only, the DNS partition writable",
      "/opt/samba/bind:/etc/bind-samba:ro" in b_on["volumes"] and "/opt/samba/data/etc:/etc/samba:ro" in b_on["volumes"]
      and "/opt/samba/data/bind-dns:/data/bind-dns" in b_on["volumes"]
      and not any("samba" in m for m in b_off["volumes"]), b_on["volumes"])
check("BIND gets a Kerberos replay cache and 128 MiB at 4 GB with the domain (80 MiB without)",
      any(t.startswith("/var/tmp:") for t in b_on["tmpfs"])
      and b_on["deploy"]["resources"]["limits"]["memory"] == "128M"
      and b_off["deploy"]["resources"]["limits"]["memory"] == "80M")
units = {u["service"]: u for u in service_units("/opt", v)}
check("a samba unit, enabled with install_samba, requiring nothing",
      units["samba"]["enabled"] and units["samba"]["requires"] == []
      and not {u["service"]: u for u in service_units("/opt", {**v, "install_samba": False})}["samba"]["enabled"])

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
