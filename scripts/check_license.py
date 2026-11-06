#!/usr/bin/env python3
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

"""Verify that source files start with the license header from LICENSE.

With no arguments, checks every git-tracked source file in the repository.
Otherwise checks only the files given (this is how pre-commit calls it).
Exits non-zero if any file is missing the header.

Usage:
    python scripts/check_license.py [FILE ...]
"""

import sys

from license_header import REPO_ROOT, comment_prefix, has_header, tracked_source_files


def main(argv):
    """Check files for the license header and report any that are missing it."""
    files = argv or tracked_source_files()

    missing = []
    for name in files:
        prefix = comment_prefix(name)
        if prefix is None:
            continue
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        if not has_header(text, prefix):
            missing.append(name)

    if missing:
        print("The following files are missing the license header:")
        for name in missing:
            print(f"  {name}")
        print("Run 'python scripts/add_license.py' to add it.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
