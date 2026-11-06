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

"""Add the contents of LICENSE as a commented header to source files.

With no arguments, processes every git-tracked source file in the repository.
Files that already have the header are left untouched.

Usage:
    python scripts/add_license.py [FILE ...]
"""

import sys

from license_header import REPO_ROOT, add_header, comment_prefix, tracked_source_files


def main(argv):
    """Add the license header to the given files (or all tracked source files)."""
    files = argv or tracked_source_files()
    changed = 0
    for name in files:
        prefix = comment_prefix(name)
        if prefix is None:
            continue
        path = REPO_ROOT / name
        text = path.read_text(encoding="utf-8")
        new = add_header(text, prefix)
        if new != text:
            path.write_text(new, encoding="utf-8")
            print(f"Added license header: {name}")
            changed += 1
    print(f"{changed} file(s) updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
