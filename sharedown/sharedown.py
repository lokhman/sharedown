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

from tornado import gen
from tornado.ioloop import IOLoop
from tornado.options import define, options, parse_command_line
from tornado.web import Application as BaseApplication
from concurrent.futures import ThreadPoolExecutor
from pydbal.connection import Connection
from ConfigParser import ConfigParser
from ast import literal_eval

from utils import ui_methods
from utils.s3 import S3

from handlers import *
from handlers import route

version = "0.1"
version_info = (0, 1, 0, 0)

__dir__ = os.path.dirname(__file__)

_config_defaults = dict(
    pydbal=dict(
        driver="mysql",
        host="localhost",
    ),
    session=dict(
        lifetime=360000,
        interval=60,
    ),
    s3=dict(
        download_url_lifetime=15,
        storage_lifetime=864000,
    ),
    cron=dict(
        interval=900,
    )
)

define("port", type=int, default=8000, help="Sharedown server port")
define("debug", type=bool, default=False, help="Start in debug mode")
define("max_workers", type=int, default=4, help="Thread pool max workers")
define("config", type=str, default="sharedown.conf", help="Path to config file")

for _option, _defaults in _config_defaults.items():
    define(_option, type=dict, default=_defaults, help="%s configuration" % _option.capitalize())


class Application(BaseApplication):
    def __init__(self):
        self.version = version

        config = ConfigParser()
        config.read(options.config)
        for option in _config_defaults.keys():
            if not config.has_section(option):
                continue
            for key, value in config.items(option):
                options[option][key] = literal_eval(value)

        self.thread_pool = ThreadPoolExecutor(options.max_workers)

        self.database = Connection(**options.pydbal)
        self.database.get_logger().propagate = False

        self.s3 = S3(**options.s3)

        IOLoop.current().spawn_callback(_cron, self)

        super(Application, self).__init__(
            route.routes,
            login_url="/web/login",
            cookie_secret="*** PLEASE UPDATE THIS SECRET KEY ***",
            template_path=os.path.join(__dir__, "templates"),
            static_path=os.path.join(__dir__, "static"),
            ui_methods=ui_methods,
            debug=options.debug,
            gzip=True
        )


@gen.coroutine
def _cron(app):
    def task():
        for file_ in app.database.query("SELECT * FROM files WHERE expires_at < NOW()").fetch_all():
            app.database.execute("DELETE FROM files WHERE `key` = ?", file_["key"])
            app.s3.delete("%s/%s" % (file_["key"], file_["name"]))

    while True:
        interval = gen.sleep(options.cron["interval"])
        yield app.thread_pool.submit(task)
        yield interval

if __name__ == "__main__":
    parse_command_line()
    Application().listen(options.port)
    IOLoop.instance().start()
