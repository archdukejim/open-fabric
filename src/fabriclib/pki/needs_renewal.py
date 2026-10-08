import datetime
import os
import re
import subprocess

from fabriclib.pki.common.cert_dates import cert_dates

RENEW_BEFORE_SECONDS = 30 * 24 * 3600      # without a renewal age: renew with under 30 days left (client certs)
DAY = 86400


def needs_renewal(cert_path, names, ca_certs=None, renew_after_days=None, max_days=None, now=None):
    """Purpose: Decide whether a certificate on disk must be (re)issued (manual 2.1.5.4, 2.1.5.7).
    Inputs:  cert_path — PEM file; names — names that must be DNS or IP SANs ([] = no name check);
             ca_certs — optional (root_path, intermediate_path) the certificate must verify against;
             renew_after_days — renew once the certificate is this many days old (service certificates:
             cert_renew_after_days); None: renew with under 30 days left; max_days — renew one whose whole lifetime is
             longer than this (cert_service_days: how an upgrade replaces long-lived certificates); now — for tests.
    Returns: True if the file is missing or unreadable, is due by age (or by the 30 days left), lives longer than
             max_days (a day's margin), does not verify against ca_certs, or lacks one of names; else False.
    Fails:   never for a bad certificate (openssl failures read as "renew"); FileNotFoundError only if
             openssl is not installed.
    Feeds:   setup/create_admin.py run, setup/mint_extra_certs.py mint_extra_certs,
             setup/mint_service_certs.py run.
    Notes:   the CA check catches a file left from an install whose CA has since been replaced.
    """
    if not os.path.exists(cert_path):
        return True
    dates = cert_dates(cert_path)
    if dates is None:
        return True
    not_before, not_after = dates
    now = now or datetime.datetime.now(datetime.timezone.utc)
    if renew_after_days is not None:
        if (now - not_before).total_seconds() >= renew_after_days * DAY:
            return True
    elif (not_after - now).total_seconds() < RENEW_BEFORE_SECONDS:
        return True
    if (not_after - now).total_seconds() <= 0:
        return True
    if max_days is not None and (not_after - not_before).total_seconds() > (max_days + 1) * DAY:
        return True
    if ca_certs:
        root, intermediate = ca_certs
        if subprocess.run(["openssl", "verify", "-CAfile", root, "-untrusted", intermediate, cert_path],
                          capture_output=True).returncode != 0:
            return True
    text = subprocess.run(["openssl", "x509", "-in", cert_path, "-noout", "-ext", "subjectAltName"],
                          capture_output=True, text=True).stdout
    have = set(re.findall(r"(?:DNS|IP Address):([^,\s]+)", text))
    return not set(names) <= have
