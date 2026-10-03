"""Asking before fabric changes the host (manual 2.7.1): the recorded answers, the questions setup asks
(unattended and interactive), what steps may do with them, the account plan with its move from the previous
accounts, and the upgrade of an older install's settings. No containers and nothing changed on this host: the
answers live in a scratch folder and the account checks read (or stand in for) the host's accounts."""
import builtins
import contextlib
import io
import os
import sys
import tempfile

import yaml

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "fabricctl", "lib"))
from fabriclib.common.jinja_env import jinja_env  # noqa: E402
from fabriclib.common.keep_original import keep_original  # noqa: E402
from fabriclib.common.restore_original import restore_original  # noqa: E402
from fabriclib.consent import plan_accounts as pa  # noqa: E402
from fabriclib.consent.allowed_to_change import allowed_to_change  # noqa: E402
from fabriclib.consent.ask_consent import ask_consent  # noqa: E402
from fabriclib.consent.check_consent import check_consent  # noqa: E402
from fabriclib.consent.consent_status import consent_status  # noqa: E402
from fabriclib.consent.plan_firewall import plan_firewall  # noqa: E402
from fabriclib.deploy.render_vars import render_vars  # noqa: E402
from fabriclib.security.ufw_rule import ufw_rule  # noqa: E402
from fabriclib.setup.errors import SetupError  # noqa: E402
from fabriclib.setup.upgrade_vars import upgrade_vars  # noqa: E402
from fabriclib.undo import undo_runtime as ur  # noqa: E402
from fabriclib.undo.undo_group import undo_group  # noqa: E402
from fabriclib.undo.uninstall_plan import uninstall_plan  # noqa: E402

FAILED = 0
JINJA = os.path.join(REPO, "fabricctl", "jinja")


def check(name, cond, detail=""):
    global FAILED
    FAILED += not cond
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {detail}"))


def refused(fn):
    """The SetupError message fn raises, or "" when it does not raise."""
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            fn()
    except SetupError as e:
        return str(e)
    return ""


cfg = tempfile.mkdtemp()
PLAN = {"packages": ["apt: install docker.io"], "accounts": ["create user fabric-dns (uid 600, gid 600)"],
        "firewall": ["ufw: allow 22/tcp (SSH) from 10.0.0.0/24"]}

print("--- before anything was asked")
check("an install set up before consent existed keeps converging (apply, timers), setup does not",
      allowed_to_change(cfg, "time", ["x"], unasked_install=True) and not allowed_to_change(cfg, "time", ["x"]))
check("nothing to change is always allowed", allowed_to_change(cfg, "firewall", []))

print("--- unattended")
msg = refused(lambda: ask_consent(cfg, PLAN, interactive=False))
check("--non-interactive without --approve stops and names every group to answer",
      "need an answer: packages, accounts, firewall" in msg and "--approve" in msg, msg)
check("... and approves nothing", not allowed_to_change(cfg, "packages", PLAN["packages"]))
check("an unknown group name is refused",
      "unknown host-change group" in refused(lambda: ask_consent(cfg, PLAN, False, approve=["firewal"])))
with contextlib.redirect_stdout(io.StringIO()):
    ask_consent(cfg, PLAN, interactive=False, approve=["all"])
check("--approve all: every planned change is allowed",
      all(allowed_to_change(cfg, g, c) for g, c in PLAN.items()))
check("a change that was not part of the approval is not allowed (subset rule)",
      not allowed_to_change(cfg, "firewall", PLAN["firewall"] + ["ufw: allow 22/tcp (SSH) from 0.0.0.0/0"]))
check("a re-run with the same plan asks nothing (unattended, no --approve)",
      refused(lambda: ask_consent(cfg, PLAN, interactive=False)) == "")
more = dict(PLAN, firewall=PLAN["firewall"] + ["ufw: allow 123/udp (NTP) from 10.0.0.0/24"])
msg = refused(lambda: ask_consent(cfg, more, interactive=False))
check("a new firewall rule asks again — about the firewall only", "need an answer: firewall" in msg, msg)
with contextlib.redirect_stdout(io.StringIO()):
    ask_consent(cfg, more, interactive=False, approve=["firewall"])
check("an approval keeps what was approved before: a run that changes less still matches",
      allowed_to_change(cfg, "firewall", PLAN["firewall"]) and allowed_to_change(cfg, "firewall", more["firewall"]))
saved = yaml.safe_load(open(os.path.join(cfg, "consent.yaml")))["groups"]["firewall"]
check("consent.yaml records the answer, the changes, when and who; it is root-only (0600)",
      saved["answer"] == "yes" and saved["when"] and saved["by"]
      and oct(os.stat(os.path.join(cfg, "consent.yaml")).st_mode & 0o777) == "0o600", saved)

