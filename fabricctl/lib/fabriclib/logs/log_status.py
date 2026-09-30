import json
import urllib.request


def log_status(v, timeout=3):
    """Log forwarding at a glance, from Fluent Bit's own metrics
    (http://<ip_fluentbit>:2020, on fabric_net only): per destination the
    records sent, retries, errors and dropped records. {"enabled": False}
    when Fluent Bit is not installed; "reachable": False when it is down."""
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
