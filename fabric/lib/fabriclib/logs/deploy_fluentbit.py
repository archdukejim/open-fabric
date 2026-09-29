import os
import shutil

from fabriclib.common.errors import ValidationError


def _write(path, text, mode, uid=0, gid=0):
    """Write if different; returns True if it changed."""
    if os.path.exists(path) and open(path).read() == text:
        return False
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chown(path + ".tmp", uid, gid)
    os.replace(path + ".tmp", path)
    return True


def deploy_fluentbit(v, secrets, jinja_env):
    """Fluent Bit's files under <deploy_base>/fluentbit: its config (from
    fabric/jinja/fluentbit/fluent-bit.yaml.j2), the CA certificates that
    verify each destination (the destination's own `ca_file`, else the
    fabric root CA), the credentials file docker reads for the container
    (root 0600, from fabric's secrets in OpenBao) and the disk buffer.
    Returns True if anything changed (the service must restart)."""
    base = os.path.join(v["deploy_base_dir"], "fluentbit")
    uid, gid = (int(v["service_users"]["fluentbit"][k]) for k in ("uid", "gid"))
    for sub, owner, mode in (("config", (0, gid), 0o750), ("buffer", (uid, gid), 0o750)):
        path = os.path.join(base, sub)
        os.makedirs(path, mode=mode, exist_ok=True)
        os.chown(path, *owner)
        os.chmod(path, mode)
    cfg = os.path.join(base, "config")
    changed = _write(os.path.join(cfg, "fluent-bit.yaml"),
                     jinja_env.get_template("fluentbit/fluent-bit.yaml.j2").render(**v), 0o640, 0, gid)
    fabric_ca = os.path.join(v["deploy_base_dir"], "stepca", "data", "certs", "root_ca.crt")
    lf = v.get("log_forwarding") or {}
    for name in ("syslog", "elastic"):
        src = (lf.get(name) or {}).get("ca_file") or fabric_ca
        if not os.path.isfile(src):
            raise ValidationError(f"log_forwarding.{name}.ca_file {src} not found")
        changed |= _write(os.path.join(cfg, f"{name}-ca.crt"), open(src).read(), 0o640, 0, gid)
    env = f"LOG_ELASTIC_PASSWORD={secrets.get('log_elastic_password', '')}\n"
    changed |= _write(os.path.join(cfg, "secrets.env"), env, 0o600)
    return changed
