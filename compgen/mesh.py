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

"""Mesh generation and mesh-processing utilities for 2D and 3D binary structures."""

import os
import shutil
import subprocess

import exodusii
import numpy as np
import pyvista
import scipy.spatial as sp

from compgen import temp


class SculptError(RuntimeError):
    """Raised when the Sculpt (psculpt/epu) subprocess fails."""


class MeshQualityError(RuntimeError):
    """Raised when a generated mesh fails a post-mesh check.

    ``reason`` is a short tag for the run summary: ``non-finite``,
    ``jacobian``, ``snap-flat``, ``snap-count``, ``snap-pairing``,
    ``snap-topology`` or ``snap-move``.
    """

    def __init__(self, message, reason="quality"):
        super().__init__(message)
        self.reason = reason


def generate_mesh(img, fname, **kwargs):
    """Run the entire process of generating a mesh for an image and write it to an exodus file.

    This function will access a temp directory to store intermediate files, but copy the final
    mesh to the cwd.

    Args:
        img (2D or 3D array): Square/cubic binary image (1 = material A) at the
            generator resolution ``N_gen = img.shape[0]``.
        fname (str): Output filename for the mesh.
    Keyword Args:
        L (float): Side length of the square/cubic domain.
        N (int or None): Mesh cells per side, ``N_mesh <= N_gen``. None means
            ``N_gen``.
        settings (dict): Global settings dict
        run_sculpt (bool): Whether to sculpt the mesh
        quality_check (bool): Whether to run a mesh quality check
        max_snap_move (float or None): Snap opposite faces to exact
            periodicity, moving nodes by at most this fraction of the element
            size (see ``snap_periodic_faces``).
    """
    if len(img.shape) == 2:
        generate_mesh_2d(img, fname, **kwargs)
    elif len(img.shape) == 3:
        generate_mesh_3d(img, fname, **kwargs)
    else:
        raise ValueError("Input image must be 2D or 3D.")


def _mesh_vfrac(img, N):
    """Volume fractions of ``img`` on the ``N``-cell mesh grid, and ``N``.

    Checks that ``img`` is square/cubic and ``N <= N_gen``.
    """
    if len(set(img.shape)) != 1:
        raise ValueError(f"Image must be square/cubic, got shape {img.shape}.")
    n_gen = img.shape[0]
    n_mesh = n_gen if N is None else int(N)
    if n_mesh > n_gen:
        raise ValueError(
            f"Mesh resolution N={n_mesh} exceeds the image resolution {n_gen}."
        )
    return overlap_vfrac(img, n_mesh), n_mesh


def generate_mesh_2d(
    img,
    fname,
    L=1.0,
    N=None,
    settings=None,
    run_sculpt=True,
    quality_check=True,
    max_snap_move=None,
):
    """Run the entire process of generating a 2D mesh for an image and write it to an exodus file.

    This function will access a temp directory to store intermediate files, but copy the final
    mesh to the cwd.

    The image is reduced to area fractions on the ``N x N`` mesh grid with
    ``overlap_vfrac`` (any ratio ``N_gen / N``), which Sculpt meshes from its
    ``-ims`` microstructure input. ``N = N_gen`` takes the same path: the
    fractions are then 0/1.

    Args:
        img (2D array): Square binary image where 1 indicates material A, at
            the generator resolution ``N_gen = img.shape[0]``.
        fname (str): Output filename for the mesh.

    Keyword Args:
        L (float): Side length of the square domain.
        N (int or None): Mesh cells per side (``<= N_gen``). None means ``N_gen``.
        settings (dict): Global settings dict
        run_sculpt (bool): Whether to sculpt the mesh. If False, write the
            voxel mesh of the thresholded fractions (``> 0.5``).
        quality_check (bool): Whether to run a mesh quality check
        max_snap_move (float or None): If set, make opposite faces match
            exactly by moving the max-face nodes onto their min-face partners,
            by at most this fraction of the element size; a mesh whose faces
            cannot be paired this way is rejected. None (default) skips it.
    """
    assert len(img.shape) == 2, "Input image must be 2D."
    if settings is None:
        settings = {}
    phi, n_mesh = _mesh_vfrac(img, N)

    with temp.TempDirectory(settings) as (cwd, _):
        if not run_sculpt:
            write_mesh_2d(phi > 0.5, "temp_mesh.e", lx=L, ly=L)
            shutil.move("temp_mesh.e", os.path.join(cwd, fname))
        else:
            _write_micro(phi, "micro.tec")
            sculpt(
                "micro.tec", prefix="sculpted_", settings=settings, sculpt_input="ims"
            )
            # -ims output is a unit-cell, origin-centred 3D slab; map to the domain
            # (this also puts the z-bottom at 0 so the unchanged slice works).
            normalize_mesh("sculpted_micro.e", (L, L, L / n_mesh), (n_mesh, n_mesh, 1))
            slice_mesh("sculpted_micro.e", prefix="sliced_")
            shutil.move("sliced_sculpted_micro.e", os.path.join(cwd, fname))

    _validate_mesh(fname, quality_check, max_snap_move, L, n_mesh)


