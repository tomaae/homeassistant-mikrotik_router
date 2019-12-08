# -*- coding: UTF-8 -*-

from struct import pack, unpack
from logging import getLogger, NullHandler

from librouteros.exceptions import (
    ProtocolError,
    FatalError,
)

LOGGER = getLogger('librouteros')
LOGGER.addHandler(NullHandler())


def parse_word(word):
    """
    Split given attribute word to key, value pair.

    Values are casted to python equivalents.

    :param word: API word.
    :returns: Key, value pair.
    """
    mapping = {'yes': True, 'true': True, 'no': False, 'false': False}
    _, key, value = word.split('=', 2)
    try:
        value = int(value)
    except ValueError:
        value = mapping.get(value, value)
    return (key, value)


def cast_to_api(value):
    """Cast python equivalent to API."""
    mapping = {True: 'yes', False: 'no'}
    # this is necesary because 1 == True, 0 == False
    if type(value) == int:
        value = str(value)
    else:
        value = mapping.get(value, str(value))
    return value


def compose_word(key, value):
    """
    Create a attribute word from key, value pair.
    Values are casted to api equivalents.
    """
    return '={}={}'.format(key, cast_to_api(value))


class Encoder:

    def encodeSentence(self, *words):
        """
        Encode given sentence in API format.

        :param words: Words to endoce.
        :returns: Encoded sentence.
        """
        encoded = map(self.encodeWord, words)
        encoded = b''.join(encoded)
        # append EOS (end of sentence) byte
        encoded += b'\x00'
        return encoded

    def encodeWord(self, word):
        """
        Encode word in API format.

        :param word: Word to encode.
        :returns: Encoded word.
        """
        #pylint: disable=no-member
        encoded_word = word.encode(encoding=self.encoding, errors='strict')
        return Encoder.encodeLength(len(word)) + encoded_word

    @staticmethod
    def encodeLength(length):
        """
        Encode given length in mikrotik format.

        :param length: Integer < 268435456.
        :returns: Encoded length.
        """
        if length < 128:
            ored_length = length
            offset = -1
        elif length < 16384:
            ored_length = length | 0x8000
            offset = -2
        elif length < 2097152:
            ored_length = length | 0xC00000
            offset = -3
        elif length < 268435456:
            ored_length = length | 0xE0000000
            offset = -4
        else:
            raise ProtocolError('Unable to encode length of {}'.format(length))

        return pack('!I', ored_length)[offset:]


class Decoder:

    @staticmethod
    def determineLength(length):
        """
        Given first read byte, determine how many more bytes
        needs to be known in order to get fully encoded length.

        :param length: First read byte.
        :return: How many bytes to read.
        """
        integer = ord(length)

        #pylint: disable=no-else-return
        if integer < 128:
            return 0
        elif integer < 192:
            return 1
        elif integer < 224:
            return 2
        elif integer < 240:
            return 3

        raise ProtocolError('Unknown controll byte {}'.format(length))

    @staticmethod
    def decodeLength(length):
        """
        Decode length based on given bytes.

        :param length: Bytes string to decode.
        :return: Decoded length.
        """
        bytes_length = len(length)

        if bytes_length < 2:
            offset = b'\x00\x00\x00'
            xor = 0
        elif bytes_length < 3:
            offset = b'\x00\x00'
            xor = 0x8000
        elif bytes_length < 4:
            offset = b'\x00'
            xor = 0xC00000
        elif bytes_length < 5:
            offset = b''
            xor = 0xE0000000
        else:
            raise ProtocolError('Unable to decode length of {}'.format(length))

        decoded = unpack('!I', (offset + length))[0]
        decoded ^= xor
        return decoded


class ApiProtocol(Encoder, Decoder):

    def __init__(self, transport, encoding):
        self.transport = transport
        self.encoding = encoding

    @staticmethod
    def log(direction_string, *sentence):
        for word in sentence:
            LOGGER.debug('{0} {1!r}'.format(direction_string, word))

        LOGGER.debug('{0} EOS'.format(direction_string))

    def writeSentence(self, cmd, *words):
        """
        Write encoded sentence.

        :param cmd: Command word.
        :param words: Aditional words.
        """
        encoded = self.encodeSentence(cmd, *words)
        self.log('<---', cmd, *words)
        self.transport.write(encoded)

    def readSentence(self):
        """
        Read every word untill empty word (NULL byte) is received.

        :return: Reply word, tuple with read words.
        """
        sentence = tuple(word for word in iter(self.readWord, ''))
        self.log('--->', *sentence)
        reply_word, words = sentence[0], sentence[1:]
        if reply_word == '!fatal':
            self.transport.close()
            raise FatalError(words[0])
        return reply_word, words

    def readWord(self):
        byte = self.transport.read(1)
        # Early return check for null byte
        if byte == b'\x00':
            return ''
        to_read = self.determineLength(byte)
        byte += self.transport.read(to_read)
        length = self.decodeLength(byte)
        word = self.transport.read(length)
        return word.decode(encoding=self.encoding, errors='strict')

    def close(self):
        self.transport.close()
