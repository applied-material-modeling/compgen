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

"""Shared helpers for adding and checking the license header on source files."""

import pathlib
import subprocess

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
LICENSE_FILE = REPO_ROOT / "LICENSE"

# Source file extensions that get a license header, mapped to their line
# comment prefix.  *.i files are MOOSE input templates, which use "#" comments.
COMMENT_PREFIXES = {
    ".py": "#",
    ".i": "#",
}


def comment_prefix(path):
    """Return the comment prefix for a path, or None if it is not a source file."""
    return COMMENT_PREFIXES.get(pathlib.PurePath(path).suffix)


def license_header(prefix):
    """Return the license text formatted as a comment block, ending in a newline."""
    lines = LICENSE_FILE.read_text(encoding="utf-8").strip().splitlines()
    return "".join(
        f"{prefix} {line}".rstrip() + "\n" if line.strip() else f"{prefix}\n"
        for line in lines
    )


def split_preamble(text):
    """Split off lines that must stay at the very top of a file.

    That is a shebang and/or a PEP 263 encoding declaration.  Returns
    (preamble, rest).
    """
    lines = text.splitlines(keepends=True)
    n = 0
    if lines and lines[0].startswith("#!"):
        n = 1
    if len(lines) > n and lines[n].startswith("#") and "coding" in lines[n]:
        n += 1
    return "".join(lines[:n]), "".join(lines[n:])


def has_header(text, prefix):
    """Check whether the text starts with the license header (after any preamble)."""
    _, rest = split_preamble(text)
    return rest.startswith(license_header(prefix))


def add_header(text, prefix):
    """Return text with the license header inserted (no-op if already present)."""
    if has_header(text, prefix):
        return text
    preamble, rest = split_preamble(text)
    if rest.strip():
        return preamble + license_header(prefix) + "\n" + rest.lstrip("\n")
    return preamble + license_header(prefix)


def tracked_source_files():
    """Return all git-tracked source files, relative to the repository root."""
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [f for f in out.split("\0") if f and comment_prefix(f)]
