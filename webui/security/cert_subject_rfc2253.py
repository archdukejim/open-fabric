import subprocess


def cert_subject_rfc2253(path):
    """Purpose: Read a PEM certificate's subject DN in RFC 2253 form with openssl.
    Inputs:  path — str, path to a PEM certificate (the Step-CA intermediate from the config).
    Returns: the subject str without the 'subject=' prefix, e.g. 'CN=Fabric Intermediate CA,O=Fabric'.
    Fails:   subprocess.CalledProcessError when openssl cannot read the file; FileNotFoundError if openssl is not
             installed. Both stop the server at start.
    Feeds:   app_state.App → parse_dn → App.issuer_dn.
    """
    res = subprocess.run(["openssl", "x509", "-in", path, "-noout", "-subject", "-nameopt", "RFC2253"],
                         capture_output=True, text=True, check=True)
    return res.stdout.strip().removeprefix("subject=").strip()
