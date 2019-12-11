"""Helper functions for Mikrotik Router."""

import logging
_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   from_entry
# ---------------------------
def from_entry(entry, param, default=""):
    """Validate and return a value from a Mikrotik API dict"""
    if param not in entry:
        return default

    return entry[param]


# ---------------------------
#   from_entry_bool
# ---------------------------
def from_entry_bool(entry, param, default=False, reverse=False):
    """Validate and return a bool value from a Mikrotik API dict"""
    if param not in entry:
        return default

    if not reverse:
        ret = entry[param]
    else:
        if entry[param]:
            ret = False
        else:
            ret = True

    return ret


# ---------------------------
#   from_list
# ---------------------------
async def from_list(data=None, source=None, key=None, key_search=None, vals=[], ensure_vals=[]):
    if not source:
        return data

    keymap = generate_keymap(data, key_search)

    for entry in source:
        uid = await get_uid(entry, key)
        if keymap and key_search in entry and entry[key_search] in keymap:
            uid = keymap[entry[key_search]]

        if not uid:
            continue

        if uid not in data:
            data[uid] = {}

        _LOGGER.debug("Processing entry {}, entry {}".format(source, entry))
        for val in vals:
            _name = val['name']
            _type = val['type'] if 'type' in val else 'str'
            _source = val['source'] if 'source' in val else _name

            if _type == 'str':
                _default = val['default'] if 'default' in val else ''
                if 'default_val' in val and val['default_val'] in val:
                    _default = val[val['default_val']]
                    
                data[uid][_name] = from_entry(entry, _source, default=_default)
            elif _type == 'bool':
                _default = val['default'] if 'default' in val else False
                _reverse = val['reverse'] if 'reverse' in val else False
                data[uid][_name] = from_entry_bool(entry, _source, default=_default, reverse=_reverse)

        for val in ensure_vals:
            if val['name'] not in data[uid]:
                _default = val['default'] if 'default' in val else ''
                data[uid][val['name']] = _default

    return data


# ---------------------------
#   get_uid
# ---------------------------
async def get_uid(entry, key):
    if key not in entry:
        return False

    if not entry[key]:
        return False

    return entry[key]


# ---------------------------
#   generate_keymap
# ---------------------------
async def generate_keymap(data, key_search):
    if not key_search:
        return None

    for uid in data:
        if key_search not in uid:
            continue

        keymap[data[uid]['name']] = data[uid]['default-name']

    return keymap
