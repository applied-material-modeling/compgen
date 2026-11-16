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

"""Consistency checks on the MOOSE physics templates."""

import re

import pytest

from compgen.moose import get_physics

AXES = "xyz"


def _strain_entries(physics):
    """(i, j) gradient components set to `strain` in a template's constraint_types.

    MOOSE reads the 9-entry string column-major: position idx = i + 3 * j holds
    the (i, j) component, e.g. position 4 (idx 3) is xy.
    """
    template, _ = get_physics(physics)
    with open(template, encoding="utf-8") as f:
        strings = set(re.findall(r"constraint_types\s*=\s*'([^']*)'", f.read()))
    assert len(strings) == 1, f"{physics}: constraint_types differ between blocks"
    types = strings.pop().split()
    assert len(types) == 9
    return {(idx % 3, idx // 3) for idx, ctype in enumerate(types) if ctype == "strain"}


@pytest.mark.parametrize("physics", ["2d/plastic", "3d/plastic"])
def test_plastic_strain_entries_are_upper_off_diagonal(physics):
    """The plastic templates fix only off-diagonal entries F_ij with i < j (F lower
    triangular), the convention that, with the complementary P shear entries held
    at zero, makes the Cauchy stress diagonal."""
    entries = _strain_entries(physics)
    assert entries, f"{physics}: no strain entries"
    bad = [f"{AXES[i]}{AXES[j]}" for i, j in entries if i >= j]
    assert not bad, f"{physics}: strain entries on the wrong triangle: {bad}"


def test_plastic_2d_and_3d_share_the_same_convention():
    """2D's strain entries are exactly 3D's restricted to the xy plane, so 2D and
    3D results follow one convention."""
    in_plane_3d = {(i, j) for i, j in _strain_entries("3d/plastic") if i < 2 and j < 2}
    assert _strain_entries("2d/plastic") == in_plane_3d
