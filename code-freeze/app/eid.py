from machine import unique_id    # type: ignore
import re

from . config import config


#######################################################################
# Entity id's

_ESC = re.compile(r"([.*+?^=!:${}()|\[\]\/\\])")

def wildcard_match(s, rule):
    if not '.' in rule: rule = "*." + rule
    rule = "^" + ".*".join(map(lambda x: _ESC.sub(r'\\\1', x), rule.split("*"))) + "$"
    return re.match(rule, s) != None

def device_id(entity_id):
    """Get device_id, possibly from alias"""
    d = entity_id.split('.')[1]
    devices = config.get('devices')
    # if it's in devices, it's a device_id!
    if d in devices: return d
    # check aliases
    for k,v in devices.items():
        if v.get('alias') == d:
            # yup, return the corresponding id
            return k
    # not in devices - there is no alias, hence d is the device_id
    return d

def attr(entity_id, attribute, default=None):
    for pattern, fields in config.get('entities').items():
        if wildcard_match(entity_id, pattern):
            if fields.get(attribute): 
                return fields.get(attribute)
    return default


#######################################################################
# Nodes

UID = ":".join("{:02x}".format(x) for x in unique_id())
NODE_ID = config.get(f'secrets/nodes/{UID}/alias', UID.replace(':', '_'))
IS_GATEWAY = config.get('app/gateway') == NODE_ID
