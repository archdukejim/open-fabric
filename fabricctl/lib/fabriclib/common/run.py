import subprocess


class CommandError(RuntimeError):
    """A command exited non-zero; message includes its stderr tail."""


def run(cmd, check=True, input=None, env=None, timeout=600, capture=True):
    """Purpose: run a command as an argument list (never through a shell) with an error that carries its
             output. Secrets go via `input` or `env`, never argv (argv is visible to every user in `ps`).
    Inputs:  cmd — list of str; check — bool, raise on non-zero exit (default True); input — str for stdin;
             env — dict replacing the whole environment (None = inherit); timeout — seconds, default 600;
             capture — bool, capture stdout/stderr as text (default True).
    Returns: subprocess.CompletedProcess (text mode).
    Fails:   CommandError (first 6 args, exit code and the last 800 chars of stderr+stdout) when check and the exit
             is non-zero; subprocess.TimeoutExpired on timeout; FileNotFoundError if the program does not exist.
    Feeds:   setup/condition_host.py."""
    res = subprocess.run(cmd, input=input, env=env, timeout=timeout, text=True,
                         capture_output=capture)
    if check and res.returncode != 0:
        tail = ((res.stderr or "") + (res.stdout or "")).strip()[-800:] if capture else ""
        raise CommandError(f"{' '.join(map(str, cmd[:6]))}{' …' if len(cmd) > 6 else ''} failed ({res.returncode})"
                           + (f": {tail}" if tail else ""))
    return res
