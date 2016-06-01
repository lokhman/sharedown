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

from tornado.web import addslash, authenticated

from . import BaseHandler, route, check_level


@route(r"/web/")
class IndexHandler(BaseHandler):
    @authenticated
    @addslash
    def get(self):
        self.render("web/index.html")


@route(r"/web/login")
class LoginHandler(BaseHandler):
    def get(self):
        if self.current_user:
            self.redirect(self.reverse_url("web_index"))
            return
        self.render("web/login.html")

    def post(self):
        _login = self.get_body_argument("login")
        _password = self.get_body_argument("password")

        user = self.db.query("SELECT * FROM users WHERE login = ? AND is_enabled = TRUE", _login).fetch()
        if not user or utils.hash_password(_password, user["password"]) != user["password"]:
            self.set_flash("The details you entered are incorrect.", BaseHandler.FLASH_ERROR)
            self.redirect(self.reverse_url("web_login") + "?login=" + _login)
            return

        session = utils.random_bytes()
        self.db.execute(
            "UPDATE users SET session = ?, activity_at = NOW() WHERE login = ?",
            session, user["login"])

        self.set_secure_cookie("session", session)
        self.redirect(self.reverse_url("web_index"))


@route(r"/web/logout")
class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("session")
        self.redirect(self.reverse_url("web_login"))


@route(r"/web/feed")
class FeedHandler(BaseHandler):
    @authenticated
    def get(self):
        self.render("web/feed.html")


@route(r"/web/users")
class UsersHandler(BaseHandler):
    @check_level(
        BaseHandler.LEVEL_SUPER,
        BaseHandler.LEVEL_ADMIN)
    def get(self):
        self.render("web/users.html")
