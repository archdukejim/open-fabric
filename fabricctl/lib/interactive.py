#!/usr/bin/env python3
import sys
import os
import yaml
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from fabriclib.common.errors import ValidationError  # noqa: E402
from fabriclib.common.load_vars import load_vars  # noqa: E402
from fabriclib.common.write_audit import write_audit  # noqa: E402
from fabriclib.dns.add_record import add_record  # noqa: E402
from fabriclib.dns.constants import RECORD_TYPES  # noqa: E402
from fabriclib.dns.format_value import format_value  # noqa: E402
from fabriclib.dns.remove_record import remove_record  # noqa: E402
from fabriclib.dns.sync_status import sync_status  # noqa: E402
from fabriclib.dns.validate_record import HOST_RE  # noqa: E402
FABRIC_DIR = os.path.dirname(SCRIPT_DIR)
CUSTOM_VARS_FILE = os.path.abspath(os.path.join(FABRIC_DIR, "config/vars.yaml"))
DEPLOYED_VARS_FILE = "/opt/fabric/config/vars.yaml"
DEPLOY_BASE_DIR = os.path.dirname(FABRIC_DIR)
BIND_DATA_DIR = os.path.join(DEPLOY_BASE_DIR, "bind9", "data")
LINK_VARS_FILE = os.environ.get("LINK_VARS_PATH", os.path.abspath(os.path.join(FABRIC_DIR, "config/link-vars.yaml")))
if not os.path.exists(LINK_VARS_FILE) and os.path.exists(os.path.join(os.path.dirname(FABRIC_DIR), "link-vars.yaml")):
    LINK_VARS_FILE = os.path.join(os.path.dirname(FABRIC_DIR), "link-vars.yaml")

# ANSI Colors
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
NC = "\033[0m"

IMMUTABLE_KEYS = {
    "ca_name", "cert_country", "cert_province", "cert_city", "cert_org", "cert_ou",
    "cert_root_digest", "cert_root_key_type", "cert_root_key_param", "cert_root_ca_days",
    "cert_intermediate_days", "cert_intermediate_digest", "cert_intermediate_key_type",
    "cert_intermediate_key_param", "cert_service_days", "cert_acme_lifetime_hours",
    "stepca_port", "stepca_cert_allow_subordinate_ca", "stepca_cert_max_lifetime_hours",
    "byoc", "ca_crt_path", "ica_crt_path", "ica_key_path", "extra_certs",
    "deploy_base_dir", "domain", "org_domain", "site_name"
}

WARNED_KEYS = {
    "hostname", "host_ip", "lan_cidr", "lan_gateway", "fabric_subnet"
}

CATEGORIES = [
    ("Docker & Services", ["host_ram_capacity", "compose_file", "project_containers", "nginx_backend_ldap", "nginx_backend_stepca", "keycloak_data_dir", "postgres_data_dir", "ip_nginx", "ip_bind9", "ip_stepca", "ip_ldap", "ip_keycloak", "ip_postgres", "image_nginx", "image_debian", "image_stepca", "image_dirsrv", "image_keycloak", "image_postgres", "cname_ca", "landing_page_cname", "cname_dns", "cname_ldap", "cname_sso", "cname_mgr", "hostname_nginx", "hostname_bind9", "hostname_stepca", "hostname_landing", "hostname_ldap", "hostname_keycloak", "hostname_mgr"])
]

def load_yaml(path):
    """Purpose: read a YAML file, treating a missing or empty file as an empty mapping.
    Inputs:  path — str, file path.
    Returns: the parsed data (normally a dict); {} if the file does not exist or is empty.
    Fails:   OSError if it exists but cannot be read; yaml.YAMLError if it is not valid YAML.
    Feeds:   print_vars, edit_links, interactive_mode, apply_mode."""
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}

def clean_data(data):
    """Purpose: recursively turn empty strings into None so they are written as YAML null.
    Inputs:  data — any YAML-like value (dicts and lists are walked).
    Returns: a new structure of the same shape with every "" replaced by None; other values unchanged.
    Fails:   never — plain recursion (RecursionError only for absurdly deep data).
    Feeds:   save_yaml."""
    if isinstance(data, dict):
        return {k: clean_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_data(v) for v in data]
    elif data == "":
        return None
    return data

def save_yaml(path, data):
    """Purpose: write the editor's data back to a YAML file (empty strings become null, key order kept).
    Inputs:  path — str, destination (CUSTOM_VARS_FILE or LINK_VARS_FILE); data — the mapping. Note the order is (path,
             data), the reverse of deploy.save_yaml.
    Returns: None.
    Fails:   OSError if the file cannot be written; yaml.representer.RepresenterError for unsupported types. It takes no
             vars lock, unlike the fabriclib DNS edits.
    Feeds:   edit_dns, edit_list_of_dicts, edit_links, mint_certificates_interactive, interactive_mode."""
    cleaned = clean_data(data)
    with open(path, "w") as f:
        yaml.dump(cleaned, f, default_flow_style=False, sort_keys=False)

