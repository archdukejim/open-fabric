import subprocess

from fabriclib.common.dns_wire import dns_wire_answers, dns_wire_query


def doh_query(name, url_host, ip, root_ca, timeout=10):
    """Purpose: an A-record lookup over DNS-over-HTTPS (RFC 8484, POST), for doctor's health check (manual 2.1.12.2):
             through nginx at url_host, pinned to ip, the certificate verified against root_ca.
    Inputs:  name — host name to look up; url_host — the DNS name's host (hostname_bind9); ip — the address nginx
             answers on; root_ca — fabric's root CA file; timeout — seconds.
    Returns: list of IPv4 answers ([] for none).
    Fails:   subprocess.CalledProcessError when curl fails (TLS, connection, an HTTP error status); struct.error or
             IndexError on a malformed reply; FileNotFoundError without curl.
    Feeds:   setup/verify_install."""
    query = dns_wire_query(name)
    res = subprocess.run(["curl", "-sf", "--max-time", str(timeout), "--cacert", root_ca, "--resolve",
                          f"{url_host}:443:{ip}", "-H", "content-type: application/dns-message", "-H",
                          "accept: application/dns-message", "--data-binary", "@-", f"https://{url_host}/dns-query"],
                         input=query, capture_output=True, check=True)
    return dns_wire_answers(query, res.stdout)
