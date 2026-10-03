import email.parser
import email.policy
import urllib.parse

from webui.constants import MAX_BODY


def read_form(headers, rfile):
    """Purpose: Read and parse a POST body: urlencoded or multipart form data.
    Inputs:  headers — the request headers (Content-Length, Content-Type); rfile — the request body stream (at most
             MAX_BODY, 64 KiB, is read).
    Returns: dict: urlencoded → {name: str} (first value of each, blanks kept); multipart → {name: str} for text parts
             and {name: bytes} for file parts.
    Fails:   ValueError 'request too large' above MAX_BODY or for a negative length, and ValueError from int() on a bad
             Content-Length; neither is an agent ValidationError, so handle_request answers 500.
    Feeds:   handler.Handler.handle_request (the CSRF check), then the POST routes.
    """
    length = int(headers.get("Content-Length") or 0)
    if length > MAX_BODY or length < 0:
        raise ValueError("request too large")
    body = rfile.read(length)
    ctype = headers.get("Content-Type", "")
    if ctype.startswith("multipart/form-data"):
        msg = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
            f"Content-Type: {ctype}\r\n\r\n".encode() + body)
        form = {}
        for part in msg.iter_parts() if msg.is_multipart() else []:
            name = part.get_param("name", header="content-disposition")
            if not name:
                continue
            data = part.get_payload(decode=True) or b""
            form[name] = data if part.get_filename() is not None else data.decode("utf-8", "replace")
        return form
    raw = body.decode("utf-8", "replace")
    return {k: v[0] for k, v in urllib.parse.parse_qs(raw, keep_blank_values=True).items()}