def audit_log(key, old_val, new_val, action="MODIFIED"):
    """Purpose: record one editor change in fabric's audit log as the sudo user.
    Inputs:  key — the variable changed; old_val, new_val — shown as text; action — str, default "MODIFIED".
    Returns: None (write_audit line "Key: <key> | Old: ... | New: ..." with source "cli").
    Fails:   never — an OSError from write_audit is swallowed.
    Feeds:   edit_dns, edit_list_of_dicts, edit_links, mint_certificates_interactive, interactive_mode."""
    try:
        write_audit(_actor(), action, f"Key: {key} | Old: {old_val} | New: {new_val}")
    except OSError:
        pass

def print_vars():
    """Purpose: `fabricctl --print`: list the top-level variables of the vars file.
    Inputs:  none; reads CUSTOM_VARS_FILE (<fabric>/config/vars.yaml).
    Returns: None; prints one numbered line per key (dicts and lists shown as "(complex structure)"), or a notice when
             the file is missing or empty.
    Fails:   OSError / yaml.YAMLError from load_yaml.
    Feeds:   `interactive.py --print` (manage.sh MODE print)."""
    data = load_yaml(CUSTOM_VARS_FILE)
    if not data:
        print(f"{YELLOW}No custom variables found in {CUSTOM_VARS_FILE}{NC}")
        return

    print(f"{BOLD}Custom Variables ({CUSTOM_VARS_FILE}):{NC}\n")
    for idx, (k, v) in enumerate(data.items(), 1):
        val_str = str(v)
        if isinstance(v, (dict, list)):
            val_str = "(complex structure)"
        print(f"  {idx}) {BLUE}{k}{NC}: {GREEN}{val_str}{NC}")
    print("")


def _actor():
    """Purpose: the name recorded as the acting user for CLI changes.
    Inputs:  none; reads env SUDO_USER, then USER.
    Returns: str — SUDO_USER, else USER, else "root".
    Fails:   never.
    Feeds:   audit_log, edit_dns_zone (add_record / remove_record actor)."""
    return os.environ.get("SUDO_USER") or os.environ.get("USER") or "root"


def _reload(full_data):
    """Purpose: re-read vars.yaml into the caller's dict after a locked fabriclib write, so a later save from this
             editor cannot overwrite that write with a stale copy.
    Inputs:  full_data — dict, the editor's working copy, changed in place; reads fabriclib's VARS_FILE via load_vars.
    Returns: None (full_data now equals the file).
    Fails:   OSError / yaml.YAMLError from load_vars.
    Feeds:   edit_dns_zone (after add_record / remove_record)."""
    fresh = load_vars()
    full_data.clear()
    full_data.update(fresh)


def _prompt_record(rtype):
    """Purpose: ask on the terminal for the fields fabriclib.dns.validate_record expects for one record type.
    Inputs:  rtype — str, one of A, AAAA, CNAME, TXT, MX, SRV (any other type gets only a name).
    Returns: dict form: name plus ip | target | text | priority/target | priority/weight/port/target (MX priority
             defaults to "10", SRV priority and weight to "0"); values are unvalidated strings.
    Fails:   EOFError / KeyboardInterrupt from input().
    Feeds:   edit_dns_zone (passed to add_record, which validates)."""
    form = {"name": input("Record name (e.g. '@', 'www'): ").strip()}
    if rtype in ('A', 'AAAA'):
        form["ip"] = input("IP address: ").strip()
    elif rtype == 'CNAME':
        form["target"] = input("Canonical name / target: ").strip()
    elif rtype == 'TXT':
        form["text"] = input("Text: ").strip()
    elif rtype == 'MX':
        form["priority"] = input("Priority [10]: ").strip() or "10"
        form["target"] = input("Mail exchange: ").strip()
    elif rtype == 'SRV':
        form["priority"] = input("Priority [0]: ").strip() or "0"
        form["weight"] = input("Weight [0]: ").strip() or "0"
        form["port"] = input("Port: ").strip()
        form["target"] = input("Target: ").strip()
    return form


_SYNC_COLOURS = {"in_sync": GREEN, "out_of_sync": YELLOW, "not_loaded": RED, "unreachable": YELLOW}


