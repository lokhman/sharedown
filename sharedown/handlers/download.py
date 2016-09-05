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

import os.path
import utils

from tornado.web import HTTPError
from tornado.gen import coroutine

from . import BaseHandler, route


@route(r"/dl/([a-zA-Z0-9]{8})")
class IndexHandler(BaseHandler):
    def _get_file(self, key):
        file_ = self.db.fetch(
            "SELECT * FROM files WHERE `key` = ? AND (expires_at IS NULL OR expires_at > NOW())", key)
        if not file_:
            raise HTTPError(404)
        return file_

    def _set_stats(self, file_, status):
        self.db.execute(
            "INSERT INTO stats (`key`, name, status, ip) VALUES(?)",
            (file_["key"], file_["name"], status, self.remote_ip))

    def _get_url(self, file_):
        try:
            url = self.s3.download_url("%s/%s" % (file_["key"], file_["name"]))
        except:
            raise HTTPError(503)
        self._set_stats(file_, BaseHandler.STATS_OK)
        return url

    @coroutine
    def _display_url(self, file_, url):
        agent = self.get_header("User-Agent", "").lower()
        if any(x in agent for x in ("iphone", "ipod", "ipad")):
            if os.path.splitext(file_["name"])[1] == ".ipa":
                family = yield self.thread_pool.submit(
                    self.db.fetch_column, "SELECT LOWER(value) FROM meta WHERE `key` = ? AND attribute = ?",
                    file_["key"], "device-family")
                if family == "iphone" and "ipad" in agent:
                    self.set_flash(
                        "This application is designed for iPhone. Please try it on an iPhone for a better experience.",
                        BaseHandler.FLASH_WARNING)
                elif family == "ipad" and "ipad" not in agent:
                    self.set_flash(
                        "This application is not supported on your device. Please try again with an iPad.",
                        BaseHandler.FLASH_ERROR)
                token = utils.tokenize_value(self.cookie_secret, url)
                url = "itms-services://?action=download-manifest&url=%s" % (
                    self.reverse_url("download_manifest", file_["key"], token, absolute=True)
                )
        self.render("download/index.html", file=file_, url=url)

    @coroutine
    def get(self, key):
        file_ = yield self.thread_pool.submit(self._get_file, key)
        if file_["password"] is not None:
            self.render("download/password.html")
            return

        url = yield self.thread_pool.submit(self._get_url, file_)
        yield self._display_url(file_, url)

    @coroutine
    def post(self, key):
        _password = self.get_body_argument("password")

        file_ = yield self.thread_pool.submit(self._get_file, key)
        if file_["password"] != _password:
            yield self.thread_pool.submit(self._set_stats, file_, BaseHandler.STATS_FAIL)
            self.set_flash("The password you entered is incorrect.", BaseHandler.FLASH_ERROR)
            self.redirect(self.reverse_url("download_index", key))
            return

        url = yield self.thread_pool.submit(self._get_url, file_)
        self._display_url(file_, url)


@route(r"/dl/([a-zA-Z0-9]{8})/manifest.plist:(.+)")
class ManifestHandler(BaseHandler):
    @coroutine
    def get(self, key, token):
        url = utils.untokenize_value(self.cookie_secret, token)
        if not url:
            raise HTTPError(403)

        _metadata = yield self.thread_pool.submit(
            self.db.fetch_all, "SELECT attribute, value FROM meta WHERE `key` = ?", key)
        metadata = {meta["attribute"]: meta["value"] for meta in _metadata}

        self.set_header("Content-Type", "application/xml")
        self.render("download/manifest.plist", url=url, metadata=metadata)
