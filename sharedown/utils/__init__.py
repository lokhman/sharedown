#!/usr/bin/env python
#
# Copyright (c) 2016 Alexander Lokhman <alex.lokhman@gmail.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import absolute_import, division, print_function, with_statement

import re
import string
import bcrypt
import mimetypes
import unicodedata

from datetime import datetime
from random import SystemRandom
from collections import Mapping, Sequence, Set

_string_alphanum = string.ascii_letters + string.digits
_valid_filename_chars = frozenset("!-_.,;'()&@$=+ " + _string_alphanum)
_re_underscore = re.compile(r"((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))")


def hash_password(password, salt=None):
    if salt is None:
        salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf8"), salt.encode("utf8"))


def random_bytes(length=32):
    return "".join(SystemRandom().choice(_string_alphanum) for _ in range(length))


def underscore(word):
    return _re_underscore.sub(r"_\1", word).lower()


def normalize_filename(filename):
    if not isinstance(filename, unicode):
        filename = filename.decode("utf-8")
    filename = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore")
    return "".join(x for x in filename.strip() if x in _valid_filename_chars)[:255]


def normalize_content_type(content_type=None, filename=None):
    if content_type:
        return content_type.split(";")[0].strip().lower()
    return mimetypes.guess_type(filename)[0]


def normalize_chunk(chunk, sep=" "):
    """http://code.activestate.com/recipes/577982-recursively-walk-python-objects/

    :param chunk: mixed data chunk
    :param sep: datetime separator
    :return: normalized chunk
    """
    if isinstance(chunk, Mapping):
        for key, value in chunk.iteritems():
            chunk[key] = normalize_chunk(value)
    elif isinstance(chunk, (Sequence, Set)) and not isinstance(chunk, (str, unicode)):
        for index, value in enumerate(chunk):
            chunk[index] = normalize_chunk(value)
    elif isinstance(chunk, datetime):
        return chunk.isoformat(sep)
    return chunk