def edit_dns_zone(full_data, zone_key, domain_var):
    """Purpose: menu for one DNS zone: show its sync state and records, add or delete a record, apply live, or
             force-recreate the zone.
    Inputs:  full_data — dict, the vars working copy (reloaded after each change); zone_key — key under dns
             ("dynamic_zone_var" is the main domain); domain_var — the domain shown for dynamic_zone_var. Reads
             BIND_DATA_DIR; prompts on stdin.
    Returns: None when the user picks "b".
    Fails:   ValidationError from add_record/remove_record is shown and the loop continues; SystemExit from apply_mode
             is caught. "f" (typed "force" to confirm) stops bind9, deletes db.<zone> and its journal, applies and
             restarts bind9; systemctl failures are not checked. EOFError/KeyboardInterrupt propagate.
    Feeds:   edit_dns."""
    disp_zone = domain_var if zone_key == 'dynamic_zone_var' else zone_key

    while True:
        zone_data = ((full_data.get('dns') or {}).get(zone_key)) or {}
        os.system('clear')
        print(f"{BOLD}--- DNS Zone: {disp_zone} ---{NC}\n")
        state, message = sync_status(disp_zone)
        print(f"  {_SYNC_COLOURS.get(state, NC)}{message}{NC}\n")

        record_map = {}
        idx = 1
        for rtype in RECORD_TYPES:
            for ridx, record in enumerate(zone_data.get(rtype) or []):
                name = record.get('name') or f"{RED}(missing name){NC}"
                print(f"  {idx}) [{rtype}] {name} -> {format_value(rtype, record)}")
                record_map[idx] = (rtype, ridx, record.get('name') or "")
                idx += 1

        print(f"\n  a) Add new record")
        if record_map:
            print(f"  d) Delete record")
        print(f"  l) Live update (apply: publish changed zones)")
        print(f"  f) Force update (rm journal, recreate zone, restart bind9)")
        print(f"  b) Back to zones")

        choice = input(f"Select an option: ").strip().lower()
        if choice == 'b':
            break
        try:
            if choice == 'd' and record_map:
                del_idx = input(f"Enter record number to delete (1-{len(record_map)}): ").strip()
                if del_idx.isdigit() and int(del_idx) in record_map:
                    rtype, ridx, name = record_map[int(del_idx)]
                    remove_record(_actor(), zone_key, rtype, ridx, name)
                    _reload(full_data)
            elif choice == 'a':
                rtype = input(f"Record type ({', '.join(RECORD_TYPES)}): ").strip().upper()
                if rtype:
                    add_record(_actor(), zone_key, rtype, _prompt_record(rtype))
                    _reload(full_data)
        except ValidationError as exc:
            print(f"{RED}{exc}{NC}")
            input("Press Enter to continue...")
            continue
        if choice == 'l':
            # deploy.py freezes/thaws each changed zone itself.
            try:
                apply_mode()
            except SystemExit:
                pass
            input("Press Enter to continue...")
        elif choice == 'f':
            print(f"\n{YELLOW}WARNING: This will delete the journal file, overwrite the zone data, and restart the BIND9 container.{NC}")
            confirm = input("Type 'force' to confirm: ").strip().lower()
            if confirm == 'force':
                subprocess.run("systemctl stop bind9", shell=True)
                for suffix in ('', '.jnl'):
                    path = os.path.join(BIND_DATA_DIR, f"db.{disp_zone}{suffix}")
                    if os.path.exists(path):
                        os.remove(path)
                        print(f"Removed {path}")
                print(f"{BLUE}Applying deployment to recreate zone...{NC}")
                try:
                    apply_mode()
                except SystemExit:
                    pass
                print(f"{BLUE}Restarting BIND9 container...{NC}")
                subprocess.run("systemctl restart bind9", shell=True)
                print(f"{GREEN}Force update complete.{NC}")
            input("Press Enter to continue...")

def edit_dns(data):
    """Purpose: menu listing the DNS zones in the vars (the main domain always first) and adding new zones.
    Inputs:  data — dict, the vars working copy; a new zone is added to data["dns"] and saved to CUSTOM_VARS_FILE.
    Returns: None when the user picks "b".
    Fails:   an invalid zone name (HOST_RE) is shown and refused; OSError from save_yaml; EOFError from input().
    Feeds:   interactive_mode (menu 1), handle_complex_variable (key dns)."""
    while True:
        dns_data = data.get('dns') if isinstance(data.get('dns'), dict) else {}
        os.system('clear')
        print(f"{BOLD}--- DNS Records Editor ---{NC}\n")

        domain_var = data.get('domain', 'example.com')

        zones = list(dns_data.keys())
        if 'dynamic_zone_var' not in zones:
            zones.insert(0, 'dynamic_zone_var')

        print("Available Zones:")
        for i, z in enumerate(zones, 1):
            disp = domain_var if z == 'dynamic_zone_var' else z
            print(f"  {i}) {disp} ({z})")

        print(f"\n  a) Add a new zone")
        print(f"  b) Back to variables")

        choice = input(f"Select a zone (1-{len(zones)}), 'a', or 'b': ").strip().lower()
        if choice == 'b':
            break
        elif choice == 'a':
            # The zone name becomes a file name (db.<zone>) and goes into named.conf.
            new_zone = input("New zone name: ").strip().rstrip('.')
            if not HOST_RE.match(new_zone):
                print(f"{RED}Invalid zone name.{NC}")
                input("Press Enter to continue...")
            elif new_zone not in dns_data:
                data.setdefault('dns', {})[new_zone] = {}
                save_yaml(CUSTOM_VARS_FILE, data)
                audit_log("dns", "None", f"Added zone {new_zone}", "MODIFIED")
        elif choice.isdigit() and 1 <= int(choice) <= len(zones):
            edit_dns_zone(data, zones[int(choice)-1], domain_var)