def generate_mesh_3d(
    img,
    fname,
    L=1.0,
    N=None,
    settings=None,
    run_sculpt=True,
    quality_check=True,
    max_snap_move=None,
):
    """Run the entire process of generating a 3D mesh for an image and write it to an exodus file.

    This function will access a temp directory to store intermediate files, but copy the final
    mesh to the cwd.

    Same as ``generate_mesh_2d`` (volume fractions on the ``N^3`` mesh grid,
    Sculpt ``-ims``), without the slice.

    Args:
        img (3D array): Cubic binary image where 1 indicates material A, at
            the generator resolution ``N_gen = img.shape[0]``.
        fname (str): Output filename for the mesh.

    Keyword Args:
        L (float): Side length of the cubic domain.
        N (int or None): Mesh cells per side (``<= N_gen``). None means ``N_gen``.
        settings (dict): Global settings dict
        run_sculpt (bool): Whether to sculpt the mesh. If False, write the
            voxel mesh of the thresholded fractions (``> 0.5``).
        quality_check (bool): Whether to run a mesh quality check
        max_snap_move (float or None): If set, make opposite faces match
            exactly by moving the max-face nodes onto their min-face partners,
            by at most this fraction of the element size; a mesh whose faces
            cannot be paired this way is rejected. None (default) skips it.
    """
    assert len(img.shape) == 3, "Input image must be 3D."
    if settings is None:
        settings = {}
    phi, n_mesh = _mesh_vfrac(img, N)

    with temp.TempDirectory(settings) as (cwd, _):
        if not run_sculpt:
            write_mesh_3d(phi > 0.5, "temp_mesh.e", lx=L, ly=L, lz=L)
            shutil.move("temp_mesh.e", os.path.join(cwd, fname))
        else:
            _write_micro(phi, "micro.tec")
            sculpt(
                "micro.tec", prefix="sculpted_", settings=settings, sculpt_input="ims"
            )
            normalize_mesh("sculpted_micro.e", (L, L, L), (n_mesh,) * 3)  # unit-cell -> domain
            shutil.move("sculpted_micro.e", os.path.join(cwd, fname))

    _validate_mesh(fname, quality_check, max_snap_move, L, n_mesh)


def mesh_quality(exofile, min_qual=0.1):
    """Check the minimum scaled Jacobian of a 2D or 3D exodus mesh.

    Args:
        exofile (str): Input mesh filename.
        min_qual (float): Smallest acceptable scaled Jacobian. Defaults to 0.1.
    Returns:
        bool: True if mesh quality is acceptable, False otherwise.
    """
    f = pyvista.read_exodus(exofile)
    qual = f.cell_quality(["scaled_jacobian"])
    return qual.get_data_range("scaled_jacobian")[0] > min_qual


def _validate_mesh(fname, quality_check, max_snap_move, L, n):
    """Post-mesh checks; raise MeshQualityError if the mesh is unusable.

    In order: finite coordinates (always), periodic face snapping (when
    ``max_snap_move`` is set), then the Jacobian check (when ``quality_check``),
    so the Jacobian is measured on the mesh MOOSE will actually see.

    The finite-coordinates check always runs: Sculpt can emit NaN nodes, which
    ``normalize_mesh`` then spreads to every coordinate, and the Jacobian check
    does not catch them.

    Args:
        fname (str): Exodus mesh, modified in place if snapped.
        quality_check (bool): Run the scaled-Jacobian check.
        max_snap_move (float or None): Largest allowed snap, as a fraction of
            the element size ``L / n``.
        L (float): Domain side length.
        n (int): Mesh cells per side.
    """
    coords, conn = read_coords_conn(fname)
    if not np.all(np.isfinite(coords)):
        raise MeshQualityError(
            "Generated mesh has non-finite node coordinates.", "non-finite"
        )
    if max_snap_move is not None:
        ncells = [n] * coords.shape[1]
        snapped = snap_periodic_faces(coords, conn, ncells, max_snap_move * L / n)
        _write_coords(fname, snapped)
    if quality_check and not mesh_quality(fname):
        raise MeshQualityError("Generated mesh did not pass quality check.", "jacobian")


def read_coords_conn(fname):
    """Node coordinates ``(n_nodes, dim)`` and zero-based connectivity of all
    element blocks of an exodus mesh."""
    with exodusii.File(fname, mode="r") as exo:
        coords = np.asarray(exo.get_coords(), dtype=float)
        conn = np.vstack(
            [
                np.asarray(exo.get_element_conn(b)) - 1
                for b in exo.get_element_block_ids()
            ]
        )
    return coords, conn


