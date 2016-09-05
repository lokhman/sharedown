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

from itertools import groupby
from collections import OrderedDict
from tornado.web import HTTPError
from tornado.gen import coroutine
from feedgen.feed import FeedGenerator

from . import BaseHandler, route


@route(r"/feed/([\w.-]{1,32})")
class IndexHandler(BaseHandler):
    def _get_feed(self, login):
        feed = self.db.fetch("SELECT * FROM feeds WHERE login = ? AND is_enabled = TRUE", login)
        if not feed:
            raise HTTPError(404)
        return feed

    def _display_feed(self, feed):
        files = self.db.fetch_all(
            "SELECT `key`, name, size, folder, COALESCE(caption, name) caption, created_at FROM files WHERE login = ? "
            "AND is_public = TRUE AND (expires_at IS NULL OR expires_at > NOW()) ORDER BY folder, caption",
            feed["login"])

        folders = OrderedDict()
        for key, group in groupby(files, lambda x: x["folder"]):
            folders[key] = list(group)
        return folders

    @coroutine
    def get(self, login):
        feed = yield self.thread_pool.submit(self._get_feed, login)
        if feed["password"]:
            self.render("feed/password.html")
            return

        folders = yield self.thread_pool.submit(self._display_feed, feed)
        self.render("feed/index.html", feed=feed, folders=folders)

    @coroutine
    def post(self, login):
        _password = self.get_body_argument("password")

        feed = yield self.thread_pool.submit(self._get_feed, login)
        if feed["password"] != _password:
            self.set_flash("The password you entered is incorrect.", BaseHandler.FLASH_ERROR)
            self.redirect(self.reverse_url("feed_index", login))
            return

        folders = yield self.thread_pool.submit(self._display_feed, feed)
        self.render("feed/index.html", feed=feed, folders=folders)


@route(r"/feed/([\w.-]{1,32})/(json|rss.xml|atom.xml)")
class ExportHandler(BaseHandler):
    @coroutine
    def get(self, login, format_):
        feed = yield self.thread_pool.submit(
            self.db.fetch, "SELECT * FROM feeds WHERE login = ? AND is_enabled = TRUE", login)
        if not feed:
            raise HTTPError(404)

        if feed["password"] and not self.http_basic_auth(feed["login"], feed["password"]):
            return  # request HTTP basic authentication to protect the feed

        files = yield self.thread_pool.submit(
            self.db.fetch_all,
            "SELECT `key`, login, name, size, folder, caption, expires_at, created_at FROM files "
            "WHERE login = ? AND is_public = TRUE AND (expires_at IS NULL OR expires_at > NOW()) "
            "ORDER BY name", login)

        if format_ == "json":
            self.write({"feed": files})
        elif format_.endswith(".xml"):
            fg = FeedGenerator()
            fg.title(feed["title"] or login)
            fg.description(login + ": Sharedown")
            fg.id(self.reverse_url("feed_index", login, absolute=True))
            fg.link(href=self.reverse_url("feed_export", login, format_, absolute=True), rel="self")

            for file_ in files:
                fe = fg.add_entry()
                fe.id(self.reverse_url("download_index", file_["key"], absolute=True))
                fe.link(href=self.reverse_url("download_index", file_["key"], absolute=True), rel="alternate")
                fe.title(file_["caption"] or file_["name"])
                fe.author(name=file_["login"])
                fe.published(utils.timezone_localize(file_["created_at"]))
                if file_["folder"]:
                    fe.category(term=file_["folder"])

            if format_ == "atom.xml":
                self.set_header("Content-Type", "application/xml; charset=UTF-8")
                self.write(fg.atom_str(True))
            elif format_ == "rss.xml":
                self.set_header("Content-Type", "application/xml; charset=UTF-8")
                self.write(fg.rss_str(True))
