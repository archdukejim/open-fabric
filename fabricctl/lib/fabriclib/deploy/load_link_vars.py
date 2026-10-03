import os

import yaml


def load_link_vars(paths, jinja_env, context):
    """Purpose: the landing page's links (link-vars.yaml), rendered with the settings, added to the context.
    Inputs:  paths — deploy_paths(); jinja_env; context — the render context, updated in place.
    Returns: None. The raw file is copied to <render>/link-vars.yaml for install; with no link-vars of the admin's
             own the shipped link-vars-template.yaml is used.
    Fails:   never for a bad file: it is reported ("Failed to parse …") and left out (the landing page keeps working).
    Feeds:   apply_deployment."""
    path = paths["link_vars"]
    if not os.path.exists(path):
        path = os.path.join(paths["fabric_dir"], "link-vars-template.yaml")
    if not os.path.exists(path):
        return
    try:
        with open(path) as f:
            raw = f.read()
        context.update(yaml.safe_load(jinja_env.from_string(raw).render(**context)) or {})
        with open(os.path.join(paths["render"], "link-vars.yaml"), "w") as f:
            f.write(raw)
    except Exception as e:                  # the admin's file: any error is reported, never fatal
        print(f"Failed to parse {path}: {e}")
