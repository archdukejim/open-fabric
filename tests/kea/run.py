#!/usr/bin/env python3
"""Kea 3.0 LTS (optional DHCP, design §5 / D16) on fabric's own image, from
fabric's templates, with real DHCP clients: a client gets a pool address and
its hostname lands in the DHCP subzone (BIND, fabric's zone and key
templates); a reserved MAC gets its fixed address; another client cannot
take over that name (DHCID); the lease list comes over the control socket;
the containers are hardened (two capabilities for DHCP, none for DDNS).

    sudo python3 tests/kea/run.py          (needs Docker, dig, root)
"""
import json
import os
import shutil
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
W = os.environ.get("FABRIC_TEST_OUT", "/tmp/fabric-tests") + "/kea"
NET, SUBNET = "keatest_net", "10.254.23.0/24"
BIND_IP, DDNS_IP = "10.254.23.30", "10.254.23.97"
FAILED = 0
sys.path[0:0] = [os.path.join(REPO, "fabricctl", "lib"), REPO]
from fabriclib.common.jinja_env import jinja_env  # noqa: E402
from fabriclib.common.read_images_lock import read_images_lock  # noqa: E402
from fabriclib.common.read_packages_lock import read_packages_lock  # noqa: E402
from fabriclib.dhcp.deploy_kea import deploy_kea  # noqa: E402
from fabriclib.dhcp.list_leases import list_leases  # noqa: E402
from fabriclib.dhcp.normalize_dhcp import normalize_dhcp  # noqa: E402


def check(name, cond, detail=""):
    global FAILED
    FAILED += not cond
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {str(detail)[:500]}"))


def sh(cmd, ok=True, **kw):
    res = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, **kw)
    if ok and res.returncode != 0:
        raise SystemExit(f"failed: {cmd}\n{res.stdout[-1500:]}{res.stderr[-1500:]}")
    return res


