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

"""Tests for mesh-processing utilities in compgen.mesh."""

import exodusii
import numpy as np
import pytest

from compgen.mesh import extrude, write_mesh_2d

LX, LY, LZ = 2.0, 1.0, 0.1
N = 3  # elements per side of the (square) test image


@pytest.fixture(name="extruded")
def fixture_extruded(tmp_path, monkeypatch):
    """Write a small two-material 2D mesh, extrude it, and read the result back."""
    # extrude prepends the prefix to the whole input path, so work in tmp_path
    monkeypatch.chdir(tmp_path)
    img = np.array([[1, 0, 0], [1, 1, 0], [0, 1, 0]], dtype=bool)
    write_mesh_2d(img, "mesh.e", lx=LX, ly=LY)

    extrude("mesh.e", lx=LX, ly=LY, lz=LZ, prefix="extruded_")

    with exodusii.File("extruded_mesh.e", mode="r") as exo:
        result = {
            "coords": exo.get_coords(),
            "conn": {i: exo.get_element_conn(i) for i in (1, 2)},
            "node_sets": {i: exo.get_node_set_nodes(i) for i in range(1, 5)},
        }
    result["img"] = img
    return result


def test_extrude_geometry(extruded):
    """Nodes are duplicated at z=0 and z=lz and quads become hexes in both blocks."""
    coords = extruded["coords"]
    nnodes_2d = (N + 1) ** 2

    assert coords.shape == (2 * nnodes_2d, 3)
    np.testing.assert_allclose(coords[:nnodes_2d, 2], 0.0)
    np.testing.assert_allclose(coords[nnodes_2d:, 2], LZ)
    np.testing.assert_allclose(coords[nnodes_2d:, :2], coords[:nnodes_2d, :2])

    img = extruded["img"]
    assert extruded["conn"][1].shape == (img.sum(), 8)
    assert extruded["conn"][2].shape == ((~img).sum(), 8)
    for conn in extruded["conn"].values():
        # Top face nodes are the bottom face nodes offset by the 2D node count
        np.testing.assert_array_equal(conn[:, 4:], conn[:, :4] + nnodes_2d)


@pytest.mark.parametrize(
    "set_id, axis, value",
    [(1, 0, 0.0), (2, 0, LX), (3, 1, 0.0), (4, 1, LY)],
    ids=["left", "right", "bottom", "top"],
)
def test_extrude_periodic_node_sets(extruded, set_id, axis, value):
    """Node sets 1-4 hold exactly the nodes on the left, right, bottom, and top faces."""
    coords = extruded["coords"]
    nodes = extruded["node_sets"][set_id]

    expected = np.flatnonzero(np.isclose(coords[:, axis], value)) + 1
    assert len(expected) == 2 * (N + 1)
    np.testing.assert_array_equal(np.sort(nodes), expected)
