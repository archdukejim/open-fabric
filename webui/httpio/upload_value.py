import base64


def upload_value(form, file_field, text_field):
    """Purpose: Take a value from an upload field or, if none was uploaded, from its paste field; binary files (DER)
             are base64-encoded for the agent.
    Inputs:  form — dict from read_form; file_field — str name of the file input; text_field — str name of the
             textarea.
    Returns: str: the uploaded file as ASCII text (PEM), or base64 of it if it is not ASCII, else the pasted text,
             else ''.
    Fails:   never.
    Feeds:   routes/stepca_post (sign/review, inspect, convert) → agentclient describe_csr, inspect_pem, convert_cert.
    """
    data = form.get(file_field)
    if isinstance(data, bytes) and data:
        try:
            return data.decode("ascii")
        except UnicodeDecodeError:
            return base64.b64encode(data).decode()
    text = form.get(text_field, "")
    return text if isinstance(text, str) else ""
