# -*- coding: UTF-8 -*-

from posixpath import join as pjoin

from librouteros.exceptions import TrapError, MultiTrapError
from librouteros.protocol import (
    compose_word,
    parse_word,
)
from librouteros.query import Query


class Api:

    def __init__(self, protocol):
        self.protocol = protocol

    def __call__(self, cmd, **kwargs):
        """
        Call Api with given command.
        Yield each row.

        :param cmd: Command word. eg. /ip/address/print
        :param kwargs: Dictionary with optional arguments.
        """
        words = (compose_word(key, value) for key, value in kwargs.items())
        self.protocol.writeSentence(cmd, *words)
        yield from self.readResponse()

    def rawCmd(self, cmd, *words):
        """
        Call Api with given command and raw words.
        End user is responsible to properly format each api word argument.
        :param cmd: Command word. eg. /ip/address/print
        :param args: Iterable with optional plain api arguments.
        """
        self.protocol.writeSentence(cmd, *words)
        yield from self.readResponse()

    def readSentence(self):
        """
        Read one sentence and parse words.

        :returns: Reply word, dict with attribute words.
        """
        reply_word, words = self.protocol.readSentence()
        words = dict(parse_word(word) for word in words)
        return reply_word, words

    def readResponse(self):
        """
        Yield each sentence untill !done is received.

        :throws TrapError: If one !trap is received.
        :throws MultiTrapError: If > 1 !trap is received.
        """
        traps = []
        reply_word = None
        while reply_word != '!done':
            reply_word, words = self.readSentence()
            if reply_word == '!trap':
                traps.append(TrapError(**words))
            elif reply_word in ('!re', '!done') and words:
                yield words

        if len(traps) > 1:
            raise MultiTrapError(*traps)
        if len(traps) == 1:
            raise traps[0]

    def close(self):
        self.protocol.close()

    def path(self, *path):
        return Path(
            path='',
            api=self,
        ).join(*path)


class Path:
    """Represents absolute command path."""

    def __init__(self, path, api):
        self.path = path
        self.api = api

    def select(self, key, *other):
        keys = (key, ) + other
        return Query(path=self, keys=keys, api=self.api)

    def __str__(self):
        return self.path

    def __repr__(self):
        return "<{module}.{cls} {path!r}>".format(
            module=self.__class__.__module__,
            cls=self.__class__.__name__,
            path=self.path,
        )

    def __iter__(self):
        yield from self('print')

    def __call__(self, cmd, **kwargs):
        yield from self.api(
            self.join(cmd).path,
            **kwargs,
        )

    def join(self, *path):
        """Join current path with one or more path strings."""
        return Path(
            api=self.api,
            path=pjoin('/', self.path, *path).rstrip('/'),
        )

    def remove(self, *ids):
        ids = ','.join(ids)
        tuple(self(
            'remove',
            **{'.id': ids},
        ))

    def add(self, **kwargs):
        ret = self(
            'add',
            **kwargs,
        )
        return tuple(ret)[0]['ret']

    def update(self, **kwargs):
        tuple(self(
            'set',
            **kwargs,
        ))
