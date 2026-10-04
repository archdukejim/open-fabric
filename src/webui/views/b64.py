import base64


def b64(text):
    """Purpose: Base64-encode a text for a data: download link.
    Inputs:  text — str (encoded as UTF-8).
    Returns: base64 str.
    Fails:   AttributeError if text is not a str.
    Feeds:   freeradius (Windows scripts), pki_result (PEM files), tsig_result (the ini file).
    """
    return base64.b64encode(text.encode()).decode()
