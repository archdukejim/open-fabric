"""Render every template the way deploy.py does, against a vars file shaped like a
long-running install (round-tripped values). Usage: render.py <out-dir>"""
import copy
import json
import os
import sys
import glob
import yaml

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'fabric', 'lib'))
from fabriclib.common.jinja_env import jinja_env  # noqa: E402  (the same env deploy.py uses)
from fabriclib.dns.reverse_zones import reverse_zones  # noqa: E402

env = jinja_env(os.path.join(REPO, 'fabric', 'jinja'))

secrets = dict(ca_password='x', rndc_secret='dGVzdC1vbmx5LXJuZGMtc2VjcmV0LTMyLWJ5dGVzISE=', ldap_admin_password='DmPass1', ldap_keycloak_password='KcPass1',
               keycloak_admin_user='admin', keycloak_admin_password='x', keycloak_db_password='x',
               ldap_super_admin_password='Sa1', ldap_group_admin_password='Ga1',
               ldap_user_creator_password='Uc1', ldap_user_modifier_password='Um1',
               webui_oidc_secret='OidcSecret1',
               tsig_secrets={'npm': 'bnBtLXRlc3Qtc2VjcmV0LTMyLWJ5dGVzLWxvbmch', 'acme_dns-01': 'YWNtZS10ZXN0LXNlY3JldA==',
                             'dev1': 'ZGV2MS1zZWNyZXQ=', 'lonely': 'bG9uZWx5LXNlY3JldA=='})
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
                        'record_types': ['TXT'], 'primary': True},
                       {'name': 'dev1', 'algorithm': 'hmac-sha256', 'domain': 'lan.j-j.family', 'record_types': ['TXT']},
                       {'name': 'lonely', 'algorithm': 'hmac-sha256', 'domain': 'lan.j-j.family', 'record_types': ['TXT']}],
            # certbot devices: rights come from the ACL's policy
            bind_acls={'certbot-devices': ['key "dev1"']},
            bind_acl_policies={'certbot-devices': {'domain': 'lan.j-j.family', 'record_types': ['TXT'],
                                                   'records': ['web', 'git']}},
            dns={'dynamic_zone_var': {'zone_authority': True,
                                      'CNAME': [{'name': 'None', 'canonical': 'pi-core'},
                                                {'name': 'calibre', 'canonical': 'nas25-apps'}]}})

# Suites that start real containers override install-specific values
# (deploy path, host IP, ports) with a JSON object in FABRIC_TEST_VARS.
user.update(json.loads(os.environ.get("FABRIC_TEST_VARS", "{}")))

ctx = {**secrets, **user, 'render_date': '2026-01-01'}
PRISTINE = copy.deepcopy(ctx)      # vars.yaml.j2 updates the dns dict it is given in place
v1 = yaml.safe_load(env.get_template('vars.yaml.j2').render(**ctx))
v2 = yaml.safe_load(env.get_template('vars.yaml.j2').render(**{**ctx, **v1}))

# Reverse zones: generated from forward A/AAAA records (deploy.py does the same).
rv = reverse_zones({'domain': 'lan.test', 'host_ip': '192.168.7.53', 'dns': {
    'dynamic_zone_var': {'zone_authority': True,
                         'A': [{'name': '@', 'ip': '192.168.7.53'}, {'name': 'fabric', 'ip': '192.168.7.53'},
                               {'name': 'nas', 'ip': '192.168.7.10'}, {'name': 'lab', 'ip': '10.1.2.3'},
                               {'name': 'cloud', 'ip': '8.8.8.8'}],
                         'AAAA': [{'name': 'nas', 'ip': 'fd12:3456:789a:1::10'}, {'name': 'pub', 'ip': '2001:db8::1'}]},
    'iot.lan.test': {'A': [{'name': 'cam', 'ip': '192.168.7.99'}]},
    '5.168.192.in-addr.arpa': {'A': []},
}})
z = rv['zones']
assert list(z) == ['1.0.0.0.a.9.8.7.6.5.4.3.2.1.d.f.ip6.arpa', '2.1.10.in-addr.arpa', '7.168.192.in-addr.arpa'], list(z)
ptr7 = {r['label']: r['target'] for r in z['7.168.192.in-addr.arpa']}
assert ptr7 == {'10': 'nas.lan.test.', '53': 'fabric.lan.test.', '99': 'cam.iot.lan.test.'}, ptr7
assert [r['label'] for r in z['7.168.192.in-addr.arpa']] == ['10', '53', '99'], 'PTRs sorted numerically'
assert z['1.0.0.0.a.9.8.7.6.5.4.3.2.1.d.f.ip6.arpa'][0] == {
    'label': '0.1.0.0.0.0.0.0.0.0.0.0.0.0.0.0', 'target': 'nas.lan.test.', 'ip': 'fd12:3456:789a:1::10',
    'source': 'AAAA nas in lan.test'}, z
