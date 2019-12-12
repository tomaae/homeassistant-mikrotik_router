"""Helper functions for Mikrotik Router."""

import logging
_LOGGER = logging.getLogger(__name__)


# ---------------------------
#   from_entry
# ---------------------------
def from_entry(entry, param, default="") -> dict:
    """Validate and return str value from Mikrotik API dict"""
    if param not in entry:
        return default

    return entry[param]


# ---------------------------
#   from_entry_bool
# ---------------------------
def from_entry_bool(entry, param, default=False, reverse=False) -> bool:
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
#   parse_api
# ---------------------------
def parse_api(data=None, source=None, key=None, key_search=None, vals=None, val_proc=None, ensure_vals=None, only=None, skip=None) -> dict:
    """Get data from API"""
    if not source:
        return data

    #print(type(source))
    keymap = generate_keymap(data, key_search)
    for entry in source:
        if only and not matches_only(entry, only):
            continue

        if skip and can_skip(entry, skip):
            continue

        uid = None
        if key or key_search:
            uid = get_uid(entry, key, key_search, keymap)
            if not uid:
                continue

            if uid not in data:
                data[uid] = {}

        _LOGGER.debug("Processing entry %s, entry %s", source, entry)
        if vals:
            data = fill_vals(data, entry, uid, vals)

        if ensure_vals:
            data = fill_ensure_vals(data, uid, ensure_vals)

        if val_proc:
            data = fill_vals_proc(data, uid, val_proc)

    return data


# ---------------------------
#   get_uid
# ---------------------------
def get_uid(entry, key, key_search, keymap) -> str:
    """Get UID for data list"""
    uid = None
    if not key_search:
        if key not in entry:
            return None

        if not entry[key]:
            return None

        uid = entry[key]
    else:
        if keymap and key_search in entry and entry[key_search] in keymap:
            uid = keymap[entry[key_search]]
        else:
            return None

    return uid


# ---------------------------
#   generate_keymap
# ---------------------------
def generate_keymap(data, key_search) -> dict:
    """Generate keymap"""
    if not key_search:
        return None

    keymap = {}
    for uid in data:
        if key_search not in data[uid]:
            continue

        keymap[data[uid][key_search]] = uid

    return keymap


# ---------------------------
#   matches_only
# ---------------------------
def matches_only(entry, only) -> bool:
    """Return True if all variables are matched"""
    ret = False
    for val in only:
        if val['key'] in entry and entry[val['key']] == val['value']:
            ret = True
        else:
            ret = False
            break

    return ret


# ---------------------------
#   can_skip
# ---------------------------
def can_skip(entry, skip) -> bool:
    """Return True if at least one variable matches"""
    ret = False
    for val in skip:
        if val['name'] in entry and entry[val['name']] == val['value']:
            ret = True
            break

    return ret


# ---------------------------
#   fill_vals
# ---------------------------
def fill_vals(data, entry, uid, vals) -> dict:
    """Fill all data"""
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
def fill_ensure_vals(data, uid, ensure_vals) -> dict:
    """Add required keys which are not available in data"""
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
def fill_vals_proc(data, uid, vals_proc) -> dict:
    """Add custom keys"""
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
                    tmp = _data[val['key']] if val['key'] in _data else 'unknown'
                    if not _value:
                        _value = tmp
                    else:
                        _value = "{}{}".format(_value, tmp)

                if 'text' in val:
                    tmp = val['text']
                    if not _value:
                        _value = tmp
                    else:
                        _value = "{}{}".format(_value, tmp)

        if _name and _value:
            if uid:
                data[uid][_name] = _value
            else:
                data[_name] = _value

    return data