def edit_list_of_dicts(key, data, schema):
    """Purpose: generic menu to add, modify or delete entries of a list-of-mappings variable.
    Inputs:  key — the variable (e.g. tsig_keys); data — dict, the vars working copy (data[key] made a list if it is
             not); schema — list of field names prompted for. "[a, b]" input becomes a list, digits an int.
    Returns: None when the user picks "b"; each change is saved to CUSTOM_VARS_FILE and audited.
    Fails:   no validation here (bad entries fail later at apply); OSError from save_yaml; EOFError from input().
    Feeds:   interactive_mode (menu 4, tsig_keys), handle_complex_variable."""
    if key not in data or not isinstance(data[key], list):
        data[key] = []
        
    lst = data[key]
    
    while True:
        os.system('clear')
        print(f"{BOLD}--- Editor: {key} ---{NC}\n")
        
        if not lst:
            print(f"{YELLOW}No custom entries defined. System defaults will be used.{NC}")
            
        for i, item in enumerate(lst, 1):
            name = item.get('name', f"Item {i}")
            print(f"  {i}) {name}")
            for k, v in item.items():
                if k != 'name':
                    print(f"      {k}: {v}")
                    
        print(f"\n  a) Add new entry")
        if lst:
            print(f"  m) Modify entry")
            print(f"  d) Delete entry")
        print(f"  b) Back to variables")
        
        choice = input(f"Select an option: ").strip().lower()
        if choice == 'b':
            break
        elif choice == 'a':
            new_item = {}
            print(f"\nAdding new entry to {key}:")
            for field in schema:
                val = input(f"  {field}: ").strip()
                if val:
                    if val.startswith('[') and val.endswith(']'):
                        val = [v.strip() for v in val[1:-1].split(',')]
                    elif val.isdigit():
                        val = int(val)
                    new_item[field] = val
            if new_item:
                lst.append(new_item)
                save_yaml(CUSTOM_VARS_FILE, data)
                audit_log(key, "None", str(new_item), "MODIFIED")
        elif choice == 'm' and lst:
            idx_str = input(f"Enter item number to modify (1-{len(lst)}): ").strip()
            if idx_str.isdigit() and 1 <= int(idx_str) <= len(lst):
                idx = int(idx_str) - 1
                item = lst[idx]
                print(f"\nModifying entry {idx+1}:")
                for field in schema:
                    current = item.get(field, '')
                    val = input(f"  {field} [{current}]: ").strip()
                    if val:
                        if val.startswith('[') and val.endswith(']'):
                            val = [v.strip() for v in val[1:-1].split(',')]
                        elif val.isdigit():
                            val = int(val)
                        item[field] = val
                save_yaml(CUSTOM_VARS_FILE, data)
                audit_log(key, "old", str(item), "MODIFIED")
        elif choice == 'd' and lst:
            idx_str = input(f"Enter item number to delete (1-{len(lst)}): ").strip()
            if idx_str.isdigit() and 1 <= int(idx_str) <= len(lst):
                del lst[int(idx_str)-1]
                save_yaml(CUSTOM_VARS_FILE, data)
                audit_log(key, "item", "None", "DELETED")

def handle_complex_variable(k, data):
    """Purpose: open the right editor for a dict/list variable picked from a category list.
    Inputs:  k — the variable name; data — dict, the vars working copy.
    Returns: None. dns -> edit_dns; tsig_keys, ldap_groups, ldap_organizational_units -> edit_list_of_dicts with a fixed
             field list; anything else prints "No interactive editor exists" and waits for Enter.
    Fails:   as the editor it calls.
    Feeds:   interactive_mode (category screens 3 and 6)."""
    if k == 'dns':
        edit_dns(data)
    elif k in ['tsig_keys', 'ldap_groups', 'ldap_organizational_units']:
        schemas = {
            'tsig_keys': ['name', 'algorithm', 'domain', 'record_types', 'records'],
            'ldap_groups': ['gidNumber', 'name', 'permissions'],
            'ldap_organizational_units': ['name', 'description', 'parent', 'uid_range']
        }
        edit_list_of_dicts(k, data, schemas[k])
    else:
        print(f"\n{YELLOW}No interactive editor exists for {k}. Please edit manually in {CUSTOM_VARS_FILE}{NC}")
        input("Press Enter to continue...")

