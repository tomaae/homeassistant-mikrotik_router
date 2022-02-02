"""Helper functions for Mikrotik Router."""


# ---------------------------
#   format_attribute
# ---------------------------
def format_attribute(attr):
    res = attr.replace("-", " ")
    res = res.capitalize()
    res = res.replace(" ip ", " IP ")
    res = res.replace(" mac ", " MAC ")
    res = res.replace(" mtu", " MTU")
    res = res.replace("Sfp", "SFP")
    res = res.replace("Poe", "POE")
    res = res.replace(" tx", " TX")
    res = res.replace(" rx", " RX")
    return res
