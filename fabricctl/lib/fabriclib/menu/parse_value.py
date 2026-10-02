def parse_value(text):
    """Purpose: turn what was typed in the vars editor into a YAML value.
    Inputs:  text — str as typed (already stripped).
    Returns: None for "", null, "" or ''; True / False for true / false (any case); an int for digits; else the text.
    Fails:   never.
    Feeds:   run_vars_menu (add a variable), edit_category (edit one)."""
    if text.lower() == "null" or text in ("", '""', "''"):
        return None
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    if text.isdigit():
        return int(text)
    return text
