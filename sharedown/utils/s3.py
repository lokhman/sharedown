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

import boto3

from botocore.config import Config
from boto3.s3.transfer import S3Transfer
from datetime import datetime, timedelta


class S3:
    SIGNATURE_VERSION = "s3v4"
    DEFAULT_CONTENT_TYPE = "binary/octet-stream"
    VALID_CONTENT_TYPES = (
        "application/vnd.android.package-archive",
        DEFAULT_CONTENT_TYPE
    )

    def __init__(self, region, bucket, download_url_lifetime, storage_lifetime, **kwargs):
        self._config = Config(signature_version=S3.SIGNATURE_VERSION)
        self._client = boto3.client("s3", region, config=self._config)
        self._download_url_lifetime = download_url_lifetime
        self._storage_lifetime = storage_lifetime
        self._bucket = bucket

    @staticmethod
    def _validate_content_type(content_type):
        return content_type if content_type in S3.VALID_CONTENT_TYPES else S3.DEFAULT_CONTENT_TYPE

    def get_expiry_date(self):
        return datetime.now() + timedelta(seconds=self._storage_lifetime)

    def upload_file(self, filename, key, content_type=DEFAULT_CONTENT_TYPE, metadata=None):
        S3Transfer(self._client).upload_file(filename, self._bucket, key, extra_args={
            "ContentType": S3._validate_content_type(content_type),
            "Metadata": metadata
        })

    def download_url(self, key):
        return self._client.generate_presigned_url("get_object", {
            "Bucket": self._bucket,
            "Key": key
        }, self._download_url_lifetime)

    def delete(self, key):
        return self._client.delete_object(Bucket=self._bucket, Key=key)

    def delete_many(self, keys):
        return self._client.delete_objects(Bucket=self._bucket, Delete={
            "Objects": map(lambda x: {"Key": x}, keys)
        })
