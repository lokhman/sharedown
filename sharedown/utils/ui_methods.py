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

import utils
import os.path
import markdown as _markdown


def wrap(handler, chunk, wrapper):
    if wrapper[0] == "<" and wrapper[-1] == ">":
        return wrapper + chunk + "</%s>" % wrapper[1:-1].split(" ")[0]
    return wrapper + chunk + wrapper


def wrap_if(handler, chunk, wrapper, clause):
    return wrap(handler, chunk, wrapper) if clause else chunk


def file_icon(handler, filename):
    return "icons/48px/%s.png" % os.path.splitext(filename)[1].strip(".").lower()


def markdown(handler, chunk):
    return _markdown.markdown(chunk, output_format="html5")


def format_size(handler, size):
    for unit in ["bytes", "KB", "MB", "GB", "TB"]:
        if abs(size) < 1024.0:
            return "%3.2f %s" % (size, unit)
        size /= 1024.0
    return "%.2f %s" % (size, "PB")


def random_bytes(handler, length):
    return utils.random_bytes(length)


def absolute_url(handler, path):
    return "%s://%s%s" % (handler.request.protocol, handler.request.host, path)
