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
import logging

from tornado.gen import coroutine
from tornado.web import HTTPError, removeslash
from pydbal.exception import DBALDriverError
from utils.metadata import Metadata

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
    @coroutine
    def post(self):
        _login = self.get_body_argument("login")
        _password = self.get_body_argument("password")

        user = yield self.thread_pool.submit(
            self.db.fetch, "SELECT * FROM users WHERE login = ? AND is_enabled = TRUE", _login)
        if not user or utils.hash_password(_password, user["password"]) != user["password"]:
            raise HTTPError(401)

        session = yield self.thread_pool.submit(self.create_session, user["login"])
        self.write({"session": session, "level": user["level"]})


@route(r"/api/auth/passwd")
class AuthPasswdHandler(BaseHandler):
    @authenticated
    @coroutine
    def post(self):
        _login = self.get_body_argument("login")
        _password = self.get_body_argument("password")

        if not _password or _login != self.current_user["login"]:
            raise HTTPError(400)

        yield self.thread_pool.submit(
            self.db.execute, "UPDATE users SET password = ? WHERE login = ?",
            utils.hash_password(_password), _login)
        self.status_ok()


@route(r"/api/auth/logout")
class AuthLogoutHandler(BaseHandler):
    @authenticated
    @coroutine
    def get(self):
        yield self.thread_pool.submit(
            self.clear_session, self.current_user["login"], self.current_user["session"])
        self.status_ok()


@route(r"/api/upload")
class UploadHandler(BaseHandler):
    @coroutine
    def put(self):
        _file = self.get_header("X-File")
        _name = self.get_header("X-SF-Name")
        _public = self.get_header("X-SF-Public", None)
        _folder = self.get_header("X-SF-Folder", None)
        _caption = self.get_header("X-SF-Caption", None)
        _password = self.get_header("X-SF-Password", None)
        _permanent = self.get_header("X-SF-Permanent", None)
        _content_type = self.get_header("Content-Type", None)

        size = os.stat(_file).st_size
        if not size:
            raise HTTPError(411)

        name = utils.normalize_filename(_name)
        if not name:
            raise HTTPError(400)

        values = {
            "login": self.current_user["login"],
            "name": name, "size": size
        }

        if _folder:
            values["folder"] = _folder[:64]
        if _caption:
            values["caption"] = _caption[:64]
        if _password:
            values["password"] = _password[:72]

        if _public is not None:
            if _public not in ("0", "1"):
                raise HTTPError(400)
            values["is_public"] = _public

        if _permanent == "0" or _permanent is None:
            values["expires_at"] = self.s3.get_expiry_date()
        elif _permanent != "1":
            expires_at = utils.datetime_parse(_permanent)
            if expires_at is None:
                raise HTTPError(400)
            values["expires_at"] = expires_at

        def prepare():
            with self.db.locked() as conn:
                while True:
                    try:
                        values["`key`"] = _key = utils.random_bytes(8)
                        conn.insert("files", values)
                        return _key
                    except DBALDriverError:
                        # Error: 1062 (ER_DUP_ENTRY)
                        if conn.error_code() != 1062:
                            raise

        key = yield self.thread_pool.submit(prepare)

        try:
            content_type = utils.normalize_content_type(_content_type, name)
            yield self.thread_pool.submit(
                self.s3.upload_file, _file, "%s/%s" % (key, name), content_type, {
                    "auth": self.current_user["login"]
                })
        except Exception as e:
            yield self.thread_pool.submit(self.db.delete, "files", {"`key`": key})
            logging.error(e.message)
            raise HTTPError(503)

        metadata = yield self.thread_pool.submit(Metadata, _file, os.path.splitext(_name)[1])

        def callback(conn):
            for attribute, value in metadata.iteritems():
                conn.execute("INSERT INTO meta (`key`, attribute, value) VALUES(?)", (key, attribute, value))

        if metadata:
            yield self.thread_pool.submit(self.db.transaction, callback)
        self.write({"key": key})


