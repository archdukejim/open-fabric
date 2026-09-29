import base64
import collections.abc
import json
import os
import posixpath
import re
import time

import jinja2
import yaml

from fabriclib.common.read_images_lock import read_images_lock
from fabriclib.common.read_packages_lock import read_packages_lock


class _RelativeEnvironment(jinja2.Environment):
    """Resolve `{% extends "../shared/base.html.j2" %}` relative to the
    including template."""

    def join_path(self, template, parent):
        if template.startswith(("./", "../")):
            return posixpath.normpath(posixpath.join(posixpath.dirname(parent), template))
        return template


def _unique(items, attribute=None):
    seen, out = set(), []
    for item in items or []:
        val = item.get(attribute, item) if isinstance(item, dict) and attribute else item
        key = json.dumps(val, sort_keys=True) if isinstance(val, (dict, list)) else val
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _flatten(value):
    out = []
    for item in value:
        if isinstance(item, collections.abc.Iterable) and not isinstance(item, (str, bytes, dict)):
            out.extend(_flatten(item))
        else:
            out.append(item)
    return out


def _bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "yes", "1", "on", "t", "y")
    return bool(value)


def _lookup(kind, arg):
    """The one lookup() fabric's templates use: pipe('date +%s')."""
    if kind == "pipe" and arg == "date +%s":
        return str(int(time.time()))
    return ""


def jinja_env(template_dir):
    """The Jinja2 environment every fabric template is rendered with:
    fabric's filters, relative extends, trim_blocks/lstrip_blocks."""
    env = _RelativeEnvironment(loader=jinja2.FileSystemLoader(template_dir), keep_trailing_newline=True,
                               trim_blocks=True, lstrip_blocks=True)
    env.filters.update({
        "to_nice_yaml": lambda v, indent=4: yaml.safe_dump(v, default_flow_style=False, indent=indent).strip(),
        "to_json": json.dumps,
        "unique": _unique,
        "regex_replace": lambda s, pattern, repl: re.sub(pattern, repl, s),
        "b64encode": lambda s: base64.b64encode(s.encode()).decode(),
        "flatten": _flatten,
        "bool": _bool,
        "dirname": os.path.dirname,
        "basename": os.path.basename,
        "combine": lambda base, *others: {k: v for d in (base, *others) for k, v in (d or {}).items()},
    })
    env.tests["match"] = lambda value, pattern: bool(re.search(pattern, str(value)))
    env.globals["lookup"] = _lookup
    # image_* defaults: the validated, digest-pinned refs (fabric/images.lock.yaml)
    env.globals["images_lock"] = {k: e["ref"] for k, e in read_images_lock(os.path.dirname(template_dir)).items()}
    env.globals["packages_lock"] = read_packages_lock(os.path.dirname(template_dir))
    return env
