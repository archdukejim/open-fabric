#!/usr/bin/env python3
"""Test helper, run as root on a fabric host: put a directory user back to
their first-login state so the scripted sign-in test also works on a host
that was set up (and signed into) before:

  - 389-DS password set to the given one (from the environment: PW)
  - Keycloak: TOTP credentials removed, a new password required

    PW=… python3 reset_user.py <user>        prints "reset <user>"
"""
import os
import subprocess
import sys

import yaml

sys.path.insert(0, "/opt/fabric/lib")
from fabriclib.keycloak.admin_client import Admin  # noqa: E402
from fabriclib.keycloak.quote import q  # noqa: E402
from fabriclib.secrets.load_secrets import load_secrets  # noqa: E402
from webui.tlsclient import TLSClient  # noqa: E402

IN_CONTAINER = r'''
import os, ldap
c = ldap.initialize("ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket")
c.simple_bind_s("cn=Directory Manager", os.environ["DS_DM_PASSWORD"])
c.modify_s(os.environ["F_DN"], [(ldap.MOD_REPLACE, "userPassword", [os.environ["F_PW"].encode()])])
'''

user = sys.argv[1]
v = yaml.safe_load(open("/opt/fabric/config/vars.yaml"))
env = {**os.environ, "F_DN": f"uid={user},ou=users,ou=accounts,{v['ldap_base_dn']}", "F_PW": os.environ["PW"]}
subprocess.run(["docker", "exec", "-i", "-e", "F_DN", "-e", "F_PW", "dirsrv", "python3", "-"],
               input=IN_CONTAINER, env=env, text=True, check=True, capture_output=True)

s = load_secrets("/opt/fabric/config/fabric-secrets.yml", v)
ca = os.path.join(v["deploy_base_dir"], "stepca", "data", "certs", "root_ca.crt")
kc = Admin(TLSClient(v["ip_keycloak"], 8443, v["hostname_keycloak"], ca),
           s["keycloak_admin_user"], s["keycloak_admin_password"])
realm = q(v.get("webui_realm") or v["domain"])
_, found = kc.call("GET", f"/{realm}/users?username={q(user)}&exact=true")
if found:
    rep = found[0]
    _, creds = kc.call("GET", f"/{realm}/users/{rep['id']}/credentials")
    for cred in creds:
        if cred.get("type") == "otp":
            kc.call("DELETE", f"/{realm}/users/{rep['id']}/credentials/{cred['id']}")
    # only the field that changes: a federated user's record carries read-only LDAP attributes
    kc.call("PUT", f"/{realm}/users/{rep['id']}", {"requiredActions": ["UPDATE_PASSWORD"]})
    kc.call("POST", f"/{realm}/users/{rep['id']}/logout")
print(f"reset {user}")