def edit_links():
    """Purpose: menu to add, modify or delete the landing page links (link-vars.yaml).
    Inputs:  none; reads and writes LINK_VARS_FILE (env LINK_VARS_PATH, else <fabric>/config/link-vars.yaml, else
             <base>/link-vars.yaml). A link may contain Jinja such as {{ domain }}.
    Returns: None when the user picks "b"; each change saved and audited.
    Fails:   OSError / yaml.YAMLError from load_yaml or save_yaml; EOFError from input().
    Feeds:   interactive_mode (menu 5)."""
    data = load_yaml(LINK_VARS_FILE)
    if 'links' not in data or not isinstance(data['links'], list):
        data['links'] = []
        
    lst = data['links']
    
    while True:
        os.system('clear')
        print(f"{BOLD}--- Landing Page Links Editor ---{NC}\n")
        
        if not lst:
            print(f"{YELLOW}No custom links defined.{NC}")
            
        for i, item in enumerate(lst, 1):
            name = item.get('name', f"Link {i}")
            link = item.get('link', '')
            print(f"  {i}) {name} -> {link}")
                    
        print(f"\n  a) Add new link")
        if lst:
            print(f"  m) Modify link")
            print(f"  d) Delete link")
        print(f"  b) Back to main menu")
        
        choice = input(f"Select an option: ").strip().lower()
        if choice == 'b':
            break
        elif choice == 'a':
            name = input(f"\n  Name: ").strip()
            link = input(f"  Link (e.g. adguard.{{{{ domain }}}}): ").strip()
            if name and link:
                lst.append({'name': name, 'link': link})
                save_yaml(LINK_VARS_FILE, data)
                audit_log("links", "None", f"Added {name}", "MODIFIED")
        elif choice == 'm' and lst:
            idx_str = input(f"Enter link number to modify (1-{len(lst)}): ").strip()
            if idx_str.isdigit() and 1 <= int(idx_str) <= len(lst):
                idx = int(idx_str) - 1
                item = lst[idx]
                print(f"\nModifying entry {idx+1}:")
                name = input(f"  Name [{item.get('name', '')}]: ").strip()
                link = input(f"  Link [{item.get('link', '')}]: ").strip()
                if name: item['name'] = name
                if link: item['link'] = link
                save_yaml(LINK_VARS_FILE, data)
                audit_log("links", "old", f"Modified {item.get('name')}", "MODIFIED")
        elif choice == 'd' and lst:
            idx_str = input(f"Enter link number to delete (1-{len(lst)}): ").strip()
            if idx_str.isdigit() and 1 <= int(idx_str) <= len(lst):
                del lst[int(idx_str)-1]
                save_yaml(LINK_VARS_FILE, data)
                audit_log("links", "item", "None", "DELETED")


