#!/usr/bin/env python3
"""Run upstream dscontainer without its SIGCHLD handler.

dscontainer reaps children from a SIGCHLD handler that calls
os.waitpid(-1, WNOHANG) unguarded. When subprocess reaps the child first the
handler raises ChildProcessError and instance setup dies at random. tini is
PID 1 in this image and reaps orphans, so the handler is simply not needed.

It also removes a pid file left in /data/run by the container's previous life: /data is persisted, PIDs in a
new container start low again, and ns-slapd refuses to start when the old file names a PID that some other
process now has ("Unable to start slapd because it is already running as process 23") — at random, depending
on PID reuse. Nothing of 389-DS runs before this entrypoint, so every pid file there is stale.
"""
import glob
import os
import runpy
import signal
import sys

DSCONTAINER = "/usr/libexec/dirsrv/dscontainer"
_real_signal = signal.signal


def _signal(sig, handler):
    """Purpose: stand-in for signal.signal that refuses to install a SIGCHLD handler, so upstream
             dscontainer's unguarded waitpid handler never runs (tini, PID 1, reaps children instead).
    Inputs:  sig — signal number; handler — the handler dscontainer asks for.
    Returns: signal.SIG_DFL for SIGCHLD (nothing installed); otherwise the previous handler, as signal.signal does.
    Fails:   as signal.signal for other signals (ValueError, OSError on an invalid signal).
    Feeds:   installed as signal.signal before this script runs /usr/libexec/dirsrv/dscontainer (the image's
             ENTRYPOINT, dirsrv/build/Dockerfile)."""
    if sig == signal.SIGCHLD:
        return signal.SIG_DFL
    return _real_signal(sig, handler)


for stale in glob.glob("/data/run/*.pid"):
    os.remove(stale)
signal.signal = _signal
sys.argv = [DSCONTAINER] + (sys.argv[1:] or ["-r"])
runpy.run_path(DSCONTAINER, run_name="__main__")