@route(r"/api/files")
class FilesHandler(BaseHandler):
    @authenticated
    @coroutine
    def get(self):
        def prepare():
            with self.db.locked() as conn:
                sqb = conn.sql_builder()
                sqb.select("f.*", "COUNT(s.key) downloads").from_("files", "f")
                sqb.left_join("f", "stats", "s", "s.key = f.key AND s.status = ?")
                sqb.set_parameter(0, BaseHandler.STATS_OK).group_by("f.key")
                sqb.order_by("f.login").add_order_by("f.name").add_order_by("f.created_at", "DESC")

                if self.check_level(BaseHandler.LEVEL_SUPER):
                    login = self.get_argument("login", None)
                else:
                    login = self.current_user["login"]

                if login:
                    sqb.and_where("f.login = ?").set_parameter(1, login)

                folder = self.get_argument("folder", None)
                if folder is not None:
                    sqb.and_where("f.folder <=> ?").set_parameter(2, folder or None)

                search = self.get_argument("search", None)
                if search:
                    sqb.and_where("f.name LIKE :search OR f.caption LIKE :search") \
                        .set_parameter(":search", "%%%s%%" % search)

                return sqb.execute().fetch_all()

        files = yield self.thread_pool.submit(prepare)
        self.write({"files": files})

    @authenticated
    @coroutine
    def delete(self):
        keys = self.get_body_arguments("keys")
        if not keys:
            raise HTTPError(400)

        def prepare():
            with self.db.locked() as conn:
                sqb = conn.sql_builder()
                sqb.select("CONCAT(`key`, '/', name) _").from_("files")
                sqb.where("`key` IN (?)").set_parameter(0, keys)

                if not self.check_level(BaseHandler.LEVEL_SUPER):
                    sqb.and_where("login = ?").set_parameter(1, self.current_user["login"])

                _keys = sqb.execute().fetch_all(conn.FETCH_COLUMN)
                try:
                    self.s3.delete_many(_keys)
                except Exception as e:
                    logging.error(e.message)

                _deleted = map(lambda x: x.partition('/')[0], _keys)
                if _deleted:
                    conn.delete("files", {"`key`": _deleted})
                return _deleted

        deleted = yield self.thread_pool.submit(prepare)
        self.write({"deleted": deleted})


@route(r"/api/files/([a-zA-Z0-9]{8})")
class FilesEntryHandler(BaseHandler):
    def _get_file(self, key):
        with self.db.locked() as conn:
            sqb = conn.sql_builder()
            sqb.select("*").from_("files")
            sqb.where("`key` = ?").set_parameter(0, key)

            if not self.check_level(BaseHandler.LEVEL_SUPER):
                sqb.and_where("login = ?").set_parameter(1, self.current_user["login"])

            file_ = sqb.execute().fetch()
        if not file_:
            raise HTTPError(404)
        return file_

    @authenticated
    @coroutine
    def get(self, key):
        file_ = yield self.thread_pool.submit(self._get_file, key)
        file_["is_permanent"] = not file_["expires_at"]
        file_["downloads"] = yield self.thread_pool.submit(
            self.db.fetch_column, "SELECT COUNT(*) FROM stats WHERE `key` = ? AND status = ? AND deleted_at IS NULL",
            key, BaseHandler.STATS_OK)

        metadata = yield self.thread_pool.submit(
            self.db.fetch_all, "SELECT attribute, value FROM meta WHERE `key` = ?", key)
        file_["metadata"] = {meta["attribute"]: meta["value"] for meta in metadata}
        file_["mimetype"] = utils.normalize_content_type(filename=file_["name"])
        self.write(file_)

    @authenticated
    @coroutine
    def patch(self, key):
        _password = self.get_body_argument("password", None)
        _caption = self.get_body_argument("caption", None)
        _folder = self.get_body_argument("folder", None)
        _is_public = self.get_body_argument("is_public", None)
        _is_permanent = self.get_body_argument("is_permanent", None)

        yield self.thread_pool.submit(self._get_file, key)

        values = {}
        if _password is not None:
            values["password"] = _password[:72] or None
        if _caption is not None:
            values["caption"] = _caption[:64] or None
        if _folder is not None:
            values["folder"] = _folder[:64] or None
        if _is_public is not None:
            if _is_public not in ("0", "1"):
                raise HTTPError(400)
            values["is_public"] = _is_public
        if _is_permanent is not None:
            if _is_permanent == "0":
                expires_at = self.s3.get_expiry_date()
            elif _is_permanent == "1":
                expires_at = None
            else:
                expires_at = utils.datetime_parse(_is_permanent)
                if expires_at is None:
                    raise HTTPError(400)
            values["expires_at"] = expires_at

        if not values:
            raise HTTPError(400)

        yield self.thread_pool.submit(
            self.db.update, "files", values, {"`key`": key})
        self.status_ok()

    @authenticated
    @coroutine
    def delete(self, key):
        file_ = yield self.thread_pool.submit(self._get_file, key)
        try:
            yield self.thread_pool.submit(
                self.s3.delete, "%s/%s" % (key, file_["name"]))
        except Exception as e:
            logging.error(e.message)
            raise HTTPError(503)

        yield self.thread_pool.submit(self.db.delete, "files", {"`key`": key})
        self.status_ok()


