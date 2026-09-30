import re
import subprocess

from fabriclib.common.errors import ValidationError
from fabriclib.pki.common.openssl import openssl
from fabriclib.pki.common.to_pem import to_pem
from fabriclib.pki.common.valid_san import valid_san

EC_CURVES = {"prime256v1", "P-256", "secp384r1", "P-384", "secp521r1", "P-521"}
SAN_KINDS = ("DNS", "IP Address", "email")


def describe_csr(data):
    """Purpose: Decode a certificate signing request and judge it against fabric's signing policy
             before anything is signed.
    Inputs:  data — exactly one CSR as PEM, DER bytes or bare base64.
    Returns: {"pem", "subject" (RFC 2253), "cn", "sans" (values without their type), "key" ("RSA <bits>",
             "EC <curve>", "Ed25519" or the algorithm), "ca_requested" (bool), "problems" (list of str),
             "text" (openssl -text)}. Empty problems means it may be signed. Recorded as problems, not
             raised: a signature that does not verify; a SAN other than DNS / IP / e-mail or malformed; no
             CN and no SAN; a CN-only request whose CN is not a host, IP or e-mail; RSA under 2048 bits;
             an EC curve other than P-256/384/521; any other key algorithm.
    Fails:   ValidationError "give exactly one certificate signing request"; to_pem's messages; openssl's
             first error line if the request cannot be parsed.
    Feeds:   agent route POST /v1/pki/describe-csr -> webui agentclient.describe_csr; inspect_pem;
             sign_csr (refuses unless problems is empty).
    Notes:   CA:TRUE is only reported: the CSR's own extensions are never copied, fabric issues a leaf
             (serverAuth + clientAuth) from its template whatever the CSR asks for.
    """
    blocks = to_pem(data, "csr")
    if len(blocks) != 1:
        raise ValidationError("give exactly one certificate signing request")
    pem = blocks[0]
    problems = []
    if subprocess.run(["openssl", "req", "-noout", "-verify"], input=pem, capture_output=True,
                      text=True).returncode != 0:
        problems.append("the request's signature does not verify (corrupt or tampered)")
    subject = openssl("req", "-noout", "-subject", "-nameopt", "RFC2253", data=pem).partition("=")[2].strip()
    cn = next((p[3:] for p in re.split(r"(?<!\\),", subject) if p.startswith("CN=")), "")
    text = openssl("req", "-noout", "-text", data=pem)

    sans = []
    san = re.search(r"Subject Alternative Name:.*?\n\s*(.+)", text)
    for item in (san.group(1).split(",") if san else []):
        kind, _, value = item.strip().partition(":")
        if kind not in SAN_KINDS or not valid_san(value):
            problems.append(f"unsupported or malformed name: {item.strip()}")
        else:
            sans.append(value)
    if not cn and not sans:
        problems.append("the request names nothing (no CN, no subject alternative names)")
    elif cn and not sans and not valid_san(cn):
        problems.append(f"the common name {cn!r} is not a host name, IP address or e-mail address")

    alg = (re.search(r"Public Key Algorithm: (\S+)", text) or [None, "?"])[1]
    if alg == "rsaEncryption":
        bits = int((re.search(r"Public-Key: \((\d+) bit\)", text) or [None, 0])[1])
        key = f"RSA {bits}"
        if bits < 2048:
            problems.append(f"RSA key too small ({bits} bits; at least 2048)")
    elif alg == "id-ecPublicKey":
        curve = (re.search(r"(?:NIST CURVE|ASN1 OID): (\S+)", text) or [None, "?"])[1]
        key = f"EC {curve}"
        if curve not in EC_CURVES:
            problems.append(f"EC curve {curve} not accepted (P-256, P-384, P-521)")
    elif alg.upper() == "ED25519":
        key = "Ed25519"
    else:
        key = alg
        problems.append(f"key algorithm {alg} not accepted")
    return {"pem": pem, "subject": subject, "cn": cn, "sans": sans, "key": key,
            "ca_requested": "CA:TRUE" in text, "problems": problems, "text": text}
