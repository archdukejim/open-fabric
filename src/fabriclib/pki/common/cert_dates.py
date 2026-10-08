import datetime
import re
import subprocess


def cert_dates(cert_path):
    """Purpose: a certificate's validity.
    Inputs:  cert_path — PEM file.
    Returns: (not_before, not_after) as aware UTC datetimes, or None when openssl cannot read it.
    Fails:   FileNotFoundError only if openssl is not installed.
    Feeds:   needs_renewal, cert_warnings."""
    out = subprocess.run(["openssl", "x509", "-in", cert_path, "-noout", "-startdate", "-enddate"],
                         capture_output=True, text=True).stdout
    found = dict(re.findall(r"(notBefore|notAfter)=(.+)", out))
    try:
        return tuple(datetime.datetime.strptime(found[k].strip(), "%b %d %H:%M:%S %Y %Z")
                     .replace(tzinfo=datetime.timezone.utc) for k in ("notBefore", "notAfter"))
    except (KeyError, ValueError):
        return None
