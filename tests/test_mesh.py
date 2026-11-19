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

from compgen.mesh import (
    MeshQualityError,
    _validate_mesh,
    downsample_vfrac,
    extrude,
    extract_grid_from_mesh,
    face_mismatch,
    generate_mesh_2d,
    generate_mesh_3d,
    overlap_vfrac,
    project_element_field_to_grid,
    snap_periodic_faces,
    write_mesh_2d,
    write_mesh_3d,
)

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


def check_elements_match_image(fname, img, lengths):
    """Check each element is one grid cell, in the block given by that pixel of img."""
    spacing = np.array(lengths) / np.array(img.shape)

    with exodusii.File(fname, mode="r") as exo:
        coords = exo.get_coords()
        conn = {block: exo.get_element_conn(block) for block in (1, 2)}

    assert len(coords) == np.prod(np.array(img.shape) + 1)

    cells = {}
    for block, elements in conn.items():
        corners = coords[elements - 1]  # (element, node, dimension)
        low = corners.min(axis=1)
        # Exodus stores the coordinates in single precision
        np.testing.assert_allclose(
            corners.max(axis=1) - low, np.tile(spacing, (len(low), 1)), rtol=1e-5
        )
        cells[block] = {tuple(c) for c in np.rint(low / spacing).astype(int).tolist()}

    assert cells[1] == {tuple(c) for c in np.argwhere(img).tolist()}
    assert cells[2] == {tuple(c) for c in np.argwhere(~img).tolist()}


@pytest.mark.parametrize("shape", [(3, 3), (2, 4), (4, 2), (3, 7)])
def test_write_mesh_2d_maps_pixels_to_elements(tmp_path, shape):
    """Elements land on the right pixels, including for non-square images."""
    img = np.random.default_rng(0).random(shape) < 0.5
    fname = str(tmp_path / "mesh.e")

    write_mesh_2d(img, fname, lx=LX, ly=LY)

    check_elements_match_image(fname, img, (LX, LY))


@pytest.mark.parametrize("shape", [(3, 3, 3), (2, 3, 4), (4, 3, 2), (2, 2, 5)])
def test_write_mesh_3d_maps_voxels_to_elements(tmp_path, shape):
    """Elements land on the right voxels, including for non-cubic images."""
    img = np.random.default_rng(0).random(shape) < 0.5
    fname = str(tmp_path / "mesh.e")

    write_mesh_3d(img, fname, lx=LX, ly=LY, lz=LZ)

    check_elements_match_image(fname, img, (LX, LY, LZ))


def _grid_coords(n=4):
    """Node coordinates of a regular n x n x n unit-cube grid."""
    ax = np.linspace(0.0, 1.0, n + 1)
    return np.stack(np.meshgrid(ax, ax, ax, indexing="ij"), -1).reshape(-1, 3)


def _rewrite_coords(fname, func):
    """Rewrite an exodus mesh in place with ``func(coords)`` as the coordinates."""
    with exodusii.File(fname, mode="r") as exo:
        coords = np.asarray(exo.get_coords(), dtype=float)
        ids = [int(b) for b in exo.get_element_block_ids()]
        conns = {b: np.asarray(exo.get_element_conn(b)) for b in ids}
    coords = func(coords)
    with exodusii.File(fname, mode="w") as exo:
        nelem = sum(len(c) for c in conns.values())
        exo.put_init("test", 3, len(coords), nelem, len(ids), 0, 0)
        exo.put_coord(coords[:, 0], coords[:, 1], coords[:, 2])
        for b in ids:
            exo.put_element_block(b, "HEX", len(conns[b]), 8)
            exo.put_element_conn(b, conns[b])


def test_face_mismatch_zero_for_regular_grid():
    """A structured grid has exactly matching opposite faces."""
    assert face_mismatch(_grid_coords()) == 0.0


def test_face_mismatch_reports_moved_face_node():
    """Moving one face node in-plane shows up as that distance."""
    coords = _grid_coords()
    i = np.flatnonzero((coords[:, 2] == 1.0) & (coords[:, 0] == 0.5) & (coords[:, 1] == 0.5))
    coords[i, 0] += 0.01
    assert face_mismatch(coords) == pytest.approx(0.01)


def test_face_mismatch_skips_flat_axis():
    """A zero-extent axis (e.g. a 2D mesh stored in 3D) is ignored."""
    coords = _grid_coords()
    coords[:, 2] = 0.0
    assert face_mismatch(coords) == 0.0


def _read(fname):
    with exodusii.File(fname, mode="r") as exo:
        coords = np.asarray(exo.get_coords(), dtype=float)
        conn = np.vstack([np.asarray(exo.get_element_conn(b)) - 1 for b in exo.get_element_block_ids()])
    return coords, conn