print("--- declining")
with contextlib.redirect_stdout(io.StringIO()):
    ask_consent(cfg, more, interactive=False, decline=["firewall"])
out = io.StringIO()
with contextlib.redirect_stdout(out):
    went_ahead = check_consent(cfg, "firewall", more["firewall"])
check("a declined recommended group: the step leaves the host as it is and says what that means",
      went_ahead is False and "not approved" in out.getvalue(), out.getvalue())
row = next(r for r in consent_status(cfg) if r["group"] == "firewall")
check("status shows it declined, with the relaxation", row["state"] == "declined" and "reachable" in row["relaxation"],
      row)
msg = refused(lambda: ask_consent(cfg, PLAN, interactive=False, decline=["accounts"]))
check("declining a required group stops setup and says why", "Service accounts declined" in msg, msg)
check("... and a step of a required group refuses on its own too",
      "not approved" in refused(lambda: check_consent(cfg, "accounts", PLAN["accounts"])))

print("--- interactive")
cfg2 = tempfile.mkdtemp()
answers = iter(["", "maybe", "y", "n"])
real_input = builtins.input
builtins.input = lambda prompt="": next(answers)
try:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        got = ask_consent(cfg2, {"packages": PLAN["packages"], "runtime": ["restart Docker"]}, interactive=True)
finally:
    builtins.input = real_input
check("each group is one question listing its changes and what no means; there is no default answer",
      got == {"packages": "yes", "runtime": "no"} and "If no:" in out.getvalue()
      and "apt: install docker.io" in out.getvalue(), got)

print("--- service accounts")
v = yaml.safe_load(jinja_env(JINJA).get_template("vars.yaml.j2").render(
    domain="lan.test", hostname="h", host_ip="10.0.0.5", lan_cidr="10.0.0.0/24", lan_gateway="10.0.0.1"))
users = v["service_users"]
check("defaults: fabric-* names in the 600-649 band (bind -> fabric-dns 600, Keycloak keeps gid 0)",
      users["bind"] == {"uid": 600, "gid": 600, "name": "fabric-dns"} and users["keycloak"]["gid"] == 0
      and all(600 <= u["uid"] <= 649 and u["name"].startswith("fabric-") for u in users.values()), users)
msg = refused(lambda: pa.plan_accounts({"service_users": {"bind": {"uid": 1, "gid": 1, "name": "fabric-dns"}}},
                                       "/nonexistent", JINJA))
check("an id taken by another account stops setup, naming both (fabric never takes one over)",
      "is taken by" in msg and "service_users.bind" in msg, msg)
fake = {"bind": 53, "fabric-dns": None}
saved_fns = (pa._user_uid, pa._group_gid, pa._uid_owner, pa._gid_owner, pa._fabric_dirs)
pa._user_uid = lambda n: fake.get(n)
pa._group_gid = lambda n: 53 if n == "bind" else None
pa._uid_owner = pa._gid_owner = lambda i: "bind" if i == 53 else None
pa._fabric_dirs = lambda base, j: ["/opt/bind9", "/opt/fabric"]
try:
    acts = pa.plan_accounts({"service_users": {"bind": users["bind"]}}, "/opt", JINJA)
finally:
    pa._user_uid, pa._group_gid, pa._uid_owner, pa._gid_owner, pa._fabric_dirs = saved_fns
check("an install with the previous bind (53) account: create fabric-dns, move its files, remove bind",
      [a["do"] for a in acts] == ["group", "user", "move", "remove"]
      and acts[2]["uid"] == (53, 600) and acts[2]["gid"] == (53, 600) and acts[3]["name"] == "bind", acts)

print("--- upgrading an older install's settings")
old = {"service_users": {"bind": {"uid": 53, "gid": 53}, "nginx": {"uid": 1443, "gid": 1443}}}
changes = upgrade_vars(old, set())
check("previous defaults are dropped (the new accounts apply), an admin's own ids are kept",
      old["service_users"] == {"nginx": {"uid": 1443, "gid": 1443}} and len(changes) == 1, (old, changes))

print("--- the firewall question")
rules = plan_firewall({**v, "ntp_serve": False}, cfg)
check("one line per rule fabric adds, plus the default policy and the DOCKER-USER limit",
      rules[0].startswith("ufw: deny incoming") and "ufw: allow 22/tcp (SSH) from 10.0.0.0/24" in rules
      and rules[-1].startswith("iptables DOCKER-USER"), rules)
check("security.firewall false asks nothing", plan_firewall({**v, "security": {"firewall": False}}, cfg) == [])
final, _ = render_vars(jinja_env(JINJA), {}, {"domain": "lan.test", "hostname": "h", "host_ip": "10.0.0.5",
                                              "lan_cidr": "10.0.0.0/24", "lan_gateway": "10.0.0.1"})
