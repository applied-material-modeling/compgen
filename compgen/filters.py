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

"""Image filtering utilities for preprocessing generated microstructures."""

import itertools

import numpy as np
import skimage
from scipy import ndimage
from compgen import utils


class FilterInputError(ValueError):
    """A filter rejected its input for a reason that recurs on every draw.

    The image shape and the filter params are fixed by the config, so redrawing a
    structure cannot help: ``runner.run_single`` aborts the run instead of
    reporting a retryable failure. Third-party filters can raise this to opt into
    the same treatment.
    """


class NonBinaryImageError(FilterInputError):
    """A filter was given a non-binary image."""


def _as_binary(img, name):
    """Return `img` as a bool array, rejecting anything that is not 0/1.

    Filters take and return bool, matching the generators. Non-binary input is
    rejected rather than coerced, since the filters would each reduce it
    differently (truncating cast, nonzero test, quantile threshold).

    Args:
        img (np.ndarray): Candidate image.
        name (str): Filter name, used in the error message.

    Returns:
        np.ndarray: Boolean view or copy of `img`.

    Raises:
        NonBinaryImageError: If `img` holds values other than 0 and 1.
    """
    arr = np.asarray(img)
    if arr.dtype == bool:
        return arr
    if not ((arr == 0) | (arr == 1)).all():
        raise NonBinaryImageError(
            f"{name} requires a binary image (bool, or numeric holding only 0/1); "
            f"got dtype {arr.dtype} with values outside {{0, 1}}. Binarize first, "
            f"e.g. with compgen.utils.standardize_image(img, dtype=bool)."
        )
    return arr.astype(bool)


def _ceil(x):
    """Round up, ignoring float noise (``7 / 25 * 25`` gives 7, not 8)."""
    return int(np.ceil(np.round(x, 9)))


def _fft_footprint_sum(x, footprint):
    """Circular convolution of `x` with a centered `footprint`, via FFT.

    Footprint offsets are wrapped modulo ``x.shape``, so a footprint larger
    than the array is handled like wrap padding would.
    """
    center = np.array(footprint.shape) // 2
    offsets = (np.argwhere(footprint) - center) % np.array(x.shape)
    kernel = np.zeros(x.shape)
    np.add.at(kernel, tuple(offsets.T), 1.0)
    axes = tuple(range(x.ndim))
    out = np.fft.irfftn(
        np.fft.rfftn(x, axes=axes) * np.fft.rfftn(kernel, axes=axes),
        s=x.shape,
        axes=axes,
    )
    return np.rint(out)  # counts are integers; drop FFT round-off


def mean_filter(img, radius=0.0234, periodic=True, method="rank"):
    """Apply a mean filter to an image.

    Args:
        img (np.ndarray): 2D or 3D image.
        radius (float): Radius of disk/ball footprint, as a fraction of the
            shortest side ``min(img.shape)``, rounded up to whole pixels.
            ``0`` is a no-op.
        periodic (bool): If True, use periodic wrapping at the boundaries.
        method (str): ``"rank"`` uses ``skimage.filters.rank.mean`` (uint8
            averages, slow for large radii). ``"fft"`` convolves with the
            footprint via FFT: exact averages and much faster, with cost
            independent of `radius`. Results can differ slightly at large
            radii, where the uint8 rounding of ``"rank"`` creates ties.

    Returns:
        np.ndarray: Smoothed binary image (bool).
    """
    if method not in ("rank", "fft"):
        raise FilterInputError(
            f"mean_filter method must be 'rank' or 'fft', got {method!r}"
        )
    img = _as_binary(img, "mean_filter")
    ndim = img.ndim
    radius = _ceil(radius * min(img.shape))
    if radius == 0 and ndim in (2, 3):
        return img

    if ndim == 3:
        footprint = skimage.morphology.ball(radius)
    elif ndim == 2:
        footprint = skimage.morphology.disk(radius)
    else:
        raise FilterInputError("mean_filter only supports 2D and 3D images")

    def smooth_fft(i):
        if periodic:
            return _fft_footprint_sum(i.astype(float), footprint)
        # Zero-pad so nothing wraps, and divide by the number of in-image
        # neighbors, matching rank.mean at the edges.
        pad = [(radius, radius)] * ndim
        inner = tuple(slice(radius, -radius) for _ in range(ndim))
        total = _fft_footprint_sum(np.pad(i.astype(float), pad), footprint)
        count = _fft_footprint_sum(np.pad(np.ones(i.shape), pad), footprint)
        return total[inner] / count[inner]

    if method == "fft":
        return utils.binary_smoother(img, smooth_fft)

    def smooth(i):
        i_u8 = skimage.util.img_as_ubyte(i.astype(float))

        if periodic:
            pad_width = [(radius, radius)] * ndim
            i_u8 = np.pad(i_u8, pad_width=pad_width, mode="wrap")

        out = skimage.filters.rank.mean(i_u8, footprint=footprint)
        out = skimage.util.img_as_float(out)

        if periodic:
            slices = tuple(slice(radius, -radius) for _ in range(ndim))
            out = out[slices]

        return out

    return utils.binary_smoother(img, smooth)


