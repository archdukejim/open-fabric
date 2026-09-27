import subprocess


class CommandError(RuntimeError):
    """A command exited non-zero; message includes its stderr tail."""


def run(cmd, check=True, input=None, env=None, timeout=600, capture=True):
    """Run a command (list form, never through a shell) and return the
    CompletedProcess. Secrets must be passed via `input` or `env`, never
    argv (argv is visible to every user in `ps`)."""
    res = subprocess.run(cmd, input=input, env=env, timeout=timeout, text=True,
                         capture_output=capture)
    if check and res.returncode != 0:
        tail = ((res.stderr or "") + (res.stdout or "")).strip()[-800:] if capture else ""
        raise CommandError(f"{' '.join(map(str, cmd[:6]))}{' …' if len(cmd) > 6 else ''} failed ({res.returncode})"
                           + (f": {tail}" if tail else ""))
    return res
