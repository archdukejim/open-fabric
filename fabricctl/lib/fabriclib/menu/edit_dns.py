import os

from fabriclib.common.console import BOLD, NC, RED
from fabriclib.common.paths import VARS_FILE
from fabriclib.dns.validate_record import HOST_RE
from fabriclib.menu.edit_dns_zone import edit_dns_zone
from fabriclib.menu.save_menu_change import save_menu_change


def edit_dns(data):
    """Purpose: menu listing the DNS zones in the vars (the main domain always first) and adding new zones.
    Inputs:  data — the vars working copy; a new zone is added to data["dns"] and saved.
    Returns: None when "b" is picked.
    Fails:   an invalid zone name (HOST_RE: it becomes a file name and goes into named.conf) is shown and refused;
             OSError saving; EOFError from input().
    Feeds:   run_vars_menu (menu 1), edit_complex_variable (key dns)."""
    while True:
        zones_data = data.get("dns") if isinstance(data.get("dns"), dict) else {}
        os.system("clear")
        print(f"{BOLD}--- DNS Records Editor ---{NC}\n")
        domain = data.get("domain", "example.com")
        zones = list(zones_data)
        if "dynamic_zone_var" not in zones:
            zones.insert(0, "dynamic_zone_var")
        print("Available Zones:")
        for i, z in enumerate(zones, 1):
            print(f"  {i}) {domain if z == 'dynamic_zone_var' else z} ({z})")
        print("\n  a) Add a new zone")
        print("  b) Back to variables")
        choice = input(f"Select a zone (1-{len(zones)}), 'a', or 'b': ").strip().lower()
        if choice == "b":
            return
        if choice == "a":
            new_zone = input("New zone name: ").strip().rstrip(".")
            if not HOST_RE.match(new_zone):
                print(f"{RED}Invalid zone name.{NC}")
                input("Press Enter to continue...")
            elif new_zone not in zones_data:
                data.setdefault("dns", {})[new_zone] = {}
                save_menu_change(VARS_FILE, data, "dns", "None", f"Added zone {new_zone}")
        elif choice.isdigit() and 1 <= int(choice) <= len(zones):
            edit_dns_zone(data, zones[int(choice) - 1], domain)
