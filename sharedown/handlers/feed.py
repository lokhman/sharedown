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

from tornado.web import HTTPError

from . import BaseHandler, route


@route(r"/feed/([\w.-]{1,32})")
class IndexHandler(BaseHandler):
    def _get_feed(self, login):
        feed = self.db.query("SELECT * FROM feeds WHERE login = ? AND is_enabled = TRUE", login).fetch()
        if not feed:
            raise HTTPError(404)
        return feed

    def _display_feed(self, feed):
        files = self.db.query(
            "SELECT `key`, name, size, COALESCE(caption, name) caption, created_at FROM files "
            "WHERE login = ? AND (expires_at IS NULL OR expires_at > NOW()) ORDER BY name",
            feed["login"]).fetch_all()

        self.render("feed/index.html", feed=feed, files=files)

    def get(self, login):
        feed = self._get_feed(login)
        if feed["password"]:
            self.render("feed/password.html")
            return

        self._display_feed(feed)

    def post(self, login):
        _password = self.get_body_argument("password")

        feed = self._get_feed(login)
        if feed["password"] != _password:
            self.set_flash("The password you entered is incorrect.", BaseHandler.FLASH_ERROR)
            self.redirect(self.reverse_url("feed_index", login))
            return

        self._display_feed(feed)
