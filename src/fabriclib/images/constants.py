"""The services whose images fabric manages, in update order (dependencies
first). `var` is the vars key holding the pinned ref (for local builds: the
base they are built FROM); `build` is the local image name, if any;
`published` names fabric's published image that replaces the local build
where the host can use it (manual 2.6.3, images/effective_service)."""
SERVICES = [
    {"name": "bind9", "unit": "bind9", "container": "bind9", "folder": "bind9", "var": "image_debian",
     "build": "fabric/bind9:local",
     "published": "bind9"},
    {"name": "stepca", "unit": "stepca", "container": "step-ca", "folder": "stepca", "var": "image_stepca",
     "build": "fabric/stepca:local",
     "published": "stepca"},
    {"name": "postgres", "unit": "postgres", "container": "postgres", "folder": "postgres", "var": "image_postgres",
     "build": None},
    {"name": "keycloak", "unit": "keycloak", "container": "keycloak", "folder": "keycloak", "var": "image_keycloak",
     "build": "fabric/keycloak:local",
     "published": "keycloak"},
    {"name": "dirsrv", "unit": "ldap", "container": "dirsrv", "folder": "dirsrv", "var": "image_debian",
     "build": "fabric/dirsrv:local",
     "published": "dirsrv"},
    {"name": "openbao", "unit": "openbao", "container": "openbao", "folder": "openbao", "var": "image_openbao",
     "build": None},
    {"name": "nginx", "unit": "nginx", "container": "nginx", "folder": "nginx", "var": "image_nginx", "build": None},
    {"name": "kea", "unit": "kea", "container": "kea-dhcp4", "folder": "kea", "var": "image_debian",
     "build": "fabric/kea:local",
     "published": "kea"},
    {"name": "freeradius", "unit": "freeradius", "container": "freeradius", "folder": "freeradius",
     "var": "image_debian", "build": "fabric/freeradius:local",
     "published": "freeradius"},
    {"name": "samba", "unit": "samba", "container": "samba", "folder": "samba", "var": "image_debian",
     "build": "fabric/samba:local",
     "published": "samba"},
    {"name": "fluentbit", "unit": "fluentbit", "container": "fluentbit", "folder": "fluentbit",
     "var": "image_fluentbit",
     "build": None},
    {"name": "adguard", "unit": "adguard", "container": "adguardhome", "folder": "adguard", "var": "image_adguard",
     "build": "fabric/adguard:local",
     "published": "adguard"},
    {"name": "oauth2proxy", "unit": "adguard-auth", "container": "oauth2-proxy-adguard", "folder": "adguard-auth",
     "var": "image_oauth2proxy", "build": None},
    {"name": "fabric-web", "unit": "fabric-web", "container": "fabric-web", "folder": "webui", "var": "image_debian",
     "build": "fabric/web:local",
     "published": "webui"},
]
STATE = "/etc/fabric/images/state.json"      # previous ref per image var (for rollback), root 0600
VERIFIED = "/etc/fabric/images/verified.json"  # digests whose signature verified (manual 2.6.3.4), root 0600
