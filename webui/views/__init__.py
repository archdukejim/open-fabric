"""The pages of the web UI (Jinja2, autoescaped; templates in webui/templates, the stylesheet in
webui/static): one file per page, all importable from here (`from webui import views`)."""
from webui.views.constants import TABS, FREERADIUS_SECTIONS, BIND9_SECTIONS, OPENBAO_SECTIONS, OPENBAO_VIEWS, SLOT_TYPES, DIRSRV_SECTIONS, STEPCA_MENU, STEPCA_VIEWS, KEY_TYPES, TSIG_SCOPES, TSIG_ANY_TYPES, SERVICES, PREVIEW_PERMS, TAB_PERMS, MENU_PERMS  # noqa: F401
from webui.views.apply_result import apply_result  # noqa: F401
from webui.views.audit import audit  # noqa: F401
from webui.views.bind9 import bind9  # noqa: F401
from webui.views.continue_page import continue_page  # noqa: F401
from webui.views.css import css  # noqa: F401
from webui.views.dirsrv import dirsrv  # noqa: F401
from webui.views.error_page import error_page  # noqa: F401
from webui.views.freeradius import freeradius  # noqa: F401
from webui.views.kea import kea  # noqa: F401
from webui.views.openbao import openbao  # noqa: F401
from webui.views.overview import overview  # noqa: F401
from webui.views.person_result import person_result  # noqa: F401
from webui.views.pki_result import pki_result  # noqa: F401
from webui.views.radius_secret import radius_secret  # noqa: F401
from webui.views.stepca import stepca  # noqa: F401
from webui.views.tsig_result import tsig_result  # noqa: F401
