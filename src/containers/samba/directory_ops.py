from add_group_member import add_group_member
from create_person import create_person
from get_person import get_person
from list_people import list_people
from reset_password import reset_password
from site_info import site_info

# the operations fabric-agent may ask for (directory_op): each is f(samdb, lp, site, **args) -> JSON-able result
OPS = {
    "add_group_member": add_group_member,
    "create_person": create_person,
    "get_person": get_person,
    "list_people": list_people,
    "reset_password": reset_password,
    "site_info": site_info,
}