@route(r"/api/feed")
class FeedHandler(BaseHandler):
    @authenticated
    @coroutine
    def get(self):
        feed = yield self.thread_pool.submit(
            self.db.fetch, "SELECT * FROM feeds WHERE login = ?",
            self.current_user["login"])
        self.write(feed or {})

    @authenticated
    @coroutine
    def post(self):
        _password = self.get_body_argument("password")[:72]
        _title = self.get_body_argument("title")[:64]
        _readme = self.get_body_argument("readme")[:65535]
        _is_enabled = self.get_body_argument("is_enabled")

        if _is_enabled not in ("0", "1"):
            raise HTTPError(400)

        yield self.thread_pool.submit(
            self.db.execute, "INSERT INTO feeds (login, password, title, readme, is_enabled) VALUES(?) "
            "ON DUPLICATE KEY UPDATE login=VALUES(login), password=VALUES(password), title=VALUES(title), "
            "readme=VALUES(readme), is_enabled=VALUES(is_enabled)",
            (self.current_user["login"], _password or None, _title or None, _readme or None, _is_enabled))
        self.status_ok()


@route(r"/api/users")
class UsersHandler(BaseHandler):
    @check_level(
        BaseHandler.LEVEL_SUPER,
        BaseHandler.LEVEL_ADMIN)
    @coroutine
    def get(self):
        def prepare():
            with self.db.locked() as conn:
                sqb = conn.sql_builder()
                sqb.select("u.login", "u.level", "u.is_enabled", "u.activity_at", "u.created_at", "COUNT(f.key) files")
                sqb.add_select("EXISTS(SELECT * FROM sess WHERE login = u.login AND expires_at IS NULL) has_token")
                sqb.add_select("EXISTS(SELECT * FROM feeds WHERE login = u.login AND is_enabled = TRUE) has_feed")
                sqb.from_("users", "u").left_join("u", "files", "f", "u.login = f.login").group_by("u.login")
                sqb.order_by("u.level").add_order_by("u.login")

                if not self.check_level(BaseHandler.LEVEL_SUPER):
                    sqb.where("u.level <> ?").set_parameter(0, BaseHandler.LEVEL_SUPER)

                return sqb.execute().fetch_all()

        users = yield self.thread_pool.submit(prepare)
        self.write({"users": users})

    @check_level(
        BaseHandler.LEVEL_SUPER,
        BaseHandler.LEVEL_ADMIN)
    @coroutine
    def post(self):
        _login = self.get_body_argument("login")
        _level = self.get_body_argument("level")
        _password = self.get_body_argument("password")
        _is_enabled = self.get_body_argument("is_enabled")

        if not re.match(r"^[\w.-]{2,32}$", _login):
            raise HTTPError(400)
        if _level not in (
            BaseHandler.LEVEL_USER,
            BaseHandler.LEVEL_ADMIN,
            BaseHandler.LEVEL_SUPER
        ):
            raise HTTPError(400)
        if not self.check_level(BaseHandler.LEVEL_SUPER) and _level == BaseHandler.LEVEL_SUPER:
            raise HTTPError(400)
        if _is_enabled not in ("0", "1"):
            raise HTTPError(400)

        with self.db.locked() as conn:
            try:
                yield self.thread_pool.submit(
                    conn.execute, "INSERT INTO users (login, password, level, is_enabled) VALUES(?)",
                    (_login,  utils.hash_password(_password), _level, _is_enabled))
            except DBALDriverError:
                # Error: 1062 (ER_DUP_ENTRY)
                if conn.error_code() == 1062:
                    raise HTTPError(409)
                raise
        self.status_ok()


