#!/usr/bin/env python3
"""The DNS filter (manual 2.4.1) with real containers: fabric's BIND image serving a test zone and
AdGuard Home (the pinned image) run from the configuration deploy_adguard generates, exactly as deployed
(built without the binary's file capabilities, run with none, DNS on 5300 inside, read-only root).
Includes what must be refused.

    sudo python3 tests/adguard/run.py            (needs Docker and dig)
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
W = os.environ.get("FABRIC_TEST_OUT", "/tmp/fabric-tests") + "/adguard"
NET, SUBNET = "adg_test_net", "10.254.41.0/24"
BIND_IP, ADG_IP = "10.254.41.30", "10.254.41.31"
FAILED = 0


def check(name, cond, detail=""):
    global FAILED
    FAILED += not cond
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {str(detail)[:400]}"))


def sh(cmd, ok=True):
    res = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True)
    if ok and res.returncode != 0:
        raise SystemExit(f"command failed: {cmd}\n{res.stderr}")
    return res


def dig(*args):
    return sh(["dig", "+time=3", "+tries=1", "-p", "5300", f"@{ADG_IP}", *args], ok=False).stdout


def api(path, auth=None):
    req = urllib.request.Request(f"http://{ADG_IP}:3000{path}")
    if auth:
        req.add_header("Authorization", "Basic " + base64.b64encode(auth.encode()).decode())
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, ""
    except OSError as e:
        return 0, str(e)


def until(fn, seconds=60):
    end = time.time() + seconds
    while time.time() < end:
        if fn():
            return True
        time.sleep(1)
    return False


sys.path.insert(0, os.path.join(REPO, "src"))
from fabriclib.common.jinja_env import jinja_env  # noqa: E402
from fabriclib.common.read_images_lock import read_images_lock  # noqa: E402
from fabriclib.dns_filter.build_adguard_config import GENERATED_END, SETTING_END  # noqa: E402
from fabriclib.dns_filter.deploy_adguard import deploy_adguard  # noqa: E402

env = jinja_env(os.path.join(REPO, "templates"))
lock = read_images_lock(os.path.join(REPO, "config"))
USERS = {"adguard": {"uid": 917, "gid": 917}, "oauth2proxy": {"uid": 918, "gid": 918}, "nginx": {"uid": 443, "gid": 443}}
V = {"deploy_base_dir": W, "service_users": USERS, "domain": "lan.test", "org_domain": "lan.test", "host_ip": "192.168.77.53",
     "ip_bind9": BIND_IP, "lan_cidr": "192.168.77.0/24", "fabric_subnet": SUBNET, "dns": {"dynamic_zone_var": {}},
     "adguard_upstreams": [], "adguard_filter_lists": [], "adguard_rules": ["||blocked.example^"],
     "hostname_keycloak": "sso.lan.test", "hostname_adguard": "adguard.lan.test", "webui_realm": "lan.test"}
SECRETS = {"adguard_admin_password": "Adg-Pw-1-Long-Enough", "adguard_oidc_secret": "oidc", "adguard_cookie_secret": "c" * 32}
CONF = f"{W}/adguard/conf/AdGuardHome.yaml"

try:
    shutil.rmtree(W, ignore_errors=True)
    os.makedirs(f"{W}/bind9/config")
    os.makedirs(f"{W}/bind9/data")
    debian = sh([sys.executable, os.path.join(REPO, "tests", "image_ref.py"), "debian"]).stdout.strip()
    sh(["docker", "build", "-q", "-t", "fabric/bind9:adgtest", "--build-arg", f"BASE_IMAGE={debian}",
        f"{REPO}/packaging/images/bind9"])
    sh(["docker", "build", "-q", "-t", "fabric/adguard:test", "--build-arg", f"BASE_IMAGE={lock['adguard']['ref']}",
        f"{REPO}/packaging/images/adguard"])
    caps = sh("docker run --rm --entrypoint getcap fabric/adguard:test /opt/adguardhome/AdGuardHome", ok=False)
    check("the built image's AdGuardHome carries no file capabilities", caps.stdout.strip() == "",
          caps.stdout + caps.stderr)
    with open(f"{W}/bind9/config/named.conf", "w") as f:
        f.write('options { directory "/var/cache/bind"; listen-on { any; }; listen-on-v6 { none; }; recursion no; };\n'
                'zone "lan.test" { type master; file "/var/lib/bind/db.lan.test"; };\n')
    with open(f"{W}/bind9/data/db.lan.test", "w") as f:
        f.write("$TTL 300\n@ IN SOA ns.lan.test. hostmaster.lan.test. 1 3600 600 86400 300\n@ IN NS ns.lan.test.\n"
                "ns IN A 10.254.41.30\nwww IN A 10.9.8.7\n")
    sh(f"chown -R 53:53 {W}/bind9/data")

    changed = deploy_adguard(V, SECRETS, {"children": [], "upstream": None}, env)
    cfg = yaml.safe_load(open(CONF))
    check("deploy: AdGuard's config, oauth2-proxy's and nginx's snippet written",
          all(changed.values()) and os.path.exists(f"{W}/adguard/oauth2-proxy/oauth2-proxy.cfg")
          and os.path.exists(f"{W}/nginx/config/conf.d/adguard-auth.inc"), changed)
    check("config out of the box: local DNS only — fabric's zone and everything else to this site's BIND",
          cfg["dns"]["upstream_dns"] == [f"[/lan.test/]{BIND_IP}", BIND_IP]
          and cfg["dns"]["local_ptr_upstreams"] == [BIND_IP] and cfg["dns"]["port"] == 5300, cfg["dns"]["upstream_dns"])
    check("config: fabric's names always allowed, then the rules from the setting",
          cfg["user_rules"][:4] == ["@@||lan.test^$important", "@@||192.168.77.53^$important", GENERATED_END,
                                    "||blocked.example^"], cfg["user_rules"])
    check("config: a local user with a bcrypt hash (never the password), DHCP off, no lists prefilled",
          cfg["users"][0]["name"] == "fabric" and cfg["users"][0]["password"].startswith("$2")
          and SECRETS["adguard_admin_password"] not in open(CONF).read() and cfg["dhcp"]["enabled"] is False
          and cfg["filters"] == [], cfg["users"])
    check("files: AdGuard's config 0600 and its own; secrets.env root 0600; the nginx snippet 0640",
          oct(os.stat(CONF).st_mode & 0o777) == "0o600" and os.stat(CONF).st_uid == 917
          and oct(os.stat(f"{W}/adguard/oauth2-proxy/secrets.env").st_mode & 0o777) == "0o600"
          and oct(os.stat(f"{W}/nginx/config/conf.d/adguard-auth.inc").st_mode & 0o777) == "0o640")

    sh(f"docker network rm {NET}", ok=False)
    sh(f"docker network create --subnet {SUBNET} {NET}")
    sh(f"docker run -d --name adg-bind --network {NET} --ip {BIND_IP} --user 53:53 --cap-drop ALL "
       f"-v {W}/bind9/config:/etc/bind:ro -v {W}/bind9/data:/var/lib/bind --tmpfs /var/cache/bind:uid=53,gid=53 "
       f"--tmpfs /run/named:uid=53,gid=53 fabric/bind9:adgtest")
    compose = yaml.safe_load(env.get_template("adguard/docker-compose.yml.j2").render(
        **V, image_adguard=lock["adguard"]["ref"], image_oauth2proxy=lock["oauth2proxy"]["ref"], ip_adguard=ADG_IP,
        ip_oauth2proxy="10.254.41.32", ip_nginx="10.254.41.10", adguard_mem_limit="256m"))["services"]["adguardhome"]
    check("compose: no capabilities, read-only, DNS published on 53 to 5300 inside",
          compose["cap_drop"] == ["ALL"] and "cap_add" not in compose and compose["read_only"] is True
          and "192.168.77.53:53:5300/udp" in compose["ports"], compose)
    sh(["docker", "run", "-d", "--name", "adg-adguard", "--network", NET, "--ip", ADG_IP,
        "--user", f"{USERS['adguard']['uid']}:{USERS['adguard']['gid']}", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true", "--tmpfs", "/tmp:size=16m,uid=917,gid=917",
        "-v", f"{W}/adguard/conf:/opt/adguardhome/conf", "-v", f"{W}/adguard/work:/opt/adguardhome/work",
        "fabric/adguard:test", *compose["command"]])
    check("AdGuard starts from fabric's config (no capabilities) and answers fabric's names via BIND",
          until(lambda: "10.9.8.7" in dig("+short", "www.lan.test")),
          sh("docker logs adg-adguard", ok=False).stdout[-800:] + sh("docker logs adg-adguard", ok=False).stderr[-800:])
    blocked = dig("blocked.example")
    check("a rule from the setting blocks", "NXDOMAIN" in blocked or "0.0.0.0" in blocked, blocked[-300:])
    check("its API refuses requests without AdGuard's login", api("/control/status")[0] in (401, 403))
    st, body = api("/control/status", f"fabric:{SECRETS['adguard_admin_password']}")
    check("its API accepts the local user nginx sends after sign-in", st == 200 and '"running":true' in body.replace(" ", ""),
          (st, body[:200]))
    check("out of the box the internet does not resolve (set it up in AdGuard's UI)",
          not dig("+short", "example.com").strip())

    # the owner sets AdGuard up in its UI (after the OIDC sign-in): upstreams, bootstrap, a list, a rule, a client
    sh("docker stop adg-adguard")
    cfg = yaml.safe_load(open(CONF))
    ui_upstreams = ["https://dns.google/dns-query", "https://dns.cloudflare.com/dns-query", "tls://dns.google"]
    cfg["dns"]["upstream_dns"] = [f"[/lan.test/]{BIND_IP}"] + ui_upstreams
    cfg["dns"]["bootstrap_dns"] = ["1.1.1.1", "8.8.8.8", "8.8.4.4"]
    cfg["filters"] = [{"enabled": False, "id": 1, "name": "AdGuard DNS filter",
                       "url": "https://adguardteam.github.io/HostlistsRegistry/assets/filter_1.txt"}]
    cfg["user_rules"].append("||ui-added.example^")
    cfg["clients"]["persistent"] = [{"name": "laptop", "ids": ["192.168.77.20"]}]
    old_hash = cfg["users"][0]["password"]
    with open(CONF, "w") as f:
        yaml.safe_dump(cfg, f)
    deploy_adguard(V, SECRETS, {"children": [{"domain": "lab.lan.test"}], "upstream": None}, env)
    new = yaml.safe_load(open(CONF))
    check("re-deploy: upstreams, bootstrap, lists, rules and clients set in the UI are kept",
          new["dns"]["upstream_dns"][-3:] == ui_upstreams and new["dns"]["bootstrap_dns"] == ["1.1.1.1", "8.8.8.8", "8.8.4.4"]
          and new["filters"][0]["enabled"] is False and new["user_rules"][-1] == "||ui-added.example^"
          and new["clients"]["persistent"][0]["name"] == "laptop", (new["dns"]["upstream_dns"], new["user_rules"]))
    check("re-deploy: fabric's lines kept in step (a linked site's zone added before the UI's), the hash is kept",
          new["dns"]["upstream_dns"][:2] == [f"[/lan.test/]{BIND_IP}", f"[/lab.lan.test/]{BIND_IP}"]
          and new["users"][0]["password"] == old_hash and SETTING_END in new["user_rules"], new["dns"]["upstream_dns"])
    again = deploy_adguard(V, SECRETS, {"children": [{"domain": "lab.lan.test"}], "upstream": None}, env)
    check("re-deploy with nothing new changes nothing (no restart)", not any(again.values()), again)
    sh("docker start adg-adguard")
    resolved = until(lambda: bool(dig("+short", "example.com").strip()), 40)
    print(("PASS " if resolved else "INFO ") + "with the UI's DoH/DoT upstreams the internet resolves"
          + ("" if resolved else " (no answer: is this host offline?)"))
    check("…and fabric's names still go to BIND", until(lambda: "10.9.8.7" in dig("+short", "www.lan.test"), 20),
          dig("www.lan.test") + sh("docker logs --tail 20 adg-adguard", ok=False).stderr[-800:])
finally:
    for c in ("adg-adguard", "adg-bind"):
        sh(f"docker rm -f {c}", ok=False)
    sh(f"docker network rm {NET}", ok=False)
print(f"\n{'FAILED' if FAILED else 'all passed'} ({FAILED} failures)")
sys.exit(1 if FAILED else 0)
