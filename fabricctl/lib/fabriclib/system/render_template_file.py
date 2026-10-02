import os
import pwd

from fabriclib.common.jinja_env import jinja_env
from fabriclib.common.load_vars import load_vars


def render_template_file(template, vars_path, output=None):
    """Purpose: `fabricctl --render-jinja <file.j2> [--vars FILE] [--output FILE|DIR]`: render one Jinja2 template with
             fabric's vars and filters, for checking a template or making a config file from them.
    Inputs:  template — the .j2 file; vars_path — the vars file (default <fabric>/config/vars.yaml, chosen by the
             caller); output — a file or a folder (default: the sudo caller's home). Env SUDO_USER/USER.
    Returns: exit status 0 after "Render complete: <dest>"; 1 with a message when the template or vars file is
             missing or the template does not render.
    Fails:   OSError writing the result (an unknown user only skips the chown).
    Feeds:   cli.py (--render-jinja).
    Notes:   the result is named after the template without .j2 (or <name>.rendered), mode 0644, owned by the
             caller."""
    if not template or not os.path.isfile(template):
        print(f"[✗] Template file not found: {template or '(none given)'}. Usage: --render-jinja <file.j2>")
        return 1
    if not os.path.isfile(vars_path):
        print(f"[✗] Vars file not found: {vars_path}")
        return 1
    user = os.environ.get("SUDO_USER") or os.environ.get("USER") or "root"
    name = os.path.basename(template)
    name = name[:-3] if name.endswith(".j2") else f"{name}.rendered"
    if output:
        dest = os.path.join(output, name) if os.path.isdir(output) else output
    else:
        try:
            dest = os.path.join(pwd.getpwnam(user).pw_dir, name)
        except KeyError:
            dest = os.path.join(os.getcwd(), name)
    print(f"Rendering {template} -> {dest}\nUsing vars: {vars_path}")
    try:
        env = jinja_env(os.path.dirname(os.path.abspath(template)))
        text = env.get_template(os.path.basename(template)).render(**load_vars(vars_path))
    except Exception as e:                  # any template error: report it (the old shell version hid it)
        print(f"[✗] Template error: {e}")
        return 1
    with open(dest, "w") as f:
        f.write(text)
    os.chmod(dest, 0o644)
    if user != "root":
        try:
            pw = pwd.getpwnam(user)
            os.chown(dest, pw.pw_uid, pw.pw_gid)
        except KeyError:
            pass
    print(f"Render complete: {dest}")
    return 0
