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

import os
import utils
import functools

from abc import ABCMeta
from datetime import datetime, timedelta
from tornado.web import URLSpec, RequestHandler, RedirectHandler, HTTPError
from tornado.escape import json_encode, json_decode
from tornado.options import options

__dir__ = os.path.dirname(__file__)
__all__ = [py[:-3] for py in os.listdir(__dir__) if py.endswith(".py")]


def route(pattern, name=None):
    def wrapper(cls):
        route.routes.append(URLSpec(pattern, cls, name=name or "%s_%s" % (
            cls.__module__.split(".")[-1],
            utils.underscore(cls.__name__[:-7])
        )))
        return cls
    return wrapper

route.routes = [
    URLSpec(r"/", RedirectHandler, {"url": "/web/"}),
    URLSpec(r"/web", RedirectHandler, {"url": "/web/"})
]


def authenticated(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self.current_user:
            raise HTTPError(403)
        return method(self, *args, **kwargs)
    return wrapper


def check_level(*_level):
    def decorator(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            if not self.check_level(*_level):
                raise HTTPError(403)
            return method(self, *args, **kwargs)
        return wrapper
    return decorator


class BaseHandler(RequestHandler):
    __metaclass__ = ABCMeta

    FLASH_INFO = "info"
    FLASH_SUCCESS = "success"
    FLASH_WARNING = "warning"
    FLASH_ERROR = "danger"

    LEVEL_USER = "USER"
    LEVEL_ADMIN = "ADMIN"
    LEVEL_SUPER = "SUPER"

    STATS_OK = "OK"
    STATS_FAIL = "FAIL"

    @property
    def db(self):
        """pyDBAL connection instance alias

        :return: pyDBAL connection instance
        :rtype: pydbal.connection.Connection
        """
        return self.application.database

    @property
    def s3(self):
        return self.application.s3

    def get_header(self, name, default=RequestHandler._ARG_DEFAULT):
        try:
            return self.request.headers[name]
        except KeyError:
            if default is self._ARG_DEFAULT:
                raise MissingHeaderError(name)
            return default

    def get_header_arguments(self, name, default=RequestHandler._ARG_DEFAULT):
        return self._get_arguments(name, default, self.request.headers)

    def get_current_user(self):
        _key = self.request.headers.get("X-API-Key") or self.get_secure_cookie("session")
        if not _key:
            return None

        now = datetime.now()
        user = self.db.query(
            "SELECT * FROM users WHERE session = ? AND is_enabled = TRUE "
            "AND activity_at > ? - INTERVAL %d SECOND" % options.session["lifetime"], _key, now).fetch()
        if not user:
            return None

        activity_at = user["activity_at"]
        if not activity_at or (now - activity_at > timedelta(seconds=options.session["interval"])):
            self.db.execute("UPDATE users SET activity_at = ? WHERE login = ?", now, user["login"])
        return user

    def check_level(self, *args):
        if self.current_user and self.current_user["level"] in args:
            return True
        return False

    def set_flash(self, message, type_=FLASH_INFO):
        self.set_secure_cookie("flash", json_encode((type_, message)))

    def get_flash(self):
        try:
            return json_decode(self.get_secure_cookie("flash"))
        except TypeError:
            return None
        finally:
            self.clear_cookie("flash")

    def write(self, chunk=None):
        if chunk is None:
            chunk = {"status": "ok"}
        chunk = utils.normalize_chunk(chunk)
        super(BaseHandler, self).write(chunk)
    status_ok = write


class MissingHeaderError(HTTPError):
    def __init__(self, header_name):
        super(MissingHeaderError, self).__init__(
            400, 'Missing header %s' % header_name)
        self.header_name = header_name