def make_orthogonal(img):
    """Mirror and tile the input array to give it orthogonal periodicity.

    This works for arrays of arbitrary dimensionality by concatenating the
    array with its flipped version along each axis (processing axes from
    last to first). Takes and returns a bool array.
    """
    arr = _as_binary(img, "make_orthogonal")
    for axis in reversed(range(arr.ndim)):
        arr = np.concatenate([arr, np.flip(arr, axis=axis)], axis=axis)
    return arr


def make_periodic(
    img: np.ndarray, margin_cells: int = 2, shift: bool = False, center: bool = False
) -> np.ndarray:
    """
    Make periodic for Sculpt/MOOSE workflow.

    `margin_cells` is a whole number of pixel layers of the input image (the
    generator grid); below, `margin` is that number.

    Overwrite the first and last `margin` layers of each axis with the layer at
    index `margin`, for 2D or 3D arrays.
    If shift is True, first circular-shift each axis to minimize the overwrite
    cost. This is opt-in: the default (False) keeps main's behavior, so existing
    configs produce the same structures.

    If center is True, copy the face layer (index 0) instead, into layers
    1..margin and the last `margin` layers. The block of 2 * margin + 1
    identical layers around each face is the same, but the mismatch with the
    interior is split between both ends of the block (margin + 1 and margin
    layers) instead of falling at one end (2 * margin + 1 layers), which gives
    smaller interface jumps. Opt-in; best combined with shift=True.

    For periodic face snapping (``mesh.generate_mesh(max_snap_move=...)``) the
    block must cover at least 2 mesh cells: with ``refinement`` r, use
    ``margin_cells >= 2 * 2**r``.

    Takes and returns a bool array.
    """
    arr = _as_binary(img, "make_periodic").copy()

    if arr.ndim not in (2, 3):
        raise FilterInputError(f"Expected 2D or 3D array, got {arr.ndim}D")
    if (
        isinstance(margin_cells, bool)
        or not isinstance(margin_cells, (int, float))
        or margin_cells != int(margin_cells)
        or margin_cells < 1
    ):
        raise FilterInputError(
            f"margin_cells must be a positive whole number of pixels, got {margin_cells}"
        )
    margin = int(margin_cells)
    if any(2 * margin >= s for s in arr.shape):
        raise FilterInputError(f"margin of {margin} layers is too large for shape {arr.shape}")

    def slices(ax):
        master = [slice(None)] * arr.ndim
        lo = [slice(None)] * arr.ndim
        hi = [slice(None)] * arr.ndim
        if center:
            master[ax] = slice(0, 1)
            lo[ax] = slice(1, margin + 1)
        else:
            master[ax] = slice(margin, margin + 1)
            lo[ax] = slice(0, margin)
        hi[ax] = slice(-margin, None)
        return tuple(master), tuple(lo), tuple(hi)

    def best_shift(a, ax):
        """Circular shift along `ax` with the fewest overwritten cells that change.

        After rolling by `i`, the master layer is the original layer
        `c = (m - i) % n`, with `m = 0` if center else `margin`, and the
        overwritten layers are `c - 1`, ..., `c - 2 * margin` (or `c - margin`,
        ..., `c + margin` without `c` if center). So the cost of every shift
        follows from 2 * margin comparisons of the array with itself rolled by
        those offsets, instead of rolling and comparing once per shift.
        """
        n = a.shape[ax]
        others = tuple(d for d in range(a.ndim) if d != ax)
        if center:
            offsets = [*range(-margin, 0), *range(1, margin + 1)]
        else:
            offsets = range(1, 2 * margin + 1)
        cost_by_master = np.zeros(n, dtype=np.int64)
        for d in offsets:
            cost_by_master += (a != np.roll(a, d, axis=ax)).sum(axis=others)
        m = 0 if center else margin
        cost_by_shift = cost_by_master[(m - np.arange(n)) % n]
        return int(np.argmin(cost_by_shift))  # smallest shift among ties

    def apply(a, ax):
        master, lo, hi = slices(ax)
        a[lo] = a[master]
        a[hi] = a[master]
        return a

    for ax in range(arr.ndim):
        if shift:
            arr = np.roll(arr, shift=best_shift(arr, ax), axis=ax)
        arr = apply(arr, ax)

    return arr


