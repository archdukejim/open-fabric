#!/bin/bash
# The lint suite (decision D34, manual 4.8.2): ruff for Python, shellcheck for shell scripts. Both run from
# their published images, pinned by digest (nothing is installed on the host).
#   sudo tests/run-all.sh lint
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
RUFF="ghcr.io/astral-sh/ruff:0.13.3@sha256:97b6a4512a9f50f50bd10ce64363b35c1f384d6615ceb6b6b9b0d05654908a55"
SHELLCHECK="koalaman/shellcheck:v0.11.0@sha256:bb596a0d169b85ddd81d8b6d3a2ff6d5baf5fca10b97f575ebc647c3dff62b3d"
PASS=0; FAIL=0
check() { if eval "$2"; then echo "PASS $1"; PASS=$((PASS+1)); else echo "FAIL $1"; FAIL=$((FAIL+1)); fi; }
cd "$REPO" || exit 1

# Purpose: list the repository's shell scripts under the given paths (*.sh, and extension-less files whose
#          first line is a shell shebang).
# Inputs:  $@ — repository paths (git pathspecs).
# Returns: the paths on stdout, one per line.
# Fails:   never (git errors print nothing).
# Feeds:   the shellcheck checks below.
shell_files() {
    git ls-files --cached --others --exclude-standard -- "$@" | while read -r f; do
        case "$f" in
            *.sh) echo "$f" ;;
            *.*) ;;
            *) head -c 40 "$f" 2>/dev/null | grep -qE '^#!(/usr)?/bin/(env )?(ba)?sh' && echo "$f" ;;
        esac
    done
}

out=$(docker run --rm -v "$REPO:/io" -w /io "$RUFF" check src scripts tests 2>&1)
echo "$out" | tail -15 | sed 's/^/    /'
check "ruff: no findings in src/, scripts/ and tests/ (pyproject.toml)" "grep -q 'All checks passed' <<<\"\$out\""

mapfile -t product < <(shell_files src packaging scripts)
out=$(docker run --rm -v "$REPO:/mnt" -w /mnt "$SHELLCHECK" -S warning "${product[@]}" 2>&1)
echo "$out" | tail -15 | sed 's/^/    /'
check "shellcheck: no warnings in the product's ${#product[@]} shell scripts" "[ -z \"\$out\" ]"

# the suites' checks run as strings through eval, which shellcheck cannot follow: variables they read look
# unused (SC2034) and per-command assignments look unseen (SC2097/SC2098)
mapfile -t suites < <(shell_files tests)
out=$(docker run --rm -v "$REPO:/mnt" -w /mnt "$SHELLCHECK" -S warning -e SC2034,SC2097,SC2098 "${suites[@]}" 2>&1)
echo "$out" | tail -15 | sed 's/^/    /'
check "shellcheck: no warnings in the tests' ${#suites[@]} shell scripts (eval-only findings excepted)" "[ -z \"\$out\" ]"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