def _shift_top_center(c, dx=0.01):
    """Move the center node of the z-max face of a unit 4x4x4 grid in x."""
    c = c.copy()
    top = np.isclose(c[:, 2], c[:, 2].max())
    mid = np.isclose(c[:, 0], 0.5) & np.isclose(c[:, 1], 0.5)
    c[top & mid, 0] += dx
    return c


CHECKER = np.indices((4, 4, 4)).sum(0) % 2 == 0  # two blocks, h = 0.25


def test_validate_mesh_rejects_nan_coords_without_quality_check(tmp_path):
    """Non-finite coordinates fail even with quality_check and snapping off."""
    fname = str(tmp_path / "mesh.e")
    write_mesh_3d(np.indices((2, 2, 2)).sum(0) % 2 == 0, fname)
    _rewrite_coords(fname, lambda c: np.where(np.arange(len(c))[:, None] == 0, np.nan, c))

    with pytest.raises(MeshQualityError, match="non-finite") as exc:
        _validate_mesh(fname, False, None, 1.0, 2)
    assert exc.value.reason == "non-finite"


def test_validate_mesh_snaps_faces_in_place(tmp_path):
    """A small face shift is snapped away; the file ends exactly periodic."""
    fname = str(tmp_path / "mesh.e")
    write_mesh_3d(CHECKER, fname)
    _rewrite_coords(fname, _shift_top_center)
    assert face_mismatch(_read(fname)[0]) == pytest.approx(0.01)

    _validate_mesh(fname, False, 0.1, 1.0, 4)  # cap 0.025

    assert face_mismatch(_read(fname)[0]) == 0.0


def test_validate_mesh_rejects_move_above_cap(tmp_path):
    """A shift larger than max_snap_move * h is rejected, file untouched."""
    fname = str(tmp_path / "mesh.e")
    write_mesh_3d(CHECKER, fname)
    _rewrite_coords(fname, _shift_top_center)

    with pytest.raises(MeshQualityError, match="need a move") as exc:
        _validate_mesh(fname, False, 0.02, 1.0, 4)  # cap 0.005
    assert exc.value.reason == "snap-move"
    assert face_mismatch(_read(fname)[0]) == pytest.approx(0.01)


def test_snap_rejects_non_flat_face(tmp_path):
    """A face node pushed off the box plane makes the face non-flat."""
    fname = str(tmp_path / "mesh.e")
    write_mesh_3d(CHECKER, fname)
    coords, conn = _read(fname)
    top = np.flatnonzero(np.isclose(coords[:, 2], 1.0))
    coords[top[5], 2] -= 0.05

    with pytest.raises(MeshQualityError, match="not flat") as exc:
        snap_periodic_faces(coords, conn, (4, 4, 4), 1.0)
    assert exc.value.reason == "snap-flat"


def test_snap_rejects_crossed_neighbors():
    """A face node shifted past its partner's neighbor has no mutual nearest
    neighbor, and the mesh is rejected rather than paired by a guess."""
    ax = np.linspace(0.0, 1.0, 5)
    coords = np.stack(np.meshgrid(ax, ax, ax, indexing="ij"), -1).reshape(-1, 3)
    idx = lambda i, j, k: (i * 5 + j) * 5 + k  # noqa: E731
    conn = np.array(
        [
            [idx(i, j, k), idx(i + 1, j, k), idx(i + 1, j + 1, k), idx(i, j + 1, k),
             idx(i, j, k + 1), idx(i + 1, j, k + 1), idx(i + 1, j + 1, k + 1), idx(i, j + 1, k + 1)]
            for i in range(4) for j in range(4) for k in range(4)
        ]
    )
    moved = coords.copy()
    moved[idx(4, 2, 2), 1] += 0.13  # y 0.5 -> 0.63: nearest min-face node is now y=0.75
    with pytest.raises(MeshQualityError, match="no mutual nearest") as exc:
        snap_periodic_faces(moved, conn, (4, 4, 4), 0.2)
    assert exc.value.reason == "snap-pairing"


def test_snap_2d_quad_mesh(tmp_path):
    """The 2D path pairs face edges of a QUAD4 mesh."""
    fname = str(tmp_path / "mesh.e")
    write_mesh_2d(np.indices((4, 4)).sum(0) % 2 == 0, fname)
    coords, conn = _read(fname)
    right = np.flatnonzero(np.isclose(coords[:, 0], coords[:, 0].max()))
    coords[right[2], 1] += 0.01

    snapped = snap_periodic_faces(coords, conn, (4, 4), 0.05)

    assert face_mismatch(snapped) == 0.0


