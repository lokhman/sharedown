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

from tornado.gen import coroutine
from tornado.web import HTTPError

from . import BaseHandler, route


@route(r"/dl/([a-zA-Z0-9]{8})")
class IndexHandler(BaseHandler):
    def _get_file(self, key):
        file_ = self.db.query(
            "SELECT * FROM files WHERE `key` = ? AND (expires_at IS NULL OR expires_at > NOW())", key).fetch()
        if not file_:
            raise HTTPError(404)
        return file_

    def _set_stats(self, file_, status):
        self.db.execute(
            "INSERT INTO stats (`key`, name, status, ip) VALUES(?)",
            (file_["key"], file_["name"], status, self.request.remote_ip))

    def _display_dl(self, file_):
        try:
            url = self.s3.download_url("%s/%s" % (file_["key"], file_["name"]))
        except:
            raise HTTPError(503)
        self._set_stats(file_, BaseHandler.STATS_OK)
        self.render("download/index.html", file=file_, url=url)

    @coroutine
    def get(self, key):
        file_ = self._get_file(key)
        if file_["password"] is not None:
            self.render("download/password.html")
            return

        yield self.application.thread_pool.submit(self._display_dl, file_)

    @coroutine
    def post(self, key):
        file_ = self._get_file(key)
        if self.get_body_argument("password") != file_["password"]:
            self._set_stats(file_, BaseHandler.STATS_FAIL)
            self.set_flash("The password you entered is incorrect.", BaseHandler.FLASH_ERROR)
            self.redirect(self.reverse_url("download_index", key))
            return

        yield self.application.thread_pool.submit(self._display_dl, file_)