def mint_certificates_interactive(data):
    """Purpose: menu to describe one extra certificate, save it to extra_certs and mint it.
    Inputs:  data — dict, the vars working copy (cert_* values are only displayed). Prompts for CN, SANs, days, key
             type/size, CA flag (path_len 0) and output directory.
    Returns: None when the user picks "b". On "m" the entry is appended to data["extra_certs"], saved, audited, and
             minted with `fabriclib/cli.py extra-cert <json>`; the minted path or the error is printed.
    Fails:   an empty CN is refused; a minting failure is printed, not raised (the entry stays saved); OSError from
             save_yaml; EOFError from input().
    Feeds:   interactive_mode (menu 2)."""
    cert_data = {
        'cn': '',
        'sans': [],
        'days': 365,
        'kty': 'RSA',
        'size': 4096,
        'is_ca': False,
        'out_dir': ''
    }
    
    country = data.get('cert_country', 'US')
    org = data.get('cert_org', 'My Org')
    ou = data.get('cert_ou', 'My OU')
    city = data.get('cert_city', 'My City')
    province = data.get('cert_province', 'My Province')
    
    while True:
        os.system('clear')
        print(f"{BOLD}--- Mint Certificates ---{NC}\n")
        
        print(f"  1) Common Name:      {GREEN}{cert_data['cn']}{NC}")
        print(f"  2) SAN (URL):        {GREEN}{cert_data['sans']}{NC}")
        print(f"  3) Validity Days:    {GREEN}{cert_data['days']}{NC}")
        print(f"  4) Key Type:         {GREEN}{cert_data['kty']}{NC}")
        print(f"  5) Key Size:         {GREEN}{cert_data['size']}{NC}")
        print(f"  6) Is CA:            {GREEN}{cert_data['is_ca']}{NC}")
        print(f"  7) Output Directory: {GREEN}{cert_data['out_dir'] or '(Caller Home)'}{NC}")
        
        print(f"\n{BOLD}System PKI Defaults (will be applied to minted cert):{NC}")
        print(f"  Country: {country} | Province: {province} | City: {city}")
        print(f"  Org: {org} | OU: {ou}")
        
        print(f"\n  {BOLD}m{NC}) Mint Certificate")
        print(f"  {BOLD}b{NC}) Back to Main Menu")
        
        choice = input(f"\nSelect option to edit (1-7), 'm' to mint, or 'b' to go back: ").strip().lower()
        if choice == 'b':
            break
        elif choice == '1':
            cert_data['cn'] = input("Common Name: ").strip() or cert_data['cn']
        elif choice == '2':
            sans_str = input("SAN (URLs) separated by commas: ").strip()
            if sans_str:
                cert_data['sans'] = [s.strip() for s in sans_str.split(',') if s.strip()]
            else:
                cert_data['sans'] = []
        elif choice == '3':
            days = input(f"Validity Days [{cert_data['days']}]: ").strip()
            if days.isdigit():
                cert_data['days'] = int(days)
        elif choice == '4':
            cert_data['kty'] = input(f"Key Type [{cert_data['kty']}]: ").strip() or cert_data['kty']
        elif choice == '5':
            size = input(f"Key Size [{cert_data['size']}]: ").strip()
            if size.isdigit():
                cert_data['size'] = int(size)
        elif choice == '6':
            is_ca = input(f"Is CA? (true/false) [{str(cert_data['is_ca']).lower()}]: ").strip().lower()
            if is_ca in ('true', 'yes', 'y'):
                cert_data['is_ca'] = True
            elif is_ca in ('false', 'no', 'n'):
                cert_data['is_ca'] = False
        elif choice == '7':
            cert_data['out_dir'] = input(f"Output Directory [{cert_data['out_dir']}]: ").strip() or cert_data['out_dir']
        elif choice == 'm':
            if not cert_data['cn']:
                print(f"{RED}Common Name is required!{NC}")
                input("Press Enter to continue...")
                continue
                
            print(f"\n{BLUE}Preparing to mint certificate...{NC}")
            import json
            
            entry = {
                'cn': cert_data['cn'],
                'sans': cert_data['sans'],
                'days': cert_data['days'],
                'kty': cert_data['kty'],
                'size': cert_data['size']
            }
            if cert_data['is_ca']:
                entry['is_ca'] = True
                entry['path_len'] = 0
            if cert_data['out_dir']:
                entry['out_dir'] = cert_data['out_dir']
                
            if 'extra_certs' not in data:
                data['extra_certs'] = []
            data['extra_certs'].append(entry)
            save_yaml(CUSTOM_VARS_FILE, data)
            audit_log("extra_certs", "None", json.dumps(entry), "ADDED")
            
            print(f"{YELLOW}Saved configuration. Minting certificate...{NC}")
            
            try:
                # fabriclib/pki/mint_extra_cert.py — same code setup uses
                res = subprocess.run(["python3", os.path.join(FABRIC_DIR, "lib", "fabriclib", "cli.py"),
                                      "extra-cert", json.dumps(entry)], capture_output=True, text=True)
                if res.returncode == 0:
                    print(f"{GREEN}Certificate minted: {res.stdout.strip()}{NC}")
                else:
                    print(f"{RED}Minting failed: {(res.stderr or res.stdout).strip()[-500:]}{NC}")
            except Exception as e:
                import traceback
                print(f"{RED}Error minting certificate: {e}{NC}")
                traceback.print_exc()
                
            input("Press Enter to continue...")

