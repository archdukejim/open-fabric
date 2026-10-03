import subprocess

from fabriclib.common.errors import ValidationError


def openssl(*args, data=None, check=True):
    """Purpose: Run the openssl CLI with input on stdin and return its output; the manual PKI code's
             single openssl runner.
    Inputs:  args — openssl arguments (str; never secrets: argv is world-readable); data — str or bytes
             fed on stdin, default None (no input); check — bool, default True: raise on a non-zero exit.
    Returns: openssl's stdout: bytes if data is bytes, else str.
    Fails:   ValidationError with openssl's first non-empty stderr line (at most 200 characters; "openssl
             failed" if stderr is empty) on a non-zero exit when check; FileNotFoundError if openssl is not
             installed.
    Feeds:   common/describe_cert, common/to_pem, describe_csr, inspect_pem, convert_cert, issue_key_pair,
             sign_csr, stage_site_ca.
    """
    text = not isinstance(data, bytes)
    res = subprocess.run(["openssl", *args], input=data, capture_output=True, text=text)
    if check and res.returncode != 0:
        err = res.stderr if text else res.stderr.decode(errors="replace")
        first = next((line for line in err.splitlines() if line.strip()), "openssl failed")
        raise ValidationError(first.strip()[:200])
    return res.stdout
