# Copyright 2026, UChicago Argonne, LLC
# All Rights Reserved
# Software Name: compgen
# By: Argonne National Laboratory
# OPEN SOURCE LICENSE (MIT)
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
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""Temporary directory context manager used to isolate intermediate workflow files."""

import tempfile
import os
import shutil
import logging

logger = logging.getLogger(__name__)


class TempDirectory:
    """Context manager for creating and cleaning up a temporary directory."""

    def __init__(self, options):
        self.base_dir = options.get("storage", {}).get("temp_dir", None)
        self.delete_after = options.get("storage", {}).get("delete_temp_dir", False)
        self.temp_dir = None
        self.orig_cwd = None

    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp(dir=self.base_dir)
        logger.info("Created temporary directory at %s", self.temp_dir)
        self.orig_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        return self.orig_cwd, self.temp_dir

    def __exit__(self, exc_type, exc_value, traceback):
        os.chdir(self.orig_cwd)
        logger.info("Returning to original directory %s", self.orig_cwd)
        if self.temp_dir and self.delete_after:
            logger.info("Deleting temporary directory %s", self.temp_dir)
            shutil.rmtree(self.temp_dir)
