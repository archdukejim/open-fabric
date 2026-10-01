import base64
import os

from fabriclib.common.console import info, ok
from fabriclib.common.errors import ValidationError
from fabriclib.common.read_images_lock import read_images_lock
from fabriclib.federation.join_upstream import join_upstream
from fabriclib.secrets.save_secrets import save_secrets
from fabriclib.setup.errors import SetupError


def run(ctx):
    """Purpose: setup step `join` (only with `fabricctl setup --join`): join the upstream before
             anything is rendered, so this install is set up as a site of that fabric — its CA an
             intermediate signed by the organisation's root (bring-your-own-CA path), its organisation suffix
             the upstream's (design federation.md §4).
    Inputs:  ctx — SetupContext: join_invitation, vars (from collect_vars: domain, host_ip, image_stepca if set),
             secrets / secrets_file (ca_password, created here if missing), config_dir, source_dir (images.lock).
    Returns: None. ctx.vars gains byoc, ca_crt_path, ica_crt_path, ica_key_path, site_name, org_domain and the
             organisation's cert_* settings (friendly_name only when unset); the deploy step saves them. The
             site CA key and certificates are kept in <base>/fabric/config/site-ca (0700).
    Fails:   SetupError with join_upstream's message (invitation damaged/expired/used, the upstream refused or
             unreachable, the root not the pinned one, a certificate that does not fit).
    Feeds:   setup STEPS, after `docker` (the key is made with the pinned Step-CA image) and before `deploy`.
    Notes:   without --join it does nothing. A re-run after a successful join reuses what was staged and does
             not contact the upstream again (the invitation is single-use). The key is made as root: the step
             user does not exist yet; the pki step copies it into Step-CA's data and gives it to that user."""
    if not ctx.join_invitation:
        return
    password = ctx.secrets.get("ca_password")
    if not password:
        password = base64.b64encode(os.urandom(32)).decode()
        try:
            save_secrets({"ca_password": password}, ctx.secrets_file)
        except ValidationError as e:
            raise SetupError(str(e)) from None
        ctx.secrets = None                       # reload on next use
    image = ctx.vars.get("image_stepca") or read_images_lock(ctx.source_dir)["stepca"]["ref"]
    v = {**ctx.vars, "image_stepca": image, "service_users": {"step": {"uid": 0, "gid": 0}}}
    info("joining the upstream fabric (one-time invitation)")
    try:
        res = join_upstream(v, ctx.join_invitation, password, os.path.join(ctx.config_dir, "site-ca"),
                            ctx.vars["domain"], ctx.vars["host_ip"], config_dir=ctx.config_dir,
                            audit_path=ctx.path("fabric", "archive", "audit.log"))
    except ValidationError as e:
        raise SetupError(f"joining the upstream failed: {e}") from None
    joined = dict(res["vars"])
    if ctx.vars.get("friendly_name"):
        joined.pop("friendly_name", None)
    ctx.vars.update(joined)
    up = res["upstream"]
    ok(f"{'joined' if res['joined'] else 'member of'} {up['site_name']} ({up['domain']}) as site "
       f"{ctx.vars['site_name']}; CA: an intermediate of the organisation's root")
