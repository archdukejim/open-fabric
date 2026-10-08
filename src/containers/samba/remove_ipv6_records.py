import ldb
from samba.dcerpc import dnsp
from samba.ndr import ndr_unpack

AAAA = 28                                # dnsp.DNS_TYPE_AAAA


def remove_ipv6_records(samdb):
    """Purpose: keep the domain's DNS on IPv4 only (D120): remove every AAAA record from the AD zones (the domain's and
             the forest's DNS partitions). The DC listens on IPv4 only (D98); provisioning on a host with IPv6 addresses
             published them anyway, and Windows prefers them, so its joins and logons tried an address nothing answered.
    Inputs:  samdb — SamDB (system).
    Returns: list of str, the names whose AAAA records were removed.
    Fails:   ldb.LdbError for a change AD refuses.
    Feeds:   converge."""
    done, base = [], str(samdb.domain_dn())
    for partition in (f"DC=DomainDnsZones,{base}", f"DC=ForestDnsZones,{base}"):
        try:
            nodes = samdb.search(base=partition, scope=ldb.SCOPE_SUBTREE, expression="(objectClass=dnsNode)",
                                 attrs=["dnsRecord", "name"])
        except ldb.LdbError:                 # a partition this DC does not hold
            continue
        for node in nodes:
            values = list(node.get("dnsRecord", []))
            keep = [v for v in values if ndr_unpack(dnsp.DnssrvRpcRecord, bytes(v)).wType != AAAA]
            if len(keep) == len(values):
                continue
            msg = ldb.Message(node.dn)
            if keep:
                msg["dnsRecord"] = ldb.MessageElement([bytes(v) for v in keep], ldb.FLAG_MOD_REPLACE, "dnsRecord")
            else:                            # nothing left: the node goes (a name with no records)
                samdb.delete(node.dn)
                done.append(f"{node.dn}: IPv6 record removed (D120)")
                continue
            samdb.modify(msg)
            done.append(f"{node.dn}: IPv6 record removed (D120)")
    return done