def interactive_mode():
    """Purpose: `fabricctl --interactive`: the top-level variables editor menu (DNS, certificates, service settings,
             TSIG keys, links, other keys; add/delete a key; apply).
    Inputs:  none; reads CUSTOM_VARS_FILE and, on apply, DEPLOYED_VARS_FILE (/opt/fabric/config/vars.yaml);
             IMMUTABLE_KEYS cannot be deleted or edited, WARNED_KEYS ask for "yes" before apply. Prompts on stdin.
    Returns: never returns normally: sys.exit(0) on q/quit/exit or after a successful apply.
    Fails:   sys.exit with apply_mode's code when the apply fails; OSError from save_yaml; EOFError from input().
    Feeds:   `interactive.py --interactive` (manage.sh default MODE).
    Notes:   CUSTOM_VARS_FILE and DEPLOYED_VARS_FILE are the same file on a standard /opt install, and edits are saved
             before apply, so the WARNED_KEYS check finds no difference there."""
    data = load_yaml(CUSTOM_VARS_FILE)
    
    while True:
        os.system('clear')
        print(f"{BOLD}--- Interactive Variables Editor ---{NC}\n")
        
        print(f"  {BOLD}1{NC}) DNS Configuration")
        print(f"  {BOLD}2{NC}) Mint Certificates")
        print(f"  {BOLD}3{NC}) Docker & Services")
        print(f"  {BOLD}4{NC}) TSIG Keys")
        print(f"  {BOLD}5{NC}) Landing Page Links")
        print(f"  {BOLD}6{NC}) Advanced Configuration")
        
        print(f"\nOptions:")
        print(f"  {BOLD}a{NC}    Add new variable")
        print(f"  {BOLD}d{NC}    Delete variable")
        print(f"  {BOLD}apply{NC} Save and Apply changes")
        print(f"  {BOLD}q{NC}    Quit without applying\n")
        
        choice = input(f"Select a category (1-6), or option: ").strip().lower()
        
        if choice in ['q', 'quit', 'exit']:
            print("Exiting.")
            sys.exit(0)
            
        if choice == 'apply':
            old_vars = load_yaml(DEPLOYED_VARS_FILE)
            warned_mods = [k for k in WARNED_KEYS if k in data and k in old_vars and data[k] != old_vars[k]]
            if warned_mods:
                print(f"\n{RED}{BOLD}[WARNING]{NC} You are about to apply changes to highly sensitive network configurations: {', '.join(warned_mods)}")
                print(f"This may break routing and require widespread restarts.")
                confirm = input("Are you absolutely sure you want to apply? (type 'yes'): ").strip().lower()
                if confirm != 'yes':
                    continue
                    
            print("Applying changes...")
            apply_mode()
            sys.exit(0)
            
        if choice == 'a':
            k = input("New variable key: ").strip()
            if k:
                v = input(f"Value for {k} (Enter for null): ").strip()
                if v.lower() == 'null' or v == '""' or v == "''" or v == "":
                    val = None
                elif v.lower() == 'true': val = True
                elif v.lower() == 'false': val = False
                elif v.isdigit(): val = int(v)
                else: val = v
                
                data[k] = val
                save_yaml(CUSTOM_VARS_FILE, data)
                audit_log(k, "None", val, "ADDED")
            continue
            
        if choice == 'd':
            k = input("Variable key to delete: ").strip()
            if k in IMMUTABLE_KEYS:
                print(f"{RED}Cannot delete immutable key: {k}{NC}")
                input("Press Enter to continue...")
                continue
            if k in data:
                old = data[k]
                del data[k]
                save_yaml(CUSTOM_VARS_FILE, data)
                audit_log(k, old, "None", "DELETED")
            continue
            
        if choice == '1':
            edit_dns(data)
            continue
        elif choice == '2':
            mint_certificates_interactive(data)
            continue
        elif choice == '4':
            schemas = {
                'tsig_keys': ['name', 'algorithm', 'domain', 'record_types', 'records']
            }
            edit_list_of_dicts('tsig_keys', data, schemas['tsig_keys'])
            continue
        elif choice == '5':
            edit_links()
            continue
            
        selected_cat_keys = None
        cat_title = ""
        if choice == '3':
            cat_title = "Docker & Services"
            selected_cat_keys = CATEGORIES[0][1]
        elif choice == '6':
            cat_title = "Advanced Configuration"
            known_keys = set(CATEGORIES[0][1]) | {'dns', 'tsig_keys', 'domain'}
            selected_cat_keys = [k for k in data.keys() if k not in known_keys]
            
        if selected_cat_keys is not None:
            while True:
                os.system('clear')
                print(f"{BOLD}--- {cat_title} ---{NC}\n")
                
                display_keys = [k for k in selected_cat_keys if k in data]
                
                if cat_title == "Advanced Configuration":
                    # Add remaining unknown keys to display_keys
                    for k in data.keys():
                        if k not in known_keys and k not in display_keys:
                            display_keys.append(k)
                            
                if not display_keys:
                    print(f"{YELLOW}No active variables in this category.{NC}")
                
                for i, k in enumerate(display_keys, 1):
                    v = data[k]
                    val_str = str(v)
                    if isinstance(v, (dict, list)):
                        val_str = "(complex structure)"
                        
                    status = ""
                    if k in IMMUTABLE_KEYS:
                        status = f" {BOLD}🔒 [IMMUTABLE]{NC}"
                    elif k in WARNED_KEYS:
                        status = f" {YELLOW}⚠️ [CAUTION]{NC}"
                        
                    print(f"  {i}) {BLUE}{k}{NC}: {GREEN}{val_str}{NC}{status}")
                
                print(f"\n  {BOLD}b{NC} Back to categories")
                subchoice = input(f"Select a variable to edit (1-{len(display_keys)}) or 'b': ").strip().lower()
                
                if subchoice == 'b':
                    break
                    
                if subchoice.isdigit():
                    idx = int(subchoice) - 1
                    if 0 <= idx < len(display_keys):
                        k = display_keys[idx]
                        if k in IMMUTABLE_KEYS:
                            print(f"\n{RED}Error: '{k}' is an immutable variable and cannot be changed post-deployment.{NC}")
                            input("Press Enter to continue...")
                            continue
                            
                        current = data[k]
                        if isinstance(current, (dict, list)):
                            handle_complex_variable(k, data)
                            continue
                        
                        print(f"\nEditing: {BLUE}{k}{NC}")
                        if k in WARNED_KEYS:
                            print(f"{YELLOW}⚠️ WARNING: Editing this variable could impact network routing!{NC}")
                            
                        print(f"Current value: {GREEN}{current}{NC}")
                        new_v = input(f"New value (Enter to keep current, 'null' to clear): ").strip()
                        if new_v:
                            if new_v.lower() == 'null' or new_v == '""' or new_v == "''":
                                val = None
                            elif new_v.lower() == 'true': val = True
                            elif new_v.lower() == 'false': val = False
                            elif new_v.isdigit(): val = int(new_v)
                            else: val = new_v
                            
                            data[k] = val
                            save_yaml(CUSTOM_VARS_FILE, data)
                            audit_log(k, current, val, "MODIFIED")
                            print(f"{GREEN}Saved.{NC}")
                            input("Press Enter to continue...")
            continue