def _label_periodic(mask, structure, connectivity):
    """Connected-component labels on a periodic (toroidal) domain.

    Labels normally, then unions component labels that touch across each periodic
    seam (with the transverse offsets the connectivity allows), so an island that
    wraps around an edge is counted as a single component.
    """
    lbl, n = ndimage.label(mask, structure=structure)
    if n <= 1:
        return lbl
    parent = list(range(n + 1))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    ndim = mask.ndim
    # A seam join already costs one orthogonal step (the wrap along `ax`), so a
    # transverse offset is allowed only if 1 + (#nonzero offset axes) <= connectivity.
    # For connectivity=1 this leaves just the aligned offset (same transverse index).
    offs = [
        o
        for o in itertools.product((-1, 0, 1), repeat=ndim - 1)
        if sum(1 for v in o if v) <= connectivity - 1
    ]
    for ax in range(ndim):
        a = np.take(lbl, 0, axis=ax)
        ma = np.take(mask, 0, axis=ax)
        b0 = np.take(lbl, -1, axis=ax)
        mb0 = np.take(mask, -1, axis=ax)
        for off in offs:
            b, mb = b0, mb0
            for d, sv in enumerate(off):
                if sv:
                    b = np.roll(b, sv, axis=d)
                    mb = np.roll(mb, sv, axis=d)
            both = ma & mb
            for x, y in zip(a[both].ravel(), b[both].ravel()):
                union(int(x), int(y))
    roots = np.array([find(i) for i in range(n + 1)])
    return roots[lbl]


def defeature(img, min_size, connectivity=1, periodic=True):
    """Remove connected islands smaller than a disk/ball of radius ``min_size``.

    Each island below the threshold is reassigned to its surrounding phase. This
    cleans up speckle in a generated microstructure before meshing (use it in a
    config ``filtering`` list, before ``make_periodic``). Works for 2D and 3D.

    Args:
        img (np.ndarray): 2D or 3D binary image.
        min_size (float): Radius of the threshold disk/ball, as a fraction of
            the shortest side ``min(img.shape)``. Islands with fewer than
            ``ceil(pi R**2)`` (2D) or ``ceil(4/3 pi R**3)`` (3D) cells are
            removed, with ``R = min_size * min(img.shape)``. ``0`` is a no-op.

    Keyword Args:
        connectivity (int): Neighbour connectivity for labelling (1 = faces).
        periodic (bool): If True, islands that wrap across the domain edges are
            measured as one component (the labelling is roll-invariant).

    Returns:
        np.ndarray: Boolean image with small islands removed.
    """
    arr = _as_binary(img, "defeature")
    if not min_size:
        return arr
    r = min_size * min(arr.shape)
    min_cells = _ceil(np.pi * r**2 if arr.ndim == 2 else 4 / 3 * np.pi * r**3)
    out = arr.copy()
    st = ndimage.generate_binary_structure(arr.ndim, connectivity)
    for phase in (True, False):
        mask = out == phase
        if not mask.any():
            continue
        if periodic:
            lbl = _label_periodic(mask, st, connectivity)
        else:
            lbl, _ = ndimage.label(mask, structure=st)
        sizes = np.bincount(lbl.ravel())
        small = np.flatnonzero(sizes < min_cells)
        small = small[small != 0]
        out[np.isin(lbl, small) & mask] = not phase
    return out
