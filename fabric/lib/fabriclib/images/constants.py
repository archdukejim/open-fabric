"""The services whose images fabric manages, in update order (dependencies
first). `var` is the vars key holding the pinned ref (for local builds: the
base they are built FROM); `build` is the local image name, if any."""
SERVICES = [
    {"name": "bind9", "unit": "bind9", "container": "bind9", "folder": "bind9", "var": "image_debian",
     "build": "fabric/bind9:local"},
    {"name": "stepca", "unit": "stepca", "container": "step-ca", "folder": "stepca", "var": "image_stepca",
     "build": "fabric/stepca:local"},
    {"name": "postgres", "unit": "postgres", "container": "postgres", "folder": "postgres", "var": "image_postgres",
     "build": None},
    {"name": "keycloak", "unit": "keycloak", "container": "keycloak", "folder": "keycloak", "var": "image_keycloak",
     "build": "fabric/keycloak:local"},
    {"name": "dirsrv", "unit": "ldap", "container": "dirsrv", "folder": "dirsrv", "var": "image_debian",
     "build": "fabric/dirsrv:local"},
    {"name": "openbao", "unit": "openbao", "container": "openbao", "folder": "openbao", "var": "image_openbao",
     "build": None},
    {"name": "nginx", "unit": "nginx", "container": "nginx", "folder": "nginx", "var": "image_nginx", "build": None},
    {"name": "kea", "unit": "kea", "container": "kea-dhcp4", "folder": "kea", "var": "image_debian",
     "build": "fabric/kea:local"},
    {"name": "freeradius", "unit": "freeradius", "container": "freeradius", "folder": "freeradius",
     "var": "image_debian", "build": "fabric/freeradius:local"},
    {"name": "fluentbit", "unit": "fluentbit", "container": "fluentbit", "folder": "fluentbit", "var": "image_fluentbit",
     "build": None},
    {"name": "fabric-web", "unit": "fabric-web", "container": "fabric-web", "folder": "webui", "var": "image_debian",
     "build": "fabric/web:local"},
]
STATE = "/etc/fabric/images/state.json"      # previous ref per image var (for rollback), root 0600