check("the settings render without secrets (a fresh install plans before anything exists)",
      final["service_users"]["bind"]["uid"] == 600)

print("--- undoing a host change (setup --undo, uninstall)")
host = tempfile.mkdtemp()                         # stands in for the host's files
orig = os.path.join(host, "etc", "app.conf")
os.makedirs(os.path.dirname(orig))
open(orig, "w").write("theirs\n")
kept = keep_original(orig, cfg)
open(orig, "w").write("# fabric: ours\n")
check("the host's file is kept once, before fabric's first change; a later change does not replace the copy",
      kept and not keep_original(orig, cfg) and restore_original(orig, cfg) == "restored"
      and open(orig).read() == "theirs\n" and restore_original(orig, cfg) is None)
new = os.path.join(host, "etc", "new.conf")
keep_original(new, cfg)
open(new, "w").write("x")
link = os.path.join(host, "etc", "resolv.conf")
os.symlink("/run/systemd/resolve/stub-resolv.conf", link)
keep_original(link, cfg)
os.remove(link)
os.symlink("/run/systemd/resolve/resolv.conf", link)
check("a file fabric added is removed again; a symlink gets its own target back",
      restore_original(new, cfg) == "removed" and not os.path.exists(new) and restore_original(link, cfg) == "restored"
      and os.readlink(link) == "/run/systemd/resolve/stub-resolv.conf")
ours = os.path.join(host, "etc", "ours.conf")
open(ours, "w").write("# fabric: rendered by fabricctl\n")
check("a file already fabric's (an install from before copies were kept) is not taken for the original",
      not keep_original(ours, cfg, marker="# fabric") and restore_original(ours, cfg) is None)
check("fabric's ufw rules: the same words add and delete them",
      ufw_rule("ssh", "10.0.0.0/24") == ["from", "10.0.0.0/24", "to", "any", "port", "22", "proto", "tcp"]
      and ufw_rule("dhcp", "eth1") == ["in", "on", "eth1", "to", "any", "port", "67", "proto", "udp"])
daemon = os.path.join(host, "daemon.json")
ur.DAEMON_JSON = daemon
open(daemon, "w").write('{"data-root": "/srv/docker", "icc": false, "no-new-privileges": true, "live-restore": false,'
                        ' "log-opts": {"max-size": "10m", "max-file": "3", "labels": "a"}}')
before = open(daemon).read()
done = ur.undo_runtime(cfg, restart=False)
check("without a kept copy only the keys still holding fabric's values leave daemon.json (an admin's value stays)",
      yaml.safe_load(open(daemon)) == {"data-root": "/srv/docker", "live-restore": False, "log-opts": {"labels": "a"}}
      and done and "no copy" in done[0], (open(daemon).read(), done))
open(daemon, "w").write(before)
keep_original(daemon, cfg)
open(daemon, "w").write('{"icc": false}')
check("with a kept copy daemon.json is put back exactly",
      ur.undo_runtime(cfg, restart=False)[0].endswith("put back as it was") and open(daemon).read() == before)


class Ctx:
    def __init__(self, config_dir, v):
        self.config_dir, self.vars = config_dir, v


fresh = tempfile.mkdtemp()
check("undo refuses the kinds fabric needs (uninstall removes those), naming the way",
      "fabricctl uninstall" in refused(lambda: undo_group(Ctx(cfg, {}), "accounts", True, True)))
check("undo refuses the resolver while BIND needs port 53",
      "use_host_dns" in refused(lambda: undo_group(Ctx(cfg, {"use_host_dns": False}), "resolver", True, True)))
check("undo refuses on an install never asked (setup asks first), and an unknown group",
      "set up before" in refused(lambda: undo_group(Ctx(fresh, {}), "trust", True, True))
      and "unknown" in refused(lambda: undo_group(Ctx(cfg, {}), "bogus", True, True)))
check("undo without --yes never runs unattended",
      "--yes" in refused(lambda: undo_group(Ctx(cfg, {"domain_file": "x"}), "trust", False, False)))
rows = {t: (how, what) for t, how, what in uninstall_plan()}
check("uninstall lists every kind of host change: removed, undone or kept (Docker's settings: how to undo first)",
      len(rows) == 8 and rows["Service accounts"][0] == "removed" and rows["Host firewall"][0] == "undone"
      and rows["Docker daemon settings"][0] == "kept" and "--undo runtime" in rows["Docker daemon settings"][1], rows)

print(f"\n{'FAILED' if FAILED else 'all passed'} ({FAILED} failures)")
sys.exit(1 if FAILED else 0)