# Local node indices of each element side, by nodes per element (exodus order).
_SIDES = {
    4: [[0, 1], [1, 2], [2, 3], [3, 0]],  # QUAD4 edges
    8: [
        [0, 1, 5, 4],
        [1, 2, 6, 5],
        [2, 3, 7, 6],
        [0, 4, 7, 3],
        [0, 3, 2, 1],
        [4, 5, 6, 7],
    ],
}


def snap_periodic_faces(coords, conn, ncells, max_move, tol=1e-6):
    """Make opposite domain faces match exactly; return the snapped coordinates.

    Sculpt builds the same face mesh on opposite sides of the box but its
    smoothing shifts the face nodes differently, which breaks periodic BCs. For
    each axis this pairs every node on the max face with one on the min face
    and moves it onto its partner's in-plane coordinates. The pairing is
    mutual nearest neighbors, and every node must have one.

    Raises MeshQualityError, naming the failed check, when a face is not flat
    (fewer nodes on the box plane than a grid of ``ncells`` has), the faces
    have different node counts, some node has no mutual nearest neighbor on the
    opposite face, the paired faces don't have the same boundary
    sides, or a node would move by more than ``max_move``.

    Args:
        coords (array): ``(n_nodes, dim)`` node coordinates.
        conn (array): ``(n_elems, 4 or 8)`` zero-based connectivity (QUAD4/HEX8).
        ncells (sequence): Mesh cells per axis (sets the flat-face node count).
        max_move (float): Largest allowed move, in mesh length units.
        tol (float): Relative tolerance for a node to lie on a face plane.
    Returns:
        array: Snapped copy of ``coords``.
    """
    # pylint: disable=too-many-locals
    coords = np.asarray(coords, dtype=float)
    out = coords.copy()
    dim = coords.shape[1]
    faces = np.sort(
        conn[:, _SIDES[conn.shape[1]]].reshape(-1, len(_SIDES[conn.shape[1]][0])), 1
    )
    uniq, count = np.unique(faces, axis=0, return_counts=True)
    boundary = uniq[count == 1]
    lo, hi = coords.min(axis=0), coords.max(axis=0)
    for d in range(dim):
        axis = "xyz"[d]
        span = hi[d] - lo[d]
        others = [k for k in range(dim) if k != d]
        ia = np.flatnonzero(np.abs(coords[:, d] - lo[d]) <= tol * span)
        ib = np.flatnonzero(np.abs(coords[:, d] - hi[d]) <= tol * span)
        need = int(np.prod([ncells[k] + 1 for k in others]))
        if min(len(ia), len(ib)) < need:
            raise MeshQualityError(
                f"Periodic snap: {axis} faces are not flat "
                f"({min(len(ia), len(ib))} nodes on the box plane, expected >= {need}).",
                "snap-flat",
            )
        if len(ia) != len(ib):
            raise MeshQualityError(
                f"Periodic snap: {axis} faces have {len(ia)} and {len(ib)} nodes.",
                "snap-count",
            )
        # Pair on the already-snapped coordinates, so edge and corner nodes
        # shared with earlier axes stay consistent.
        pa, pb = out[np.ix_(ia, others)], out[np.ix_(ib, others)]
        _, ab = sp.cKDTree(pb).query(pa)
        _, ba = sp.cKDTree(pa).query(pb)
        unpaired = int(np.count_nonzero(ba[ab] != np.arange(len(ia))))
        if unpaired:
            raise MeshQualityError(
                f"Periodic snap: {unpaired} {axis}-face nodes have no mutual nearest "
                "neighbor on the opposite face.",
                "snap-pairing",
            )
        partner = ab  # index into ib for each node of ia
        lut = np.full(len(coords), -1)
        lut[ia] = ib[partner]
        side_a = boundary[np.all(np.isin(boundary, ia), axis=1)]
        side_b = boundary[np.all(np.isin(boundary, ib), axis=1)]
        mapped = {tuple(r) for r in np.sort(lut[side_a], 1).tolist()}
        if len(side_a) != len(side_b) or mapped != {tuple(r) for r in side_b.tolist()}:
            raise MeshQualityError(
                f"Periodic snap: {axis} faces have different side topology.",
                "snap-topology",
            )
        move = float(np.linalg.norm(pa - pb[partner], axis=1).max())
        if move > max_move:
            raise MeshQualityError(
                f"Periodic snap: {axis} faces need a move of {move:.3g} > {max_move:.3g}.",
                "snap-move",
            )
        for j, k in enumerate(others):
            out[ib[partner], k] = pa[:, j]
    return out


