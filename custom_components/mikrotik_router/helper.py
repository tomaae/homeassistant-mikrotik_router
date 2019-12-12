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
async def from_list(data=None, source=None, key=None, key_search=None, vals=None, val_proc=None, ensure_vals=None, only=None, skip=None):
    if not source:
        return data

    keymap = generate_keymap(data, key_search)
    for entry in source:
        if only and not await matches_only(entry, only):
            continue

        if skip and await can_skip(entry, skip):
            continue

        uid = None
        if key or key_search:
            uid = await get_uid(entry, key, key_search, keymap)
            if not uid:
                continue

            if uid not in data:
                data[uid] = {}

        _LOGGER.debug("Processing entry %s, entry %s", source, entry)
        if vals:
            data = await fill_vals(data, entry, uid, vals)

        if ensure_vals:
            data = await fill_ensure_vals(data, uid, ensure_vals)

        if val_proc:
            data = await fill_vals_proc(data, uid, val_proc)

    return data


# ---------------------------
#   get_uid
# ---------------------------
async def get_uid(entry, key, key_search, keymap):
    if not key_search:
        if key not in entry:
            return False

        if not entry[key]:
            return False

    else:
        if not keymap or key_search not in entry or entry[key_search] not in keymap:
            return False

        key = keymap[entry[key_search]]

    return entry[key]


# ---------------------------
#   generate_keymap
# ---------------------------
async def generate_keymap(data, key_search):
    if not key_search:
        return None

    keymap = []
    for uid in data:
        if key_search not in uid:
            continue

        keymap[data[uid]['name']] = data[uid]['default-name']

    return keymap


# ---------------------------
#   matches_only
# ---------------------------
async def matches_only(entry, only):
    ret = False
    for val in only:
        if val['name'] in entry and entry[val['name']] == val['value']:
            ret = True
        else:
            ret = False
            break

    return ret


# ---------------------------
#   can_skip
# ---------------------------
async def can_skip(entry, skip):
    ret = False
    for val in skip:
        if val['name'] in entry and entry[val['name']] == val['value']:
            ret = True
            break

    return ret


# ---------------------------
#   fill_vals
# ---------------------------
async def fill_vals(data, entry, uid, vals):
    for val in vals:
        _name = val['name']
        _type = val['type'] if 'type' in val else 'str'
        _source = val['source'] if 'source' in val else _name

        if _type == 'str':
            _default = val['default'] if 'default' in val else ''
            if 'default_val' in val and val['default_val'] in val:
                _default = val[val['default_val']]

            if uid:
                data[uid][_name] = from_entry(entry, _source, default=_default)
            else:
                data[_name] = from_entry(entry, _source, default=_default)

        elif _type == 'bool':
            _default = val['default'] if 'default' in val else False
            _reverse = val['reverse'] if 'reverse' in val else False

            if uid:
                data[uid][_name] = from_entry_bool(entry, _source, default=_default, reverse=_reverse)
            else:
                data[_name] = from_entry_bool(entry, _source, default=_default, reverse=_reverse)

    return data


# ---------------------------
#   fill_ensure_vals
# ---------------------------
async def fill_ensure_vals(data, uid, ensure_vals):
    for val in ensure_vals:
        if uid:
            if val['name'] not in data[uid]:
                _default = val['default'] if 'default' in val else ''
                data[uid][val['name']] = _default
        else:
            if val['name'] not in data:
                _default = val['default'] if 'default' in val else ''
                data[val['name']] = _default

    return data


# ---------------------------
#   fill_vals_proc
# ---------------------------
async def fill_vals_proc(data, uid, vals_proc):
    _data = data[uid] if uid else data
    for val_sub in vals_proc:
        _name = None
        _action = None
        _value = None
        for val in val_sub:
            if 'name' in val:
                _name = val['name']
                continue

            if 'action' in val:
                _action = val['action']
                continue

            if not _name and not _action:
                break

            if _action == 'combine':
                if 'key' in val:
                    _value += _data[val['key']] if val['key'] in _data else 'unknown'

                if 'text' in val:
                    _value += val['text']

        if _name and _value:
            if uid:
                data[uid][_name] = _value
            else:
                data[_name] = _value

    return data
