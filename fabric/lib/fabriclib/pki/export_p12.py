import os
import subprocess
import tempfile


def export_p12(crt, key, chain_files, friendly_name, password, out):
    """Bundle a certificate, its key and the CA chain into a password-protected
    PKCS#12 file (AES-256, SHA-256 MAC) for browser import. The password goes
    to openssl through a 0600 temp file, never argv. `out` is written 0600."""
    with tempfile.TemporaryDirectory(prefix="fabric-p12-") as tmp:     # 0700
        pw_file, chain = os.path.join(tmp, "pw"), os.path.join(tmp, "chain.pem")
        with open(pw_file, "w") as f:
            f.write(password)
        with open(chain, "w") as f:
            for path in chain_files:
                with open(path) as src:
                    f.write(src.read())
        old = os.umask(0o077)
        try:
            subprocess.run(["openssl", "pkcs12", "-export", "-in", crt, "-inkey", key, "-certfile", chain,
                            "-name", friendly_name, "-keypbe", "AES-256-CBC", "-certpbe", "AES-256-CBC",
                            "-macalg", "sha256", "-passout", f"file:{pw_file}", "-out", out],
                           check=True, capture_output=True)
        finally:
            os.umask(old)
    os.chmod(out, 0o600)
