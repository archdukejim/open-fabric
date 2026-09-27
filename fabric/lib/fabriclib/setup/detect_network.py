import ipaddress
import socket
import subprocess


def detect_network():
    """Best guesses for hostname, host_ip, lan_gateway, lan_cidr from the
    interface that carries the default route. Missing values are None."""
    guess = {"hostname": socket.gethostname().split(".")[0], "host_ip": None,
             "lan_gateway": None, "lan_cidr": None}
    route = subprocess.run(["ip", "-4", "route", "show", "default"], capture_output=True, text=True).stdout.split()
    if "via" in route:
        guess["lan_gateway"] = route[route.index("via") + 1]
    dev = route[route.index("dev") + 1] if "dev" in route else None
    if dev:
        addr = subprocess.run(["ip", "-o", "-4", "addr", "show", "dev", dev], capture_output=True, text=True).stdout.split()
        if "inet" in addr:
            iface = ipaddress.ip_interface(addr[addr.index("inet") + 1])
            guess["host_ip"] = str(iface.ip)
            guess["lan_cidr"] = str(iface.network)
    return guess
