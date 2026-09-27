#!/usr/bin/env python3
import os
import sys
import yaml
import shutil
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fabriclib.common.jinja_env import jinja_env as jinja_env_for  # noqa: E402
from fabriclib.common.errors import ValidationError  # noqa: E402
from fabriclib.dns.normalize_acl_policies import normalize_acl_policies  # noqa: E402
from fabriclib.dns.normalize_tsig_keys import normalize_tsig_keys  # noqa: E402
import filecmp
import json
import re
from datetime import datetime

FABRIC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_DIR = os.path.dirname(FABRIC_DIR)
DEPLOY_BASE_DIR = os.environ.get("DEPLOY_BASE_DIR", "/opt")
TARGET_FABRIC = os.path.join(DEPLOY_BASE_DIR, "fabric")

def run_cmd(cmd, check=True, timeout=120):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        if check and res.returncode != 0:
            print(f"Command failed: {cmd}\n{res.stderr}")
            sys.exit(1)
        return res
    except subprocess.TimeoutExpired:
        print(f"Command timed out after {timeout}s: {cmd}")
        sys.exit(1)

def load_yaml(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        return yaml.safe_load(f) or {}

def save_yaml(data, path):
    with open(path, 'w') as f:
        yaml.safe_dump(data, f, default_flow_style=False)

def generate_secret_b64(length=32):
    return run_cmd(f"openssl rand -base64 {length} | tr -d '\\n'").stdout.strip()

def ensure_dir(path, mode=0o750, uid=0, gid=0):
    if not os.path.exists(path):
        os.makedirs(path, mode=mode)
    os.chmod(path, mode)
    os.chown(path, uid, gid)

def get_service_user(vars_dict, service_name):
    users = vars_dict.get('service_users', {})
    svc = users.get(service_name, {})
    return int(svc.get('uid', 0)), int(svc.get('gid', 0))

# -----------------------------------------------------------------------
# BIND9 zone deployment
# Forward zones carry an update-policy, which makes them dynamic: BIND
# ignores `rndc reload` for them and keeps its own journal (.jnl). To
# replace one safely we freeze it (flushes the journal into the file and
# blocks updates), swap the file, drop the stale journal and thaw it.
# -----------------------------------------------------------------------
SERIAL_RE = re.compile(r"^\s*\d+\s*;\s*Serial.*$", re.MULTILINE)

def rndc(args, timeout=15):
    try:
        return subprocess.run(f"docker exec -u bind bind9 rndc {args}", shell=True,
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"rndc {args} timed out")
        return None

def zone_content_changed(src, dst):
    """Compare zone files ignoring the SOA serial, which changes on every render."""
    if not os.path.exists(dst):
        return True
    with open(src) as a, open(dst) as b:
        return SERIAL_RE.sub("", a.read()) != SERIAL_RE.sub("", b.read())

def install_zone_file(src, dst, uid, gid):
    shutil.copy2(src, dst)
    os.chown(dst, uid, gid)
    os.chmod(dst, 0o640)
    # A journal written against the old file no longer matches it: BIND
    # would refuse to load the zone ("journal out of sync").
    if os.path.exists(dst + ".jnl"):
        os.remove(dst + ".jnl")

def deploy_zone_files(src_dir, dst_dir, uid, gid):
    """Return [(zone, src, dst)] for zone files whose records actually changed."""
    changed = []
    if not os.path.isdir(src_dir):
        return changed
    for fname in sorted(os.listdir(src_dir)):
        if not fname.startswith("db."):
            continue
        src, dst = os.path.join(src_dir, fname), os.path.join(dst_dir, fname)
        if zone_content_changed(src, dst):
            changed.append((fname[3:], src, dst))
    return changed

def reload_zone(zone, src, dst, uid, gid):
    print(f"Updating zone {zone}...")
    frozen = rndc(f"freeze {zone}")
    install_zone_file(src, dst, uid, gid)
    jnl = dst + ".jnl"
    if os.path.exists(jnl):
        os.remove(jnl)
    if frozen is not None and frozen.returncode == 0:
        res = rndc(f"thaw {zone}")
    else:
        # Static zone (no update-policy): a plain reload is enough.
        res = rndc(f"reload {zone}")
    if res is None or res.returncode != 0:
        print(f"  Warning: BIND9 did not accept zone {zone}: {(res.stderr or res.stdout).strip() if res else 'timeout'}")

def apply_deployment(start_services=True):
    """Render and deploy all configuration. With start_services=False (first
    install, used by `fabricctl setup`) files are deployed but nothing is
    started, restarted or reloaded: certificates do not exist yet."""
    print("Starting native Python deployment...")
    
    custom_vars_path = os.environ.get("CUSTOM_VARS_PATH", os.path.join(TARGET_FABRIC, "config/vars.yaml"))
    secrets_path = os.environ.get("SECRETS_FILE_OVERRIDE", os.path.join(TARGET_FABRIC, "config/fabric-secrets.yml"))

    # 1. Load Custom Vars
    custom_vars = load_yaml(custom_vars_path)
    
    # 2. Handle Secrets
    secrets = load_yaml(secrets_path)
    changed_secrets = False
    
    if 'ca_password' not in secrets:
        secrets['ca_password'] = generate_secret_b64(32)
        changed_secrets = True
    if 'rndc_secret' not in secrets:
        secrets['rndc_secret'] = generate_secret_b64(32)
        changed_secrets = True
    if 'ldap_admin_password' not in secrets:
        secrets['ldap_admin_password'] = generate_secret_b64(24)
        changed_secrets = True
    if 'ldap_keycloak_password' not in secrets:
        secrets['ldap_keycloak_password'] = generate_secret_b64(24)
        changed_secrets = True
    if 'keycloak_admin_user' not in secrets:
        secrets['keycloak_admin_user'] = 'admin'
        changed_secrets = True
    if 'keycloak_admin_password' not in secrets:
        secrets['keycloak_admin_password'] = generate_secret_b64(24)
        changed_secrets = True
    if 'keycloak_db_password' not in secrets:
        secrets['keycloak_db_password'] = generate_secret_b64(32)
        changed_secrets = True
        
    for name in ('ldap_super_admin_password', 'ldap_group_admin_password',
                 'ldap_user_creator_password', 'ldap_user_modifier_password',
                 'webui_oidc_secret'):
        if name not in secrets:
            # Alphanumeric: safe inside LDIF and JSON without quoting.
            secrets[name] = run_cmd("openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 32").stdout.strip()
            changed_secrets = True

    if 'tsig_secrets' not in secrets:
        secrets['tsig_secrets'] = {}
        changed_secrets = True
        
    # TSIG keys: defaults + validation; an embedded `secret` (an existing
    # key whose RFC2136 clients must keep working) moves into the secrets
    # file and always wins; otherwise one is generated once and kept.
    try:
        tsig_keys, embedded = normalize_tsig_keys(custom_vars.get('tsig_keys', []), custom_vars.get('domain', ''),
                                                  custom_vars.pop('tsig_secrets', None))
    except ValidationError as e:
        print(f"Error: {e}")
        sys.exit(1)
    custom_vars['tsig_keys'] = tsig_keys
    try:
        custom_vars['bind_acl_policies'] = normalize_acl_policies(custom_vars.get('bind_acl_policies'),
                                                                  custom_vars.get('domain', ''))
    except ValidationError as e:
        print(f"Error: {e}")
        sys.exit(1)
    # A key's `acls` puts it in those BIND ACLs (same entries `fabricctl tsig
    # --acl` writes), so a vars file can assign keys to ACLs directly.
    acl_map = custom_vars.get('bind_acls') or {}
    for key in tsig_keys:
        for acl in key.get('acls') or []:
            entries = acl_map.setdefault(acl, []) or []
            if f'key "{key["name"]}"' not in entries:
                entries.append(f'key "{key["name"]}"')
            acl_map[acl] = entries
    if acl_map:
        custom_vars['bind_acls'] = acl_map
    for kname, secret in embedded.items():
        if secrets['tsig_secrets'].get(kname) != secret:
            secrets['tsig_secrets'][kname] = secret
            changed_secrets = True
    for key in tsig_keys:
        kname = key.get('name')
        if kname and kname not in secrets['tsig_secrets']:
            secrets['tsig_secrets'][kname] = generate_secret_b64(32)
            changed_secrets = True
            
    if changed_secrets:
        save_yaml(secrets, secrets_path)
        os.chmod(secrets_path, 0o600)
        
    # 3. Render vars.yaml.j2
    jinja_dir = os.path.join(FABRIC_DIR, 'jinja')
    jinja_env = jinja_env_for(jinja_dir)   # fabriclib/common/jinja_env.py
    
    merged_context = {**secrets, **custom_vars}
    merged_context['render_date'] = datetime.utcnow().strftime('%Y-%m-%d')
    
    try:
        vars_template = jinja_env.get_template('vars.yaml.j2')
        rendered_vars_str = vars_template.render(**merged_context)
    except Exception as e:
        print(f"Failed to render vars.yaml.j2: {e}")
        sys.exit(1)
        
    fresh_vars = yaml.safe_load(rendered_vars_str) or {}
    
    host_ram = int(fresh_vars.get('host_ram_capacity', 0))
    if host_ram > 0 and host_ram < 3:
        print(f"Error: host_ram_capacity is set to {host_ram}. The absolute minimum is 3GB to safely run Keycloak and Postgres. Set it to 0 for unlimited, or >= 3.")
        sys.exit(1)
    
    deployed_vars_path = os.path.join(TARGET_FABRIC, "config/vars.yaml")
    if os.path.exists(deployed_vars_path):
        old_vars = load_yaml(deployed_vars_path)
        final_vars = {}
        final_vars = fresh_vars
        for k, v in old_vars.items():
            if k.startswith('image_') and k not in custom_vars:
                final_vars[k] = v
                
        # Archive old vars
        archive_dir = os.path.join(TARGET_FABRIC, "archive")
        ensure_dir(archive_dir)
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        shutil.copy(deployed_vars_path, os.path.join(archive_dir, f"{stamp}-vars.yaml"))
    else:
        final_vars = fresh_vars
        
    render_tmp = "/tmp/fabric-render"
    if os.path.exists(render_tmp):
        shutil.rmtree(render_tmp)
    os.makedirs(render_tmp, exist_ok=True)
    
    save_yaml(final_vars, os.path.join(render_tmp, "vars.yaml"))
    merged_context.update(final_vars)
    
    # Load and render link-vars.yaml
    link_vars_path = os.environ.get("LINK_VARS_PATH", os.path.join(TARGET_FABRIC, "config/link-vars.yaml"))
    if not os.path.exists(link_vars_path):
        link_vars_path = os.path.join(REPO_DIR, "link-vars.yaml")
    if not os.path.exists(link_vars_path):
        link_vars_path = os.path.join(REPO_DIR, "link-vars-template.yaml")

    if os.path.exists(link_vars_path):
        try:
            with open(link_vars_path, 'r') as f:
                raw_links = f.read()
            rendered_links = jinja_env.from_string(raw_links).render(**merged_context)
            link_vars = yaml.safe_load(rendered_links) or {}
            merged_context.update(link_vars)
            
            with open(os.path.join(render_tmp, "link-vars.yaml"), 'w') as f:
                f.write(raw_links)
        except Exception as e:
            print(f"Failed to parse {link_vars_path}: {e}")
    
    # 4. Render all other templates
    print("Rendering Jinja2 templates...")
    def render_file(src_rel, dest_rel):
        dest_path = os.path.join(render_tmp, dest_rel)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        try:
            tpl = jinja_env.get_template(src_rel)
            with open(dest_path, 'w') as f:
                f.write(tpl.render(**merged_context))
        except Exception as e:
            print(f"Error rendering {src_rel}: {e}")
            sys.exit(1)

    # Nginx
    render_file('nginx/nginx.conf.j2', 'nginx/nginx.conf')
    render_file('nginx/www/certificates/index.html.j2', 'nginx/www/certificates/index.html')
    render_file('nginx/www/landing/index.html.j2', 'nginx/www/landing/index.html')
    render_file('nginx/www/manual/index.html.j2', 'nginx/www/manual/index.html')
    render_file('nginx/www/ldap/index.html.j2', 'nginx/www/ldap/index.html')
    render_file('nginx/www/ldap/install-ldap.sh.j2', 'nginx/www/ldap/install-ldap.sh')
    os.makedirs(os.path.join(render_tmp, 'nginx/www/shared'), exist_ok=True)
    os.makedirs(os.path.join(render_tmp, 'nginx/www/manual'), exist_ok=True)
    shutil.copy(os.path.join(jinja_dir, 'nginx/www/shared/style.css'), os.path.join(render_tmp, 'nginx/www/shared/style.css'))
    for asset in ('marked.min.js', 'mermaid.min.js'):
        shutil.copy(os.path.join(jinja_dir, 'nginx/www/manual', asset), os.path.join(render_tmp, 'nginx/www/manual', asset))
    
    domain_file = merged_context.get('domain_file', 'example_com')
    for script in ['certs', 'firefox-ubuntu', 'chrome-ubuntu', 'all-ubuntu', 'python-ubuntu']:
        src = f'nginx/www/certificates/install-{script}.sh.j2'
        dest = f'nginx/www/certificates/install-{script.replace("-ubuntu", "")}-{domain_file}.sh'
        render_file(src, dest)
        
    # Docker Compose and Systemd Wrappers
    sys_svcs = [
        {'service': 'nginx', 'compose': 'nginx', 'folder': 'nginx', 'requires': []},
        {'service': 'bind9', 'compose': 'bind9', 'folder': 'bind9', 'requires': []},
        {'service': 'stepca', 'compose': 'step-ca', 'folder': 'stepca', 'requires': []},
        {'service': 'ldap', 'compose': 'dirsrv', 'folder': 'dirsrv', 'requires': []},
        {'service': 'postgres', 'compose': 'postgres', 'folder': 'postgres', 'requires': []},
        {'service': 'keycloak', 'compose': 'keycloak', 'folder': 'keycloak', 'requires': ['postgres']},
        {'service': 'webui', 'compose': 'webui', 'folder': 'webui', 'requires': ['fabric-agent']},
    ]

    for svc_info in sys_svcs:
        svc_folder = svc_info['folder']
        svc_name = svc_info['service']
        
        if svc_folder in ['keycloak', 'postgres'] and not final_vars.get('install_keycloak'):
            continue
        if svc_folder == 'dirsrv' and not final_vars.get('install_ldap'):
            continue
        if svc_folder == 'webui' and not final_vars.get('install_webui'):
            continue
            
        render_file(f'{svc_folder}/docker-compose.yml.j2', f'{svc_folder}/docker-compose.yml')
        
        # Render systemd wrapper
        dest_path = os.path.join(render_tmp, f"systemd/{svc_name}.service")
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        try:
            tpl = jinja_env.get_template('systemd/wrapper.service.j2')
            with open(dest_path, 'w') as f:
                f.write(tpl.render(**merged_context, item=svc_info))
        except Exception as e:
            print(f"Error rendering wrapper for {svc_name}: {e}")
            sys.exit(1)
        
    
    # Bind9 Config
    for f in ['named.conf', 'named.conf.acl', 'named.conf.logs', 'named.conf.options', 'named.conf.tls', 'named.conf.zones', 'named.conf.keys', 'rndc.key']:
        render_file(f'bind9/config/{f}.j2', f'bind9/config/{f}')
        
    # Bind9 Zones
    dns = final_vars.get('dns', {})
    for k, v in dns.items():
        zone_name = final_vars.get('domain') if k == 'dynamic_zone_var' else k
        dest_path = os.path.join(render_tmp, f"bind9/data/db.{zone_name}")
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        tpl = jinja_env.get_template('bind9/data/zone.j2')
        with open(dest_path, 'w') as f:
            f.write(tpl.render(**merged_context, zone_name=zone_name, zone_records=v))
            
    for rz in final_vars.get('reverse_zone_names', []):
        dest_path = os.path.join(render_tmp, f"bind9/data/db.{rz}")
        tpl = jinja_env.get_template('bind9/data/reverse-zone.j2')
        with open(dest_path, 'w') as f:
            f.write(tpl.render(**merged_context, reverse_zone_name=rz))

    # 389 Directory Server seed data
    if final_vars.get('install_ldap'):
        for ldif in ['00-config.ldif.j2', '10-tree.ldif.j2', '20-accounts.ldif.j2', '30-aci.ldif.j2']:
            render_file(f'dirsrv/seed/{ldif}', f"dirsrv/seed/{ldif.replace('.j2', '')}")
        shutil.copy(os.path.join(jinja_dir, 'dirsrv/seed.py'), os.path.join(render_tmp, 'dirsrv/seed/seed.py'))

    # webui management UI
    if final_vars.get('install_webui'):
        render_file('webui/webui.json.j2', 'webui/webui.json')
        render_file('systemd/fabric-agent.service.j2', 'systemd/fabric-agent.service')

    # Step-CA
    render_file('stepca/leaf.tpl.j2', 'stepca/templates/certs/leaf.tpl')
    render_file('stepca/subca.tpl.j2', 'stepca/templates/certs/subca.tpl')
    
    # RFC2136
    for key in tsig_keys:
        if 'primary' not in key:
            kname = key['name']
            kdir = os.path.join(render_tmp, f"rfc2136/{kname}")
            os.makedirs(kdir, exist_ok=True)
            with open(os.path.join(kdir, "rfc2136.ini"), 'w') as f:
                f.write(f"""# RFC2136 credentials for TSIG key: {kname}
dns_rfc2136_server = {final_vars.get('host_ip')}
dns_rfc2136_port = {final_vars.get('bind_dns_port', 53)}
dns_rfc2136_name = {kname}
dns_rfc2136_secret = {secrets['tsig_secrets'].get(kname)}
dns_rfc2136_algorithm = {key.get('algorithm', 'hmac-sha256').upper()}
dns_rfc2136_base_domain = {key.get('domain', final_vars.get('domain'))}
""")

    print("Deploying configurations...")
    
    # Ensure Base Directories
    for d in ['fabric/config/certs', 'nginx/www/certificates', 'nginx/www/shared', 'nginx/www/landing', 'nginx/www/manual/docs', 'nginx/www/ldap']:
        ensure_dir(os.path.join(DEPLOY_BASE_DIR, d), 0o755)

    nginx_uid, nginx_gid = get_service_user(final_vars, 'nginx')
    os.chown(os.path.join(DEPLOY_BASE_DIR, 'nginx/www'), nginx_uid, nginx_gid)
    
    def copy_tree_with_perms(src, dst, uid=0, gid=0, fmode=0o640, dmode=0o750):
        changed = False
        if not os.path.exists(dst):
            os.makedirs(dst)
            changed = True
        os.chown(dst, uid, gid)
        os.chmod(dst, dmode)
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            if os.path.isdir(s):
                if copy_tree_with_perms(s, d, uid, gid, fmode, dmode):
                    changed = True
            else:
                if not os.path.exists(d) or not filecmp.cmp(s, d, shallow=False):
                    shutil.copy2(s, d)
                    os.chown(d, uid, gid)
                    os.chmod(d, fmode)
                    changed = True
        return changed

    # Sync repo fabric directory (safely)
    if os.path.realpath(FABRIC_DIR) != os.path.realpath(TARGET_FABRIC):
        copy_tree_with_perms(FABRIC_DIR, TARGET_FABRIC, 0, 0, 0o640, 0o750)
    
    if os.path.exists(os.path.join(REPO_DIR, "setup.sh")):
        setup_src = os.path.join(REPO_DIR, "setup.sh")
        setup_dst = os.path.join(TARGET_FABRIC, "setup.sh")
        if os.path.realpath(setup_src) != os.path.realpath(setup_dst):
            shutil.copy2(setup_src, setup_dst)
            os.chmod(setup_dst, 0o755)
    
    sec_dst = os.path.join(TARGET_FABRIC, "config/fabric-secrets.yml")
    if os.path.realpath(secrets_path) != os.path.realpath(sec_dst):
        shutil.copy2(secrets_path, sec_dst)
        os.chmod(sec_dst, 0o600)

    
    shutil.copy2(os.path.join(render_tmp, "vars.yaml"), os.path.join(TARGET_FABRIC, "config/vars.yaml"))
    
    if os.path.exists(os.path.join(render_tmp, "link-vars.yaml")):
        shutil.copy2(os.path.join(render_tmp, "link-vars.yaml"), os.path.join(TARGET_FABRIC, "config/link-vars.yaml"))
        os.chmod(os.path.join(TARGET_FABRIC, "config/link-vars.yaml"), 0o644)
    
    # Nginx Web Assets
    for folder in ['certificates', 'shared', 'landing', 'manual', 'ldap']:
        src_dir = os.path.join(render_tmp, f"nginx/www/{folder}")
        dest_dir = os.path.join(DEPLOY_BASE_DIR, f"nginx/www/{folder}")
        if os.path.exists(src_dir):
            copy_tree_with_perms(src_dir, dest_dir, nginx_uid, nginx_gid, 0o644, 0o755)
            
    # Docs: from a checkout (<repo>/docs), kept in the installed tree
    # (<fabric>/docs) so setup/reinstall run from /opt/fabric still has them.
    docs_src = next((d for d in (os.path.join(REPO_DIR, "docs"), os.path.join(FABRIC_DIR, "docs"))
                     if os.path.isdir(d)), None)
    if docs_src:
        if os.path.realpath(docs_src) != os.path.realpath(os.path.join(TARGET_FABRIC, "docs")):
            copy_tree_with_perms(docs_src, os.path.join(TARGET_FABRIC, "docs"), 0, 0, 0o644, 0o755)
        copy_tree_with_perms(docs_src, os.path.join(DEPLOY_BASE_DIR, "nginx/www/manual/docs"), nginx_uid, nginx_gid, 0o644, 0o755)
        
    # Service Directories, Config Files & Systemd Wrappers
    services_to_restart = set()
    images_to_rebuild = set()
    daemon_reload_needed = False

    for svc_info in sys_svcs:
        svc_folder = svc_info['folder']
        svc_name = svc_info['service']
        
        if svc_folder in ['keycloak', 'postgres'] and not final_vars.get('install_keycloak'): continue
        if svc_folder == 'dirsrv' and not final_vars.get('install_ldap'): continue
        
        uid, gid = get_service_user(final_vars, 'bind' if svc_folder == 'bind9' else ('step' if svc_folder == 'stepca' else ('ldap' if svc_folder == 'dirsrv' else svc_folder)))
        
        svc_dir = os.path.join(DEPLOY_BASE_DIR, svc_folder)
        ensure_dir(svc_dir, 0o750, uid, gid)
        
        src_dc = os.path.join(render_tmp, f"{svc_folder}/docker-compose.yml")
        dest_dc = os.path.join(svc_dir, "docker-compose.yml")
        
        src_sys = os.path.join(render_tmp, f"systemd/{svc_name}.service")
        dest_sys = f"/etc/systemd/system/{svc_name}.service"
        
        needs_restart = False
        
        if os.path.exists(src_dc):
            if not os.path.exists(dest_dc) or not filecmp.cmp(src_dc, dest_dc, shallow=False):
                needs_restart = True
                shutil.copy2(src_dc, dest_dc)
                os.chmod(dest_dc, 0o640)
                os.chown(dest_dc, uid, gid)

        # Thin local image layers (fabric/jinja/<svc>/build). webui also
        # carries its app code. A changed context means rebuild + restart.
        build_src = os.path.join(jinja_dir, svc_folder, "build")
        if os.path.isdir(build_src) and os.path.exists(src_dc):
            build_dst = os.path.join(svc_dir, "build")
            context_changed = copy_tree_with_perms(build_src, build_dst, 0, 0, 0o644, 0o755)
            if svc_folder == 'webui':
                context_changed |= copy_tree_with_perms(os.path.join(FABRIC_DIR, "lib", "webui"),
                                                        os.path.join(build_dst, "app"), 0, 0, 0o644, 0o755)
            if context_changed:
                images_to_rebuild.add(svc_folder)
                needs_restart = True
            
        if os.path.exists(src_sys):
            if not os.path.exists(dest_sys) or not filecmp.cmp(src_sys, dest_sys, shallow=False):
                needs_restart = True
                daemon_reload_needed = True
                shutil.copy2(src_sys, dest_sys)
                os.chmod(dest_sys, 0o644)
                os.chown(dest_sys, 0, 0)
            
        if needs_restart:
            services_to_restart.add(svc_name)
    # Nginx Conf
    ensure_dir(os.path.join(DEPLOY_BASE_DIR, "nginx/config"), 0o755, nginx_uid, nginx_gid)
    src_nginx = os.path.join(render_tmp, "nginx/nginx.conf")
    dst_nginx = os.path.join(DEPLOY_BASE_DIR, "nginx/config/nginx.conf")
    nginx_config_changed = False
    if not os.path.exists(dst_nginx) or not filecmp.cmp(src_nginx, dst_nginx, shallow=False):
        shutil.copy2(src_nginx, dst_nginx)
        os.chown(dst_nginx, nginx_uid, nginx_gid)
        nginx_config_changed = True

    # Bind9 Files
    bind_uid, bind_gid = get_service_user(final_vars, 'bind')
    for d in ['config', 'data', 'log', 'cache']:
        ensure_dir(os.path.join(DEPLOY_BASE_DIR, f"bind9/{d}"), 0o750, bind_uid, bind_gid)
    
    bind9_config_changed = copy_tree_with_perms(os.path.join(render_tmp, "bind9/config"), os.path.join(DEPLOY_BASE_DIR, "bind9/config"), bind_uid, bind_gid, 0o640, 0o750)
    changed_zones = deploy_zone_files(os.path.join(render_tmp, "bind9/data"), os.path.join(DEPLOY_BASE_DIR, "bind9/data"), bind_uid, bind_gid)
    
    os.chmod(os.path.join(DEPLOY_BASE_DIR, "bind9/config/named.conf.keys"), 0o600)
    os.chmod(os.path.join(DEPLOY_BASE_DIR, "bind9/config/rndc.key"), 0o600)

    # 389 Directory Server seed files (group-readable by the container user only:
    # 20-accounts.ldif holds role-account passwords)
    ldap_seed_changed = False
    if final_vars.get('install_ldap'):
        ldap_uid, ldap_gid = get_service_user(final_vars, 'ldap')
        ensure_dir(os.path.join(DEPLOY_BASE_DIR, "dirsrv/data"), 0o750, ldap_uid, ldap_gid)
        ldap_seed_changed = copy_tree_with_perms(os.path.join(render_tmp, "dirsrv/seed"),
                                                 os.path.join(DEPLOY_BASE_DIR, "dirsrv/seed"),
                                                 0, ldap_gid, 0o640, 0o750)

    # webui container (config, build context) + fabric-agent host unit
    webui_changed = agent_unit_changed = False
    if final_vars.get('install_webui'):
        webui_uid, webui_gid = get_service_user(final_vars, 'webui')
        nginx_gid = get_service_user(final_vars, 'nginx')[1]
        base = os.path.join(DEPLOY_BASE_DIR, "webui")
        ensure_dir(base, 0o755)
        ensure_dir(os.path.join(base, "config"), 0o750, 0, webui_gid)
        ensure_dir(os.path.join(base, "run"), 0o750, webui_uid, nginx_gid)    # container -> nginx socket
        ensure_dir(os.path.join(base, "agent"), 0o750, 0, webui_gid)          # fabric-agent socket
        cfg_dst = os.path.join(base, "config/webui.json")
        cfg_src = os.path.join(render_tmp, "webui/webui.json")
        if not os.path.exists(cfg_dst) or not filecmp.cmp(cfg_src, cfg_dst, shallow=False):
            shutil.copy2(cfg_src, cfg_dst)
            webui_changed = True
        os.chown(cfg_dst, webui_uid, webui_gid)
        os.chmod(cfg_dst, 0o400)
        unit_src = os.path.join(render_tmp, "systemd/fabric-agent.service")
        unit_dst = "/etc/systemd/system/fabric-agent.service"
        if not os.path.exists(unit_dst) or not filecmp.cmp(unit_src, unit_dst, shallow=False):
            shutil.copy2(unit_src, unit_dst)
            os.chown(unit_dst, 0, 0)
            os.chmod(unit_dst, 0o644)
            agent_unit_changed = daemon_reload_needed = True

    # Step-CA Files
    step_uid, step_gid = get_service_user(final_vars, 'step')
    ensure_dir(os.path.join(DEPLOY_BASE_DIR, "stepca/data"), 0o750, step_uid, step_gid)
    if os.path.exists(os.path.join(render_tmp, "stepca/templates/certs")):
        if copy_tree_with_perms(os.path.join(render_tmp, "stepca/templates"), os.path.join(DEPLOY_BASE_DIR, "stepca/data/templates"), step_uid, step_gid, 0o640, 0o750):
            services_to_restart.add('stepca')

    # Runtime data directories (owned by the service that writes them)
    for rel, user, wanted in [("bind9/data", "bind", True), ("bind9/log", "bind", True), ("bind9/cache", "bind", True),
                              ("dirsrv/data", "ldap", final_vars.get('install_ldap')),
                              ("dirsrv/data/tls", "ldap", final_vars.get('install_ldap'))]:
        if wanted:
            ensure_dir(os.path.join(DEPLOY_BASE_DIR, rel), 0o750, *get_service_user(final_vars, user))
    if final_vars.get('install_keycloak'):
        ensure_dir(final_vars.get('postgres_data_dir', os.path.join(DEPLOY_BASE_DIR, "postgres/data")), 0o750,
                   *get_service_user(final_vars, 'postgres'))
        ensure_dir(final_vars.get('keycloak_data_dir', os.path.join(DEPLOY_BASE_DIR, "keycloak/data")), 0o750,
                   *get_service_user(final_vars, 'keycloak'))

    # RFC2136 credentials for non-primary TSIG keys (certbot-style DNS-01 clients)
    for key in tsig_keys:
        if 'primary' in key:
            continue
        src = os.path.join(render_tmp, f"rfc2136/{key['name']}/rfc2136.ini")
        dst = key.get('out') or os.path.join(DEPLOY_BASE_DIR, key['name'], "rfc2136.ini")
        if os.path.exists(src):
            os.makedirs(os.path.dirname(dst), mode=0o700, exist_ok=True)
            shutil.copy2(src, dst)
            os.chown(dst, 0, 0)
            os.chmod(dst, 0o600)

    if not start_services:
        # fabricctl setup: start nothing here, but a re-run finds the stack
        # live. Zones are swapped safely, changed images rebuilt, and every
        # service whose config changed is returned for setup to restart.
        bind9_up = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", "bind9"],
                                  capture_output=True, text=True).stdout.strip() == "true"
        if bind9_up and (bind9_config_changed or "bind9" in services_to_restart):
            for zone, src, dst in changed_zones:
                rndc(f"freeze {zone}")          # sync the journal; the restart loads the new file
                install_zone_file(src, dst, bind_uid, bind_gid)
            services_to_restart.add("bind9")
        elif bind9_up:
            for zone, src, dst in changed_zones:
                reload_zone(zone, src, dst, bind_uid, bind_gid)
        else:
            for zone, src, dst in changed_zones:
                install_zone_file(src, dst, bind_uid, bind_gid)
        if nginx_config_changed:
            services_to_restart.add("nginx")
        if webui_changed:
            services_to_restart.add("webui")
        if agent_unit_changed:
            services_to_restart.add("fabric-agent")
        if daemon_reload_needed:
            subprocess.run(["systemctl", "daemon-reload"], timeout=30)
        # No --pull: setup never takes a new base image implicitly.
        for folder in sorted(images_to_rebuild):
            print(f"Building {folder} image...")
            res = subprocess.run(["docker", "compose", "-f", os.path.join(DEPLOY_BASE_DIR, folder, "docker-compose.yml"),
                                  "build"], capture_output=True, text=True, timeout=1800)
            if res.returncode != 0:
                print(f"Error: building the {folder} image failed:\n{res.stdout[-1500:]}{res.stderr[-1500:]}")
                sys.exit(1)
        print("Configuration deployed (services not started).")
        return services_to_restart

    # Reloading services
    def get_svc_timeout(s):
        if s == "keycloak": return 90
        if s == "postgres": return 60
        return 30

    if daemon_reload_needed:
        print("Reloading systemd daemon...")
        try:
            subprocess.run("systemctl daemon-reload", shell=True, timeout=15)
        except subprocess.TimeoutExpired:
            print("systemctl daemon-reload timed out")
        
    try:
        res = subprocess.run("docker ps --format '{{.Names}}'", shell=True, capture_output=True, text=True, timeout=15)
        running = res.stdout.split('\n')
    except subprocess.TimeoutExpired:
        print("docker ps timed out")
        running = []

    # If BIND9 is down or about to restart it reads zone files on start, so
    # they must be in place before the restart below.
    bind9_live_reload = "bind9" in running and "bind9" not in services_to_restart
    if not bind9_live_reload:
        for zone, src, dst in changed_zones:
            install_zone_file(src, dst, bind_uid, bind_gid)

    # webui is restarted last and without blocking: this apply may have been
    # started from the web UI, and restarting it drops that request.
    restart_webui = "webui" in services_to_restart or webui_changed
    services_to_restart.discard("webui")

    # No --pull on purpose: apply never takes a new base image; only an
    # explicit update (`fabricctl --update-containers`) does.
    for folder in sorted(images_to_rebuild):
        print(f"Rebuilding {folder} image...")
        subprocess.run(["docker", "compose", "-f", os.path.join(DEPLOY_BASE_DIR, folder, "docker-compose.yml"),
                        "build"], timeout=1200)

    for svc in services_to_restart:
        print(f"Restarting {svc} due to configuration changes...")
        try:
            subprocess.run(f"systemctl restart {svc}", shell=True, timeout=get_svc_timeout(svc))
        except subprocess.TimeoutExpired:
            print(f"Restart of {svc} timed out")

    print("Reloading active services...")
    if bind9_live_reload:
        if bind9_config_changed:
            print("Reloading BIND9 configuration...")
            # Keys and update-policy grants (TSIG) take effect here; a
            # silent failure would leave a removed key working. Generous
            # timeout: reconfig is slow on a loaded Pi.
            res = rndc("reconfig", timeout=90)
            if res is None or res.returncode != 0:
                print("Error: BIND9 did not accept the new configuration "
                      f"({(res.stderr or res.stdout).strip() if res else 'timeout'}); check `docker logs bind9`.")
                sys.exit(1)
        for zone, src, dst in changed_zones:
            reload_zone(zone, src, dst, bind_uid, bind_gid)
        
    if "nginx" in running and "nginx" not in services_to_restart:
        if nginx_config_changed:
            print("Reloading NGINX...")
            try:
                subprocess.run("docker exec nginx nginx -s reload", shell=True, timeout=15)
            except subprocess.TimeoutExpired:
                print("Reloading NGINX timed out")

    if ldap_seed_changed and ("dirsrv" in running or "ldap" in services_to_restart):
        print("Applying 389-DS seed data...")
        subprocess.run(["bash", os.path.join(TARGET_FABRIC, "lib", "dirsrv.sh"), "seed"], timeout=600)

    if agent_unit_changed and subprocess.run(["systemctl", "is-enabled", "--quiet", "fabric-agent"]).returncode == 0:
        # --no-block: this apply may itself be running inside fabric-agent.
        print("Restarting fabric-agent (queued)...")
        subprocess.run(["systemctl", "restart", "--no-block", "fabric-agent"], timeout=15)

    if restart_webui and subprocess.run(["systemctl", "is-enabled", "--quiet", "webui"]).returncode == 0:
        print("Restarting webui (queued)...")
        subprocess.run(["systemctl", "restart", "--no-block", "webui"], timeout=15)
        services_to_restart.add("webui")

    print("Deployment complete.")
    return services_to_restart

if __name__ == "__main__":
    apply_deployment()
