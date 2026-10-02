"""The kinds of host change fabric asks about (design host-consent.md §2), in the order setup asks.

level: "required" — declining stops setup; "recommended" — declining leaves that part unmanaged and shows a
relaxation; "choice" — needed only because of a setting, declining asks for the other choice."""

GROUPS = {
    "packages": {"title": "Packages", "level": "required", "step": "host",
                 "declined": "setup cannot run without them"},
    "runtime": {"title": "Docker daemon settings", "level": "recommended", "step": "docker",
                "declined": "the Docker daemon is not hardened (containers may gain privileges via setuid "
                            "binaries; logs can fill the disk)"},
    "services": {"title": "fabric's own services", "level": "required", "step": "deploy",
                 "declined": "fabric cannot run without its services"},
    "accounts": {"title": "Service accounts", "level": "required", "step": "accounts",
                 "declined": "the services cannot own their files without them"},
    "resolver": {"title": "Host DNS resolver", "level": "choice", "step": "network",
                 "declined": "set use_host_dns: true (keep the host's resolver) and free port 53 another way"},
    "firewall": {"title": "Host firewall", "level": "recommended", "step": "firewall",
                 "declined": "the host firewall is not managed by fabric: every published port is reachable "
                             "from any network that can route to this host"},
    "trust": {"title": "Host trust store", "level": "recommended", "step": "pki",
              "declined": "this host does not trust fabric's CA: tools on the host (curl, apt, browsers) reject "
                          "fabric's certificates unless given the CA"},
    "time": {"title": "Time service (chrony)", "level": "recommended", "step": "deploy",
             "declined": "chrony keeps the host's own configuration: fabric does not serve time to the network "
                         "or follow the upstream site"},
}
