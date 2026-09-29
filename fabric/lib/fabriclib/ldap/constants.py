"""Device RBAC vocabulary, shared by the directory operations and the web UI."""
import re

DEVICE_TYPES = ["laptop", "desktop", "phone", "tablet", "printer", "camera", "iot", "network", "server", "other"]

# permission -> (what it grants, what enforces it)
PERMISSIONS = {
    "network:eap-tls": ("Join the network with its certificate (802.1X EAP-TLS)", "FreeRADIUS"),
    "network:mab": ("Join the network by MAC address (MAB — printers, IoT)", "FreeRADIUS"),
    "dns:dhcp-register": ("Register its DHCP hostname in the DHCP zone", "Kea DHCP-DDNS"),
    "pki:acme": ("Obtain and renew certificates by ACME", "Step-CA"),
    "pki:scep": ("Enrol certificates by SCEP (MDM, network gear)", "Step-CA"),
}

DEVICE_NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
ROLE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")
USER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,63}$")
FINGERPRINT_RE = re.compile(r"^[0-9A-F]{2}(:[0-9A-F]{2}){31}$")
