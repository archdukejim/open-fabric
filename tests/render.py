"""Render every template the way deploy.py does, against a vars file shaped like a
long-running install (old keys, round-tripped values). Usage: render.py <out-dir>"""
import os
import sys
import glob
import yaml
import jinja2

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'fabric', 'lib'))
import deploy  # noqa: E402

env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.join(REPO, 'fabric', 'jinja')),
                         keep_trailing_newline=True, trim_blocks=True, lstrip_blocks=True,
                         undefined=jinja2.StrictUndefined if '--strict' in sys.argv else jinja2.Undefined)
for n, f in [('to_nice_yaml', deploy.to_nice_yaml_filter), ('unique', deploy.unique_filter),
             ('regex_replace', deploy.regex_replace_filter), ('flatten', deploy.flatten_filter),
             ('bool', deploy.bool_filter), ('dirname', deploy.dirname_filter),
             ('basename', deploy.basename_filter), ('b64encode', deploy.b64encode_filter), ('to_json', __import__('json').dumps), ('combine', lambda b, *o: {k: v for d in (b, *o) for k, v in (d or {}).items()})]:
    env.filters[n] = f
env.tests['match'] = deploy.match_test
env.globals['lookup'] = deploy.lookup_func

secrets = dict(ca_password='x', rndc_secret='x', ldap_admin_password='DmPass1', ldap_keycloak_password='KcPass1',
               keycloak_admin_user='admin', keycloak_admin_password='x', keycloak_db_password='x',
               ldap_super_admin_password='Sa1', ldap_group_admin_password='Ga1',
               ldap_user_creator_password='Uc1', ldap_user_modifier_password='Um1',
               webui_oidc_secret='OidcSecret1', tsig_secrets={})
user = dict(playbook_dir='/opt/core/playbooks', deploy_base_dir='/opt', domain='lan.j-j.family', hostname='pi-core',
            host_ip='192.168.7.53', lan_cidr='192.168.7.0/24', lan_gateway='192.168.7.1',
            core_subnet='10.255.0.0/24', landing_page_cname=None, install_keycloak=True,
            cert_country='US', cert_province='S', cert_city='C', cert_org='O', cert_ou='IT', ca_name='CA',
            project_containers=['nginx', 'step-ca', 'bind9', 'openldap', 'keycloak', 'postgres', 'openldap'],
            service_dirs=[{'folder': 'openldap', 'owner': 'ldap'}, {'folder': 'extra', 'owner': 'root'}],
            nginx_backend_ldap='openldap:389',
            dns={'dynamic_zone_var': {'zone_authority': True,
                                      'CNAME': [{'name': 'None', 'canonical': 'pi-core'},
                                                {'name': 'calibre', 'canonical': 'nas25-apps'}]}})

ctx = {**secrets, **user}
v1 = yaml.safe_load(env.get_template('vars.yaml.j2').render(**ctx))
v2 = yaml.safe_load(env.get_template('vars.yaml.j2').render(**{**ctx, **v1}))
diff = {k: (v1.get(k), v2.get(k)) for k in set(v1) | set(v2) if v1.get(k) != v2.get(k)}
assert not diff, diff
print('project_containers', v2['project_containers'])
print('service_dirs', [d['folder'] for d in v2['service_dirs']])
print('ldap backends', v2['nginx_backend_ldap'], v2['nginx_backend_ldaps'])
print('install_webui', v2['install_webui'], v2['hostname_mgr'])
print('CNAMEs', [r['name'] for r in v2['dns']['dynamic_zone_var']['CNAME']])

full = {**secrets, **v2}
out = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else None
for tpl in sorted(env.list_templates()):
    if not tpl.endswith('.j2') or tpl.startswith(('nginx/www/', 'openldap/')) or tpl == 'vars.yaml.j2':
        continue
    extra = {}
    if tpl.startswith('bind9/data/zone'):
        extra = dict(zone_name='lan.j-j.family', zone_records=v2['dns']['dynamic_zone_var'])
    if tpl.startswith('bind9/data/reverse'):
        extra = dict(reverse_zone_name='7.168.192.in-addr.arpa')
    if tpl.startswith('systemd/'):
        extra = dict(item={'service': 'ldap', 'compose': 'dirsrv', 'folder': 'dirsrv', 'requires': []})
    if tpl.endswith('.json.j2'):
        __import__('json').loads(env.get_template(tpl).render(**full))
    text = env.get_template(tpl).render(**full, **extra)
    if out:
        dest = os.path.join(out, tpl[:-3])
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        open(dest, 'w', encoding='utf-8').write(text)
    if tpl.endswith(('.yml.j2', '.yaml.j2')):
        yaml.safe_load(text)
print('all templates rendered')
