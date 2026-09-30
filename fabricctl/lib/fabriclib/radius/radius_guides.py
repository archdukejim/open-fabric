from fabriclib.pki.common.ca_files import ca_files
from fabriclib.radius.windows_setup_script import windows_setup_script


def radius_guides(v, root_pem=None):
    """What the FreeRADIUS tab's setup guides need, filled in for this
    install: where switches send RADIUS, the certificate name supplicants
    check, where the CA certificates are published, the RADIUS clients, the
    groups mapped for password logins, and a Windows setup script per
    method ({tls, ttls}: {filename, script}). Only public data."""
    if root_pem is None:
        with open(ca_files(v)[0]) as f:
            root_pem = f.read()
    windows = {}
    for method in ("tls", "ttls"):
        filename, script = windows_setup_script(v, method, root_pem)
        windows[method] = {"filename": filename, "script": script}
    return {"host_ip": v.get("host_ip", ""), "server_name": v.get("hostname_radius", ""),
            "certs_url": f"http://{v.get('hostname_certs', '')}/", "domain": v.get("domain", ""),
            "clients": [c.get("name") for c in v.get("radius_clients") or []],
            "people": [m.get("group") for m in v.get("radius_people") or []],
            "windows": windows}