def _write_coords(fname, coords):
    """Rewrite an exodus mesh with new node coordinates, keeping its blocks.

    Rewrites the whole file with exodusii, like ``normalize_mesh``: reopening
    it with netCDF4 in the same process fails with an HDF error once exodusii
    has read it. Meshes from ``generate_mesh_*`` carry no node or side sets;
    a file that has them is refused rather than silently stripped.
    """
    with exodusii.File(fname, mode="r") as exo:
        if exo.num_node_sets() or exo.num_side_sets():
            raise ValueError(
                f"{fname}: cannot rewrite coordinates of a mesh with node/side sets"
            )
        blocks = []
        for b in exo.get_element_block_ids():
            info = exo.get_element_block(b)
            blocks.append(
                (
                    int(b),
                    str(info.elem_type),
                    str(info.name),
                    np.asarray(exo.get_element_conn(b)),
                )
            )
    with exodusii.File(fname, mode="w") as exo:
        nelem = sum(len(c) for *_, c in blocks)
        exo.put_init("snapped", coords.shape[1], len(coords), nelem, len(blocks), 0, 0)
        exo.put_coord(*(coords[:, i] for i in range(coords.shape[1])))
        for b, etype, name, conn in blocks:
            exo.put_element_block(b, etype, len(conn), conn.shape[1])
            if name:
                exo.put_element_block_name(b, name)
            exo.put_element_conn(b, conn)


def face_mismatch(coords, tol=1e-6):
    """Largest distance between a face node and its periodic partner.

    For each axis with nonzero extent, the nodes on the min and max faces (within
    ``tol`` times the axis span) are compared in the remaining coordinates: the
    result is the largest nearest-neighbor distance, taken both ways. Periodic
    BCs need this to be ~0. Returns ``inf`` if a face is empty while its
    opposite is not.

    Args:
        coords (array): ``(n_nodes, dim)`` node coordinates.
        tol (float): Relative tolerance for a node to lie on a face.
    Returns:
        float: The largest mismatch over all axes (0.0 for matching faces).
    """
    coords = np.asarray(coords, dtype=float)
    lo, hi = coords.min(axis=0), coords.max(axis=0)
    worst = 0.0
    for d in range(coords.shape[1]):
        span = hi[d] - lo[d]
        if span <= 0:
            continue
        a = coords[np.abs(coords[:, d] - lo[d]) <= tol * span]
        b = coords[np.abs(coords[:, d] - hi[d]) <= tol * span]
        a, b = np.delete(a, d, axis=1), np.delete(b, d, axis=1)
        if len(a) == 0 or len(b) == 0:
            if len(a) or len(b):
                return np.inf
            continue
        dab = sp.cKDTree(b).query(a)[0].max()
        dba = sp.cKDTree(a).query(b)[0].max()
        worst = max(worst, dab, dba)
    return float(worst)


def sculpt(mesh, prefix="sculpted_", settings=None, sculpt_input="ice"):
    """Call Sculpt on a mesh, then combine the parallel output with epu.

    Args:
        mesh (str): Input filename. For ``sculpt_input="ice"`` a Cartesian-exodus
            mesh; for ``sculpt_input="ims"`` a microstructure (volume-fraction) file.

    Keyword Args:
        prefix (str): Prefix for the output sculpted mesh filename.
        settings (dict): Global settings dict
        sculpt_input (str): Sculpt input mode, ``"ice"`` (Cartesian exodus) or
            ``"ims"`` (microstructure volume fractions).

    Raises:
        SculptError: if psculpt or epu exits with a non-zero status.
    """
    if settings is None:
        settings = {}

    flag = {"ice": "-ice", "ims": "-ims"}[sculpt_input]
    outfile = os.path.splitext(f"{prefix}{mesh}")[0]
    # Config values win over the shell, e.g. CUBIT's bundled MPI over a conda one.
    env = dict(os.environ) | settings["sculpt"].get("environment", {})
    capture = not settings.get("verbose", False)
    ranks = int(settings["mpi"]["ranks"])

    cmd = (
        [
            settings["sculpt"]["mpi"],
            settings["sculpt"]["rank_command"],
            str(ranks),
        ]
        + [settings["sculpt"]["executable"]]
        + settings["sculpt"]["options"]
        + [flag, mesh, "--exodus_file", outfile]
    )
    epu_cmd = [settings["sculpt"]["epu"], "-auto", outfile + ".e" + f".{ranks}.0"]

    try:
        subprocess.run(cmd, check=True, env=env, capture_output=capture)
        if ranks == 1:
            # epu exits 0 without writing anything for a single part
            # ("no concatenation needed"), so just rename the one part.
            part = outfile + ".e.1.0"
            if os.path.exists(part):
                shutil.move(part, outfile + ".e")
        else:
            subprocess.run(epu_cmd, check=True, env=env, capture_output=capture)
    except subprocess.CalledProcessError as e:
        raise SculptError(f"sculpt ({sculpt_input}) failed: {e}") from e
    if not os.path.exists(outfile + ".e"):
        raise SculptError(
            f"sculpt ({sculpt_input}) produced no {outfile}.e "
            f"(files present: {sorted(os.listdir('.'))})"
        )


