import subprocess

from fabriclib.common.errors import ValidationError


def openssl(*args, data=None, check=True):
    """Run openssl with `data` on stdin (str or bytes). Returns stdout as the
    same type as `data` (str when there is none). With check, a failure
    raises ValidationError carrying openssl's first error line."""
    text = not isinstance(data, bytes)
    res = subprocess.run(["openssl", *args], input=data, capture_output=True, text=text)
    if check and res.returncode != 0:
        err = res.stderr if text else res.stderr.decode(errors="replace")
        first = next((line for line in err.splitlines() if line.strip()), "openssl failed")
        raise ValidationError(first.strip()[:200])
    return res.stdout
