#!/bin/bash
# Output helpers — source this file, do not execute directly.

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
BLUE='\033[0;34m'

# Purpose: print an informational line with a cyan "[*]" prefix.
# Inputs:  $* — the message words; reads the colour variables above.
# Returns: the line on stdout; exit status 0.
# Fails:   never — echo only.
# Feeds:   do_extra_certs, do_service_cert (certs.sh); manage.sh messages.
info()  { echo -e "${CYAN}[*]${NC} $*"; }
# Purpose: print a success line with a green "[+]" prefix.
# Inputs:  $* — the message words.
# Returns: the line on stdout; exit status 0.
# Fails:   never — echo only.
# Feeds:   _mint_extra_cert, do_extra_certs, do_service_cert (certs.sh); _vars_archive (vars.sh).
ok()    { echo -e "${GREEN}[+]${NC} $*"; }
# Purpose: print a warning line with a yellow "[!]" prefix.
# Inputs:  $* — the message words.
# Returns: the line on stdout; exit status 0.
# Fails:   never — echo only.
# Feeds:   do_extra_certs, do_service_cert (certs.sh).
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
# Purpose: print an error line with a red "[✗]" prefix (callers then exit themselves).
# Inputs:  $* — the message words.
# Returns: the line on stdout (not stderr); exit status 0.
# Fails:   never — echo only.
# Feeds:   _mint_extra_cert, do_extra_certs, do_service_cert (certs.sh); do_render_jinja and flag parsing (manage.sh).
err()   { echo -e "${RED}[✗]${NC} $*"; }

# Purpose: print the running script's header comment as help text and exit.
# Inputs:  none; reads the script "$0" (manage.sh) and prints its comment lines from line 3 up to the first "# ---".
# Returns: the help text on stdout, then exits the shell with status 0.
# Fails:   never exits non-zero. Prints nothing for manage.sh: its line 4 is already "# ---", so the range ends at once.
# Feeds:   manage.sh (--help / -h).
usage() {
    sed -n '3,/^# ---/{ /^# ---/d; s/^# \?//p }' "$0"
    exit 0
}
