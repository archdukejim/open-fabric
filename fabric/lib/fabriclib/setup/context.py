import os
from dataclasses import dataclass, field

import yaml

from fabriclib.common.paths import FABRIC_DIR


@dataclass
class SetupContext:
    """Everything a setup step needs. `source_dir` is the fabric/ tree the
    code runs from (a git checkout or an installed copy); the install lives
    under `deploy_base` (default /opt)."""
    deploy_base: str = "/opt"
    source_dir: str = FABRIC_DIR
    user_vars_file: str = None
    offline: bool = False
    non_interactive: bool = False
    assume_yes: bool = False
    vars: dict = field(default_factory=dict)      # rendered vars (after deploy)
    secrets: dict = field(default_factory=dict)
    restart_services: set = field(default_factory=set)   # certs/config changed this run
    force_certs: bool = False                     # re-issue service certs even if current

    @property
    def target_dir(self):
        return os.path.join(self.deploy_base, "fabric")

    @property
    def config_dir(self):
        return os.path.join(self.target_dir, "config")

    @property
    def vars_file(self):
        return os.path.join(self.config_dir, "vars.yaml")

    @property
    def secrets_file(self):
        return os.path.join(self.config_dir, "fabric-secrets.yml")

    def path(self, *parts):
        return os.path.join(self.deploy_base, *parts)

    def load_state(self):
        """Read the rendered vars and secrets written by the deploy step."""
        for attr, path in (("vars", self.vars_file), ("secrets", self.secrets_file)):
            if os.path.exists(path):
                with open(path) as f:
                    setattr(self, attr, yaml.safe_load(f) or {})
        return self

    def uid(self, user):
        u = self.vars.get("service_users", {}).get(user, {})
        return int(u.get("uid", 0)), int(u.get("gid", 0))

    def enabled(self, flag, default=False):
        return bool(self.vars.get(flag, default))
