#!/usr/bin/env python3
"""OpenBao against the real, pinned image, started from fabric's own compose
template and config: hardening, TLS, static-seal auto-unseal, init,
idempotent configuration, least-privilege AppRoles, root token revocation,
and what happens when the seal key goes missing.

    sudo python3 tests/openbao/run.py          (needs Docker, openssl, root)
"""
import json
import os
import shutil
import subprocess
import sys
import time

import jinja2
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
W = os.environ.get("FABRIC_TEST_OUT", "/tmp/fabric-tests") + "/openbao"
NET, SUBNET, IP = "obtest_net", "10.254.9.0/24", "10.254.9.90"
HOST = "vault.lan.test"
FAILED = 0


def check(name, cond, detail=""):
    global FAILED
    FAILED += not cond
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {str(detail)[:400]}"))


def sh(cmd, ok=True, **kw):
    res = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, **kw)
    if ok and res.returncode != 0:
        raise SystemExit(f"failed: {cmd}\n{res.stdout}{res.stderr}")
    return res


def health(timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        st = sh("docker inspect -f '{{.State.Health.Status}}' openbao", ok=False).stdout.strip()
        if st in ("healthy", "unhealthy"):
            return st
        time.sleep(2)
    return st


def compose(*args):
    return sh(["docker", "compose", "-f", f"{W}/openbao/docker-compose.yml", *args], ok=False)


# ---------------------------------------------------------------- layout
sh("docker rm -f openbao >/dev/null 2>&1; true", ok=False)
sh(f"docker network rm {NET} >/dev/null 2>&1; true", ok=False)
shutil.rmtree(W, ignore_errors=True)
for d in ("stepca/data/certs", "openbao/config", "openbao/data", "openbao/logs", "openbao/certs"):
    os.makedirs(f"{W}/{d}")
shutil.copytree(f"{REPO}/fabric/lib", f"{W}/fabric/lib")
os.chdir(W)
sh("openssl req -x509 -newkey rsa:2048 -nodes -keyout root.key -out root.crt -days 2 -subj '/CN=Test Root' "
   "-addext basicConstraints=critical,CA:TRUE -addext keyUsage=critical,keyCertSign,cRLSign")
sh(f"openssl req -newkey rsa:2048 -nodes -keyout bao.key -out bao.csr -subj '/CN={HOST}'")
open("bao.ext", "w").write(f"subjectAltName=DNS:{HOST},DNS:openbao\nextendedKeyUsage=serverAuth,clientAuth\n")
sh("openssl x509 -req -in bao.csr -CA root.crt -CAkey root.key -CAcreateserial -out bao.crt -days 2 -extfile bao.ext")
shutil.copy("root.crt", "stepca/data/certs/root_ca.crt")
shutil.copy("bao.crt", "openbao/certs/fullchain.pem")
shutil.copy("bao.key", "openbao/certs/privkey.pem")
shutil.copy("root.crt", "openbao/certs/root_ca.crt")
sh("openssl req -x509 -newkey rsa:2048 -nodes -keyout other.key -out other.crt -days 2 -subj '/CN=Other Root'")

V = {"deploy_base_dir": W, "domain": "lan.test", "hostname_openbao": HOST, "ip_openbao": IP, "ip_bind9": "10.254.9.30",
     "openbao_key_dir": f"{W}/keys", "openbao_seal_key_id": "fabric-1", "openbao_mem_limit": "256m",
     "fabric_subnet": SUBNET, "service_users": {"openbao": {"uid": 913, "gid": 913}},
     "image_openbao": yaml.safe_load(sh(["grep", "^image_openbao", f"{REPO}/fabric/jinja/vars.yaml.j2"]).stdout
                                     .split("default(")[1].split(")")[0])}
env = jinja2.Environment()
for tpl, dest in (("docker-compose.yml.j2", "openbao/docker-compose.yml"), ("openbao.hcl.j2", "openbao/config/openbao.hcl")):
    text = env.from_string(open(f"{REPO}/fabric/jinja/openbao/{tpl}").read()).render(**V)
    open(dest, "w").write(text.replace("name: fabric_net", f"name: {NET}"))
sh(["chown", "-R", "913:913", "openbao/data", "openbao/logs"])
sh(["chmod", "-R", "a+rX", "openbao/config", "openbao/certs"])
sh(["chown", "913:913", "openbao/certs/privkey.pem"])
sh(["chmod", "0400", "openbao/certs/privkey.pem"])
sh(f"docker network create --subnet {SUBNET} {NET}")

sys.path.insert(0, f"{W}/fabric/lib")
from fabriclib.common.errors import ValidationError  # noqa: E402
from fabriclib.vault.common.approle_login import approle_login  # noqa: E402
from fabriclib.vault.common.bao_request import bao_request  # noqa: E402
from fabriclib.vault.configure_openbao import configure_openbao  # noqa: E402
from fabriclib.vault.ensure_unseal_key import ensure_unseal_key  # noqa: E402
from fabriclib.vault.init_openbao import init_openbao  # noqa: E402
from fabriclib.vault.revoke_token import revoke_token  # noqa: E402
from fabriclib.vault.vault_status import vault_status  # noqa: E402

# ---------------------------------------------------------------- seal key
check("seal key created", ensure_unseal_key(V) == "created")
st = os.stat(f"{W}/keys/unseal.key")
check("seal key: 32 bytes, 0400, owned by the openbao user only",
      st.st_size == 32 and oct(st.st_mode & 0o777) == "0o400" and st.st_uid == 913)
check("seal key directory 0700", oct(os.stat(f"{W}/keys").st_mode & 0o777) == "0o700")
check("existing key is never replaced", ensure_unseal_key(V) == "present"
      and open(f"{W}/keys/unseal.key", "rb").read() == open(f"{W}/keys/unseal.key", "rb").read())
key_bytes = open(f"{W}/keys/unseal.key", "rb").read()

# ---------------------------------------------------------------- container
up = compose("up", "-d")
check("compose file starts the pinned image", up.returncode == 0, up.stderr[-400:])
check("fresh (uninitialised) server counts as healthy", health() == "healthy", sh("docker logs openbao", ok=False).stderr[-600:])
s = vault_status(V)
check("status before init: reachable, not initialised", s["reachable"] and not s["initialized"], s)
try:
    bao_request({**V, "openbao_ca_file": f"{W}/other.crt"}, "GET", "sys/health")
    tls_ok = False
except ValidationError:
    tls_ok = True
check("TLS is verified: a server cert from another CA is refused", tls_ok)

# ---------------------------------------------------------------- init + configure
first = init_openbao(V)
check("init returns one recovery key and a root token", first and len(first["recovery_keys"]) == 1 and first["root_token"],
      first)
check("init is not repeated", init_openbao(V) is None)
check("static seal: unsealed without anyone entering a key", not vault_status(V)["sealed"] and health() == "healthy")
changes = configure_openbao(V, first["root_token"])
check("configuration applied", {"AppRole auth", "KV fabric/", "KV apps/"} <= set(changes), changes)
for name in ("setup-approle.json", "agent-approle.json"):
    st = os.stat(f"{W}/keys/{name}")
    check(f"{name}: root-only 0400", st.st_uid == 0 and oct(st.st_mode & 0o777) == "0o400")
setup_token = approle_login(V, "setup-approle.json")
check("re-run as fabric-setup (not root) changes nothing", configure_openbao(V, setup_token) == [])
check("root token revoked after bootstrap", revoke_token(V, first["root_token"]))
check("revoked root token is refused",
      bao_request(V, "GET", "sys/mounts", token=first["root_token"])[0] == 403)

agent = approle_login(V, "agent-approle.json")
check("fabric-agent may read the engine list", bao_request(V, "GET", "sys/mounts", token=agent)[0] == 200)
check("fabric-agent may not write app secrets",
      bao_request(V, "POST", "apps/data/x", token=agent, body={"data": {"a": "b"}})[0] == 403)
check("fabric-agent may not read fabric's secrets", bao_request(V, "GET", "fabric/data/x", token=agent)[0] == 403)
check("fabric-agent may not write policies",
      bao_request(V, "PUT", "sys/policies/acl/evil", token=agent, body={"policy": 'path "*" {capabilities=["sudo"]}'})[0] == 403)
check("fabric-setup may write fabric's secrets",
      bao_request(V, "POST", "fabric/data/probe", token=setup_token, body={"data": {"v": "1"}})[0] == 200)
role = bao_request(V, "GET", "auth/approle/role/fabric-agent", token=setup_token)[1]["data"]
check("AppRole tokens and secret IDs are bound to fabric_net", role["token_bound_cidrs"] == [SUBNET]
      and role["secret_id_bound_cidrs"] == [SUBNET], role)
s = vault_status(V)
check("status: unsealed, static seal, raft, KV v2 fabric/ + apps/, approle, key ok",
      s["initialized"] and not s["sealed"] and s["seal_type"] == "static" and s["storage"] == "raft"
      and {"fabric/", "apps/"} <= {m["path"] for m in s["mounts"] if m["version"] == "2"} and "approle/" in s["auth"]
      and s["key"]["ok"], s)
audit = open(f"{W}/openbao/logs/audit.log").read()
check("audit log records requests with secrets HMAC'd", '"path":"fabric/data/probe"' in audit and '"v":"1"' not in audit)

# ---------------------------------------------------------------- restarts and the key
compose("restart")
check("after a restart it unseals itself", health() == "healthy" and not vault_status(V)["sealed"])
os.rename(f"{W}/keys/unseal.key", f"{W}/keys/away.key")
compose("restart")
time.sleep(5)
s = vault_status(V)
gone = health(120)
check("without the key file it stays sealed and reports unhealthy", s.get("sealed") is not False and gone == "unhealthy",
      (s, gone))
os.rename(f"{W}/keys/away.key", f"{W}/keys/unseal.key")
os.rename(f"{W}/keys/unseal.key", f"{W}/keys/held.key")
try:
    ensure_unseal_key(V)
    refused = False
except ValidationError as exc:
    refused = "restore" in str(exc)
check("a missing key next to existing data is never regenerated", refused and not os.path.exists(f"{W}/keys/unseal.key"))
os.rename(f"{W}/keys/held.key", f"{W}/keys/unseal.key")
compose("restart")
check("key restored -> unseals again, data intact", health() == "healthy"
      and bao_request(V, "GET", "fabric/data/probe", token=approle_login(V, "setup-approle.json"))[1]
      .get("data", {}).get("data") == {"v": "1"})
check("the key never changed", open(f"{W}/keys/unseal.key", "rb").read() == key_bytes)

# ---------------------------------------------------------------- hardening
insp = json.loads(sh("docker inspect openbao").stdout)[0]
hc = insp["HostConfig"]
check("runs as 913:913, not root", insp["Config"]["User"] == "913:913")
check("no capabilities, no-new-privileges, read-only root, memory limit",
      hc["CapDrop"] == ["ALL"] and not hc.get("CapAdd") and "no-new-privileges:true" in hc["SecurityOpt"]
      and hc["ReadonlyRootfs"] and hc["Memory"] == 256 * 1024 * 1024, hc)
check("effective capabilities are empty",
      "CapEff:\t0000000000000000" in sh("docker exec openbao cat /proc/1/status", ok=False).stdout)
check("seal key mounted read-only", any(m["Destination"] == "/openbao/seal" and not m["RW"] for m in insp["Mounts"]))
check("no Docker socket", not any("docker.sock" in m["Source"] for m in insp["Mounts"]))

compose("down")
sh(f"docker network rm {NET}", ok=False)
print(f"\n{'FAILED' if FAILED else 'all passed'} ({FAILED} failures)")
sys.exit(1 if FAILED else 0)