def downsample_vfrac(img, factor):
    """Block-mean downsample a binary image to grayscale area/volume fractions.

    Unlike a binary (majority-vote) downsample this keeps the sub-cell fraction,
    which lets Sculpt place a smooth interface inside a coarse cell via ``-ims``.
    Works for 2D and 3D. ``factor <= 1`` returns a float copy.
    """
    arr = np.asarray(img, float)
    if factor <= 1:
        return arr
    crop = tuple(slice(0, (s // factor) * factor) for s in arr.shape)
    arr = arr[crop]
    new_shape = []
    for s in arr.shape:
        new_shape += [s // factor, factor]
    return arr.reshape(new_shape).mean(axis=tuple(range(1, 2 * arr.ndim, 2)))


def overlap_weights(n_out, n_in):
    """Integer 1D overlap matrix between an ``n_out`` and an ``n_in`` grid.

    Both grids split the same interval into equal cells. In units of
    ``1 / lcm(n_out, n_in)`` every cell edge is an integer, so entry ``(i, j)``
    is the exact overlap length of output cell ``i`` and input cell ``j``, and
    every row sums to ``n_in / gcd`` (the output cell size). Divide by that to
    get fractions.

    Returns:
        tuple: ``(W, row_sum)``, ``W`` an ``(n_out, n_in)`` int64 array.
    """
    g = np.gcd(n_out, n_in)
    a, b = n_in // g, n_out // g  # output / input cell size, integer units
    out_edges = np.arange(n_out + 1) * a
    in_edges = np.arange(n_in + 1) * b
    lo = np.maximum(out_edges[:-1, None], in_edges[None, :-1])
    hi = np.minimum(out_edges[1:, None], in_edges[None, 1:])
    return np.clip(hi - lo, 0, None).astype(np.int64), int(a)


def overlap_vfrac(img, n):
    """Resample a square/cubic image to ``n`` cells per side by exact overlap.

    Each output cell gets the overlap-weighted mean of the input cells it
    covers: for a binary image, its exact area/volume fraction of material.
    The 1D overlap matrix ``W`` (``overlap_weights``) is applied along every
    axis, ``W img W^T`` in 2D. Works for any ratio ``img.shape[0] / n``;
    for an integer ratio and a binary image it equals ``downsample_vfrac``
    bit for bit, since the integer weights are summed exactly and divided once.

    Args:
        img (array): 2D or 3D square/cubic image.
        n (int): Output cells per side.

    Returns:
        np.ndarray: Float image of shape ``(n,) * img.ndim``.
    """
    arr = np.asarray(img, float)
    if len(set(arr.shape)) != 1:
        raise ValueError(f"overlap_vfrac needs a square/cubic image, got {arr.shape}")
    W, row_sum = overlap_weights(int(n), arr.shape[0])
    W = W.astype(float)
    for ax in range(arr.ndim):
        arr = np.moveaxis(np.tensordot(W, arr, axes=([1], [ax])), 0, ax)
    return arr / float(row_sum) ** arr.ndim


def _write_micro(phi, fname):
    """Write a 2-material Sculpt microstructure (.tec) for a 2D/3D fraction field.

    ``phi`` is the material-A fraction; ``phi_2 = 1 - phi``. Cells are 1x1x1 with
    ``k=1`` (2D) or ``k=Nz`` (3D); body order is i fastest, then j, then k.
    """
    a = np.clip(np.asarray(phi, float), 0.0, 1.0)
    grids = [g.T.ravel() for g in np.indices(a.shape)]  # i fastest, then j, (then k)
    x = grids[0]
    y = grids[1]
    z = grids[2] if a.ndim == 3 else np.zeros(x.size, dtype=int)
    av = a.T.ravel()
    data = np.column_stack([x, y, z, av, 1.0 - av])
    nz = a.shape[2] if a.ndim == 3 else 1
    with open(fname, "w", encoding="utf-8") as f:
        f.write("TITLE = vfrac\nVARIABLES = x y z phi_1 phi_2\n")
        f.write(f"ZONE i = {a.shape[0]} , j = {a.shape[1]} , k = {nz}\n")
        np.savetxt(f, data, fmt=["%d", "%d", "%d", "%.6f", "%.6f"])


def normalize_mesh(exofile, L, cells=None):
    """Rescale an exodus hex mesh's coords so each axis spans ``[0, L[axis]]``.

    Used on Sculpt's ``-ims`` output, which is on a unit-cell grid with cell
    centers at integer coordinates. With ``cells`` (cells per axis) the known grid
    extent ``[-0.5, cells - 0.5]`` is mapped to ``[0, L]`` and the result clipped
    to the box: Sculpt's smoothing can push a few nodes on box edges slightly
    outside the grid, and mapping the raw ``[min, max]`` instead would pull every
    face inward by that overshoot. Without ``cells``, ``[min, max] -> [0, L]``.
    Either way the z-bottom lands at 0, so the unchanged ``slice_mesh`` works for
    the 2D path. Coords only; blocks unchanged.
    """
    with exodusii.File(exofile, mode="r") as exo:
        coords = np.asarray(exo.get_coords())
        block_ids = [int(b) for b in exo.get_element_block_ids()]
        conns = {b: np.asarray(exo.get_element_conn(b)) for b in block_ids}

    L = np.asarray(L, float)
    if cells is None:
        mn = coords.min(axis=0)
        span = coords.max(axis=0) - mn
        span[span == 0] = 1.0
    else:
        mn = np.full(coords.shape[1], -0.5)
        span = np.asarray(cells, float)
    coords = (coords - mn) / span * L
    if cells is not None:
        coords = np.clip(coords, 0.0, L)

    names = {1: "mat_a", 2: "mat_b"}
    nelem = sum(len(c) for c in conns.values())
    with exodusii.File(exofile, mode="w") as exo:
        exo.put_init("normalized", 3, coords.shape[0], nelem, len(block_ids), 0, 0)
        exo.put_coord(coords[:, 0], coords[:, 1], coords[:, 2])
        for b in block_ids:
            exo.put_element_block(b, "HEX", len(conns[b]), 8)
            exo.put_element_block_name(b, names.get(b, f"mat_{b}"))
            exo.put_element_conn(b, conns[b])


def extrude(mesh, lx=1.0, ly=1.0, prefix="extruded_", lz=0.01, tol=1e-6):
    """Read a 2D mesh and extrude it into 3D.

    Args:
        mesh (str): Input 2D mesh filename.

    Keyword Args:
        prefix (str): Prefix for the output 3D mesh filename.
        lz (float): Length of the extrusion in the z-direction.

    """
    with exodusii.File(mesh, mode="r") as exo:
        coords = exo.get_coords()
        conn_a = exo.get_element_conn(1)
        conn_b = exo.get_element_conn(2)

    nnodes_orig = coords.shape[0]

    coords = np.hstack([coords, np.zeros((nnodes_orig, 1))])
    coords = np.vstack([coords, coords + np.array([0.0, 0.0, lz])])

    def update_conn(conn):
        return list(conn) + [i + nnodes_orig for i in conn]

    conn_a = np.array([update_conn(e) for e in conn_a])
    conn_b = np.array([update_conn(e) for e in conn_b])

    # Identify periodic node_sets
    node_nums = np.arange(1, coords.shape[0] + 1)
    left = coords[:, 0] < tol
    right = coords[:, 0] > lx - tol
    bottom = coords[:, 1] < tol
    top = coords[:, 1] > ly - tol

    with exodusii.File(f"{prefix}{mesh}", mode="w") as exo:
        exo.put_init(
            "3D Extruded Mesh", 3, coords.shape[0], len(conn_a) + len(conn_b), 2, 4, 0
        )
        exo.put_coord(coords[:, 0], coords[:, 1], coords[:, 2])
        exo.put_element_block(1, "HEX", len(conn_a), 8)
        exo.put_element_block_name(1, "mat_a")
        exo.put_element_conn(1, conn_a)
        exo.put_element_block(2, "HEX", len(conn_b), 8)
        exo.put_element_block_name(2, "mat_b")
        exo.put_element_conn(2, conn_b)

        exo.put_node_set_param(1, len(node_nums[left]))
        exo.put_node_set_nodes(1, node_nums[left])
        exo.put_node_set_param(2, len(node_nums[right]))
        exo.put_node_set_nodes(2, node_nums[right])
        exo.put_node_set_param(3, len(node_nums[bottom]))
        exo.put_node_set_nodes(3, node_nums[bottom])
        exo.put_node_set_param(4, len(node_nums[top]))
        exo.put_node_set_nodes(4, node_nums[top])


def slice_mesh(mesh, prefix="sliced_", eps=1e-4):
    """Take a 2D slice of a 3D hex mesh.

    This function assumes that the input mesh is a single element thick in the z-direction.

    Args:
        mesh (str): Input 3D mesh filename.

    Keyword Args:
        prefix (str): Prefix for the output 2D mesh filename.
    """
    with exodusii.File(mesh, mode="r") as exo:
        coords = exo.get_coords()
        conn_a = exo.get_element_conn(1)
        conn_b = exo.get_element_conn(2)

    node_nums = range(1, coords.shape[0] + 1)
    keep_nodes = np.abs(coords[:, 2]) < eps

    node_map = {}
    kk = 1
    for ii, keep in zip(node_nums, keep_nodes):
        if keep:
            node_map[ii] = kk
            kk += 1

    coords = coords[keep_nodes, :2]

    def update_conn(conn):
        new_conn = [node_map[c] for c in conn if c in node_map]
        points = coords[np.array(new_conn, dtype=int) - 1]
        # Really, I have to orient the points correctly to make a quad?
        center = np.mean(points, axis=0)
        angles = np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0])
        sorted_indices = np.argsort(angles)
        new_conn = [new_conn[i] for i in sorted_indices]

        if len(new_conn) != 4:
            raise ValueError("Element does not have 4 nodes after slicing.")

        return new_conn

    new_conn_a = np.array([update_conn(e) for e in conn_a])
    new_conn_b = np.array([update_conn(e) for e in conn_b])

    with exodusii.File(f"{prefix}{mesh}", mode="w") as exo:
        exo.put_init(
            "2D Sliced Mesh",
            2,
            coords.shape[0],
            len(new_conn_a) + len(new_conn_b),
            2,
            0,
            0,
        )
        exo.put_coord(coords[:, 0], coords[:, 1])
        exo.put_element_block(1, "QUAD", len(new_conn_a), 4)
        exo.put_element_block_name(1, "mat_a")
        exo.put_element_conn(1, new_conn_a)
        exo.put_element_block(2, "QUAD", len(new_conn_b), 4)
        exo.put_element_block_name(2, "mat_b")
        exo.put_element_conn(2, new_conn_b)


def write_mesh_2d(img, fname, lx=1.0, ly=1.0):
    """Write a 2D mesh file from a binary image.

    Args:
        img (2D array): Binary image where 1 indicates material A
        fname (str): Output filename for the mesh.

    Keyword Args:
        lx (float): Length of the domain in x-direction.
        ly (float): Length of the domain in y-direction.
    """
    nx, ny = img.shape

    x_vals = np.linspace(0, lx, nx + 1)
    y_vals = np.linspace(0, ly, ny + 1)

    X, Y = np.meshgrid(x_vals, y_vals, indexing="ij")
    points = np.vstack([X.flatten(), Y.flatten()]).T

    mat_a = []
    mat_b = []
    for je in range(ny):
        for ie in range(nx):
            # Counter-clockwise (positive Jacobian): (i, j), (i+1, j), (i+1, j+1), (i, j+1).
            # Clockwise quads are inverted elements; host libMesh tolerates them, but Kokkos
            # side integrals (e.g. Neumann BCs) then come out with the wrong sign.
            cell = [
                ie * (ny + 1) + je + 1,
                (ie + 1) * (ny + 1) + je + 1,
                (ie + 1) * (ny + 1) + je + 1 + 1,
                ie * (ny + 1) + je + 1 + 1,
            ]
            if img[ie, je]:
                mat_a.append(cell)
            else:
                mat_b.append(cell)

    with exodusii.File(fname, mode="w") as exo:
        exo.put_init("2D Mesh", 2, len(points), len(mat_a) + len(mat_b), 2, 0, 0)
        exo.put_coord(points[:, 0], points[:, 1])
        exo.put_element_block(1, "QUAD", len(mat_a), 4)
        exo.put_element_block_name(1, "mat_a")
        exo.put_element_conn(1, np.array(mat_a))
        exo.put_element_block(2, "QUAD", len(mat_b), 4)
        exo.put_element_block_name(2, "mat_b")
        exo.put_element_conn(2, np.array(mat_b))


def write_mesh_3d(img, fname, lx=1.0, ly=1.0, lz=1.0):
    """Write a 3D mesh file from a binary image.

    Args:
        img (3D array): Binary image where 1 indicates material A
        fname (str): Output filename for the mesh.

    Keyword Args:
        lx (float): Length of the domain in x-direction.
        ly (float): Length of the domain in y-direction.
        lz (float): Length of the domain in z-direction.
    """
    nx, ny, nz = img.shape

    x_vals = np.linspace(0, lx, nx + 1)
    y_vals = np.linspace(0, ly, ny + 1)
    z_vals = np.linspace(0, lz, nz + 1)

    X, Y, Z = np.meshgrid(x_vals, y_vals, z_vals, indexing="ij")
    points = np.vstack([X.flatten(), Y.flatten(), Z.flatten()]).T

    def node(i, j, k):
        """1-based id of grid point (i, j, k), matching the ordering of points."""
        return (i * (ny + 1) + j) * (nz + 1) + k + 1

    mat_a = []
    mat_b = []
    for ke in range(nz):
        for je in range(ny):
            for ie in range(nx):
                cell = [
                    node(ie, je, ke),
                    node(ie + 1, je, ke),
                    node(ie + 1, je + 1, ke),
                    node(ie, je + 1, ke),
                    node(ie, je, ke + 1),
                    node(ie + 1, je, ke + 1),
                    node(ie + 1, je + 1, ke + 1),
                    node(ie, je + 1, ke + 1),
                ]
                if img[ie, je, ke]:
                    mat_a.append(cell)
                else:
                    mat_b.append(cell)

    with exodusii.File(fname, mode="w") as exo:
        exo.put_init("3D Mesh", 3, len(points), len(mat_a) + len(mat_b), 2, 0, 0)
        exo.put_coord(points[:, 0], points[:, 1], points[:, 2])
        exo.put_element_block(1, "HEX", len(mat_a), 8)
        exo.put_element_block_name(1, "mat_a")
        exo.put_element_conn(1, np.array(mat_a))
        exo.put_element_block(2, "HEX", len(mat_b), 8)
        exo.put_element_block_name(2, "mat_b")
        exo.put_element_conn(2, np.array(mat_b))


def project_element_field_to_grid(mesh_coords, mesh_conn, element_field, L, N):
    """Project an element field from an unstructured mesh onto a structured grid.

    This uses closest element centroid projection.

    Args:
        mesh_coords (array): ``(n_nodes, dim)`` coordinates of the mesh nodes.
        mesh_conn (array): Connectivity of the mesh elements, assumed to be quads.
        element_field (type, shape, data): Element field values to project.
        L (float): Side length of the square/cubic domain.
        N (int): Grid cells per side.
    """
    tensor_type = element_field["type"]
    shape = element_field["shape"]
    data = element_field["data"]
    dim = mesh_coords.shape[1]

    # Grid centroids, in C order of the (N,) * dim grid
    centers = (np.indices((N,) * dim).reshape(dim, -1).T + 0.5) * (L / N)

    # Cell centroids
    elem_centroids = np.zeros((mesh_conn.shape[0], dim))
    for iel, conn in enumerate(mesh_conn):
        points = mesh_coords[conn]
        elem_centroids[iel, :] = np.mean(points, axis=0)

    tree = sp.cKDTree(elem_centroids)
    # Find the closest element for each grid point
    _, closest_elems = tree.query(centers, k=1)

    return {
        "type": tensor_type,
        "shape": shape,
        "data": data[:, closest_elems].reshape((-1,) + (N,) * dim + shape),
    }


def extract_grid_from_mesh(mesh_data, img, L, N=None, length_names=None):
    """Extract grid information from mesh data.

    Args:
        mesh_data (dict): Mesh data containing unstructured grid output
        img (array): Generated binary image (1 = material A), as meshed, at
            the generator resolution. Resampled to the output grid with
            ``overlap_vfrac`` and thresholded at 0.5, it is kept as
            ``material_generated`` for comparison; the exported ``material``
            is projected from the mesh, like the stimuli and responses.
        L (float): Side length of the square/cubic domain.

    Keyword Args:
        N (int or None): Output grid cells per side, ``N_out``
            (``output.grid_extractor.params.N``). None means ``img.shape[0]``.
        length_names (list): Names for the length entries in the output grid.

    Returns:
        dict: Extracted grid information.
    """
    if length_names is None:
        length_names = ["lx", "ly", "lz"]
    dim = mesh_data["coords"].shape[1]
    n_out = img.shape[0] if N is None else int(N)

    def project(field):
        return project_element_field_to_grid(
            mesh_data["coords"], mesh_data["connectivity"], field, L, n_out
        )

    grid = {
        "cell_fields": {
            "material": {
                "type": "scalar",
                "shape": tuple(),
                # Material of the mesh actually solved, on the same grid and
                # with the same projection as the stimuli/responses below.
                "data": project(mesh_data["element_fields"]["material"])["data"][0],
            },
            # The generated image on the output grid, to check the mesh
            # against what was meshed.
            "material_generated": {
                "type": "scalar",
                "shape": tuple(),
                "data": overlap_vfrac(img, n_out) > 0.5,
            },
            "stimuli": {},
            "responses": {},
        }
        | {name: L for name in length_names[:dim]},
    }

    for name, val in mesh_data["element_fields"]["stimuli"].items():
        grid["cell_fields"]["stimuli"][name] = project(val)

    for name, val in mesh_data["element_fields"]["responses"].items():
        grid["cell_fields"]["responses"][name] = project(val)

    return grid