def apply_mode():
    """Purpose: `fabricctl --apply`: run the deploy engine (deploy.apply_deployment) on the vars file, report which
             variables changed and restart the services it returns.
    Inputs:  none; sets env CUSTOM_VARS_PATH, SECRETS_FILE_OVERRIDE and DEPLOY_BASE_DIR for deploy.py; reads the newest
             <fabric>/archive/*-vars.yaml (else DEPLOYED_VARS_FILE) and /tmp/fabric-render/vars.yaml.
    Returns: None; progress printed. Returns early ("System is up to date") when no top-level key differs.
    Fails:   sys.exit(<code>) with "Error deploying configurations!" when apply_deployment exits; sys.exit(1) with a
             traceback on any other exception. A failing `systemctl restart` raises CalledProcessError (not caught); a
             timeout is printed.
    Feeds:   `interactive.py --apply` (manage.sh MODE apply, fabriclib/system/apply_changes.py for the web UI);
             interactive_mode; edit_dns_zone.
    Notes:   apply_deployment already restarted those services, so each active one is restarted a second time here,
             fabric-web synchronously. The archive it compares with is written by apply_deployment in the same run."""
    import glob
    from deploy import apply_deployment
    print(f"{BOLD}Applying changes natively...{NC}")
    
    archives = glob.glob(os.path.join(FABRIC_DIR, "archive/*-vars.yaml"))
    if archives:
        latest_archive = max(archives)
        old_vars = load_yaml(latest_archive)
    else:
        old_vars = load_yaml(DEPLOYED_VARS_FILE)
        
    print(f"  {BLUE}[1/3]{NC} Rendering and deploying configurations...")
    
    os.environ["CUSTOM_VARS_PATH"] = CUSTOM_VARS_FILE
    os.environ["SECRETS_FILE_OVERRIDE"] = os.path.join(FABRIC_DIR, 'config', 'fabric-secrets.yml')
    os.environ["DEPLOY_BASE_DIR"] = DEPLOY_BASE_DIR
    
    try:
        restarted_services = apply_deployment()
        if restarted_services is None:
            restarted_services = set()
    except SystemExit as e:
        print(f"{RED}Error deploying configurations! Exit code {e.code}{NC}")
        sys.exit(e.code)
    except Exception as e:
        import traceback
        print(f"{RED}Exception during deployment!{NC}")
        traceback.print_exc()
        sys.exit(1)
        
    new_vars = load_yaml("/tmp/fabric-render/vars.yaml")
    
    changed_keys = []
    for k, v in new_vars.items():
        if k not in old_vars or old_vars[k] != v:
            changed_keys.append(k)
            
    for k in old_vars:
        if k not in new_vars:
            changed_keys.append(k)
            
    if not changed_keys:
        print(f"{GREEN}No variables have changed. System is up to date.{NC}")
        return
        
    print(f"Changed variables: {YELLOW}{', '.join(changed_keys)}{NC}")
    print(f"  {BLUE}[2/3]{NC} Done deploying configuration files.")
    def get_svc_timeout(s):
        if s == "keycloak": return 90
        if s == "postgres": return 60
        return 30

    print(f"  {BLUE}[3/3]{NC} Restarting system services...")
    for svc in restarted_services:
        try:
            res_check = subprocess.run(["systemctl", "is-active", svc], capture_output=True, timeout=10)
            if res_check.returncode == 0:
                print(f"    Restarting {svc}...")
                subprocess.run(["systemctl", "restart", svc], check=True, timeout=get_svc_timeout(svc))
            else:
                print(f"    Skipping {svc} (not currently active)")
        except subprocess.TimeoutExpired:
            print(f"{RED}    Timeout while checking/restarting {svc}. Please check systemctl status manually.{NC}")
            
    print(f"\n{BOLD}{GREEN}Apply complete!{NC}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: interactive.py [--print | --interactive | --apply]")
        sys.exit(1)
        
    mode = sys.argv[1]
    if mode == "--print":
        print_vars()
    elif mode == "--interactive":
        interactive_mode()
    elif mode == "--apply":
        apply_mode()
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
