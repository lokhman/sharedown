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

from tornado.gen import coroutine
from tornado.web import HTTPError, removeslash
from pydbal.exception import DBALDriverError

from . import BaseHandler, route, authenticated, check_level


@route(r"/api/?")
class IndexHandler(BaseHandler):
    @removeslash
    def get(self):
        self.write({"version": self.application.version})


@route(r"/api/auth")
class AuthHandler(BaseHandler):
    @authenticated
    def get(self):
        self.status_ok()


@route(r"/api/auth/login")
class AuthLoginHandler(BaseHandler):
    def post(self):
        _login = self.get_body_argument("login")
        _password = self.get_body_argument("password")

        user = self.db.query("SELECT * FROM users WHERE login = ? AND is_enabled = TRUE", _login).fetch()
        if not user or utils.hash_password(_password, user["password"]) != user["password"]:
            raise HTTPError(401)

        session = utils.random_bytes()
        self.db.execute(
            "UPDATE users SET session = ?, activity_at = NOW() WHERE login = ?",
            session, user["login"])

        self.write({"session": session})


@route(r"/api/auth/logout")
class AuthLogoutHandler(BaseHandler):
    @authenticated
    def get(self):
        self.db.execute(
            "UPDATE users SET session = NULL WHERE login = ?",
            self.current_user["login"])
        self.status_ok()


@route(r"/api/upload")
class UploadHandler(BaseHandler):
    @coroutine
    def post(self):
        _file = self.get_header("X-File")
        _name = self.get_header("X-Name")
        _caption = self.request.headers.get("X-Caption") or None
        _password = self.request.headers.get("X-Password") or None
        _permanent = self.request.headers.get("X-Permanent") or False
        _content_type = self.request.headers.get("Content-Type") or None

        size = os.stat(_file).st_size
        if not size:
            raise HTTPError(411)

        name = utils.normalize_filename(_name)
        expires_at = None if _permanent else self.s3.get_expiry_date()
        content_type = utils.normalize_content_type(_content_type, name)

        self.db.begin_transaction()
        while True:
            key = utils.random_bytes(8)
            try:
                self.db.execute(
                    "INSERT INTO files (`key`, login, name, size, caption, password, expires_at) VALUES(?)",
                    (key, self.current_user["login"], name, size, _caption, _password, expires_at))
                break
            except DBALDriverError:
                # Error: 1062 (ER_DUP_ENTRY)
                if self.db.error_code() != 1062:
                    raise

        try:
            yield self.application.thread_pool.submit(
                self.s3.upload_file, _file, "%s/%s" % (key, name), content_type, {
                    "expires": expires_at.isoformat() if expires_at else "never",
                    "auth": self.current_user["login"]
                })
        except:
            self.db.rollback()
            raise HTTPError(503)

        self.db.commit()
        self.write({"key": key})


@route(r"/api/files")
class FilesHandler(BaseHandler):
    @authenticated
    @coroutine
    def get(self):
        sqb = (
            self.db.sql_builder()
                .select("f.*", "COUNT(s.key) downloads").from_("files", "f")
                .left_join("f", "stats", "s", "s.key = f.key AND s.status = ?")
                .set_parameter(0, BaseHandler.STATS_OK).group_by("f.key")
                .order_by("f.name").add_order_by("f.created_at", "DESC")
        )

        if self.check_level(BaseHandler.LEVEL_SUPER):
            login = self.get_argument("login", None)
            sqb.add_select("f.login")
        else:
            login = self.current_user["login"]

        if login:
            sqb.and_where("f.login = ?").set_parameter(1, login)

        stmt = yield self.application.thread_pool.submit(sqb.execute)
        self.write({"files": stmt.fetch_all()})


@route(r"/api/files/([a-zA-Z0-9]{8})")
class FilesEntryHandler(BaseHandler):
    def _get_file(self, key):
        sqb = (
            self.db.sql_builder()
                .select("f.*", "COUNT(s.key) downloads").from_("files", "f")
                .left_join("f", "stats", "s", "s.key = f.key AND s.status = ?")
                .set_parameter(0, BaseHandler.STATS_OK).group_by("f.key")
                .where("f.key = ?").set_parameter(1, key)
        )
        if not self.check_level(BaseHandler.LEVEL_SUPER):
            sqb.and_where("f.login = ?").set_parameter(2, self.current_user["login"])
        file_ = sqb.execute().fetch()
        if not file_:
            raise HTTPError(404)
        return file_

    @authenticated
    def get(self, key):
        self.write(self._get_file(key))

    @authenticated
    def patch(self, key):
        _password = self.get_body_argument("password", None)
        _caption = self.get_body_argument("caption", None)

        file_, values = self._get_file(key), {}
        if _password is not None:
            values["password"] = _password or None
        if _caption is not None:
            values["caption"] = _caption or None

        if not values:
            raise HTTPError(400)
        self.db.update("files", values, {"`key`": key})
        self.status_ok()

    @authenticated
    @coroutine
    def delete(self, key):
        file_ = self._get_file(key)
        try:
            yield self.application.thread_pool.submit(self.s3.delete, "%s/%s" % (key, file_["name"]))
        except:
            raise HTTPError(503)

        self.db.execute("DELETE FROM files WHERE `key` = ?", key)
        self.status_ok()


