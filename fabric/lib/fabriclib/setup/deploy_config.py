import importlib
import os
import shutil
import sys

import yaml

from fabriclib.common.console import ok
from fabriclib.common.paths import LIB_DIR

CLI_WRAPPER = """#!/bin/bash
# fabricctl - fabric management CLI (installed by fabricctl setup)
if [[ " $* " == *" --version "* ]]; then
  exec bash "{target}/lib/manage.sh" --version
fi
if [[ "$EUID" -ne 0 ]]; then
  echo "Please run as root (sudo fabricctl)"
  exit 1
fi
exec bash "{target}/lib/manage.sh" "$@"
"""
LEGACY_ALIAS = """#!/bin/bash
echo "core-mgr is now fabricctl — this alias will be removed in the next release." >&2
exec /usr/local/bin/fabricctl "$@"
"""


def _write_exec(path, text):
    with open(path, "w") as f:
        f.write(text)
    os.chmod(path, 0o755)


def run(ctx):
    """Render every template from <config>/fabric.yaml and deploy config,
    compose files, systemd units and web assets without starting anything
    (deploy.py, start_services=False). Installs the fabricctl command."""
    fabric_yaml = os.path.join(ctx.config_dir, "fabric.yaml")
    with open(fabric_yaml, "w") as f:           # persist plan choices made after collect_vars
        yaml.safe_dump(ctx.vars, f, sort_keys=False)

    # Secrets are created in the install, never in a git checkout.
    if not os.path.exists(ctx.secrets_file):
        legacy = os.path.join(os.path.dirname(ctx.source_dir), "fabric-secrets.yml")
        if os.path.exists(legacy):
            shutil.copy2(legacy, ctx.secrets_file)
        else:
            open(ctx.secrets_file, "a").close()
    os.chmod(ctx.secrets_file, 0o600)

    os.environ.update({
        "DEPLOY_BASE_DIR": ctx.deploy_base,
        "CUSTOM_VARS_PATH": fabric_yaml,
        "SECRETS_FILE_OVERRIDE": ctx.secrets_file,
        "LINK_VARS_PATH": os.path.join(ctx.config_dir, "link-vars.yaml"),
    })
    if LIB_DIR not in sys.path:
        sys.path.insert(0, LIB_DIR)
    deploy = importlib.reload(importlib.import_module("deploy"))   # reads DEPLOY_BASE_DIR at import
    deploy.apply_deployment(start_services=False)
    ctx.load_state()
    ok(f"configuration deployed to {ctx.deploy_base}")

    _write_exec("/usr/local/bin/fabricctl", CLI_WRAPPER.format(target=ctx.target_dir))
    _write_exec("/usr/local/bin/core-mgr", LEGACY_ALIAS)
    ok("installed /usr/local/bin/fabricctl")
