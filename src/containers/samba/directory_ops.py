from site_info import site_info

# the operations fabric-agent may ask for (directory_op): each is f(samdb, lp, site, **args) -> JSON-able result
OPS = {
    "site_info": site_info,
}
