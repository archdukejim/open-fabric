import os

LIB_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FABRIC_DIR = os.path.dirname(LIB_DIR)
# the templates: jinja/ in an installed tree, templates/ in a checkout (manual 1.3.2)
JINJA_DIR = next((d for d in (os.path.join(FABRIC_DIR, "jinja"), os.path.join(FABRIC_DIR,
                                                                              "templates")) if os.path.isdir(d)),
                 os.path.join(FABRIC_DIR, "jinja"))


def deploy_paths():
    """Purpose: where the deploy engine reads from and writes to, read at call time (setup sets them per run).
    Inputs:  env DEPLOY_BASE_DIR (default /opt), CUSTOM_VARS_PATH (default <base>/fabric/config/vars.yaml),
             SECRETS_FILE_OVERRIDE (default <base>/fabric/config/fabric-secrets.yml), LINK_VARS_PATH (default
             <base>/fabric/config/link-vars.yaml).
    Returns: dict — fabric_dir (the tree this code runs from), repo_dir (its parent: a checkout), base (deploy base),
             target (<base>/fabric), config (<target>/config), vars, secrets, link_vars, federation (the registry),
             jinja (<fabric_dir>/jinja; a checkout's templates/), render (/tmp/fabric-render).
    Fails:   never.
    Feeds:   apply_deployment and every deploy step."""
    base = os.environ.get("DEPLOY_BASE_DIR", "/opt")
    target = os.path.join(base, "fabric")
    config = os.path.join(target, "config")
    return {
        "fabric_dir": FABRIC_DIR, "repo_dir": os.path.dirname(FABRIC_DIR), "base": base, "target": target,
        "config": config,
        "vars": os.environ.get("CUSTOM_VARS_PATH", os.path.join(config, "vars.yaml")),
        "secrets": os.environ.get("SECRETS_FILE_OVERRIDE", os.path.join(config, "fabric-secrets.yml")),
        "link_vars": os.environ.get("LINK_VARS_PATH", os.path.join(config, "link-vars.yaml")),
        "federation": os.path.join(config, "federation.yaml"),
        "jinja": JINJA_DIR, "render": "/tmp/fabric-render",
    }
