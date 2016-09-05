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

from ipa import IPAFile


class Metadata(dict):
    DEVICE_FAMILY = "device-family"
    APP_NAME = "app-name"
    APP_VERSION = "app-version"
    BUNDLE_ID = "bundle-id"

    def __init__(self, path, ext=None):
        if ext is None:
            ext = os.path.splitext(path.lower())[1]

        try:
            if ext == ".ipa":
                super(Metadata, self).__init__(Metadata._ipa(path))
        except StandardError:
            pass

    @staticmethod
    def _ipa(path):
        with IPAFile(path) as ipa:
            return (
                (Metadata.DEVICE_FAMILY, ipa.get_device_family()),
                (Metadata.APP_NAME, ipa.get_app_name()),
                (Metadata.APP_VERSION, ipa.get_app_version()),
                (Metadata.BUNDLE_ID, ipa.app_info["CFBundleIdentifier"]),
            )