@route(r"/api/users/([\w.-]{2,32})")
class UsersEntryHandler(BaseHandler):
    def _get_user(self, login):
        with self.db.locked() as conn:
            sqb = conn.sql_builder()
            sqb.select("login", "level", "is_enabled", "activity_at", "created_at")
            sqb.from_("users").where("login = ?").set_parameter(0, login)

            if not self.check_level(BaseHandler.LEVEL_SUPER):
                sqb.and_where("level <> ?").set_parameter(1, BaseHandler.LEVEL_SUPER)

            user = sqb.execute().fetch()
        if not user:
            raise HTTPError(404)
        return user

    @check_level(
        BaseHandler.LEVEL_SUPER,
        BaseHandler.LEVEL_ADMIN)
    @coroutine
    def get(self, login):
        user = yield self.thread_pool.submit(self._get_user, login)
        self.write(user)

    @check_level(
        BaseHandler.LEVEL_SUPER,
        BaseHandler.LEVEL_ADMIN)
    @coroutine
    def patch(self, login):
        _login = self.get_body_argument("login", None)
        _level = self.get_body_argument("level", None)
        _password = self.get_body_argument("password", None)
        _is_enabled = self.get_body_argument("is_enabled", None)

        values = {}
        if _login is not None and _login != login:
            if not re.match(r"^[\w.-]{2,32}$", _login):
                raise HTTPError(400)
            values["login"] = _login

        if _level is not None:
            if _level not in (
                BaseHandler.LEVEL_USER,
                BaseHandler.LEVEL_ADMIN,
                BaseHandler.LEVEL_SUPER
            ):
                raise HTTPError(400)
            if not self.check_level(BaseHandler.LEVEL_SUPER) and _level == BaseHandler.LEVEL_SUPER:
                raise HTTPError(400)
            values["level"] = _level

        if _password:
            values["password"] = utils.hash_password(_password)

        if _is_enabled is not None:
            if _is_enabled not in ("0", "1"):
                raise HTTPError(400)
            values["is_enabled"] = _is_enabled

        if not values:
            raise HTTPError(400)

        yield self.thread_pool.submit(self._get_user, login)

        with self.db.locked() as conn:
            try:
                yield self.thread_pool.submit(
                    conn.update, "users", values, {"login": login})
            except DBALDriverError:
                # Error: 1062 (ER_DUP_ENTRY)
                if conn.error_code() == 1062:
                    raise HTTPError(409)
                raise
        self.status_ok()

    @check_level(
        BaseHandler.LEVEL_SUPER,
        BaseHandler.LEVEL_ADMIN)
    @coroutine
    def delete(self, login):
        user = yield self.thread_pool.submit(self._get_user, login)
        if user["login"] == self.current_user["login"]:
            raise HTTPError(409)

        yield self.thread_pool.submit(self.db.delete, "users", {"login": login})
        self.status_ok()


@route(r"/api/users/([\w.-]{2,32})/token")
class UsersEntryTokenHandler(BaseHandler):
    def _check_user(self, login):
        with self.db.locked() as conn:
            sqb = conn.sql_builder()
            sqb.select("COUNT(*)").from_("users")
            sqb.where("login = ?").set_parameter(0, login)

            if not self.check_level(BaseHandler.LEVEL_SUPER):
                sqb.and_where("level <> ?").set_parameter(1, BaseHandler.LEVEL_SUPER)

            if sqb.execute().fetch_column() != 1:
                raise HTTPError(404)
        return True

    @check_level(BaseHandler.LEVEL_SUPER)
    @coroutine
    def get(self, login):
        self._check_user(login)
        token = yield self.thread_pool.submit(
            self.db.fetch_column, "SELECT session FROM sess WHERE login = ? AND expires_at IS NULL", login)
        self.write({"token": token})

    @check_level(BaseHandler.LEVEL_SUPER)
    @coroutine
    def post(self, login):
        self._check_user(login)

        def callback(conn):
            session = utils.random_bytes()
            conn.execute("DELETE FROM sess WHERE login = ? AND expires_at IS NULL", login)
            conn.execute("INSERT INTO sess (login, session) VALUES(?)", (login, session))
            return session

        token = yield self.thread_pool.submit(self.db.transaction, callback)
        self.write({"token": token})

    @check_level(BaseHandler.LEVEL_SUPER)
    @coroutine
    def delete(self, login):
        self._check_user(login)
        yield self.thread_pool.submit(
            self.db.execute, "DELETE FROM sess WHERE login = ? AND expires_at IS NULL", login)
        self.status_ok()
