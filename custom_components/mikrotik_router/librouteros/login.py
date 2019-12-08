from binascii import unhexlify, hexlify
from hashlib import md5


def encode_password(token, password):
    #pylint: disable=redefined-outer-name
    token = token.encode('ascii', 'strict')
    token = unhexlify(token)
    password = password.encode('ascii', 'strict')
    hasher = md5()
    hasher.update(b'\x00' + password + token)
    password = hexlify(hasher.digest())
    return '00' + password.decode('ascii', 'strict')


def token(api, username, password):
    """Login using pre routeros 6.43 authorization method."""
    sentence = api('/login')
    tok = tuple(sentence)[0]['ret']
    encoded = encode_password(tok, password)
    tuple(api('/login', **{'name': username, 'response': encoded}))


def plain(api, username, password):
    """Login using post routeros 6.43 authorization method."""
    tuple(api('/login', **{'name': username, 'password': password}))