@route(r"/api/feed")
class FeedHandler(BaseHandler):
    @authenticated
    def get(self):
        self.write(self.db.query(
            "SELECT * FROM feeds WHERE login = ?",
            self.current_user["login"]).fetch() or {})

    @authenticated
    def post(self):
        _password = self.get_body_argument("password") or None
        _title = self.get_body_argument("title") or None
        _readme = self.get_body_argument("readme") or None
        _is_enabled = self.get_body_argument("is_enabled") or False

        self.db.execute(
            "INSERT INTO feeds (login, password, title, readme, is_enabled) VALUES(?) "
            "ON DUPLICATE KEY UPDATE login=VALUES(login), password=VALUES(password), title=VALUES(title), "
            "readme=VALUES(readme), is_enabled=VALUES(is_enabled)",
            (self.current_user["login"], _password, _title, _readme, _is_enabled))
        self.status_ok()


@route(r"/api/users")
class UsersHandler(BaseHandler):
    @check_level(
        BaseHandler.LEVEL_SUPER,
        BaseHandler.LEVEL_ADMIN)
    def get(self):
        sqb = (
            self.db.sql_builder()
                .select("u.login", "u.level", "u.is_enabled", "u.activity_at", "u.created_at", "COUNT(f.key) files")
                .add_select("EXISTS(SELECT * FROM feeds WHERE login = u.login AND is_enabled = TRUE) has_feed")
                .from_("users", "u").left_join("u", "files", "f", "u.login = f.login")
                .group_by("u.login").order_by("u.login")
        )
        if not self.check_level(BaseHandler.LEVEL_SUPER):
            sqb.where("u.level <> ?").set_parameter(0, BaseHandler.LEVEL_SUPER)
        self.write({"users": sqb.execute().fetch_all()})

    @coroutine
    @check_level(
        BaseHandler.LEVEL_SUPER,
        BaseHandler.LEVEL_ADMIN)
    def post(self):
        _login = self.get_body_argument("login")
        _level = self.get_body_argument("level")
        _password = self.get_body_argument("password")
        _is_enabled = self.get_body_argument("is_enabled")

        if not re.match(r"^[\w.-]{1,32}$", _login):
            raise HTTPError(400)

        try:
            yield self.application.thread_pool.submit(
                self.db.execute, "INSERT INTO users (login, password, level, is_enabled) VALUES(?)",
                (_login, utils.hash_password(_password), _level, _is_enabled))
            self.status_ok()
        except DBALDriverError:
            # Error: 1062 (ER_DUP_ENTRY)
            if self.db.error_code() == 1062:
                raise HTTPError(409)
            raise


@route(r"/api/users/(.{1,32})")
class UsersEntryHandler(BaseHandler):
    def _get_user(self, login):
        sqb = (
            self.db.sql_builder()
                .select("u.login", "u.level", "u.is_enabled", "u.activity_at", "u.created_at")
                .from_("users", "u").where("u.login = ?").set_parameter(0, login).order_by("u.login")
        )
        if not self.check_level(BaseHandler.LEVEL_SUPER):
            sqb.where("u.level <> ?").set_parameter(1, BaseHandler.LEVEL_SUPER)
        user = sqb.execute().fetch()
        if not user:
            raise HTTPError(404)
        return user

    @check_level(
        BaseHandler.LEVEL_SUPER,
        BaseHandler.LEVEL_ADMIN)
    def get(self, login):
        self.write(self._get_user(login))

    @coroutine
    @check_level(
        BaseHandler.LEVEL_SUPER,
        BaseHandler.LEVEL_ADMIN)
    def patch(self, login):
        _login = self.get_body_argument("login")
        _level = self.get_body_argument("level")
        _password = self.get_body_argument("password")
        _is_enabled = self.get_body_argument("is_enabled")

        if not re.match(r"^[\w.-]{1,32}$", _login):
            raise HTTPError(400)
        if _level not in (BaseHandler.LEVEL_SUPER, BaseHandler.LEVEL_ADMIN, BaseHandler.LEVEL_USER):
            raise HTTPError(400)
        if not self.check_level(BaseHandler.LEVEL_SUPER) and _level == BaseHandler.LEVEL_SUPER:
            raise HTTPError(400)

        self._get_user(login)

        values = {"level": _level, "is_enabled": _is_enabled}
        if _login != login:
            values["login"] = _login
        if _password:
            values["password"] = utils.hash_password(_password)

        try:
            yield self.application.thread_pool.submit(
                self.db.update, "users", values, {"login": login})
            self.status_ok()
        except DBALDriverError:
            # Error: 1062 (ER_DUP_ENTRY)
            if self.db.error_code() == 1062:
                raise HTTPError(409)
            raise

    @coroutine
    @check_level(
        BaseHandler.LEVEL_SUPER,
        BaseHandler.LEVEL_ADMIN)
    def delete(self, login):
        user = self._get_user(login)
        if user["login"] == self.current_user["login"]:
            raise HTTPError(409)

        yield self.application.thread_pool.submit(
            self.db.execute, "DELETE FROM users WHERE login = ?", login)
        self.status_ok()
