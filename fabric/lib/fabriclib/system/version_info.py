import os

from fabriclib.common.paths import FABRIC_DIR


def version_info():
    """{"version": contents of fabric/VERSION, "build": contents of fabric/BUILD}"""
    def read(name):
        try:
            with open(os.path.join(FABRIC_DIR, name)) as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""
    return {"version": read("VERSION") or "unknown", "build": read("BUILD")}
