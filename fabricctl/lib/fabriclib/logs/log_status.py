import json
import urllib.request


def log_status(v, timeout=3):
    """Purpose: Log forwarding at a glance, from Fluent Bit's own metrics (http://<ip_fluentbit>:2020, reachable on
             fabric_net only).
    Inputs:  v — the vars dict (install_fluentbit, ip_fluentbit).
             timeout — seconds for the HTTP request (default 3).
    Returns: {"enabled": False} when Fluent Bit is not installed; else {"enabled": True, "reachable", "outputs": {name:
             {"sent", "retries", "errors", "dropped"}} (null outputs skipped), and "error" when unreachable}.
    Fails:   never for network or JSON errors (they go into "error"); KeyError if ip_fluentbit is missing.
    Feeds:   run_logs_command (status); tests/fluentbit/run.py.
    """
    if not v.get("install_fluentbit"):
        return {"enabled": False}
    out = {"enabled": True, "reachable": False, "outputs": {}}
    try:
        with urllib.request.urlopen(f"http://{v['ip_fluentbit']}:2020/api/v1/metrics", timeout=timeout) as r:
            metrics = json.load(r)
    except (OSError, ValueError) as exc:
        out["error"] = str(exc)
        return out
    out["reachable"] = True
    for name, m in (metrics.get("output") or {}).items():
        if name.startswith("null"):
            continue
        out["outputs"][name] = {"sent": m.get("proc_records", 0), "retries": m.get("retries", 0),
                                "errors": m.get("errors", 0), "dropped": m.get("dropped_records", 0)}
    return out