def until(pred, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(1)
    return False


def cleanup():
    sh("docker rm -f kt-dhcp4 kt-ddns kt-bind kt-c1 kt-c2 kt-c3 >/dev/null 2>&1", ok=False)
    sh(f"docker network rm {NET} >/dev/null 2>&1", ok=False)


cleanup()
shutil.rmtree(W, ignore_errors=True)
os.makedirs(f"{W}/bind9/data")
lock, pkgs = read_images_lock(os.path.join(REPO, "fabricctl")), read_packages_lock(os.path.join(REPO, "fabricctl"))
DEBIAN, BUSYBOX = lock["debian"]["ref"], \
    "busybox:1.37@sha256:bdf57e528e45e4433820e045b29b4597825a1c9e38353532d90a01445013f82e"
k = pkgs["kea"]

# ------------------------------------------------------------------ images
build = sh(["docker", "build", "-q", "-t", "fabric/kea:test", "--build-arg", f"BASE_IMAGE={DEBIAN}",
            "--build-arg", f"KEA_VERSION={k['version']}", "--build-arg", f"KEA_REPO={k['repo']}",
            "--build-arg", f"KEA_SUITE={k['suite']}", "--build-arg", f"KEA_KEY_URL={k['key_url']}",
            "--build-arg", f"KEA_KEY_FINGERPRINT={k['key_fingerprint']}", f"{REPO}/fabricctl/jinja/kea/build"], ok=False)
check("Kea image builds from ISC's repository (signing key pinned, exact version)", build.returncode == 0,
      build.stderr[-600:])
bad = sh(["docker", "build", "-q", "--build-arg", f"BASE_IMAGE={DEBIAN}", "--build-arg", f"KEA_VERSION={k['version']}",
          "--build-arg", f"KEA_REPO={k['repo']}", "--build-arg", f"KEA_SUITE={k['suite']}",
          "--build-arg", f"KEA_KEY_URL={k['key_url']}", "--build-arg", "KEA_KEY_FINGERPRINT=" + "0" * 40,
          f"{REPO}/fabricctl/jinja/kea/build"], ok=False)
check("the build refuses a repository key that is not the pinned one", bad.returncode != 0
      and "is not the pinned" in bad.stderr + bad.stdout, bad.stderr[-300:])
version = sh("docker run --rm --entrypoint /usr/sbin/kea-dhcp4 fabric/kea:test -V", ok=False).stdout
check("Kea 3.0 LTS inside (the pinned version)", version.startswith("3.0."), version[:80])
sh(["docker", "build", "-q", "-t", "fabric/bind9:keatest", "--build-arg", f"BASE_IMAGE={DEBIAN}",
    f"{REPO}/fabricctl/jinja/bind9/build"])

# ------------------------------------------------------------------ fabric's files
V = {"deploy_base_dir": W, "domain": "lan.test", "install_kea": True, "ip_kea_ddns": DDNS_IP, "ip_bind9": BIND_IP,
     "host_ip": BIND_IP, "service_users": {"kea": {"uid": 915, "gid": 915}},
     "dhcp": {"interfaces": ["eth0"], "lease_time": 3600,
              "subnets": [{"subnet": SUBNET, "pools": ["10.254.23.100 - 10.254.23.150"], "routers": "10.254.23.1",
                           "reservations": [{"mac": "02:00:00:00:00:42", "ip": "10.254.23.42",
                                             "hostname": "printer"}]}]}}
V["dhcp"] = normalize_dhcp(V)
env = jinja_env(os.path.join(REPO, "fabricctl", "jinja"))
secret = sh("openssl rand -base64 32").stdout.strip()
check("Kea's configs, lease and socket folders, and the DHCP subzone file written",
      deploy_kea(V, {"kea_ddns_secret": secret}, env, 53, 53) and os.path.exists(f"{W}/bind9/data/db.dhcp.lan.test")
      and oct(os.stat(f"{W}/kea/config/kea-dhcp-ddns.conf").st_mode & 0o777) == "0o640")
os.makedirs(f"{W}/bind9/config", exist_ok=True)
bv = {**V, "dns": {}, "bind_acls": {"lan": ["any"]}, "tsig_keys": [], "tsig_secrets": {}, "kea_ddns_secret": secret}
open(f"{W}/bind9/config/named.conf", "w").write(
    'options { directory "/var/cache/bind"; listen-on { any; }; listen-on-v6 { none; }; recursion no; };\n'
    'acl "lan" { any; };\n'
    + env.get_template("bind9/config/named.conf.keys.j2").render(**bv)
    + env.get_template("bind9/config/named.conf.zones.j2").render(**bv))
sh(f"chown -R 53:53 {W}/bind9/data")

# ------------------------------------------------------------------ containers
sh(f"docker network create --subnet {SUBNET} --gateway 10.254.23.1 {NET}")
sh(f"docker run -d --name kt-bind --network {NET} --ip {BIND_IP} --user 53:53 --cap-drop ALL "
   f"-v {W}/bind9/config:/etc/bind:ro -v {W}/bind9/data:/var/lib/bind --tmpfs /var/cache/bind:uid=53,gid=53 "
   f"--tmpfs /run/named:uid=53,gid=53 fabric/bind9:keatest")
# production runs kea-dhcp4 in the host network; here it serves the test bridge's eth0,
# with the command from fabric's compose template
import shlex  # noqa: E402
import yaml  # noqa: E402
KEA_CMD = yaml.safe_load(env.get_template("kea/docker-compose.yml.j2").render(
    **V, image_kea="fabric/kea:test", image_debian="debian", kea_mem_limit="128m",
    packages_lock=pkgs))["services"]["kea-dhcp4"]["command"]


def start_dhcp4():
    sh(f"docker run -d --name kt-dhcp4 --network {NET} --ip 10.254.23.2 --read-only "
       f"--security-opt no-new-privileges:true --cap-drop ALL --cap-add NET_RAW --cap-add NET_BIND_SERVICE --tmpfs /tmp "
       f"-v {W}/kea/config:/config:ro -v {W}/kea/leases:/var/lib/kea -v {W}/kea/run:/run/kea "
       f"fabric/kea:test {shlex.join(KEA_CMD)}")


start_dhcp4()
sh(f"docker run -d --name kt-ddns --network {NET} --ip {DDNS_IP} --user 915:915 --read-only "
   f"--security-opt no-new-privileges:true --cap-drop ALL --tmpfs /tmp --tmpfs /run/kea:uid=915,gid=915 "
   f"-v {W}/kea/config:/config:ro fabric/kea:test /usr/sbin/kea-dhcp-ddns -c /config/kea-dhcp-ddns.conf")
check("kea-dhcp4 runs and its control socket answers", until(lambda: os.path.exists(f"{W}/kea/run/kea4-ctrl-socket")),
      sh("docker logs kt-dhcp4", ok=False).stdout[-800:] + sh("docker logs kt-dhcp4", ok=False).stderr[-800:])


def client(name, mac=None, hostname=None):
    args = ["docker", "run", "--name", name, "--network", NET, "--cap-add", "NET_ADMIN", "--cap-add", "NET_RAW"]
    if mac:
        args += ["--mac-address", mac]
    args += [BUSYBOX, "udhcpc", "-i", "eth0", "-n", "-q", "-f", "-t", "5", "-s", "/bin/true"]
    if hostname:
        args += ["-x", f"hostname:{hostname}"]
    out = sh(args, ok=False)
    text = out.stdout + out.stderr
    got = [ln.split("lease of ")[1].split()[0] for ln in text.splitlines() if "lease of " in ln]
    return got[-1] if got else None, text


ip1, out1 = client("kt-c1", "02:00:00:00:00:11", "laptop1")
check("a client gets an address from the pool", ip1 is not None and ip1.startswith("10.254.23.1"), out1[-400:])


def dig(name):
    return sh(["dig", "+short", f"@{BIND_IP}", name], ok=False).stdout.strip()


check("its hostname is registered in the DHCP subzone (Kea DDNS -> BIND, kea-ddns key)",
      until(lambda: dig("laptop1.dhcp.lan.test") == ip1, 30),
      (dig("laptop1.dhcp.lan.test"), sh("docker logs kt-ddns", ok=False).stdout[-600:]))
ip2, out2 = client("kt-c2", "02:00:00:00:00:42")
check("a reserved MAC gets its fixed address", ip2 == "10.254.23.42", out2[-400:])
ip3, out3 = client("kt-c3", "02:00:00:00:00:13", "laptop1")
time.sleep(3)
check("another client asking for the same name cannot take it over (DHCID)", ip3 and ip3 != ip1
      and dig("laptop1.dhcp.lan.test") == ip1, (ip3, dig("laptop1.dhcp.lan.test")))
leases = list_leases(V)
check("lease list over the control socket shows the clients", any(l["ip"] == ip1 and l["hostname"].startswith("laptop1")
      for l in leases) and any(l["ip"] == "10.254.23.42" for l in leases), leases)
check("the key may not touch anything but the DHCP subzone",
      "REFUSED" in sh(f"printf 'server {BIND_IP}\\nzone lan.test\\nupdate add evil.lan.test 60 A 1.2.3.4\\nsend\\n' "
                      f"| nsupdate -y hmac-sha256:kea-ddns:{secret} 2>&1", ok=False).stdout
      or "NOTAUTH" in sh(f"printf 'server {BIND_IP}\\nzone lan.test\\nupdate add evil.lan.test 60 A 1.2.3.4\\nsend\\n' "
                         f"| nsupdate -y hmac-sha256:kea-ddns:{secret} 2>&1", ok=False).stdout)

def leases_or_none():
    try:
        return list_leases(V)
    except Exception:
        return []


# a new container over the same run folder (restart, upgrade): the old PID file must not stop it
sh("docker rm -f kt-dhcp4")
start_dhcp4()
check("kea-dhcp4 starts again over the previous container's run folder; leases kept",
      until(lambda: sh("docker inspect -f {{.State.Running}} kt-dhcp4", ok=False).stdout.strip() == "true"
            and os.path.exists(f"{W}/kea/run/kea4-ctrl-socket") and time.sleep(3) is None
            and sh("docker inspect -f {{.State.Running}} kt-dhcp4", ok=False).stdout.strip() == "true"
            and any(l["ip"] == ip1 for l in leases_or_none())),
      sh("docker logs kt-dhcp4", ok=False).stderr[-600:])

insp = {c: json.loads(sh(f"docker inspect {c}").stdout)[0] for c in ("kt-dhcp4", "kt-ddns")}
h4, hd = insp["kt-dhcp4"]["HostConfig"], insp["kt-ddns"]["HostConfig"]
check("kea-dhcp4: only NET_RAW + NET_BIND_SERVICE, read-only, no-new-privileges",
      sorted(c.replace("CAP_", "") for c in h4.get("CapAdd") or []) == ["NET_BIND_SERVICE", "NET_RAW"]
      and h4["CapDrop"] == ["ALL"]
      and h4["ReadonlyRootfs"] and "no-new-privileges:true" in h4["SecurityOpt"], h4.get("CapAdd"))
check("kea-ddns: uid 915, no capabilities, read-only",
      insp["kt-ddns"]["Config"]["User"] == "915:915" and not hd.get("CapAdd") and hd["ReadonlyRootfs"])

cleanup()
print(f"\n{'FAILED' if FAILED else 'all passed'} ({FAILED} failures)")
sys.exit(1 if FAILED else 0)
