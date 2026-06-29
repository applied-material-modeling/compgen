"""Image filtering utilities for preprocessing generated microstructures."""

import itertools

import numpy as np
import skimage
from scipy import ndimage
from compgen import utils


def mean_filter(img, radius=3, periodic=True):
    """Apply a mean filter to an image.

    Args:
        img (np.ndarray): 2D or 3D image.
        radius (int): Radius of disk/ball footprint.
        periodic (bool): If True, use periodic wrapping at the boundaries.

    Returns:
        np.ndarray: Smoothed binary image.
    """
    ndim = img.ndim

    if ndim == 3:
        footprint = skimage.morphology.ball(radius)
    elif ndim == 2:
        footprint = skimage.morphology.disk(radius)
    else:
        raise ValueError("mean_filter only supports 2D and 3D images")

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
    last to first).
    """
    arr = np.asarray(img)
    for axis in reversed(range(arr.ndim)):
        arr = np.concatenate([arr, np.flip(arr, axis=axis)], axis=axis)
    return arr


def make_periodic(img: np.ndarray, margin: int = 2, shift: bool = True) -> np.ndarray:
    """
    Make periodic for Sculpt/MOOSE workflow.

    Overwrite the first and last `margin` layers of each axis with the layer at
    index `margin`, for 2D or 3D arrays.
    If shift is True, check the circular shift that minimizes the overwrite cost.

    A value `margin = 2` seems to work consistently with Sculpt/MOOSE.
    """
    arr = np.array(img, copy=True, dtype=int)

    if arr.ndim not in (2, 3):
        raise RuntimeError(f"Expected 2D or 3D array, got {arr.ndim}D")
    if not isinstance(margin, int) or margin < 1:
        raise ValueError(f"margin must be a positive integer, got {margin}")
    if any(2 * margin >= s for s in arr.shape):
        raise ValueError(f"margin={margin} is too large for shape {arr.shape}")

    def slices(ax):
        master = [slice(None)] * arr.ndim
        lo = [slice(None)] * arr.ndim
        hi = [slice(None)] * arr.ndim
        master[ax] = slice(margin, margin + 1)
        lo[ax] = slice(0, margin)
        hi[ax] = slice(-margin, None)
        return tuple(master), tuple(lo), tuple(hi)

    def cost(a, ax):
        master, lo, hi = slices(ax)
        return np.sum(np.abs(a[hi] - a[master]) + np.abs(a[lo] - a[master]))

    def apply(a, ax):
        master, lo, hi = slices(ax)
        a[lo] = a[master]
        a[hi] = a[master]
        return a

    for ax in range(arr.ndim):
        if shift:
            best_shift = 0
            best_cost = cost(arr, ax)
            for i in range(1, arr.shape[ax]):
                c = cost(np.roll(arr, shift=i, axis=ax), ax)
                if c < best_cost:
                    best_shift = i
                    best_cost = c
            arr = np.roll(arr, shift=best_shift, axis=ax)
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
    """Remove connected islands smaller than ``min_size`` cells (both phases).

    Each island below the threshold is reassigned to its surrounding phase. This
    cleans up speckle in a generated microstructure before meshing (use it in a
    config ``filtering`` list, before ``make_periodic``). Works for 2D and 3D.

    Args:
        img (np.ndarray): 2D or 3D binary image.
        min_size (int): Islands with fewer than this many cells are removed.
            ``0`` is a no-op.

    Keyword Args:
        connectivity (int): Neighbour connectivity for labelling (1 = faces).
        periodic (bool): If True, islands that wrap across the domain edges are
            measured as one component (the labelling is roll-invariant).

    Returns:
        np.ndarray: Boolean image with small islands removed.
    """
    arr = np.asarray(img).astype(bool)
    if not min_size:
        return arr
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
        small = np.flatnonzero(sizes < min_size)
        small = small[small != 0]
        out[np.isin(lbl, small) & mask] = not phase
    return out
