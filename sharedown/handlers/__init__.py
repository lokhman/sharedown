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
import re
import utils
import base64
import functools

from abc import ABCMeta
from tornado.web import URLSpec, RequestHandler, RedirectHandler, HTTPError
from tornado.escape import native_str, json_encode, json_decode
from tornado.options import options
from tornado.gen import coroutine

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

    _RE_JSON_CALLBACK = re.compile(r"^[a-zA-Z_$][0-9a-zA-Z_$]*(?:\[(?:"".+""|\'.+\'|\d+)\])*?$")

    @property
    def thread_pool(self):
        return self.application.thread_pool

    @property
    def db(self):
        """pyDBAL connection instance alias

        :return: pyDBAL thread-safe connection instance
        :rtype: pydbal.threading.SafeConnection
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

    @property
    def cookie_secret(self):
        self.require_setting("cookie_secret", "secure cookies")
        return self.application.settings["cookie_secret"]

    @property
    def remote_ip(self):
        return self.request.headers.get("X-Real-IP") or self.request.remote_ip

    @property
    def scheme(self):
        return self.request.headers.get("X-Scheme") or self.request.protocol

    @property
    def hostname(self):
        return self.scheme + "://" + self.request.host

    @property
    def content_type(self):
        return self.request.headers.get("Content-Type")

    @coroutine
    def prepare(self):
        # if request contains JSON encoded body
        if self.get_header("Content-Type", "").startswith("application/json"):
            try:
                json_data = json_decode(self.request.body)
                for key, value in json_data.items():
                    if isinstance(value, bool):
                        value = int(value)
                    if not isinstance(value, list):
                        value = (value, )
                    json_data[key] = [native_str(str(x)) for x in value]
                self.request.body_arguments.update(json_data)
            except (ValueError, AttributeError):
                pass  # no need to log it

        # get session key from "X-API-Key" header or from "session" secure cookie
        session = self.get_header("X-API-Key", None) or self.get_secure_cookie("session")
        if not session:
            return

        user = yield self.thread_pool.submit(
            self.db.fetch, "SELECT u.*, s.session FROM users u INNER JOIN sess s ON s.login = u.login AND s.session = ?"
            " WHERE u.is_enabled = TRUE AND (s.expires_at IS NULL OR s.expires_at > NOW())", session)
        if not user:
            return

        yield self.thread_pool.submit(
            self.db.execute, "UPDATE sess SET expires_at = NOW() + INTERVAL %d SECOND WHERE login = ? AND session = ? "
            "AND expires_at IS NOT NULL" % options.session["lifetime"], user["login"], user["session"])

        self.current_user = user

    def create_session(self, login):
        session = utils.random_bytes()
        self.db.execute(
            "INSERT INTO sess (login, session, expires_at) VALUES(?, ?, NOW() + INTERVAL %d SECOND)" %
            options.session["lifetime"], login, session)
        return session

    def clear_session(self, login, session):
        self.db.execute("DELETE FROM sess WHERE login = ? AND session = ?", login, session)

    def check_level(self, *args):
        if self.current_user and self.current_user["level"] in args:
            return True
        return False

    def set_flash(self, message, type_=FLASH_INFO):
        flash = json_encode((type_, message))
        self.set_secure_cookie("flash", flash)
        setattr(self, "_flash", flash)

    def get_flash(self):
        try:
            return json_decode(getattr(self, "_flash", self.get_secure_cookie("flash")))
        except TypeError:
            return None
        finally:
            self.clear_cookie("flash")

    def write(self, chunk=None):
        if chunk is None:
            chunk = {"status": "ok"}
        chunk = utils.normalize_chunk(chunk)
        if isinstance(chunk, dict):
            callback = self.get_argument("callback", None)
            if callback and all(map(lambda x: BaseHandler._RE_JSON_CALLBACK.match(x), callback.split("."))):
                self.set_header("Content-Type", "text/javascript; charset=UTF-8")
                chunk = "/**/%s(%s);" % (callback, json_encode(chunk))
        super(BaseHandler, self).write(chunk)
    status_ok = write

    def http_basic_auth(self, user, password, realm="Restricted"):
        auth_header = self.request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Basic "):
            auth_decoded = base64.decodestring(auth_header[6:])
            _user, _password = auth_decoded.split(":", 2)
            if _user == user and _password == password:
                return True
        self.set_header("WWW-Authenticate", "Basic realm=" + realm)
        self.set_status(401)
        self.write_error(401)
        return False

    def reverse_url(self, name, *args, **kwargs):
        url = super(BaseHandler, self).reverse_url(name, *args)
        if kwargs.get("absolute", False):
            url = self.hostname + url
        return url


class MissingHeaderError(HTTPError):
    def __init__(self, header_name):
        super(MissingHeaderError, self).__init__(
            400, "Missing header %s" % header_name)
        self.header_name = header_name
