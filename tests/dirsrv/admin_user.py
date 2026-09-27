"""Run fabriclib/ldap/ensure_admin_user.py (setup's admin step) against the
test 389-DS container. Inputs come from the environment, never argv."""
import os
import sys

sys.path.insert(0, os.path.join(os.environ["REPO"], "fabric", "lib"))
from fabriclib.ldap.ensure_admin_user import ensure_admin_user  # noqa: E402

print(ensure_admin_user({"ldap_base_dn": os.environ["BASE"]}, "jim", os.environ["PW"], "jim@lan.test",
                        container="dstest"))
