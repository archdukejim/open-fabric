"""Render every template the way deploy.py does, against a vars file shaped like a
long-running install (round-tripped values). Usage: render.py <out-dir>"""
import json
import os
import sys
import glob
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'fabric', 'lib'))
from fabriclib.common.jinja_env import jinja_env  # noqa: E402  (the same env deploy.py uses)

env = jinja_env(os.path.join(REPO, 'fabric', 'jinja'))

secrets = dict(ca_password='x', rndc_secret='dGVzdC1vbmx5LXJuZGMtc2VjcmV0LTMyLWJ5dGVzISE=', ldap_admin_password='DmPass1', ldap_keycloak_password='KcPass1',
               keycloak_admin_user='admin', keycloak_admin_password='x', keycloak_db_password='x',
               ldap_super_admin_password='Sa1', ldap_group_admin_password='Ga1',
               ldap_user_creator_password='Uc1', ldap_user_modifier_password='Um1',
               webui_oidc_secret='OidcSecret1',
               tsig_secrets={'npm': 'bnBtLXRlc3Qtc2VjcmV0LTMyLWJ5dGVzLWxvbmch', 'acme_dns-01': 'YWNtZS10ZXN0LXNlY3JldA=='})
user = dict(deploy_base_dir='/opt', domain='lan.j-j.family', hostname='pi-core',
            host_ip='192.168.7.53', lan_cidr='192.168.7.0/24', lan_gateway='192.168.7.1',
            fabric_subnet='10.255.0.0/24', landing_page_cname=None, install_keycloak=True,
            cert_country='US', cert_province='S', cert_city='C', cert_org='O', cert_ou='IT', ca_name='CA',
            project_containers=['nginx', 'step-ca', 'bind9', 'dirsrv', 'keycloak', 'postgres', 'dirsrv'],
            service_dirs=[{'folder': 'dirsrv', 'owner': 'ldap'}, {'folder': 'extra', 'owner': 'root'}],
            # as normalize_tsig_keys leaves them: an NPM-style per-host key and a primary one
            tsig_keys=[{'name': 'npm', 'algorithm': 'hmac-sha256', 'domain': 'lan.j-j.family',
                        'record_types': ['TXT'], 'records': ['npm', 'shelfmark']},
                       {'name': 'acme_dns-01', 'algorithm': 'hmac-sha256', 'domain': 'lan.j-j.family',
                        'record_types': ['TXT'], 'primary': True}],
            dns={'dynamic_zone_var': {'zone_authority': True,
                                      'CNAME': [{'name': 'None', 'canonical': 'pi-core'},
                                                {'name': 'calibre', 'canonical': 'nas25-apps'}]}})

# Suites that start real containers override install-specific values
# (deploy path, host IP, ports) with a JSON object in FABRIC_TEST_VARS.
user.update(json.loads(os.environ.get("FABRIC_TEST_VARS", "{}")))

ctx = {**secrets, **user, 'render_date': '2026-01-01'}
v1 = yaml.safe_load(env.get_template('vars.yaml.j2').render(**ctx))
v2 = yaml.safe_load(env.get_template('vars.yaml.j2').render(**{**ctx, **v1}))
import re as _re
bad_rev = [z for z in v1.get('reverse_zone_names') or [] if not _re.fullmatch(r'\d+\.\d+\.\d+\.in-addr\.arpa', z)]
assert not bad_rev, f'reverse zone names are malformed (Jinja escape bug?): {bad_rev!r}'
print('reverse zones', v1.get('reverse_zone_names'))
diff = {k: (v1.get(k), v2.get(k)) for k in set(v1) | set(v2) if v1.get(k) != v2.get(k)}
assert not diff, diff
print('project_containers', v2['project_containers'])
print('service_dirs', [d['folder'] for d in v2['service_dirs']])
print('ldap backends', v2['nginx_backend_ldap'], v2['nginx_backend_ldaps'])
print('install_webui', v2['install_webui'], v2['hostname_mgr'])
print('CNAMEs', [r['name'] for r in v2['dns']['dynamic_zone_var']['CNAME']])

full = {**secrets, **v2}
out = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else None
if out:
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, 'vars.yaml'), 'w') as f:
        yaml.safe_dump(v2, f)
for tpl in sorted(env.list_templates()):
    if not tpl.endswith('.j2') or tpl == 'vars.yaml.j2':
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
zones = env.get_template('bind9/config/named.conf.zones.j2').render(**full)
keys = env.get_template('bind9/config/named.conf.keys.j2').render(**full)
for want in ('grant "npm" name _acme-challenge.npm.lan.j-j.family. TXT;',
             'grant "npm" name _acme-challenge.shelfmark.lan.j-j.family. TXT;',
             'grant "acme_dns-01" subdomain _acme-challenge TXT;'):
    assert want in zones, f'missing update-policy grant: {want}'
assert 'zonesub' not in zones, 'a records-limited key must not get zonesub'
assert 'secret "bnBtLXRlc3Qtc2VjcmV0LTMyLWJ5dGVzLWxvbmch";' in keys, 'embedded TSIG secret not rendered'
print('TSIG keys and RFC2136 grants rendered')
print('all templates rendered')
