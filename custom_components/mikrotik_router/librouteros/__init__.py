# -*- coding: UTF-8 -*-

from socket import create_connection
from collections import ChainMap

from librouteros.exceptions import (
    ConnectionClosed,
    FatalError,
)
from librouteros.connections import SocketTransport
from librouteros.protocol import ApiProtocol
from librouteros.login import (
    plain,
    token,
)
from librouteros.api import Api

DEFAULTS = {
    'timeout': 10,
    'port': 8728,
    'saddr': '',
    'subclass': Api,
    'encoding': 'ASCII',
    'ssl_wrapper': lambda sock: sock,
    'login_method': plain,
}


def connect(host, username, password, **kwargs):
    """
    Connect and login to routeros device.
    Upon success return a Api class.

    :param host: Hostname to connecto to. May be ipv4,ipv6,FQDN.
    :param username: Username to login with.
    :param password: Password to login with. Only ASCII characters allowed.
    :param timeout: Socket timeout. Defaults to 10.
    :param port: Destination port to be used. Defaults to 8728.
    :param saddr: Source address to bind to.
    :param subclass: Subclass of Api class. Defaults to Api class from library.
    :param ssl_wrapper: Callable (e.g. ssl.SSLContext instance) to wrap socket with.
    :param login_method: Callable with login method.
    """
    arguments = ChainMap(kwargs, DEFAULTS)
    transport = create_transport(host, **arguments)
    protocol = ApiProtocol(transport=transport, encoding=arguments['encoding'])
    api = arguments['subclass'](protocol=protocol)

    try:
        arguments['login_method'](api=api, username=username, password=password)
        return api
    except (ConnectionClosed, FatalError):
        transport.close()
        raise


def create_transport(host, **kwargs):
    sock = create_connection((host, kwargs['port']), kwargs['timeout'], (kwargs['saddr'], 0))
    sock = kwargs['ssl_wrapper'](sock)
    return SocketTransport(sock=sock)