def test_generate_mesh_3d_snap_without_sculpt(tmp_path, monkeypatch):
    """The unsculpted voxel mesh is exactly periodic, so a tiny cap passes."""
    monkeypatch.chdir(tmp_path)
    img = np.random.default_rng(0).random((3, 3, 3)) < 0.5
    generate_mesh_3d(img, "mesh.e", run_sculpt=False, max_snap_move=1e-9)
    assert (tmp_path / "mesh.e").exists()


def test_generate_mesh_2d_coarsens_without_sculpt(tmp_path, monkeypatch):
    """mesh N below the image size meshes the thresholded overlap fractions."""
    monkeypatch.chdir(tmp_path)
    img = np.random.default_rng(1).random((12, 12)) < 0.5
    generate_mesh_2d(img, "mesh.e", N=5, run_sculpt=False, max_snap_move=1e-9)
    coords, conn = _read(str(tmp_path / "mesh.e"))
    assert len(conn) == 25 and coords.max() == pytest.approx(1.0)


def test_generate_mesh_rejects_mesh_finer_than_image(tmp_path, monkeypatch):
    """N_mesh > N_gen is an error."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="exceeds"):
        generate_mesh_2d(np.zeros((8, 8), dtype=bool), "mesh.e", N=9, run_sculpt=False)


@pytest.mark.parametrize("shape,factor", [((24, 24), 2), ((24, 24), 3), ((24, 24), 8), ((12, 12, 12), 4), ((12, 12, 12), 3)])
def test_overlap_vfrac_matches_downsample_for_integer_ratio(shape, factor):
    """For an integer ratio the overlap operator is the block mean, exactly."""
    img = np.random.default_rng(2).random(shape) > 0.5
    out = overlap_vfrac(img, shape[0] // factor)
    assert np.array_equal(out, downsample_vfrac(img, factor))


@pytest.mark.parametrize("n_gen,n", [(256, 96), (192, 50), (10, 7), (9, 9)])
def test_overlap_vfrac_non_integer_ratio(n_gen, n):
    """Any ratio: fractions in [0, 1], total material conserved, constants kept."""
    img = np.random.default_rng(3).random((n_gen, n_gen)) > 0.5
    out = overlap_vfrac(img, n)
    assert out.shape == (n, n)
    assert out.min() >= 0 and out.max() <= 1
    assert out.mean() == pytest.approx(img.mean())
    assert np.array_equal(overlap_vfrac(np.ones((n_gen,) * 2), n), np.ones((n, n)))


def test_overlap_vfrac_exact_fraction():
    """A 1D-style step at x = 0.5 of a 4-cell grid seen from 3 cells: the
    middle cell straddles it and is half full."""
    img = np.zeros((4, 4))
    img[:2] = 1
    out = overlap_vfrac(img, 3)
    assert np.allclose(out[:, 0], [1.0, 0.5, 0.0])


def test_project_element_field_to_grid_any_resolution(tmp_path):
    """A voxel mesh projected to a coarser and a finer grid samples the
    element under each grid centroid."""
    fname = str(tmp_path / "mesh.e")
    img = np.random.default_rng(5).random((6, 6)) > 0.5
    write_mesh_2d(img, fname)
    coords, conn = _read(fname)
    with exodusii.File(fname, mode="r") as exo:
        n_a = len(exo.get_element_conn(1))
    material = np.zeros(len(conn))
    material[:n_a] = 1
    field = {"type": "scalar", "shape": (), "data": material[None, :]}
    same = project_element_field_to_grid(coords, conn, field, 1.0, 6)["data"][0]
    assert np.array_equal(same.astype(bool), img)
    fine = project_element_field_to_grid(coords, conn, field, 1.0, 12)["data"][0]
    assert np.array_equal(fine.astype(bool), np.kron(img, np.ones((2, 2), dtype=bool)))


def test_extract_grid_uses_output_resolution(tmp_path):
    """The grid has N_out cells per side; material_generated is the meshed
    image resampled to N_out."""
    fname = str(tmp_path / "mesh.e")
    img = np.kron(np.random.default_rng(6).random((4, 4)) > 0.5, np.ones((3, 3), dtype=bool))
    write_mesh_2d(img, fname)
    coords, conn = _read(fname)
    with exodusii.File(fname, mode="r") as exo:
        n_a = len(exo.get_element_conn(1))
    material = np.zeros(len(conn))
    material[:n_a] = 1
    mesh_data = {
        "coords": coords,
        "connectivity": conn,
        "element_fields": {
            "material": {"type": "scalar", "shape": (), "data": material[None, :]},
            "stimuli": {},
            "responses": {},
        },
    }
    grid = extract_grid_from_mesh(mesh_data, img, 1.0, N=4)["cell_fields"]
    assert grid["material"]["data"].shape == (4, 4)
    assert np.array_equal(grid["material"]["data"].astype(bool), grid["material_generated"]["data"])
    assert grid["lx"] == grid["ly"] == 1.0 and "lz" not in grid