assert {s['ip'] for s in rv['skipped']} == {'8.8.8.8', '2001:db8::1'}, 'public addresses get no local reverse zone'
apex = reverse_zones({'domain': 'lan.test', 'dns': {'dynamic_zone_var': {'A': [{'name': '@', 'ip': '192.168.9.1'}]}}})
assert apex['zones']['9.168.192.in-addr.arpa'][0]['target'] == 'lan.test.', 'apex record -> PTR to the zone, not "@."'
full_rev = reverse_zones(v1)
print('reverse zones', list(full_rev['zones']))
diff = {k: (v1.get(k), v2.get(k)) for k in set(v1) | set(v2) if v1.get(k) != v2.get(k)}
assert not diff, diff
print('project_containers', v2['project_containers'])
print('service_dirs', [d['folder'] for d in v2['service_dirs']])
print('ldap backends', v2['nginx_backend_ldap'], v2['nginx_backend_ldaps'])
print('install_webui', v2['install_webui'], v2['hostname_mgr'])
print('CNAMEs', [r['name'] for r in v2['dns']['dynamic_zone_var']['CNAME']])

full = {**secrets, **v2, 'reverse_zone_names': list(full_rev['zones'])}
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
        extra = dict(reverse_zone_name='7.168.192.in-addr.arpa', ptr_records=rv['zones']['7.168.192.in-addr.arpa'])
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
assert 'zonesub' not in zones, 'no key asked for any_name: nothing may get zonesub'
for want in ('grant "dev1" name _acme-challenge.web.lan.j-j.family. TXT;',
             'grant "dev1" name _acme-challenge.git.lan.j-j.family. TXT;'):
    assert want in zones, f'missing ACL-policy grant: {want}'
assert 'grant "lonely"' not in zones, 'a key with no records, policy or any_name must get no update rights'
acl = env.get_template('bind9/config/named.conf.acl.j2').render(**full)
assert 'acl "certbot-devices"' in acl and 'key "dev1";' in acl, 'policy ACL not rendered'
assert 'secret "bnBtLXRlc3Qtc2VjcmV0LTMyLWJ5dGVzLWxvbmch";' in keys, 'embedded TSIG secret not rendered'
print('TSIG keys and RFC2136 grants rendered')

# Web UI at any host name; certificate page on its own host.
assert v2['hostname_mgr'] == 'fabric.lan.j-j.family' and v2['hostname_certs'] == 'certs.lan.j-j.family', v2['hostname_mgr']
custom = yaml.safe_load(env.get_template('vars.yaml.j2').render(**{**copy.deepcopy(PRISTINE), 'webui_hostname': 'Admin.Example.org'}))
assert custom['hostname_mgr'] == 'admin.example.org', custom['hostname_mgr']
names = [r['name'] for r in custom['dns']['dynamic_zone_var']['CNAME']]
assert 'fabric' not in names and 'admin' not in names, f'no CNAME for a web UI outside the domain: {names}'
ngx = env.get_template('nginx/nginx.conf.j2').render(**{**secrets, **custom})
assert 'server_name admin.example.org;' in ngx and 'server_name certs.lan.j-j.family;' in ngx
same = yaml.safe_load(env.get_template('vars.yaml.j2').render(**{**copy.deepcopy(PRISTINE), 'hostname': 'fabric'}))
assert 'fabric' not in [r['name'] for r in same['dns']['dynamic_zone_var']['CNAME']], 'CNAME must not shadow the host A record'
print('web UI host name (default, custom, same as host) and certs host rendered')
print('all templates rendered')
