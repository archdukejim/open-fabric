from add_group_member import add_group_member
from create_person import create_person
from get_person import get_person
from link_device_cert import link_device_cert
from list_people import list_people
from read_devices import read_devices
from read_networks import read_networks
from remove_device import remove_device
from remove_role import remove_role
from reset_password import reset_password
from save_device import save_device
from save_role import save_role
from site_info import site_info

# the operations fabric-agent may ask for (directory_op): each is f(samdb, lp, site, **args) -> JSON-able result
OPS = {
    "add_group_member": add_group_member,
    "create_person": create_person,
    "get_person": get_person,
    "link_device_cert": link_device_cert,
    "list_people": list_people,
    "read_devices": read_devices,
    "read_networks": read_networks,
    "remove_device": remove_device,
    "remove_role": remove_role,
    "reset_password": reset_password,
    "save_device": save_device,
    "save_role": save_role,
    "site_info": site_info,
}
